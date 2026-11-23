"""Generate the public catalogue using only the verified snapshot and public source registry."""

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, time
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from radar.categories import job_category

TZ = ZoneInfo("Asia/Shanghai")
STATUSES = ("招聘中", "未开始", "已截止", "待核实")
JOB_FIELDS = {
    "岗位代码": "code",
    "所属部门": "department",
    "学校类型": "school_type",
    "学段": "stage",
    "聘用形式": "employment",
    "招聘人数": "count",
    "工作安排": "workload",
    "发布时间": "published",
    "报名开始": "starts",
    "报名截止": "deadline",
}
REQUIREMENTS = {
    "学历与学位": "degree",
    "专业方向": "major",
    "岗位职责": "duties",
    "资格证书": "certificate",
    "职称要求": "rank",
    "其他要求": "other",
    "通用资格": "general",
    "待遇": "pay",
}


def parse_time(value, end=False):
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if len(value) == 10 and end:
        moment = datetime.combine(moment.date(), time.max)
    return moment.astimezone(TZ) if moment.tzinfo else moment.replace(tzinfo=TZ)


def display_time(value):
    moment = parse_time(value)
    if not moment:
        return ""
    return moment.strftime("%Y-%m-%d" if len(value) == 10 else "%Y-%m-%d %H:%M")


def status_for(data, at):
    ends = parse_time(data.get("deadline"), end=True)
    starts = parse_time(data.get("starts"))
    if ends and at > ends:
        return "已截止"
    if data.get("issue"):
        return "待核实"
    if starts and at < starts:
        return "未开始"
    return "招聘中" if ends and not data.get("early_close") else "待核实"


def text(value):
    return escape(str(value or ""))


def web_url(value):
    if not isinstance(value, str) or re.search(r"[\x00-\x20\\]", value):
        return ""
    try:
        parts = urlsplit(value, allow_fragments=True)
        if (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and not (parts.username or parts.password)
        ):
            return value
    except ValueError:
        pass
    return ""


def link(label, url):
    target = web_url(url)
    if not target:
        return text(label)
    return f'<a href="{text(target)}" target="_blank" rel="noopener noreferrer">{text(label)}</a>'


def page(title, content, base="./"):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="浏览音乐教职公开招聘岗位、资格要求及官方公告。">
  <meta name="referrer" content="no-referrer">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'">
  <title>{text(title)}</title>
  <link rel="stylesheet" href="{base}style.css">
  <script src="{base}radar.js" defer></script>
</head>
<body>
  <header class="topbar"><div class="wrap">
    <a class="brand" href="{base}">音乐教职雷达</a>
    <nav aria-label="网站导航"><a href="{base}">招聘岗位</a><a href="{base}sources/">监控来源</a></nav>
  </div></header>
  <main class="wrap">{content}</main>
  <footer class="footer"><div class="wrap muted">公开招聘索引 · 报名条件及变更以原公告为准</div></footer>
</body>
</html>
"""


def job_badge(data, at):
    status = status_for(data, at)
    return f'<span class="badge" data-status="{status}">{status}</span>'


def job_attributes(data):
    fields = {
        "starts": parse_time(data.get("starts")),
        "deadline": parse_time(data.get("deadline"), end=True),
    }
    attrs = " ".join(
        f'data-{key}="{int(value.timestamp() * 1000)}"'
        for key, value in fields.items()
        if value is not None
    )
    return (
        f'data-job {attrs} data-unverified="{str(bool(data.get("issue"))).lower()}" '
        f'data-early-close="{str(bool(data.get("early_close"))).lower()}"'
    )


def listing(job, at):
    data = job["data"]
    search = " ".join(
        str(part or "")
        for part in (
            job["title"],
            job["school"],
            data.get("city"),
            data.get("province"),
            data.get("department"),
            data.get("degree"),
            data.get("major"),
            data.get("duties"),
        )
    ).lower()
    place = " · ".join(
        str(part)
        for part in (job["school"], data.get("city"), data.get("stage"))
        if part
    )
    category = job_category({**data, "title": job["title"], "school": job["school"]})
    cutoff = display_time(data.get("deadline"))
    deadline = f"报名截止 {cutoff}" if cutoff else "截止时间未知"
    return f"""<li class="listing" {job_attributes(data)} data-school="{text(job["school"])}"
       data-stage="{text(data.get("stage"))}" data-category="{category}" data-search="{text(search)}">
  <div class="listing-head">
    <h3><a href="jobs/{job["identity"]}/">{text(job["title"])}</a></h3>
    {job_badge(data, at)}
  </div>
  <p class="muted">{text(place)}</p>
  <p class="footnote">{deadline}</p>
