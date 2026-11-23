import json
import os
import re
from datetime import datetime, time

from pathlib import Path
from .settings import ROOT, DATA, TZ, now
from .categories import SECONDARY, job_category

PRIVATE_PROFILE = Path(os.getenv("RADAR_PROFILE_FILE") or DATA / "profile.json")
PROFILE = json.loads(
    (
        PRIVATE_PROFILE if PRIVATE_PROFILE.is_file() else ROOT / "data/profile.json"
    ).read_text()
)

# Match the duties, discipline and job name. Institution names alone are never evidence of a specialty.
DOMAINS = {
    "作曲": r"作曲|编曲|配器|乐队写作|音乐创作|composition|orchestration",
    "音乐理论": r"音乐理论|音乐基础理论|乐理|视唱|练耳|和声|复调|曲式|作品分析|作曲技术理论|solf[eè]ge|ear training|harmony",
    "钢琴伴奏": r"艺术指导|钢琴合作|钢琴协作|钢琴伴奏|合作钢琴|collaborative piano|accompanist",
    "钢琴": r"钢琴|piano|键盘演奏",
    "音乐教学": r"音乐教育|音乐学科|音乐教[学师]|学科教学[（(]?音乐|中学音乐|高中音乐|初中音乐|小学音乐|中小学音乐|音乐课|music education|music teacher|teacher of music|music educator|music instructor",
    "音乐科技": r"电子音乐|数字音乐|音乐科技|音乐制作|录音艺术|计算机音乐|音乐人工智能|人工智能音乐|AI\s*作曲|AIGC\s*音乐",
    "音乐学": r"音乐学(?!院|校|科)|音乐史|民族音乐|音乐研究",
}


def directions(text):
    return [name for name, pattern in DOMAINS.items() if re.search(pattern, text, re.I)]


def analyze(job, profile=None):
    profile = profile if profile is not None else PROFILE
    title = job["title"]
    context = " ".join(str(job.get(k) or "") for k in ("major", "duties", "specialty"))
    tags = directions(title + " " + context)
    matched = [x for x in tags if x in profile["skills"]]
    reasons, checks, barriers = [], [], []
    score = 25
    if matched:
        weight = {
            "作曲": 58,
            "音乐理论": 58,
            "钢琴伴奏": 55,
            "钢琴": 46,
            "音乐教学": 54,
        }
        score += max(weight.get(x, 40) for x in matched) + min(
            8, 4 * (len(matched) - 1)
        )
        reasons.append("专业与实践重合：" + "、".join(matched))
    elif tags:
        score += 20
        reasons.append("同属音乐领域，具体研究或实践方向需比对")
    if profile.get("teaching") and re.search("教师|教学|讲师", title) and matched:
        score += 5
        reasons.append("有艺术学校或中学教学经历可作为教学证据")
    if job.get("province") == "广东":
        reasons.append("符合广东地区轻度偏好")
    hard = " ".join(
        str(job.get(k) or "")
        for k in ("degree", "other", "certificate", "rank", "major", "duties")
    )
    if re.search(r"算法|机器学习|编程|Python|C\+\+", title + " " + hard, re.I):
        checks.append("需要核实算法或编程能力，作曲和音乐 AI 经历不能替代技术要求")
        score = min(score, 65)
    if re.search(
        r"中英|英语|english", str(profile.get("language") or ""), re.I
    ) and re.search(
        r"双语|英文授课|英语授课|bilingual|english", hard + " " + title, re.I
    ):
        reasons.append("有中英双语授课基础，课程术语和国际课程经验需逐项核实")
    degree = job.get("degree") or ""
    highest = profile.get("highest_degree", "")
    if "博士" in degree and highest != "博士":
        if re.search(
            r"博士(?:学位|研究生)?优先|博士在读可|或硕士|硕士及以上|硕士或", degree
        ) or re.search(r"放宽至?硕士|硕士.{0,10}亦可", hard):
            checks.append("公告含博士或放宽条款，需核对适用条件")
        else:
            barriers.append(
                f"岗位要求博士学位；目前已取得{highest or '待核实'}学位，博士在读不等于取得博士学位"
            )
    if not degree:
        checks.append("未提取到明确的最低学位，需核对原公告和岗位表")
    if job.get("certificate") and any(
        "教师资格" in value for value in profile.get("certificates", [])
    ):
        checks.append("已提供教师资格证信息，需核对学段、学科及公告的其他要求")
    if job.get("certificate") or job.get("rank"):
        checks.append(
            "核实所需教师资格或职称："
            + "；".join(filter(None, (job.get("certificate"), job.get("rank"))))[:160]
        )
    if job.get("other"):
        checks.append("逐项核对岗位表的年龄、经历、业绩或其他条件")
    if job.get("issue"):
        checks.append("部分来源证据待人工核实")
    if job.get("general"):
        checks.append("核实公告通用资格，包括身份、毕业时限等条件")
    if not matched:
        checks.append("核对专业名称、研究方向和专业目录")
    if barriers:
        verdict = "明确不符合"
    elif not degree:
        verdict = "信息不足"
    elif checks or not re.search("硕士|本科|学士|不限", degree):
        verdict = "可能符合，需要核实"
    else:
        verdict = "基本符合"
    return {
        "score": min(100, score),
        "eligibility": verdict,
        "matched": matched,
        "reasons": reasons,
        "checks": barriers + checks,
        "directions": tags,
        "method": "规则匹配",
        "category": job_category(job),
        "priority": job_category(job) == SECONDARY,
    }


def local_dt(value, end=False):
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if len(value) == 10:
        dt = datetime.combine(dt.date(), time.max if end else time.min)
    return dt.replace(tzinfo=TZ) if dt.tzinfo is None else dt.astimezone(TZ)


def status(job, at=None):
    at = at or now()
    end = local_dt(job.get("deadline"), end=True)
    start = local_dt(job.get("starts"))
    if end and at > end:
        return "已截止"
    if job.get("withdrawn") or job.get("issue"):
        return "待核实"
    if start and at < start:
        return "未开始"
    if not end or job.get("early_close"):
        return "待核实"
    return "招聘中"


def recommended(job):
    return (
        job["score"] >= 75
        and job["status"] == "招聘中"
        and job["priority"]
        and job["eligibility"] in ("基本符合", "可能符合，需要核实")
        and job.get("flag") not in ("忽略", "已结束")
    )
