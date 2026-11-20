"""Isolated acceptance checks. All example vacancy rows below stay in a temporary database."""

import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

TEST_DIR = tempfile.TemporaryDirectory()
os.environ["RADAR_DATA"] = TEST_DIR.name
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(TEST_DIR.name) / "tests.sqlite3")
os.environ["RADAR_PASSWORD"] = os.urandom(24).hex()
os.environ["RADAR_SECURE_COOKIE"] = "false"

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select, func

from radar import api, worker
from radar.analysis import analyze, status
from radar.crawl import crawl_source
from radar.db import Base, Evidence, Job, Notice, Run, Sessions, Source, engine
from radar.extract import attachment_rows, notice_dates, prose_rows
from radar.net import FetchError, public_url
from radar.readmodel import filter_jobs, job_view
from radar.settings import TZ

INDEX = "https://school.example/jobs/"
ARTICLE = INDEX + "notice-2026.html"
FILE = INDEX + "positions.xlsx"


def workbook():
    book = Workbook()
    sheet = book.active
    sheet.append(
        ["岗位代码", "部门", "招聘岗位", "专业要求", "学历/学位", "人数", "其他条件"]
    )
    sheet.append(
        ["M01", "音乐系", "教学岗", "配器与和声", "硕士及以上", 2, "须核实工作年限"]
    )
    sheet.append(["M02", "作曲系", "电子音乐作曲教师", "作曲", "已取得博士学位", 1, ""])
    sheet.append(["H01", "附中", "历史教师", "历史", "硕士", 1, ""])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


class School:
    """A deterministic transport for testing updates and worker recovery, without live traffic."""

    def __init__(self):
        self.day = "26"
        self.fail = False
        self.urls = []
        self.index = INDEX
        self.article = ARTICLE
        self.file = FILE

    def get(self, url, hosts, headers=None):
        self.urls.append(url)
        if url == self.index:
            data = f'<a href="{self.article}">2026年第一批专任教师招聘公告</a>'.encode()
        elif url == self.article:
            if self.fail:
                raise FetchError("HTTP 403")
            data = f'<title>2026年第一批专任教师招聘公告</title><div class="v_news_content"><p>报名时间：2026年11月20日08:30至11月{self.day}日17:00。</p><p>招聘部门和学历条件等详见附件，请逐项核对报考条件。</p><a href="{self.file}">专任教师岗位表.xlsx</a><p>报名人员请查看原公告，并且依据本次招聘要求核实自己的材料。</p></div>'.encode()
        else:
            data = workbook()
        return url, {}, data


class Rules(unittest.TestCase):
    def test_phd_and_professional_score_are_independent(self):
        result = analyze(
            {
                "title": "作曲教师",
                "degree": "须已取得博士学位",
                "other": "教学经验丰富者优先",
            }
        )
        self.assertGreater(result["score"], 80)
        self.assertEqual(result["eligibility"], "明确不符合")
        self.assertIn("博士在读", result["checks"][0])

    def test_explicit_exception_not_blanket_acceptance(self):
        self.assertEqual(
            analyze(
                {
                    "title": "作曲教师",
                    "degree": "博士",
                    "other": "获指定奖项可放宽至硕士",
                }
            )["eligibility"],
            "可能符合，需要核实",
        )

    def test_duties_synonyms_and_ai(self):
        self.assertIn(
            "音乐理论",
            analyze({"title": "专任教师", "duties": "教授复调和曲式分析"})["matched"],
        )
        ai = analyze(
            {
                "title": "AI作曲算法教师",
                "degree": "硕士",
                "duties": "要求机器学习与Python编程",
            }
        )
        self.assertLess(ai["score"], 75)
        self.assertTrue(any("编程" in x for x in ai["checks"]))

    def test_unlabelled_phd_in_prose(self):
        text = "岗位名称：作曲教师\n应聘人员须已取得博士学位，具体资格见公告。"
        self.assertIn("博士学位", prose_rows("", text)[0]["degree"])

    def test_unknown_certificates_and_primary(self):
        j = analyze(
            {
                "title": "音乐教师",
                "degree": "硕士",
                "certificate": "中学教师资格证",
                "stage": "小学",
            }
        )
        self.assertFalse(j["priority"])
        self.assertEqual(j["eligibility"], "可能符合，需要核实")
        self.assertEqual(analyze({"title": "钢琴教师"})["eligibility"], "信息不足")

    def test_windows_and_timezones(self):
        text = "考试时间2026年12月27日。网上报名时间为2026年11月20日09：00至11月27日18：00。缴费至11月30日。"
        d = notice_dates(text)
        self.assertEqual(
            d, {"starts": "2026-11-20T09:00", "deadline": "2026-11-27T18:00"}
        )
        for when, expected in [
            ("2026-11-20T08:55", "未开始"),
            ("2026-11-27T17:59", "招聘中"),
            ("2026-11-27T18:01", "已截止"),
        ]:
            self.assertEqual(
                status(d, datetime.fromisoformat(when).replace(tzinfo=TZ)), expected
            )
        self.assertEqual(
            notice_dates("报名时间为2025年3月20日至4月15日24:00截止。")["deadline"],
            "2025-04-15",
        )
        self.assertEqual(
            status({"starts": "2026-11-02"}, datetime(2026, 11, 20, tzinfo=TZ)),
            "待核实",
        )
        self.assertNotIn(
            "deadline", notice_dates("报名时间另行通知。考试于2026年12月2日开始。")
        )

    def test_unannounced_end_never_uses_start_date(self):
        text = "报名时间为2026年11月1日起，截止时间视岗位情况另行通知。"
        self.assertNotIn("deadline", notice_dates(text))

    def test_degree_specific_deadlines(self):
        text = "报名时间：招聘博士研究生、高级职称岗位，公告发布之日至2026年12月31日，招满即停。招聘硕士研究生岗位，报名时间：2026年5月13日至5月21日。"
        data = notice_dates(text)
        self.assertNotIn("deadline", data)
        self.assertEqual(
            [(w["for"], w["deadline"]) for w in data["windows"]],
            [(["博士"], "2026-12-31"), (["硕士"], "2026-05-21")],
        )

    def test_private_urls_rejected(self):
        for u in (
            "file:///etc/passwd",
            "http://127.0.0.1/private",
            "http://user:secret@example.org/",
        ):
            with self.assertRaises(FetchError):
                public_url(u)
        with self.assertRaises(FetchError):
            public_url("https://unconfigured.example.com/", {"school.example"})