</li>"""


def select_filter(name, label, values):
    options = "".join(f'<option value="{text(v)}">{text(v)}</option>' for v in values)
    return (
        f'<label>{label}<select name="{name}">'
        f'<option value="">全部{label}</option>{options}</select></label>'
    )


def homepage(jobs, verified, at, captured):
    schools = sorted({j["school"] for j in jobs})
    stages = sorted({j["data"]["stage"] for j in jobs if j["data"].get("stage")})
    active = sum(status_for(j["data"], at) == "招聘中" for j in jobs)
    categories = (
        ("secondary", "中学与国际学校"),
        ("university", "高校与音乐学院"),
        ("primary", "小学与幼教"),
        ("other", "其他 / 学段待核实"),
        ("all", "全部"),
    )
    tabs = "".join(
        f'<a href="?category={value}#listing-title" class="category-tab" data-category-link="{value}">{label}</a>'
        for value, label in categories
    )
    filters = "\n".join(
        (
            select_filter("status", "状态", STATUSES),
            select_filter("school", "学校", schools),
            select_filter("stage", "学段", stages),
        )
    )
    listings = "\n".join(listing(job, at) for job in jobs)
    empty = "" if not jobs else " hidden"
    return page(
        "音乐教职雷达｜公开招聘岗位",
        f"""
<section class="hero"><h1>音乐教职雷达</h1>
  <p>重点关注初中、高中及国际学校音乐教师机会。</p>
</section>
<div class="stats" aria-label="收录概况">
  <div><span>已收录岗位</span><strong>{len(jobs)}</strong></div>
  <div><span>正在招聘</span><strong id="open-count">{active}</strong></div>
  <div><span>已核验来源</span><strong>{verified}</strong></div>
</div>
<section aria-labelledby="listing-title">
  <h2 id="listing-title">招聘岗位</h2>
  <p class="muted footnote">公开数据更新于 {text(display_time(captured) or "未知")}（北京时间）</p>
  <nav class="category-tabs" aria-label="岗位分类">{tabs}</nav>
  <form class="panel" id="filters" aria-label="筛选岗位">
    <input type="hidden" name="category" value="secondary">
    <div class="filters">
      <label>搜索岗位<input name="q" type="search" placeholder="如 作曲、钢琴、浙江音乐学院"></label>
      {filters}
    </div>
    <div class="filter-footer"><p id="result-count" aria-live="polite">显示 {len(jobs)} 个岗位</p>
      <button type="reset">清除筛选</button></div>
  </form>
  <p class="panel muted" id="no-results"{empty}>这个分类暂时没有符合筛选条件的岗位。请查看下方的招聘平台或选择其他分类。</p>
  <noscript><p class="muted">当前显示全部岗位。启用 JavaScript 可按学校类别筛选。</p></noscript>
  <ul class="job-list" id="job-list">{listings}</ul>
