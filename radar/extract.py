"""Conservative extraction: a job needs its own title in prose or its own table row."""

import hashlib
import io
import re
import unicodedata
import zipfile
from datetime import datetime
from urllib.parse import unquote, urljoin, urlsplit, urldefrag

import openpyxl
import pdfplumber
import xlrd
from docx import Document
from lxml import html

from .analysis import directions

JOB_NOTICE = re.compile(
    r"招聘|公开选聘|诚聘|选聘教师|人才引进|引进人才|招募教师|延长.*报名"
)
IGNORE = re.compile(
    r"拟聘|拟录|录用|招聘会|宣讲会|招聘系统|报名系统|招聘网站|毕业生就业|拟入|候选人|进面|复审|面试(?:工作安排|成绩|名单|安排|通知|公告)|笔试(?:结果|通知|安排|公告|成绩)|非教学岗位|(?:参加笔试|参加面试|进入面试).{0,12}名单|后续考核安排|考试(?:工作安排|安排|结果|通知)|考核(?:成绩|日程)|体检|体测|排名|成绩公示|结果公示|应聘须知|工作纪实|喜报|博士后|科研助理|辅导员|党政管理"
)
ATT = re.compile(r"\.(xlsx|xls|pdf|docx|doc|zip|rar)(?:$|[?#\s）)])", re.I)
HEADERS = {
    "title": r"^(岗位名称|招聘岗位名称|招聘岗位|需求岗位|岗位|拟聘岗位|招聘职位|职位名称|学科岗位|招聘学科)$",
    "code": r"岗位(编码|代码|编号)|职位代码",
    "department": r"用人部门|用人单位|招聘部门|^部门$|^学院$|所属学院|^系部$",
    "school_field": r"招聘单位|学校名称",
    "count": r"人数|名额|招聘数量|计划数",
    "degree": r"学历|学位",
    "major": r"专业要求|专业名称|学科方向|专业方向|^专业|学科专业",
    "certificate": r"资格证|教师资格",
    "rank": r"职称|职业资格",
    "other": r"其他|其它|备注|工作经历|政治面貌|年龄|任职条件|岗位条件",
    "duties": r"岗位职责|工作内容|岗位描述",
    "pay": r"薪资|薪酬|待遇",
    "employment": r"聘用形式|聘用类别|编制性质|用工形式",
    "workload": r"全职|兼职|工作性质",
}
DATE = r"(?:(?P<year>20\d{2})[年./-])?(?P<month>\d{1,2})[月./-](?P<day>\d{1,2})日?(?:[ T]?(?P<hour>\d{1,2})(?:[:时](?P<minute>\d{2})分?|时))?"
DATE_RE = re.compile(DATE)


def compact(t):
    return re.sub(
        r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])",
        "",
        " ".join(str(t or "").split()),
    ).strip()


def document(data):
    for enc in ("utf-8-sig", "gb18030"):
        try:
            raw = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raw = data.decode("utf8", "replace")
    return html.document_fromstring(raw or "<html></html>")


def public_link(base, raw):
    url = urldefrag(urljoin(base, raw.strip()))[0]
    p = urlsplit(url)
    return (
        url
        if p.scheme in ("https", "http")
        and p.hostname
        and not p.username
        and not p.password
        else ""
    )


def links(tree, base):
    for a in tree.xpath(".//a[@href]"):
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = public_link(base, href)
        if url:
            label = max((compact(a.get("title")), compact(a.text_content())), key=len)
            yield url, label


def candidates(tree, base, hosts):
    found = {}
    for url, title in links(tree, base):
        if urlsplit(url).hostname not in hosts or url == base:
            continue
        if (
            len(title) < 8
            or re.fullmatch(
                r".{0,5}(?:招聘信息|招聘公告|招聘工作|招聘岗位)(?:\s*>+)?", title
            )
            and not re.search(r"20\d{2}", title)
            or not JOB_NOTICE.search(title)
            or IGNORE.search(title)
            or ATT.search(url)
        ):
            continue
        if re.search(
            r"(?:/list[\w.-]*|/index[\w.-]*|/main\.htm)/?$", urlsplit(url).path, re.I
        ):
            continue
        found.setdefault(url, title[:180])
    return list(found.items())


