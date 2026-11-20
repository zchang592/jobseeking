"""Small operational commands for a running personal instance."""

import argparse
import json
import time
from sqlalchemy import select

from .db import Run, Sessions, Source, init
from .readmodel import overview, run_view
from .settings import ROOT
from .worker import enqueue


def main():
    parser = argparse.ArgumentParser(prog="python -m radar.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="查看当前数据库、来源和最近任务的概要")
    refresh = commands.add_parser("refresh", help="提交到与网页共用的后台队列")
    refresh.add_argument("--wait", action="store_true", help="等待已提交的任务结束")
    commands.add_parser("sync-sources", help="将来源目录中新添加的栏目加入已有数据库")
    args = parser.parse_args()
    init()
    if args.command == "status":
        with Sessions() as db:
            info = overview(db)
            data = {
                k: info[k]
                for k in (
                    "date",
                    "total",
                    "new",
                    "open",
                    "high",
                    "sources",
                    "verified",
                    "last_run",
                )
            }
            print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.command == "refresh":
        run_id = enqueue()
        print(f"队列任务 #{run_id}", flush=True)
        if args.wait:
            while True:
                with Sessions() as db:
                    run = db.get(Run, run_id)
                    if run.finished:
                        print(json.dumps(run_view(run), ensure_ascii=False, indent=2))
                        return 1 if run.state == "失败" else 0
                time.sleep(3)
    else:
        added = 0
        with Sessions.begin() as db:
            existing = set(db.scalars(select(Source.url)))
            for cfg in json.loads((ROOT / "data/sources.json").read_text()):
                row = dict(cfg)
                if row["url"] in existing:
                    continue
                db.add(
                    Source(
                        name=row.pop("school"),
                        url=row.pop("url"),
                        enabled=row.pop("enabled", True),
                        meta=row,
                    )
                )
                added += 1
        print(f"添加 {added} 个新来源")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