</section>
<section class="panel discovery">
  <h2>更多中学与国际学校机会</h2>
  <p class="muted">以下入口供你自行查看和申请，实际条件及截止时间以招聘方页面为准。</p>
  <div class="discovery-links">
    <a href="https://www.zhipin.com/web/geek/job?query=%E9%AB%98%E4%B8%AD%E9%9F%B3%E4%B9%90%E6%95%99%E5%B8%88" target="_blank" rel="noopener noreferrer">BOSS 直聘 · 高中音乐教师 ↗</a>
    <a href="https://www.zhipin.com/web/geek/job?query=%E5%88%9D%E4%B8%AD%E9%9F%B3%E4%B9%90%E6%95%99%E5%B8%88" target="_blank" rel="noopener noreferrer">BOSS 直聘 · 初中音乐教师 ↗</a>
    <a href="https://www.zhipin.com/web/geek/job?query=%E5%9B%BD%E9%99%85%E5%AD%A6%E6%A0%A1%E9%9F%B3%E4%B9%90%E6%95%99%E5%B8%88" target="_blank" rel="noopener noreferrer">BOSS 直聘 · 国际学校音乐教师 ↗</a>
    <a href="https://www.tes.com/jobs/browse/music-china" target="_blank" rel="noopener noreferrer">TES · 中国音乐教师岗位 ↗</a>
    <a href="https://wellington.avature.cn/en_GB/careers" target="_blank" rel="noopener noreferrer">惠灵顿 / 惠立学校 · 招聘官网 ↗</a>
    <a href="https://www.isb.cn/employment" target="_blank" rel="noopener noreferrer">北京顺义国际学校 · 招聘官网 ↗</a>
    <a href="https://www.scis-china.org/careers/employment-opportunities" target="_blank" rel="noopener noreferrer">上海长宁国际学校 · 招聘官网 ↗</a>
  </div>
</section>""",
    )


def fields(data, labels):
    values = []
    for label, key in labels.items():
        value = data.get(key)
        if key in {"published", "starts", "deadline"}:
            value = display_time(value)
        if key == "deadline" and not value:
            value = "截止时间未知"
        if value:
            values.append(f"<div><dt>{label}</dt><dd>{text(value)}</dd></div>")
    return "\n".join(values)


def proof_list(proofs, notices):
    entries = []
    for proof in proofs:
        notice = notices[proof["notice"]]
        proof_data = proof["data"]
        source = link(notice.get("title") or "原始公告", notice.get("url"))
        attachments = {
            att["url"]: att.get("name") or "公告附件"
            for att in notice.get("data", {}).get("attachments", [])
            if web_url(att.get("url"))
        }
        if web_url(proof_data.get("file")):
            location = proof_data.get("location")
            label = proof_data.get("file_name") or "岗位所在附件"
            attachments[proof_data["file"]] = (
                f"{label} · {location}" if location else label
            )
        if web_url(proof_data.get("detail_url")):
            attachments[proof_data["detail_url"]] = "岗位原文"
        links = "".join(
            f"<li>{link(label, url)}</li>" for url, label in attachments.items()
        )
        checked = display_time(notice.get("checked"))
        note = (
            f' <span class="muted footnote">核验 {text(checked)}</span>'
            if checked
            else ""
        )
        entries.append(
            f"<li>{source}{note}" + (f"<ul>{links}</ul>" if links else "") + "</li>"
        )
    return "\n".join(entries)


def job_detail(job, proofs, notices, at):
    data = job["data"]
    reqs = fields(data, REQUIREMENTS)
    apply_url = web_url(data.get("apply_url"))
    entry = f"<p>{link('官方报名入口', apply_url)}</p>" if apply_url else ""
    status_note = ""
    if data.get("early_close"):
        status_note = '<p class="muted">公告包含招满即停条款，请向招聘单位核实。</p>'
    elif data.get("issue"):
        status_note = '<p class="muted">部分条件待核实，请查看原公告。</p>'
    return page(
        f"{job['title']}｜音乐教职雷达",
        f"""
<p><a href="../../">← 返回招聘岗位</a></p>
<section class="panel" {job_attributes(data)}>
  <div class="job-head"><h1 class="job-title">{text(job["title"])}</h1>{job_badge(data, at)}</div>
  <p class="tagline">{text(job["school"])} · {text(data.get("city") or data.get("province") or "地区待核实")}</p>
  <dl class="facts">{fields(data, JOB_FIELDS)}</dl>
  {status_note}{entry}