def body_info(tree, url, fallback):
    for node in tree.xpath("//script|//style|//nav|//footer|//header|//noscript"):
        node.drop_tree()
    for xp in ('//*[@property="og:title"]/@content', "//h1/text()", "//title/text()"):
        values = [compact(x) for x in tree.xpath(xp)]
        titles = [x for x in values if JOB_NOTICE.search(x) and len(x) > 8]
        if titles:
            fallback = re.split(
                r"\s+-\s+|-(?=[\u3400-\u9fff].*(学院|大学))|\s*\|\s*", titles[0]
            )[0]
            break
    body = None
    for cls in (
        "v_news_content",
        "xw_content",
        "contentN",
        "wp_articlecontent",
        "article_content",
        "article-content",
        "articleCon",
        "conTxt",
        "RichText",
        "TRS_Editor",
    ):
        nodes = tree.xpath(
            '//*[contains(concat(" ",normalize-space(@class)," "),$token)]',
            token=" " + cls + " ",
        )
        if nodes:
            body = nodes[0]
            break
    if body is None:
        nodes = tree.xpath(
            '//article|//*[@id="vsb_content" or @id="zoom" or @id="js_content" or @id="content"]'
        )
        body = nodes[0] if nodes else tree
    parts = [
        compact(e.text_content())
        for e in body.xpath(".//p[not(.//p)]|.//li[not(.//li) and not(ancestor::nav)]")
    ]
    if len("".join(parts)) < 80:
        parts = [compact(x) for x in body.itertext()]
    text = "\n".join(x for x in parts if x)[:300000]
    atl = {}
    for link, label in links(tree, url):
        m = ATT.search(unquote(urlsplit(link).path)) or ATT.search(label)
        if m and link not in atl:
            atl[link] = {
                "url": link,
                "name": label[:150] or unquote(urlsplit(link).path.rsplit("/", 1)[-1]),
                "type": m[1].lower(),
            }
    return fallback, body, text, list(atl.values())


def date_value(m, year=None):
    yr = m["year"] or year
    if not yr:
        return None
    try:
        if m["hour"] == "24" and int(m["minute"] or 0) == 0:
            return datetime(int(yr), int(m["month"]), int(m["day"])).date().isoformat()
        d = datetime(
            int(yr),
            int(m["month"]),
            int(m["day"]),
            int(m["hour"] or 0),
            int(m["minute"] or 0),
        )
        return d.isoformat(timespec="minutes") if m["hour"] else d.date().isoformat()
    except ValueError:
        return None


def notice_dates(text, metadata=""):
    text = unicodedata.normalize("NFKC", text)
    data = {}
    pub = re.search(
        r"(?:发布日期|发布时间|发表时间|日期|时间)\s*[:：]\s*(20\d{2}[-年./]\d{1,2}[-月./]\d{1,2})",
        metadata,
    )
    if pub:
        data["published"] = date_value(DATE_RE.match(pub[1]))
    flat = re.sub(r"\s+", "", text)
    windows = []
    for piece in re.split(r"[。；;！？]", flat):
        match = re.search(
            r"(?:(?:网上|网络)?报名(?:的)?(?:起止时间|日期|时间|期限|截止(?:日期|时间)?)|申请截止(?:日期|时间)?|投递截止(?:日期|时间)?)",
            piece,
        )
        if not match:
            continue
        tail = re.split(
            r"缴费|打印准考证|笔试|资格初审|面试时间", piece[match.end() :][:120]
        )[0]
        dates = list(DATE_RE.finditer(tail))
        if not dates:
            continue
        first = dates[0]
        a = date_value(first, (data.get("published") or "")[:4])
        if not a:
            continue
        window = {}
        if len(dates) >= 2 and re.search(
            r"至|到|[-—~～]", tail[first.end() : dates[1].start()]
        ):
            b = date_value(dates[1], a[:4])
            if not b or b < a:
                continue
            window.update(starts=a, deadline=b)
        elif (
            "截止" in match[0]
            or re.search(
                r"(?:截至|截止(?:时间|日期)?(?:为|至)?|发布之日至)[:：]?$",
                tail[: first.start()],
            )
            or re.match(r"(?:以前|之前|前|止|为止|截止)", tail[first.end() :])
        ):
            window["deadline"] = a
        if window:
            qualifier = (
                piece[max(0, match.start() - 26) : match.start()]
                + tail[: first.start()]
            )
            degrees = [x for x in ("博士", "硕士", "本科") if x in qualifier]
            window["for"] = degrees
            if "招满" in tail or "额满" in tail:
                window["early_close"] = True
            if window not in windows:
                windows.append(window)
    if len(windows) == 1 and not windows[0]["for"]:
        data.update({k: v for k, v in windows[0].items() if k != "for"})
    elif windows:
        data["windows"] = windows
    return data


