"""Each source is isolated, each notice commits its jobs and evidence atomically."""

import json
import os
import re
from datetime import timedelta
from urllib.parse import urlsplit

from sqlalchemy import select

from .db import Evidence, Job, Log, Notice, Sessions, Source
from .extract import (
    IGNORE,
    JOB_NOTICE,
    attachment_rows,
    body_info,
    candidates,
    compact,
    directory_page,
    digest,
    document,
    links,
    notice_dates,
    prose_rows,
    table_rows,
)
from .net import FetchError
from .settings import now, stamp


PARSER_VERSION = 3


def validators(headers):
    return {k: headers[k] for k in ("etag", "last-modified") if k in headers}


def conditional(saved):
    return {
        k: saved[v]
        for k, v in (("If-None-Match", "etag"), ("If-Modified-Since", "last-modified"))
        if saved.get(v)
    }


def parse_page(url, raw, fallback):
    dom = document(raw)
    metadata = compact(
        " ".join(
            dom.xpath(
                '//meta[@name="ArticlePublishTime" or @property="article:published_time"]/@content'
            )
        )
    )
    heading = compact(dom.text_content())[:30000]
    title, body, text, atts = body_info(dom, url, fallback)
    if (
        len(text) < 60
        or not JOB_NOTICE.search(title + text[:1600])
        or re.search(r"访问验证|验证码验证|滑动滑块|请完成安全验证", text[:800])
    ):
        raise FetchError("正文不完整或需要访问验证")
    if IGNORE.search(title):
        raise FetchError("后续结果或非教学公告，待核实")
    common = notice_dates(
        text, (("发布时间：" + metadata + " ") if metadata else "") + heading
    )
    if not common.get("published"):
        m = re.search(r"(?<!\d)(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\s*$", fallback)
        if m:
            common.update(notice_dates("", "日期：" + m[1]))
    apply = next(
        (
            url
            for url, label in links(body, url)
            if re.search("点击报名|报名入口|立即报名|网上报名系统|招聘报名网站", label)
        ),
        None,
    )
    if not apply:
        m = re.search(
            r"(?:报名网站|报名网址|报名入口|招聘报名网站)[^。；\n]{0,48}\s*(https?://[a-zA-Z0-9.:/_?%=&-]+)",
            text,
        )
        if m:
            apply = m[1].rstrip(".,")
    if apply:
        common["apply_url"] = apply
    employment = re.search(
        r"事业单位报备员额内用人|非事业编制|编制外聘用|事业编制|劳务派遣|合同制教师|临聘教师|代课教师",
        text,
    )
    if employment:
        common["employment"] = employment[0]
    general = [
        p
        for p in text.splitlines()
        if len(p) < 600
        and re.search(
            r"中华人民共和国国籍|非应届.*在读|在读.*非应届|应届毕业生.{0,60}(取得|获得).{0,8}(证书|学位)",
            p,
        )
    ]
    if general:
        common["general"] = "；".join(dict.fromkeys(general))[:720]
    rows = []
    for i, t in enumerate(body.xpath(".//table[not(.//table)]"), 1):
        cells = (
            [c.text_content() for c in tr.xpath("./td|./th")] for tr in t.xpath(".//tr")
        )
        rows += table_rows(cells, f"正文表 {i}")[0]
    if not rows:
        rows = prose_rows(title, text)
    return {
        "title": title,
        "common": common,
        "rows": rows,
        "attachments": atts,
        "body_excerpt": next(
            (
                compact(p)[:330]
                for p in text.splitlines()
                if "招聘" in p and len(p) > 30
            ),
            title,
        ),
    }


