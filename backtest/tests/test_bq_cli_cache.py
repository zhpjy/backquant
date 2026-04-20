import json
import os
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from app.cli.config import CliSettings
from app.cli.errors import CliError, EXIT_ARGUMENT, EXIT_LOCAL
from app.cli.main import main
from app.cli.output import json_error, json_ok


class BqCliFoundationTestCase(unittest.TestCase):
    def test_settings_default_jobs_cache_path_under_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            old_cwd = Path.cwd()
            os.chdir(cwd)
            try:
                with patch.dict(os.environ, {}, clear=True):
                    settings = CliSettings.from_env()
            finally:
                os.chdir(old_cwd)

        self.assertEqual(settings.jobs_cache_path, cwd / ".bq" / "jobs.json")
        self.assertEqual(settings.timeout_seconds, 10)

    def test_settings_from_env_uses_process_environment_by_default(self):
        with patch.dict(
            os.environ,
            {
                "BQ_BASE_URL": "http://127.0.0.1:8088",
                "BQ_TOKEN": "token-from-env",
                "BQ_TIMEOUT_SECONDS": "21",
            },
            clear=True,
        ):
            settings = CliSettings.from_env()

        self.assertEqual(settings.base_url, "http://127.0.0.1:8088")
        self.assertEqual(settings.token, "token-from-env")
        self.assertEqual(settings.timeout_seconds, 21)

    def test_settings_accepts_token_without_username_password(self):
        settings = CliSettings.from_env(
            {
                "BQ_BASE_URL": "  http://127.0.0.1:8088/  ",
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

    def test_main_returns_click_exception_as_argument_error_json(self):
        with patch("sys.stdout", new_callable=StringIO) as stdout:
            exit_code = main(["unknown-command"])

        self.assertEqual(exit_code, EXIT_ARGUMENT)
        self.assertEqual(
            json.loads(stdout.getvalue().strip()),
            {
                "ok": False,
                "error": {
                    "code": "CLI_ARGUMENT_ERROR",
                    "message": "No such command 'unknown-command'.",
                },
            },
        )

    def test_main_returns_clierror_payload_and_exit_code(self):
        error = CliError(
            code="LOCAL_FILE_ERROR",
            message="cannot read cache",
            exit_code=EXIT_LOCAL,
            details={"path": "/tmp/jobs.json"},
        )
        with patch("app.cli.main.cli.main", side_effect=error):
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                exit_code = main([])

        self.assertEqual(exit_code, EXIT_LOCAL)
        self.assertEqual(
            json.loads(stdout.getvalue().strip()),
            {
                "ok": False,
                "error": {
                    "code": "LOCAL_FILE_ERROR",
                    "message": "cannot read cache",
                    "details": {"path": "/tmp/jobs.json"},
                },
            },
        )
