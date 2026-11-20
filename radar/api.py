import hashlib
import hmac
import os
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager
from threading import Lock
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .analysis import PROFILE
from .db import Job, Log, Notice, Run, Sessions, Setting, Source, init
from .net import FetchError, public_url
from .readmodel import (
    FLAGS,
    all_jobs,
    brief,
    detail,
    filter_jobs,
    job_view,
    overview,
    run_view,
)
from .worker import enqueue

COOKIE = "radar_session"
TTL = 7 * 86400
failures = deque()
login_lock = Lock()


def password():
    value = os.getenv("RADAR_PASSWORD", "")
    if len(value) < 12:
        raise HTTPException(503, "请先运行初始化脚本，配置至少 12 位的 RADAR_PASSWORD")
    return value


def signature(value):
    return hmac.new(
        password().encode(), ("radar-session-v1|" + value).encode(), hashlib.sha256
    ).hexdigest()


def signed_in(req: Request):
    parts = req.cookies.get(COOKIE, "").split(".")
    if len(parts) != 3 or not parts[0].isdigit() or len(parts[0]) > 12:
        raise HTTPException(401, "请登录个人雷达")
    expires = int(parts[0])
    if not time.time() < expires <= time.time() + TTL + 5 or not hmac.compare_digest(
        signature(".".join(parts[:2])), parts[2]
    ):
        raise HTTPException(401, "登录已过期，请重新登录")


def session():
    with Sessions() as db:
        yield db


