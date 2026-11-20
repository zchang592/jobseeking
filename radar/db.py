"""One schema for the single-user SQLite install and PostgreSQL deployment."""

import json

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import DATABASE_URL, ROOT, stamp


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    meta = Column(JSON, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    removed = Column(Boolean, default=False, nullable=False)
    attempted = Column(String)
    succeeded = Column(String)
    sample = Column(String)
    issue = Column(Text)
    counts = Column(JSON, default=dict)


class Notice(Base):
    __tablename__ = "notices"
    id = Column(Integer, primary_key=True)
    source_id = Column(ForeignKey("sources.id"), nullable=False, index=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    digest = Column(String)
    checked = Column(String)
    data = Column(JSON, default=dict)
    issue = Column(Text)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    identity = Column(String, unique=True, nullable=False)
    school = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    data = Column(JSON, nullable=False)
    first_seen = Column(String, default=stamp, nullable=False)
    checked = Column(String, nullable=False)
    flag = Column(String, default="未标记", nullable=False)
    saved = Column(Boolean, default=False, nullable=False)
    withdrawn = Column(Boolean, default=False, nullable=False)


class Evidence(Base):
    __tablename__ = "evidence"
    job_id = Column(ForeignKey("jobs.id"), primary_key=True)
    notice_id = Column(ForeignKey("notices.id"), primary_key=True)
    data = Column(JSON, nullable=False)
    current = Column(Boolean, nullable=False, default=True)


class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    slot = Column(String, unique=True)
    active = Column(String, unique=True)
    trigger = Column(String, nullable=False)
    state = Column(String, default="等待中", nullable=False)
    created = Column(String, default=stamp, nullable=False)
    finished = Column(String)
    report = Column(JSON, default=dict)


class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, index=True)
    source_id = Column(Integer)
    at = Column(String, default=stamp, nullable=False)
    message = Column(Text, nullable=False)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)


def connect(url):
    sqlite = url.startswith("sqlite")
    engine = create_engine(
        url, pool_pre_ping=True, connect_args={"timeout": 30} if sqlite else {}
    )
    if sqlite:

        @event.listens_for(engine, "connect")
        def pragmas(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")

    return engine


engine = connect(DATABASE_URL)
Sessions = sessionmaker(engine, expire_on_commit=False)


def init(snapshot=True):
    Base.metadata.create_all(engine)
    with Sessions.begin() as db:
        if db.get(Setting, "initialized"):
            return
        for item in json.loads((ROOT / "data/sources.json").read_text()):
            item = dict(item)
            db.add(
                Source(
                    name=item.pop("school"),
                    url=item.pop("url"),
                    enabled=item.pop("enabled", True),
                    meta=item,
                )
            )
        db.flush()
        path = ROOT / "data/verified.json"
        if snapshot and path.exists():
            restore(db, json.loads(path.read_text()))
        db.add(Setting(key="initialized", value=True))


def restore(db: Session, snapshot):
    sources = {s.url: s for s in db.scalars(select(Source))}
    notices, jobs = {}, {}
    for row in snapshot["sources"]:
        s = sources.get(row["url"])
        if s:
            for k in ("attempted", "succeeded", "sample", "issue", "counts"):
                setattr(s, k, row.get(k))
    for row in snapshot["notices"]:
        n = Notice(
            source_id=sources[row["source"]].id,
            **{k: v for k, v in row.items() if k != "source"},
        )
        db.add(n)
        notices[n.url] = n
    for row in snapshot["jobs"]:
        j = Job(**row)
        db.add(j)
        jobs[j.identity] = j
    db.flush()
    for row in snapshot["evidence"]:
        db.add(
            Evidence(
                job_id=jobs[row["job"]].id,
                notice_id=notices[row["notice"]].id,
                data=row["data"],
                current=row.get("current", True),
            )
        )
