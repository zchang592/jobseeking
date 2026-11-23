"""Classify vacancies by the job's school level, including existing stored records."""

import re

SECONDARY = "secondary"
UNIVERSITY = "university"
PRIMARY = "primary"
OTHER = "other"

_SECONDARY = re.compile(
    r"初中|高中|中学|中小学|初高中|初高?中|初级中学|高级中学|附属中等(?:音乐|艺术)学校|附中"
    r"|secondary|k[–-]?12|senior\s+school|middle\s+(?:and\s+high\s+)?school|high\s+school|grades?\s*6\s*[-–~至]\s*(?:8|9|12)",
    re.I,
)
_PRIMARY = re.compile(
    r"小学|幼儿园|幼教|primary|junior\s+school|elementary|kindergarten|early\s*(?:years|childhood)|\bpre-?k\b|\bpyp\b",
    re.I,
)
_INTERNATIONAL = re.compile(
    r"国际学校|双语学校|国际部|国际课程|international\s+school|bilingual\s+school", re.I
)
_UNIVERSITY = re.compile(
    r"高等教育|高职|大专|大学|学院|university|college|conservator", re.I
)


def job_category(job):
    # Specific job and department wording takes priority over a K–12 school name.
    for key in ("title", "department", "stage", "school"):
        part = str(job.get(key) or "")
        if _SECONDARY.search(part):
            return SECONDARY
        if _PRIMARY.search(part):
            return PRIMARY
    kind = " ".join(
        str(job.get(key) or "") for key in ("title", "school", "school_type", "stage")
    )
    if _INTERNATIONAL.search(kind):
        return SECONDARY
    if _UNIVERSITY.search(kind):
        return UNIVERSITY
    return OTHER