</section>
<section class="panel"><h2>报考要求</h2>
  {f'<dl class="requirements">{reqs}</dl>' if reqs else '<p class="muted">请以招聘公告列出的要求为准。</p>'}
</section>
<section class="panel"><h2>官方公告与附件</h2>
  <ul class="proof-list">{proof_list(proofs, notices)}</ul>
</section>""",
        base="../../",
    )


def sources_page(catalog, observations):
    entries = []
    for source in catalog:
        url = source["url"]
        state = observations.get(url, {})
        if not source.get("enabled", True):
            status = "已暂停"
        elif state.get("sample") and state.get("succeeded"):
            status = "已核验"
        else:
            status = "待核实"
        sample = (
            link("核验样本", state.get("sample"))
            if web_url(state.get("sample"))
            else ""
        )
        city = " · ".join(
            dict.fromkeys(x for x in (source.get("province"), source.get("city")) if x)
        )
        stamp = display_time(state.get("succeeded"))
        info = f"最近成功 {stamp}" if stamp else "暂无成功核验记录"
        issue = " · 最近采集有待核实项目" if state.get("issue") else ""
        entries.append(f"""<li class="listing"><div class="listing-head">
          <h3>{link(source["school"], url)}</h3>
          <span class="badge" data-status="{status}">{status}</span>
          </div><p class="muted">{text(city)} · {info}{issue} {sample}</p></li>""")
    return page(
        "监控来源｜音乐教职雷达",
        f"""
<h1 class="job-title">监控来源</h1>
<p class="muted">链接指向学校与公开招聘栏目。核验样本可能属于往期招聘。</p>
<ul class="job-list">{"".join(entries)}</ul>""",
        base="../",
    )


def build(snapshot_path, output, at=None):
    at = at or datetime.now(TZ)
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "data/sources.json").read_text(encoding="utf-8"))
    sites = {s["url"] for s in catalog}
    states = {s["url"]: s for s in snapshot["sources"] if s["url"] in sites}
    notices = {
        n["url"]: n
        for n in snapshot["notices"]
        if n["source"] in sites and web_url(n["url"])
    }
    proofs = defaultdict(list)
    for entry in snapshot["evidence"]:
        if entry["notice"] in notices and entry.get("current", True):
            proofs[entry["job"]].append(entry)
    jobs = [
        job
        for job in snapshot["jobs"]
        if job["identity"] in proofs and re.fullmatch(r"[a-f0-9]{64}", job["identity"])
    ]
    jobs.sort(
        key=lambda j: (
            status_for(j["data"], at) == "招聘中",
            j["data"].get("published") or "",
            j["first_seen"],
        ),
        reverse=True,
    )
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty output directory for the public site")
    output.mkdir(parents=True, exist_ok=True)
    for relative in ("style.css", "radar.js"):
        (output / relative).write_bytes((ROOT / "pages" / relative).read_bytes())
    (output / "signal-field.webp").write_bytes(
        (ROOT / "web/public/signal-field.webp").read_bytes()
    )
    (output / ".nojekyll").touch()
    verified = sum(
        bool(s.get("sample") and s.get("succeeded")) for s in states.values()
    )
    (output / "index.html").write_text(
        homepage(jobs, verified, at, snapshot["captured"]), encoding="utf-8"
    )
    (output / "sources").mkdir()
    (output / "sources/index.html").write_text(
        sources_page(catalog, states), encoding="utf-8"
    )
    for job in jobs:
        folder = output / "jobs" / job["identity"]
        folder.mkdir(parents=True)
        content = job_detail(job, proofs[job["identity"]], notices, at)
        (folder / "index.html").write_text(content, encoding="utf-8")
    return len(jobs)


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--snapshot", type=Path, default=ROOT / "data/verified.json")
    args.add_argument("--output", type=Path, required=True)
    options = args.parse_args()
    count = build(options.snapshot, options.output)
    print(f"已构建公开版本，{count} 个岗位")


if __name__ == "__main__":
    main()
