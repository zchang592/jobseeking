"""Optional SMTP digest. Reserve the daily delivery before network I/O."""

import os
import smtplib
import ssl
from email.message import EmailMessage
from sqlalchemy import select
from .db import Sessions, Setting, Evidence, Notice
from .readmodel import brief, recommended, until
from .settings import stamp


def digest_mail():
    cfg = {
        k: os.getenv("SMTP_" + k, "")
        for k in ("HOST", "PORT", "USER", "PASSWORD", "FROM", "TO", "MODE")
    }
    if not all(cfg[k] for k in ("HOST", "FROM", "TO")):
        return "未配置邮件"
    with Sessions.begin() as db:
        digest = brief(db)
        day = digest["date"]
        daily = "email:daily:" + day
        if db.get(Setting, daily):
            return "本日简报已处理"
        events, lines = (
            [],
            [
                f"音乐教职雷达 · {day}",
                f"今日发现 {len(digest['new'])} 岗，当前可优先申请 {len(digest['high'])} 岗。",
            ],
        )
        sections = [
            ("新增推荐", [j for j in digest["high"]], False),
            (
                "截止提醒",
                [j for j in digest["soon"] if recommended(j) and until(j) in (1, 3, 7)],
                True,
            ),
        ]
        for label, items, deadline in sections:
            entries = []
            for job in items:
                key = (
                    "email:"
                    + str(job["id"])
                    + (
                        ":" + job["deadline"] + ":" + str(until(job))
                        if deadline
                        else ":new"
                    )
                )
                if db.get(Setting, key):
                    continue
                url = db.scalar(
                    select(Notice.url)
                    .join(Evidence)
                    .where(Evidence.job_id == job["id"], Evidence.current.is_(True))
                )
                entries.append(
                    f"• {job['school']} · {job['title']}（{job['score']} 分，{job['eligibility']}）\n  截止：{job.get('deadline') or '未知'}\n  {url or ''}"
                )
                events.append(key)
            if entries:
                lines.extend(["", label, *entries])
        db.add(Setting(key=daily, value={"at": stamp(), "state": "发送中"}))
        for key in events:
            db.add(Setting(key=key, value={"day": day, "state": "投递已预留"}))
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = (
        f"音乐教职雷达｜{day} 招聘简报",
        cfg["FROM"],
        cfg["TO"],
    )
    msg.set_content("\n".join(lines))
    try:
        tls = ssl.create_default_context()
        implicit = cfg["MODE"].lower() != "starttls"
        args = (cfg["HOST"], int(cfg["PORT"] or (465 if implicit else 587)))
        conn = (
            smtplib.SMTP_SSL(*args, context=tls, timeout=18)
            if implicit
            else smtplib.SMTP(*args, timeout=18)
        )
        with conn as smtp:
            if not implicit:
                smtp.starttls(context=tls)
            if cfg["USER"]:
                smtp.login(cfg["USER"], cfg["PASSWORD"])
            smtp.send_message(msg)
    except Exception as exc:
        message = "邮件未确认投递：" + type(exc).__name__
        with Sessions.begin() as db:
            db.get(Setting, daily).value = {"at": stamp(), "state": message}
        return message
    with Sessions.begin() as db:
        db.get(Setting, daily).value = {"at": stamp(), "state": "已发送"}
        for key in events:
            db.get(Setting, key).value = {"day": day, "state": "已发送"}
    return "简报已发送"