def role_text(title, major, duties):
    # A school called a conservatory can also be hiring a history teacher.
    title = re.sub(
        r"[\u3400-\u9fff]{1,20}(?:音乐学院|艺术学院)(?:附属中等(?:艺术|音乐)学校)?",
        "",
        title,
    )
    return " ".join((title, major, duties))


def table_rows(rows, place, inherited=None):
    out, header = [], dict(inherited or {})
    for number, raw in enumerate(rows, 1):
        cells = [compact(c)[:2200] for c in raw]
        if not any(cells):
            continue
        mapping = {}
        for i, c in enumerate(cells):
            if len(c) > 30:
                continue
            for field, pattern in HEADERS.items():
                if re.search(pattern, c.replace(" ", "")) and field not in ("other",):
                    mapping[i] = field
                    break
                if field == "other" and re.search(pattern, c):
                    mapping[i] = field
                    break
        if "title" in mapping.values() and len(mapping) >= 2:
            header = mapping
            continue
        if not header:
            continue
        row = {}
        for i, k in header.items():
            if (
                i < len(cells)
                and cells[i]
                and cells[i] not in ("—", "/", "无", "不限（无）")
            ):
                row[k] = "；".join(filter(None, (row.get(k), cells[i])))
        title = row.get("title", "")
        major = row.get("major", "")
        if not (1 < len(title) < 110) or not directions(
            role_text(title, major, row.get("duties", ""))
        ):
            continue
        if re.search("辅导员|管理岗|行政岗|党务|后勤|调律|维修", title):
            continue
        row["location"] = f"{place} · 第 {number} 行"
        row["excerpt"] = "｜".join(
            f"{k}：{v}"
            for k, v in zip(
                ["岗位", "方向", "学历"], [title, major, row.get("degree", "")]
            )
            if v
        )[:550]
        out.append(row)
    return out, header


def check_zip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        sizes = z.infolist()
        if len(sizes) > 1800 or sum(e.file_size for e in sizes) > 60 * 1024 * 1024:
            raise ValueError("附件解压后过大")