class Workflow(unittest.TestCase):
    def setUp(self):
        if Path(engine.url.database).resolve().parent != Path(TEST_DIR.name).resolve():
            raise RuntimeError("Tests require the isolated temporary database")
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        self.web = School()
        with Sessions.begin() as db:
            s = Source(
                name="测试学校",
                url=INDEX,
                meta={"kind": "学校官网", "city": "广州", "stage": "高等教育"},
            )
            db.add(s)
            db.flush()
            self.source = s.id

    def ingest(self, force=False):
        return crawl_source(self.source, None, self.web, force=force)

    def test_initial_snapshot_is_real_private_and_repeatable(self):
        from radar.db import init
        from radar.readmodel import detail

        init()
        init()
        with Sessions() as db:
            verified = db.scalar(
                select(func.count())
                .select_from(Source)
                .where(Source.sample.is_not(None), Source.succeeded.is_not(None))
            )
            self.assertGreaterEqual(verified, 10)
            job = next(
                j
                for j in db.scalars(select(Job).where(Job.school == "浙江音乐学院"))
                if j.data.get("code") == "A17-26-03"
            )
            result = detail(db, job)
            self.assertEqual(result["eligibility"], "明确不符合")
            self.assertEqual(result["status"], "待核实")
            self.assertIsNone(result.get("deadline"))
            self.assertIn("/attachment/", result["evidence"][0]["file"])
            self.assertFalse(any(j.saved for j in db.scalars(select(Job))))

    def test_excel_to_jobs_and_original_links(self):
        rows = attachment_rows("xlsx", workbook())
        self.assertEqual([r["code"] for r in rows], ["M01", "M02"])
        self.assertEqual(self.ingest()["new"], 2)
        with Sessions() as db:
            j = db.scalar(select(Job).where(Job.title == "教学岗"))
            from radar.readmodel import detail

            item = detail(db, j)
            self.assertEqual(item["evidence"][0]["url"], ARTICLE)
            self.assertEqual(item["evidence"][0]["file"], FILE)
            self.assertIn("第 2 行", item["evidence"][0]["location"])

    def test_incremental_extension_and_preserved_application(self):
        self.ingest()
        self.web.urls.clear()
        self.assertEqual(self.ingest()["skipped"], 1)
        self.assertEqual(self.web.urls, [INDEX])
        with Sessions.begin() as db:
            j = db.scalar(select(Job))
            j.saved = True
            j.flag = "已申请"
        self.web.day = "29"
        self.assertEqual(self.ingest(True)["new"], 0)
        with Sessions() as db:
            jobs = list(db.scalars(select(Job)))
            self.assertEqual(len(jobs), 2)
            self.assertTrue(all(j.data["deadline"] == "2026-11-29T17:00" for j in jobs))
            self.assertTrue(jobs[0].saved)
            self.assertEqual(jobs[0].flag, "已申请")

    def test_failed_read_is_visible_and_recovers(self):
        self.ingest()
        self.web.fail = True
        self.assertEqual(self.ingest(True)["errors"], 1)
        with Sessions() as db:
            self.assertIn("403", db.scalar(select(Notice)).issue)
            self.assertTrue(db.scalar(select(Job)).data["issue"])
        self.web.fail = False
        self.ingest(True)
        with Sessions() as db:
            self.assertFalse(db.scalar(select(Notice)).issue)
            self.assertFalse(db.scalar(select(Job)).data.get("issue"))

    def test_corroborated_cross_source_code(self):
        self.ingest()
        second = School()
        second.index = "https://public.example/jobs/"
        second.article = second.index + "n.html"
        with Sessions.begin() as db:
            s = Source(name="测试学校", url=second.index, meta={"kind": "自定义来源"})
            db.add(s)
            db.flush()
            sid = s.id
        self.assertEqual(crawl_source(sid, None, second)["new"], 0)
        with Sessions() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(Evidence)), 4)

    def test_dated_repost_without_position_code_keeps_one_job(self):
        from radar.crawl import apply_rows

        row = {
            "title": "作曲教师",
            "department": "作曲系",
            "major": "作曲",
            "location": "正文表 1",
        }
        page = {
            "title": "测试学校年度专任教师招聘公告",
            "common": {"published": "2026-11-03"},
        }
        with Sessions.begin() as db:
            src = db.get(Source, self.source)
            counts = []
            for u in (ARTICLE, INDEX + "copy", INDEX + "next-round"):
                n = Notice(
                    source_id=src.id,
                    url=u,
                    title=page["title"],
                    checked="2026-11-20T12:00:00+08:00",
                )
                db.add(n)
                db.flush()
                if u.endswith("next-round"):
                    page["common"]["published"] = "2026-11-19"
                counts.append(apply_rows(db, src, n, page, [row], []))
            self.assertEqual(counts, [1, 0, 1])
            self.assertEqual(
                db.scalar(
                    select(func.count()).select_from(Evidence).where(Evidence.current)
                ),
                3,
            )

    def test_queue_schedule_and_worker_execution(self):
        before = datetime(2026, 11, 20, 8, 29, tzinfo=TZ)
        self.assertIsNone(worker.schedule(before))
        task = worker.schedule(before + timedelta(minutes=1))
        self.assertEqual(worker.enqueue(), task)
        with (
            patch("radar.worker.Web", return_value=self.web, create=True),
            patch.object(self.web, "close", create=True),
            patch("radar.worker.digest_mail", return_value="未配置邮件"),
        ):
            self.assertEqual(worker.execute(task)["new"], 2)
        self.assertEqual(worker.schedule(before + timedelta(hours=4)), task)
        with Sessions() as db:
            self.assertEqual(db.get(Run, task).state, "已完成")
        self.assertNotEqual(worker.enqueue(), task)

    def test_email_deliveries_and_deadline_reminders_are_idempotent(self):
        from radar.mail import digest_mail
        from radar.settings import now
        from radar.db import Setting

        self.ingest()
        with Sessions.begin() as db:
            job = db.scalar(select(Job).where(Job.title == "教学岗"))
            end = (now().date() + timedelta(days=7)).isoformat()
            job.data = {**job.data, "starts": now().date().isoformat(), "deadline": end}
        env = {
            "SMTP_HOST": "smtp.example.invalid",
            "SMTP_FROM": "from@example.invalid",
            "SMTP_TO": "to@example.invalid",
        }
        with patch.dict(os.environ, env), patch("radar.mail.smtplib.SMTP_SSL") as smtp:
            self.assertEqual(digest_mail(), "简报已发送")
            msg = smtp.return_value.__enter__.return_value.send_message.call_args.args[
                0
            ]
            text = msg.get_content()
            self.assertIn("截止提醒", text)
            self.assertIn(ARTICLE, text)
            self.assertNotIn("电子音乐作曲教师", text)
            self.assertEqual(digest_mail(), "本日简报已处理")
            self.assertEqual(smtp.call_count, 1)
        with Sessions() as db:
            self.assertTrue(db.get(Setting, "email:" + str(job.id) + ":" + end + ":7"))

    def test_auth_filters_and_progress(self):
        self.ingest()
        with patch("radar.api.init"), TestClient(api.app) as client:
            self.assertEqual(client.get("/profile").status_code, 401)
            self.assertEqual(client.get("/jobs").status_code, 401)
            self.assertEqual(client.post("/refresh").status_code, 403)
            h = {"X-Radar-Request": "1"}
            self.assertEqual(
                client.post(
                    "/session", headers=h, json={"password": "wrong"}
                ).status_code,
                401,
            )
            self.assertEqual(
                client.post(
                    "/session",
                    headers=h,
                    json={"password": os.environ["RADAR_PASSWORD"]},
                ).status_code,
                200,
            )
            result = client.get("/jobs", params={"q": "配器", "min_score": "75"}).json()
            self.assertEqual(result["total"], 1)
            item = result["items"][0]
            client.patch(
                "/jobs/" + str(item["id"]),
                headers=h,
                json={"saved": True, "flag": "准备申请"},
            ).raise_for_status()
            self.assertEqual(client.get("/jobs?view=saved").json()["total"], 1)
            self.assertEqual(client.post("/refresh", headers=h).status_code, 202)
            client.delete("/session", headers=h)
            self.assertEqual(client.get("/jobs").status_code, 401)


if __name__ == "__main__":
    unittest.main()
