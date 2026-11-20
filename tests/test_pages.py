import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.build_pages import ROOT, TZ, build, status_for, web_url


class PublicPagesTests(unittest.TestCase):
    def test_real_pages_preserve_official_evidence_and_exclude_private_fields(self):
        snapshot = json.loads((ROOT / "data/verified.json").read_text(encoding="utf-8"))
        job = next(j for j in snapshot["jobs"] if j["data"].get("code") == "A17-26-03")
        job["data"]["private_profile"] = "private-profile-test-marker"
        job["data"]["application_state"] = "private-state-test-marker"
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "snapshot.json"
            state.write_text(json.dumps(snapshot), encoding="utf-8")
            site = Path(temp) / "site"
            self.assertGreaterEqual(build(state, site), 35)
            self.assertTrue((site / ".nojekyll").is_file())
            self.assertTrue((site / "sources/index.html").is_file())
            self.assertEqual(
                {path.name for path in site.iterdir()},
                {
                    ".nojekyll",
                    "index.html",
                    "sources",
                    "jobs",
                    "style.css",
                    "radar.js",
                    "signal-field.webp",
                },
            )
            detail = (site / "jobs" / job["identity"] / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertIn("电子音乐作曲专任教师", detail)
            self.assertIn("研究生/博士", detail)
            self.assertIn("截止时间未知", detail)
            self.assertIn("PDF 第 1 页", detail)
            self.assertIn("https://www.zjcm.edu.cn", detail)
            self.assertIn("../../style.css", detail)
            for page in site.rglob("*.html"):
                body = page.read_text(encoding="utf-8")
                self.assertNotIn("private-profile-test-marker", body)
                self.assertNotIn("private-state-test-marker", body)

    def test_date_only_deadline_expires_at_beijing_midnight(self):
        job = {"deadline": "2026-11-20"}
        self.assertEqual(
            status_for(job, datetime(2026, 11, 20, 23, 59, tzinfo=TZ)), "招聘中"
        )
        self.assertEqual(
            status_for(job, datetime(2026, 11, 21, 0, 0, tzinfo=TZ)), "已截止"
        )
        self.assertEqual(status_for({}, datetime(2026, 11, 20, tzinfo=TZ)), "待核实")

    def test_only_web_links_are_published(self):
        self.assertEqual(
            web_url("https://recruiting.example.edu.cn/jobs"),
            "https://recruiting.example.edu.cn/jobs",
        )
        for value in ("mailto:recruiter@example.com", "/local.pdf", None):
            self.assertEqual(web_url(value), "")


if __name__ == "__main__":
    unittest.main()