def attachment_rows(kind, data):
    rows = []
    if kind in ("xlsx", "docx"):
        check_zip(data)
    if kind == "xlsx":
        wb = openpyxl.load_workbook(
            io.BytesIO(data), read_only=True, data_only=True, keep_links=False
        )
        try:
            for sheet in wb.worksheets[:15]:
                if (sheet.max_row or 0) > 12000 or (sheet.max_column or 0) > 120:
                    raise ValueError("工作表超出大小限制")
                rows += table_rows(
                    sheet.iter_rows(
                        values_only=True, max_col=min(sheet.max_column or 100, 120)
                    ),
                    sheet.title,
                )[0]
        finally:
            wb.close()
    elif kind == "xls":
        wb = xlrd.open_workbook(file_contents=data, on_demand=True)
        try:
            for sheet in wb.sheets()[:15]:
                if sheet.nrows > 12000 or sheet.ncols > 120:
                    raise ValueError("工作表超出大小限制")
                rows += table_rows(
                    (sheet.row_values(i) for i in range(sheet.nrows)), sheet.name
                )[0]
        finally:
            wb.release_resources()
    elif kind == "pdf":
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > 60:
                raise ValueError("PDF 页数过多")
            readable = False
            header = {}
            for i, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                for table in tables:
                    found, header = table_rows(table, f"PDF 第 {i} 页", header)
                    rows += found
                text = page.extract_text() or ""
                readable |= bool(text.strip())
                if not tables:
                    rows += prose_rows("", text, f"PDF 第 {i} 页")
                page.close()
            if not readable:
                raise ValueError("扫描版 PDF 需人工核实")
    elif kind == "docx":
        doc = Document(io.BytesIO(data))
        for i, t in enumerate(doc.tables[:60], 1):
            rows += table_rows(
                ([c.text for c in r.cells] for r in t.rows), f"Word 表 {i}"
            )[0]
        rows += prose_rows("", "\n".join(p.text for p in doc.paragraphs))
    else:
        raise ValueError("附件格式需人工核实")
    return rows


def prose_rows(title, text, location="公告正文"):
    rows = []
    for line in text.splitlines():
        m = re.match(
            r"^(?:招聘岗位名称|岗位名称|岗位一|岗位二|岗位三|招聘职位)[:：]\s*([^。；：:，]{2,80})$",
            line.strip(),
        )
        if m and directions(role_text(m[1], "", "")):
            rows.append({"title": m[1], "location": location, "excerpt": line[:500]})
    if not rows and 0 < len(title) < 110:
        role = re.sub(r"岗位招聘公告.*|招聘公告.*|招聘简章.*", "", title)
        if (
            re.search("教师|讲师|艺术指导|伴奏", role)
            and directions(role_text(role, "", ""))
            and len(text) >= 80
        ):
            excerpt = next(
                (p for p in text.splitlines() if "招聘" in p and directions(p)), title
            )
            rows.append({"title": role, "location": location, "excerpt": excerpt[:500]})
    if len(rows) == 1:
        for dest, pat in (
            ("degree", r"(?:学历学位要求|学历要求|学位要求)[:：]\s*([^\n。；]{2,90})"),
            (
                "certificate",
                r"((?:须|应|需|持有|具有)[^\n。；]{0,16}教师资格证[^\n。；]{0,15})",
            ),
        ):
            m = re.search(pat, text)
            if m:
                rows[0][dest] = m[1]
        if not rows[0].get("degree"):
            m = re.search(
                r"(?:须|应当|应|必须|要求|需|具有|具备|已取得)(?:具有|获得|取得|已取得)?(?:相关专业|本专业)?(?:博士研究生学历[、，并及和]*)?博士学位",
                text,
            )
            if m:
                rows[0]["degree"] = m[0]
    return rows


def digest(data):
    return hashlib.sha256(data).hexdigest()


def directory_page(tree, base):
    """Named posts published directly in CUHK-Shenzhen's official faculty directory."""
    rows = []
    for url, label in links(tree, base):
        ref = re.search(r"\(Ref\.\s*([A-Z]+\d{4}/\d+/\d+)\)", label)
        if not ref or urlsplit(url).hostname != "jobs.cuhk.edu.cn":
            continue
        name = re.split(r"\s*[–-]\s*音乐学院\s*\(Ref\.", label)[0].strip()
        if not directions(name):
            continue
        rows.append(
            {
                "title": name,
                "code": ref[1],
                "excerpt": label,
                "location": "学院官网教职岗位目录",
                "detail_url": url,
                "issue": "官网岗位目录已核验，详细资格与截止日期待人工核实",
            }
        )
    if not rows:
        raise ValueError("官方岗位目录结构改变，未取得有岗位编号的记录")
    return {
        "title": "教职岗位 · 香港中文大学（深圳）音乐学院",
        "common": {},
        "rows": rows,
        "attachments": [],
    }
