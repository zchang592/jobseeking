from collections import Counter

from sqlalchemy import select

from .analysis import analyze, local_dt, recommended, status
from .db import Evidence, Job, Notice, Run, Source
from .settings import now

FLAGS = ("未标记", "准备申请", "已申请", "面试中", "已结束", "忽略")


def job_view(job):
    data = {
        **job.data,
        "id": job.id,
        "title": job.title,
        "school": job.school,
        "flag": job.flag,
        "saved": job.saved,
        "first_seen": job.first_seen,
        "checked": job.checked,
        "withdrawn": job.withdrawn,
    }
    return {**data, **analyze(data), "status": status(data)}


def rank(job):
    quality = {"基本符合": 3, "可能符合，需要核实": 2, "信息不足": 1, "明确不符合": 0}
    return (
        recommended(job),
        job["flag"] != "忽略",
        job["status"] not in ("已截止", "未开始"),
        job["eligibility"] != "明确不符合",
        job["priority"],
        job["score"],
        quality[job["eligibility"]],
        job.get("province") == "广东",
        job.get("published") or "",
        -job["id"],
    )


def all_jobs(db):
    return [job_view(j) for j in db.scalars(select(Job))]


def until(job):
    d = local_dt(job.get("deadline"))
    return (d.date() - now().date()).days if d else None


def filter_jobs(rows, p):
    rows = list(rows)
    for key in ("school", "city", "stage", "status", "eligibility", "flag", "province"):
        if p.get(key):
            rows = [j for j in rows if j.get(key) == p[key]]
    if p.get("q"):
        q = p["q"].strip().casefold()
        rows = [
            j
            for j in rows
            if q
            in " ".join(
                str(j.get(k) or "")
                for k in (
                    "school",
                    "title",
                    "city",
                    "major",
                    "department",
                    "directions",
                    "duties",
                )
            ).casefold()
        ]
    if p.get("direction"):
        rows = [j for j in rows if p["direction"] in j["directions"]]
    for key in ("published", "deadline"):
        for suffix in ("from", "to"):
            v = p.get(f"{key}_{suffix}")
            if v:
                rows = [
                    j
                    for j in rows
                    if j.get(key)
                    and (j[key][:10] >= v if suffix == "from" else j[key][:10] <= v)
                ]
    score = int(p.get("min_score", 0) or 0)
    rows = [j for j in rows if j["score"] >= score]
    tab = p.get("view")
    if tab == "recommended":
        rows = [j for j in rows if recommended(j)]
    elif tab == "soon":
        rows = [
            j
            for j in rows
            if j["status"] == "招聘中" and until(j) is not None and 0 <= until(j) <= 7
        ]
    elif tab == "new":
        rows = [j for j in rows if j["first_seen"][:10] == now().date().isoformat()]
    elif tab == "saved":
        rows = [j for j in rows if j["saved"] or j["flag"] != "未标记"]
    sort = p.get("sort")
    if sort == "deadline":
        rows.sort(
            key=lambda j: (
                j["status"] == "已截止",
                j.get("deadline") or "9999",
                j["id"],
            )
        )
    elif sort in ("published", "first_seen", "score"):
        rows.sort(key=lambda j: (j.get(sort) or "", j["id"]), reverse=True)
    else:
        rows.sort(key=rank, reverse=True)
    return rows


def detail(db, j):
    row = job_view(j)
    evidence = []
    for e, n, s in db.execute(
        select(Evidence, Notice, Source)
        .join(Notice, Evidence.notice_id == Notice.id)
        .join(Source, Notice.source_id == Source.id)
        .where(Evidence.job_id == j.id)
    ):
        attachments = [
            {k: a.get(k) for k in ("url", "name", "type", "error")}
            for a in (n.data or {}).get("attachments", [])
        ]
        evidence.append(
            {
                **e.data,
                "current": e.current,
                "url": n.url,
                "title": n.title,
                "source": s.name,
                "kind": s.meta.get("kind"),
                "checked": n.checked,
                "issue": n.issue,
                "attachments": attachments,
            }
        )
    row["evidence"] = sorted(
        evidence, key=lambda x: (x["current"], x["kind"] == "学校官网"), reverse=True
    )
    return row


def run_view(r):
    return (
        {
            k: getattr(r, k)
            for k in ("id", "trigger", "state", "created", "finished", "report")
        }
        if r
        else None
    )


def overview(db):
    rows = all_jobs(db)
    found = filter_jobs(rows, {"view": "new"})
    soon = filter_jobs(rows, {"view": "soon", "sort": "deadline"})
    high = filter_jobs(rows, {"view": "recommended"})
    active = sum(j["status"] == "招聘中" for j in rows)
    srcs = list(db.scalars(select(Source).where(Source.removed.is_(False))))
    return {
        "date": now().date().isoformat(),
        "total": len(rows),
        "new": len(found),
        "open": active,
        "high": len(high),
        "soon": len(soon),
        "top": sorted(rows, key=rank, reverse=True)[:5],
        "deadlines": soon[:4],
        "sources": len(srcs),
        "enabled": sum(s.enabled for s in srcs),
        "verified": sum(bool(s.sample and s.succeeded) for s in srcs),
        "last_checked": max((s.succeeded or "" for s in srcs), default=""),
        "last_run": run_view(db.scalar(select(Run).order_by(Run.id.desc()))),
        "breakdown": dict(Counter(j["status"] for j in rows)),
    }


def brief(db):
    rows = all_jobs(db)
    return {
        "date": now().date().isoformat(),
        "new": filter_jobs(rows, {"view": "new"}),
        "high": filter_jobs(rows, {"view": "recommended"}),
        "soon": filter_jobs(rows, {"view": "soon", "sort": "deadline"}),
    }
