import json
import os
import tempfile
import unittest
from pathlib import Path

from app.cli.config import CliSettings
from app.cli.output import json_error, json_ok


class BqCliFoundationTestCase(unittest.TestCase):
    def test_settings_default_jobs_cache_path_under_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            old_cwd = Path.cwd()
            os.chdir(cwd)
            try:
                settings = CliSettings.from_env({})
            finally:
                os.chdir(old_cwd)

        self.assertEqual(settings.jobs_cache_path, cwd / ".bq" / "jobs.json")
        self.assertEqual(settings.timeout_seconds, 10)

    def test_settings_accepts_token_without_username_password(self):
        settings = CliSettings.from_env(
            {
                "BQ_BASE_URL": "http://127.0.0.1:8088",
                "BQ_TOKEN": "token-123",
            }
        )

        self.assertEqual(settings.base_url, "http://127.0.0.1:8088")
        self.assertEqual(settings.token, "token-123")
        self.assertEqual(settings.username, "")
        self.assertEqual(settings.password, "")

    def test_json_helpers_render_expected_shape(self):
        success_text = json_ok({"job_id": "job_demo"})
        error_text = json_error("LOCAL_FILE_ERROR", "cannot read file")

        self.assertEqual(json.loads(success_text), {"ok": True, "data": {"job_id": "job_demo"}})
        self.assertEqual(
            json.loads(error_text),
            {"ok": False, "error": {"code": "LOCAL_FILE_ERROR", "message": "cannot read file"}},
        )
