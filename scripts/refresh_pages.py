"""Refresh a public snapshot in an isolated database using the checked-in source catalogue."""

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent


def restore_public_snapshot(state):
    from radar.db import Sessions, Source, restore, select

    data = json.loads(state.read_text(encoding="utf-8"))
    with Sessions.begin() as db:
        allowed = set(db.scalars(select(Source.url)))
        sources = [s for s in data["sources"] if s["url"] in allowed]
        notices = [n for n in data["notices"] if n["source"] in allowed]
        urls = {n["url"] for n in notices}
        evidence = [e for e in data["evidence"] if e["notice"] in urls]
        identities = {e["job"] for e in evidence}
        jobs = [j for j in data["jobs"] if j["identity"] in identities]
        restore(
            db,
            {
                "sources": sources,
                "notices": notices,
                "evidence": evidence,
                "jobs": jobs,
            },
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()

    with TemporaryDirectory(prefix="radar-pages-") as temp:
        # The public collector always starts from an isolated store and ignores .env.
        os.environ.update(
            RADAR_DATA=temp,
            DATABASE_URL=f"sqlite:///{temp}/pages.sqlite3",
            RADAR_PROFILE_FILE=str(ROOT / "data/profile.json"),
            PYTHON_DOTENV_DISABLED="1",
        )
        from radar.db import init
        from radar.worker import enqueue, execute
        from scripts.export_verified import export

        init(snapshot=False)
        seed = args.snapshot if args.snapshot.is_file() else ROOT / "data/verified.json"
        restore_public_snapshot(seed)
        result = execute(enqueue("GitHub Pages"))
        print({key: result[key] for key in ("sources", "read", "new", "errors")})
        if "error" in result:
            raise SystemExit("采集任务中断，保留上一版快照。")

        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        staged = args.snapshot.with_suffix(".next.json")
        export(staged)
        staged.replace(args.snapshot)


if __name__ == "__main__":
    main()