@asynccontextmanager
async def lifespan(_):
    init()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def request_guard(request: Request, call_next):
    if (
        request.method not in ("GET", "HEAD", "OPTIONS")
        and request.headers.get("X-Radar-Request") != "1"
    ):
        return JSONResponse({"detail": "请求校验失败"}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/health")
def health(db=Depends(session)):
    db.scalar(select(func.count()).select_from(Source))
    return {"status": "ok"}


class Login(BaseModel):
    password: str = Field(max_length=512)


@app.post("/session")
def login(body: Login, res: Response):
    with login_lock:
        while failures and failures[0] < time.monotonic() - 300:
            failures.popleft()
        if len(failures) >= 12:
            raise HTTPException(429, "尝试过多，请在五分钟后重试")
        if not hmac.compare_digest(body.password.encode(), password().encode()):
            failures.append(time.monotonic())
            raise HTTPException(401, "密码不正确")
        failures.clear()
    value = f"{int(time.time()) + TTL}.{secrets.token_hex(16)}"
    res.set_cookie(
        COOKIE,
        value + "." + signature(value),
        httponly=True,
        samesite="strict",
        max_age=TTL,
        path="/",
        secure=os.getenv("RADAR_SECURE_COOKIE", "false").lower() == "true",
    )
    return {"ok": True}


@app.delete("/session")
def logout(res: Response):
    res.delete_cookie(COOKIE, path="/")
    return {"ok": True}


private = APIRouter(dependencies=[Depends(signed_in)])


@private.get("/overview")
def dashboard(db=Depends(session)):
    return overview(db)


@private.get("/jobs")
def jobs(request: Request, db=Depends(session)):
    params = request.query_params
    try:
        page = max(1, int(params.get("page", 1)))
        all_rows = all_jobs(db)
        rows = filter_jobs(all_rows, params)
    except ValueError:
        raise HTTPException(422, "筛选分数或页码无效")
    size = 16
    page = min(page, max(1, (len(rows) + size - 1) // size))
    facets = {
        k: sorted({j[k] for j in all_rows if j.get(k)})
        for k in ("school", "city", "stage")
    }
    facets["direction"] = sorted({t for j in all_rows for t in j["directions"]})
    return {
        "items": rows[(page - 1) * size : page * size],
        "total": len(rows),
        "page": page,
        "pages": max(1, (len(rows) + size - 1) // size),
        "facets": facets,
    }


@private.get("/jobs/{job_id}")
def get_job(job_id: int, db=Depends(session)):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "未找到岗位")
    return detail(db, j)


class Progress(BaseModel):
    flag: str | None = None
    saved: bool | None = None


@private.patch("/jobs/{job_id}")
def update_job(job_id: int, body: Progress, db=Depends(session)):
    j = db.get(Job, job_id)
    if not j:
        raise HTTPException(404, "未找到岗位")
    if body.flag is not None:
        if body.flag not in FLAGS:
            raise HTTPException(422, "无效的申请进度")
        j.flag = body.flag
    if body.saved is not None:
        j.saved = body.saved
    db.commit()
    return job_view(j)


def source_view(s):
    return {
        "id": s.id,
        "name": s.name,
        "url": s.url,
        **s.meta,
        "enabled": s.enabled,
        "attempted": s.attempted,
        "succeeded": s.succeeded,
        "sample": s.sample,
        "issue": s.issue or (s.meta.get("setup_note") if not s.succeeded else None),
        "counts": s.counts or {},
    }


@private.get("/sources")
def sources(db=Depends(session)):
    return [
        source_view(s)
        for s in db.scalars(
            select(Source).where(Source.removed.is_(False)).order_by(Source.id)
        )
    ]


class AddSource(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    url: str = Field(max_length=1600)
    homepage: str = Field(default="", max_length=1600)
    wechat: str = Field(default="", max_length=80)
    city: str = Field(default="", max_length=40)
    province: str = Field(default="", max_length=40)
    stage: str = Field(default="高等教育", max_length=25)
    school_type: str = Field(default="学校", max_length=30)
    mode: str = "index"


@private.post("/sources", status_code=201)
def create_source(body: AddSource, db=Depends(session)):
    if body.mode not in ("index", "article"):
        raise HTTPException(422, "来源模式无效")
    try:
        url = public_url(body.url.strip())
        home = public_url(body.homepage.strip()) if body.homepage.strip() else ""
    except FetchError as exc:
        raise HTTPException(422, str(exc))
    old = db.scalar(select(Source).where(Source.url == url))
    if old and not old.removed:
        raise HTTPException(409, "该网址已在监控列表")
    meta = body.model_dump(exclude={"name", "url"})
    meta.update(
        homepage=home,
        kind="公众号文章"
        if urlsplit(url).hostname == "mp.weixin.qq.com"
        else "自定义来源",
    )
    if old:
        old.removed, old.enabled, old.name, old.meta = False, True, body.name, meta
        src = old
    else:
        src = Source(name=body.name.strip(), url=url, meta=meta)
        db.add(src)
    db.commit()
    return source_view(src)


class Switch(BaseModel):
    enabled: bool


@private.patch("/sources/{source_id}")
def switch(source_id: int, body: Switch, db=Depends(session)):
    s = db.get(Source, source_id)
    if not s or s.removed:
        raise HTTPException(404, "来源不存在")
    s.enabled = body.enabled
    db.commit()
    return source_view(s)


@private.delete("/sources/{source_id}")
def remove(source_id: int, db=Depends(session)):
    s = db.get(Source, source_id)
    if not s:
        raise HTTPException(404, "来源不存在")
    s.removed, s.enabled = True, False
    db.commit()
    return {"ok": True}


@private.get("/notices")
def notices(source_id: int, db=Depends(session)):
    ns = db.scalars(
        select(Notice)
        .where(Notice.source_id == source_id)
        .order_by(Notice.checked.desc())
        .limit(60)
    )
    return [
        {
            "id": n.id,
            "title": n.title,
            "url": n.url,
            "checked": n.checked,
            "issue": n.issue,
            "files": len((n.data or {}).get("attachments", [])),
        }
        for n in ns
    ]


@private.get("/activity")
def activity(db=Depends(session)):
    latest = db.scalar(select(Run).order_by(Run.id.desc()))
    return {
        "latest": run_view(latest),
        "logs": [
            {"at": l.at, "message": l.message}
            for l in db.scalars(select(Log).order_by(Log.id.desc()).limit(50))
        ],
    }


@private.post("/refresh", status_code=202)
def refresh():
    return {"run_id": enqueue()}


@private.get("/brief")
def daily(db=Depends(session)):
    day = brief(db)
    delivery = db.get(Setting, "email:daily:" + day["date"])
    return {
        **day,
        "email_configured": all(os.getenv("SMTP_" + k) for k in ("HOST", "FROM", "TO")),
        "delivery": delivery.value["state"] if delivery else None,
    }


@private.get("/profile")
def profile():
    return PROFILE


app.include_router(private)
