import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from click.testing import CliRunner

from app.cli.errors import EXIT_LOCAL, EXIT_REMOTE
from app.cli.main import cli


class BqStrategyCommandTestCase(unittest.TestCase):
    @patch("app.cli.commands.strategy.JobCache")
    @patch("app.cli.commands.strategy.BackQuantClient")
    def test_run_saves_remote_strategy_runs_job_and_records_cache(self, client_cls, cache_cls):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_path = Path(tmpdir) / "foo.py"
            strategy_path.write_text("def init(context):\n    pass\n", encoding="utf-8")

            client = Mock()
            client.save_strategy.return_value = {"ok": True}
            client.run_strategy.return_value = {"job_id": "job_demo"}
            client_cls.return_value = client

            cache = Mock()
            cache_cls.return_value = cache

            runner = CliRunner()
            result = runner.invoke(
                cli,
                [
                    "strategy",
                    "run",
                    "--file",
                    str(strategy_path),
                    "--start",
                    "2026-01-01",
                    "--end",
                    "2026-01-31",
                ],
            )

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["job_id"], "job_demo")
        self.assertEqual(payload["data"]["file"], str(strategy_path))
        self.assertEqual(payload["data"]["strategy_id"], "foo")
        client.save_strategy.assert_called_once_with("foo", "def init(context):\n    pass\n")
        client.run_strategy.assert_called_once_with(
            strategy_id="foo",
            start_date="2026-01-01",
            end_date="2026-01-31",
            cash=1000000.0,
            benchmark="000300.XSHG",
            frequency="1d",
        )
        self.assertLess(
            client.mock_calls.index(call.save_strategy("foo", "def init(context):\n    pass\n")),
            client.mock_calls.index(
                call.run_strategy(
                    strategy_id="foo",
                    start_date="2026-01-01",
                    end_date="2026-01-31",
                    cash=1000000.0,
                    benchmark="000300.XSHG",
                    frequency="1d",
                )
            ),
        )
        cache.record_run.assert_called_once_with("job_demo", strategy_path.resolve(), "foo")

    @patch("app.cli.commands.strategy.BackQuantClient")
    def test_compile_wraps_remote_payload(self, client_cls):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_path = Path(tmpdir) / "alpha.py"
            strategy_path.write_text("def init(context):\n    pass\n", encoding="utf-8")

            client = Mock()
            client.compile_strategy.return_value = {
                "ok": True,
                "stdout": "syntax ok",
                "stderr": "",
                "diagnostics": [],
            }
            client_cls.return_value = client

            runner = CliRunner()
            result = runner.invoke(cli, ["strategy", "compile", "--file", str(strategy_path)])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["strategy_id"], "alpha")
        self.assertTrue(payload["data"]["compile"]["ok"])

    @patch("app.cli.commands.strategy.BackQuantClient")
    def test_compile_returns_compile_error_when_remote_returns_not_ok(self, client_cls):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_path = Path(tmpdir) / "bad.py"
            strategy_path.write_text("def init(context):\n    pass\n", encoding="utf-8")

            client = Mock()
            client.compile_strategy.return_value = {
                "ok": False,
                "stdout": "",
                "stderr": "syntax error",
                "diagnostics": [{"line": 1, "message": "invalid syntax"}],
            }
            client_cls.return_value = client

            runner = CliRunner()
            result = runner.invoke(cli, ["strategy", "compile", "--file", str(strategy_path)])

        self.assertEqual(result.exit_code, EXIT_REMOTE)
        payload = json.loads(result.output)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "COMPILE_ERROR")
        self.assertEqual(payload["error"]["message"], "syntax error")

    def test_compile_missing_local_file_returns_local_file_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_path = Path(tmpdir) / "missing.py"
            runner = CliRunner()
            result = runner.invoke(cli, ["strategy", "compile", "--file", str(strategy_path)])

        self.assertEqual(result.exit_code, EXIT_LOCAL)
        payload = json.loads(result.output)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "LOCAL_FILE_ERROR")

    @patch("app.cli.commands.strategy.BackQuantClient")
    def test_pull_overwrites_local_file_with_remote_code(self, client_cls):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_path = Path(tmpdir) / "demo.py"
            strategy_path.write_text("print('old')\n", encoding="utf-8")

            client = Mock()
            client.get_strategy.return_value = {"ok": True, "data": {"id": "demo", "code": "print('new')\n"}}
            client_cls.return_value = client

            runner = CliRunner()
            result = runner.invoke(cli, ["strategy", "pull", "--file", str(strategy_path)])

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(strategy_path.read_text(encoding="utf-8"), "print('new')\n")
            payload = json.loads(result.output)
            self.assertEqual(payload["data"]["file"], str(strategy_path))
            self.assertEqual(payload["data"]["strategy_id"], "demo")
