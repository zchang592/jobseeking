"""Persistent queue, one worker per shared data volume. All scheduling uses Beijing time."""

import fcntl
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import time as clock_time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .crawl import crawl_source
from .db import Log, Run, Sessions, Source, init
from .mail import digest_mail
from .net import Web
from .settings import DATA, now, stamp


def enqueue(trigger="手动更新", slot=None):
    with Sessions() as db:
        if slot:
            prior = db.scalar(select(Run).where(Run.slot == slot))
            if prior:
                return prior.id
        active = db.scalar(select(Run).where(Run.active == "collection"))
        if active:
            return active.id
        run = Run(trigger=trigger, slot=slot, active="collection")
        db.add(run)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            active = db.scalar(select(Run).where(Run.active == "collection"))
            if active:
                return active.id
            return db.scalar(select(Run.id).where(Run.slot == slot))
        return run.id


def schedule(at):
    if at.timetz().replace(tzinfo=None) >= clock_time(8, 30):
        return enqueue("每日定时", at.date().isoformat())


def execute(run_id):
    with Sessions.begin() as db:
        run = db.get(Run, run_id)
        run.state = "采集中"
        scheduled = bool(run.slot)
        sources = list(
            db.scalars(
                select(Source.id).where(
                    Source.enabled.is_(True), Source.removed.is_(False)
                )
            )
        )
    summary = {"sources": len(sources), "read": 0, "new": 0, "errors": 0}
    state = "已完成"
    web = Web()
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            for result in pool.map(lambda i: crawl_source(i, run_id, web), sources):
                for k in ("read", "new", "errors"):
                    summary[k] += result[k]
        if summary["errors"]:
            state = "部分失败"
        summary["mail"] = digest_mail() if scheduled else "手动更新完成"
    except Exception as exc:
        state = "失败"
        summary["error"] = f"{type(exc).__name__}：{str(exc)[:180]}"
    finally:
        web.close()
        with Sessions.begin() as db:
            run = db.get(Run, run_id)
            run.state, run.finished, run.report, run.active = (
                state,
                stamp(),
                summary,
                None,
            )
            db.add(
                Log(
                    run_id=run_id,
                    message=f"{state}：读取 {summary['read']} 篇，新增 {summary['new']} 岗",
                )
            )
    return summary


def main():
    with (DATA / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        init()
        with Sessions.begin() as db:
            for run in db.scalars(select(Run).where(Run.state == "采集中")):
                run.state = "等待中"
        while True:
            schedule(now())
            with Sessions() as db:
                task = db.scalar(
                    select(Run.id).where(Run.state == "等待中").order_by(Run.id)
                )
            if task:
                execute(task)
            else:
                time.sleep(5)


if __name__ == "__main__":
    main()
