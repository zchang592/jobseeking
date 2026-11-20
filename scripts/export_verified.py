"""Export only public collection facts. Never export settings, application history or user-added sources."""

import argparse
import json
import re
from pathlib import Path
from sqlalchemy import select

from radar.db import Sessions, Evidence, Job, Notice, Source
from radar.settings import ROOT, stamp


def export(out):
    catalog = {s["url"] for s in json.loads((ROOT / "data/sources.json").read_text())}
    result = {
        "captured": stamp(),
        "sources": [],
        "notices": [],
        "jobs": [],
        "evidence": [],
    }
    with Sessions() as db:
        sources = {
            s.id: s for s in db.scalars(select(Source).where(Source.url.in_(catalog)))
        }
        notices = {
            n.id: n
            for n in db.scalars(select(Notice).where(Notice.source_id.in_(sources)))
        }
        proofs = list(
            db.scalars(
                select(Evidence).where(
                    Evidence.notice_id.in_(notices), Evidence.current.is_(True)
                )
            )
        )
        job_ids = {e.job_id for e in proofs}
        jobs = {
            j.id: j
            for j in db.scalars(
                select(Job).where(Job.id.in_(job_ids), Job.withdrawn.is_(False))
            )
        }
        for s in sources.values():
            item = {
                k: getattr(s, k)
                for k in ("url", "attempted", "succeeded", "sample", "issue", "counts")
            }
            ns = [
                n
                for n in notices.values()
                if n.source_id == s.id
                and (
                    n.digest
                    or (n.data or {}).get("snapshot_verified")
                    or (n.url == s.sample and s.succeeded)
                )
            ]
            # Attach an actual notice to each source audit entry; prefer one that yielded a job.
            if ns:
                evidence_ids = {e.notice_id for e in proofs}
                ns.sort(
                    key=lambda n: (
                        n.id not in evidence_ids,
                        bool(re.search(r"笔试|面试|考核安排|资格审查", n.title)),
                        bool(n.issue),
                        n.id,
                    )
                )
                item["sample"] = ns[0].url
            result["sources"].append(item)
        for n in notices.values():
            item = {k: getattr(n, k) for k in ("url", "title", "checked", "issue")}
            # Keep public citation metadata. First live recheck reparses documents from source.
            safe_keys = ("url", "type", "name", "error")
            attachments = [
                {k: a[k] for k in safe_keys if k in a}
                for a in (n.data or {}).get("attachments", [])
            ]
            item.update(
                source=sources[n.source_id].url,
                digest=None,
                data={
                    "attachments": attachments,
                    "snapshot": True,
                    "snapshot_verified": bool(
                        n.digest
                        or (n.data or {}).get("snapshot_verified")
                        or (
                            n.url == sources[n.source_id].sample
                            and sources[n.source_id].succeeded
                        )
                    ),
                },
            )
            result["notices"].append(item)
        for j in jobs.values():
            result["jobs"].append(
                {
                    k: getattr(j, k)
                    for k in (
                        "identity",
                        "school",
                        "title",
                        "data",
                        "first_seen",
                        "checked",
                    )
                }
            )
        for e in proofs:
            if e.job_id in jobs:
                result["evidence"].append(
                    {
                        "job": jobs[e.job_id].identity,
                        "notice": notices[e.notice_id].url,
                        "data": e.data,
                    }
                )
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        f"已导出 {len(result['jobs'])} 个岗位，{len(result['notices'])} 条公告访问记录"
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    export(p.parse_args().output)
