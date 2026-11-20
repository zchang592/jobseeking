import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
TZ = ZoneInfo("Asia/Shanghai")
DATA = Path(os.environ.get("RADAR_DATA", ROOT / "runtime"))
DATA.mkdir(parents=True, exist_ok=True)
DATABASE_URL = (
    os.environ.get("DATABASE_URL") or f"sqlite:///{DATA.resolve()}/radar.sqlite3"
)


def now():
    return datetime.now(TZ)


def stamp():
    return now().isoformat(timespec="seconds")