def collect_notice(web, src, url, label, hosts, old):
    cached = old.data or {} if old else {}
    if cached.get("parser_version") != PARSER_VERSION:
        cached = {}
    real, headers, raw = web.get(
        url,
        hosts,
        conditional(cached.get("validators", {})) if cached.get("page") else {},
    )
    if not raw:
        page = cached["page"]
    elif src.meta.get("adapter") == "faculty_directory":
        page = directory_page(document(raw), real)
    else:
        page = parse_page(real, raw, label)
    notice_validators = validators(headers) if raw else cached.get("validators", {})
    attach, rows, errors = [], list(page["rows"]), []
    previous = {a["url"]: a for a in cached.get("attachments", [])}
    for index, at in enumerate(page["attachments"]):
        record = dict(at)
        last = previous.get(at["url"], {})
        try:
            if index >= 10:
                raise FetchError("单公告附件超过 10 项")
            if at["type"] not in ("xlsx", "xls", "docx", "pdf"):
                raise FetchError("该格式尚需人工读取")
            _, ah, binary = web.get(
                at["url"],
                hosts,
                conditional(last.get("validators", {})) if last.get("hash") else {},
            )
            if binary and binary[:300].lstrip().lower().startswith(
                (b"<!doctype html", b"<html")
            ):
                raise FetchError("链接返回网页，未取得附件文件")
            h = digest(binary) if binary else last.get("hash")
            found = (
                last.get("rows", [])
                if h and h == last.get("hash")
                else attachment_rows(at["type"], binary)
            )
            record.update(
                hash=h,
                rows=found,
                validators=validators(ah) if binary else last.get("validators", {}),
            )
            for row in found:
                rows.append({**row, "file": at["url"], "file_name": at["name"]})
        except Exception as exc:
            record["error"] = str(exc)[:180] or type(exc).__name__
            errors.append(at["name"][:55] + "：" + record["error"])
        attach.append(record)
    info = {
        "parser_version": PARSER_VERSION,
        "page": page,
        "attachments": attach,
        "validators": notice_validators,
    }
    signature = digest(
        json.dumps(
            [page, [(a["url"], a.get("hash"), a.get("error")) for a in attach]],
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    )
    return page, rows, info, signature, errors


def employer(src, notice_title, row):
    school = row.get("school_field") or src.name
    matches = re.findall(
        r"[\u3400-\u9fff]{2,28}?(?:学院|大学)附属(?:中等音乐学校|中等艺术学校|小学|中学|音乐学校)",
        notice_title + " " + row["title"],
    )
    if matches:
        school = matches[0]
    elif src.meta.get("school_type") == "政府公开招聘" and not row.get("school_field"):
        # The government's notice title may identify the hiring school; avoid
        # assigning the government agency as the school itself.
        match = re.search(
            r"(?:20\d{2}年)?(?:春季|秋季|冬季|上半年|下半年)?"
            r"([\u3400-\u9fff]{2,35}?(?:高级中学|初级中学|中学|第一中学|第二中学|实验学校))",
            notice_title,
        )
        school = match.group(1) if match else "招聘学校待核实"
    return school


def identity(school, row, title, url, published):
    year = re.search(r"20\d{2}", title)
    cycle = year[0] if year else (published or "")[:4]
    batch = re.findall(
        r"第[一二三四五六七八九十\d]+批|[上下]半年|春季|秋季|冬季", title
    )
    # Only merge across websites when the hiring cycle and an official position code agree.
    key = (
        [school, cycle, "/".join(batch), row["code"]]
        if row.get("code") and cycle
        else [
            school,
            url,
            row.get("code")
            or (
                row["title"]
                + "|"
                + row.get("department", "")
                + "|"
                + row.get("major", "")
            ),
        ]
    )
    return digest(json.dumps(key, ensure_ascii=False).encode())


def repost(db, notice, school, row, published):
    """A dated, verbatim repost with the same employer, position and department/discipline."""
    if (
        row.get("code")
        or not published
        or not (row.get("major") or row.get("department"))
    ):
        return None

    def headline(text):
        return re.sub(r"^(?:【转载】|转载[:：]|转发[:：])", "", compact(text))

    candidates = db.execute(
        select(Job, Notice.title)
        .join(Evidence, Evidence.job_id == Job.id)
        .join(Notice, Notice.id == Evidence.notice_id)
        .where(
            Job.school == school,
            Job.title == row["title"],
            Evidence.current.is_(True),
            Notice.id != notice.id,
        )
    )
    matches = {
        j.id: j
        for j, t in candidates
        if headline(t) == headline(notice.title)
        and j.data.get("published") == published
        and not j.data.get("code")
        and all(j.data.get(k) == row.get(k) for k in ("major", "department"))
    }
    return next(iter(matches.values())) if len(matches) == 1 else None


def apply_rows(db, src, notice, page, rows, errors):
    seen = set()
    created = 0
    for row in rows:
        school = employer(src, page["title"], row)
        fields = {
            k: v
            for k, v in row.items()
            if k not in ("file", "file_name", "location", "excerpt", "school_field")
        }
        data = {
            **{
                k: src.meta.get(k) for k in ("stage", "city", "province", "school_type")
            },
            **page["common"],
            **fields,
        }
        windows = data.pop("windows", [])
        possible = [
            w
            for w in windows
            if any(deg in (data.get("degree") or "") for deg in w["for"])
        ]
        if len(possible) == 1:
            data.update({k: v for k, v in possible[0].items() if k != "for"})
        if "附属中等" in school:
            data.update(stage="中职", school_type="附属中等艺术学校")
        elif "小学" in school:
            data["stage"] = "小学"
        elif "附属中学" in school:
            data["stage"] = "中学"
        if not data.get("employment"):
            for word in ("合同制", "临聘", "兼职", "代课", "人才引进", "专任教师"):
                if word in row["title"] + page["title"]:
                    data["employment"] = word
                    break
        if not data.get("workload"):
            data["workload"] = next(
                (v for v in ("兼职", "全职", "非全日制") if v in row["title"]), None
            )
        data["issue"] = "部分附件待人工核实" if errors else row.get("issue")
        key = identity(school, row, page["title"], notice.url, data.get("published"))
        if key in seen:
            continue
        seen.add(key)
        job = db.scalar(select(Job).where(Job.identity == key))
        if job is None:
            job = repost(db, notice, school, row, data.get("published"))
        if not job:
            job = Job(
                identity=key,
                school=school,
                title=row["title"],
                data=data,
                checked=notice.checked,
            )
            db.add(job)
            db.flush()
            created += 1
        else:
            seen.add(job.identity)
            job.withdrawn = False
            # Official records take precedence over user-defined secondary sources.
            if src.meta.get("kind") in ("学校官网", "政府官网") or not job.data.get(
                "official"
            ):
                job.data = data
                job.title = row["title"]
            job.checked = notice.checked
        if src.meta.get("kind") in ("学校官网", "政府官网"):
            job.data = {**job.data, "official": True}
        trace = db.get(Evidence, (job.id, notice.id))
        proof = {
            k: row[k]
            for k in ("file", "file_name", "location", "excerpt", "detail_url")
            if row.get(k)
        }
        if trace:
            trace.data, trace.current = proof, True
        else:
            db.add(Evidence(job_id=job.id, notice_id=notice.id, data=proof))
    for trace in db.scalars(select(Evidence).where(Evidence.notice_id == notice.id)):
        job = db.get(Job, trace.job_id)
        if job.identity not in seen:
            trace.current = False
            other = db.scalar(
                select(Evidence).where(
                    Evidence.job_id == job.id,
                    Evidence.notice_id != notice.id,
                    Evidence.current.is_(True),
                )
            )
            job.withdrawn = not bool(other)
    return created


def crawl_source(source_id, run_id, web, *, force=False, limit=None):
    stats = dict(candidates=0, read=0, skipped=0, new=0, errors=0)
    with Sessions() as db:
        src = db.get(Source, source_id)
        src.attempted = stamp()
        db.commit()
        hosts = {urlsplit(src.url).hostname, *src.meta.get("hosts", [])}
        issues = []
        try:
            real, _, listing = web.get(src.url, hosts)
            tree = document(listing)
            if (
                src.meta.get("mode") == "article"
                or src.meta.get("adapter") == "faculty_directory"
            ):
                found = [
                    (
                        src.url,
                        src.meta.get("article_title")
                        or compact(tree.xpath("string(//title)")),
                    )
                ]
            else:
                found = candidates(tree, real, hosts)
            stats["candidates"] = len(found)
            if not found:
                raise FetchError("栏目可访问，本页未识别到可核验的招聘公告")
            existing = {
                n.url: n
                for n in db.scalars(select(Notice).where(Notice.source_id == src.id))
            }
            threshold = (now() - timedelta(hours=18)).isoformat(timespec="seconds")
            eligible = [
                (u, t)
                for u, t in found
                if force or u not in existing or (existing[u].checked or "") < threshold
            ]
            stats["skipped"] = len(found) - len(eligible)
            # First scan: newest unseen links first. Later scans rotate older checked notices.
            eligible.sort(
                key=lambda p: (
                    p[0] in existing,
                    (existing[p[0]].checked or "") if p[0] in existing else "",
                )
            )
            max_items = limit or int(os.getenv("RADAR_NOTICES_PER_SOURCE", "5"))
            for url, label in eligible[:max_items]:
                n = existing.get(url) or db.scalar(
                    select(Notice).where(Notice.url == url)
                )
                try:
                    page, rows, info, sig, errors = collect_notice(
                        web, src, url, label, hosts, n
                    )
                    if n is None:
                        n = Notice(source_id=src.id, url=url, title=page["title"])
                        db.add(n)
                        db.flush()
                    prior_failure = bool(n.issue)
                    n.title, n.checked, n.issue = (
                        page["title"],
                        stamp(),
                        "；".join(errors)[:1200] or None,
                    )
                    if n.digest != sig or prior_failure:
                        stats["new"] += apply_rows(db, src, n, page, rows, errors)
                    else:
                        for job in db.scalars(
                            select(Job)
                            .join(Evidence)
                            .where(
                                Evidence.notice_id == n.id, Evidence.current.is_(True)
                            )
                        ):
                            job.checked = n.checked
                    n.digest, n.data = sig, info
                    src.sample, src.succeeded = url, n.checked
                    stats["read"] += 1
                    if errors:
                        stats["errors"] += 1
                        issues.append(n.issue)
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    msg = str(exc)[:240] or type(exc).__name__
                    stats["errors"] += 1
                    issues.append(label[:35] + "：" + msg)
                    n = db.scalar(select(Notice).where(Notice.url == url))
                    if not n:
                        n = Notice(source_id=src.id, url=url, title=label)
                        db.add(n)
                    n.issue, n.checked = msg, stamp()
                    if n.id:
                        for job in db.scalars(
                            select(Job)
                            .join(Evidence)
                            .where(
                                Evidence.notice_id == n.id, Evidence.current.is_(True)
                            )
                        ):
                            job.data = {**job.data, "issue": "最近核验未取得正文"}
                    db.commit()
            if (
                not eligible
                and src.sample
                and not any(n.issue for n in existing.values())
            ):
                src.succeeded = stamp()
            if not eligible and src.issue:
                issues.append(src.issue)
        except Exception as exc:
            stats["errors"] += 1
            issues.append(str(exc)[:250] or type(exc).__name__)
        src.issue = "；".join(issues)[:1500] or None
        src.counts = stats
        db.add(
            Log(
                run_id=run_id,
                source_id=src.id,
                message=f"{src.name}：读取 {stats['read']} 篇，新增 {stats['new']} 岗"
                + ("；" + src.issue if src.issue else ""),
            )
        )
        db.commit()
        return stats
