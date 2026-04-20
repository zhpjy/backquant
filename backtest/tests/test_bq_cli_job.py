import json
import unittest
from unittest.mock import Mock, patch

from click.testing import CliRunner

from app.cli.errors import EXIT_LOCAL
from app.cli.main import cli


class BqJobCommandTestCase(unittest.TestCase):
    @patch("app.cli.commands.job.JobCache")
    @patch("app.cli.commands.job.BackQuantClient")
    def test_job_show_returns_remote_payload_and_cached_file(self, client_cls, cache_cls):
        client = Mock()
        client.get_job.return_value = {"job_id": "job_demo", "status": "FINISHED"}
        client_cls.return_value = client

        cache = Mock()
        cache.lookup.return_value = {"file": "/tmp/foo.py", "strategy_id": "foo"}
        cache_cls.return_value = cache

        runner = CliRunner()
        result = runner.invoke(cli, ["job", "show", "--job-id", "job_demo"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["file"], "/tmp/foo.py")
        self.assertEqual(payload["data"]["strategy_id"], "foo")
        self.assertEqual(payload["data"]["remote"]["status"], "FINISHED")

    @patch("app.cli.commands.job.JobCache")
    @patch("app.cli.commands.job.BackQuantClient")
    def test_job_result_returns_null_file_when_cache_miss(self, client_cls, cache_cls):
        client = Mock()
        client.get_job_result.return_value = {"summary": {"total_returns": 0.1}}
        client_cls.return_value = client

        cache = Mock()
        cache.lookup.return_value = None
        cache_cls.return_value = cache

        runner = CliRunner()
        result = runner.invoke(cli, ["job", "result", "--job-id", "job_demo"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertIsNone(payload["data"]["file"])
        self.assertIsNone(payload["data"]["strategy_id"])
        self.assertEqual(payload["data"]["remote"]["summary"]["total_returns"], 0.1)

    @patch("app.cli.commands.job.JobCache")
    @patch("app.cli.commands.job.BackQuantClient")
    def test_job_log_passthrough_remote_payload_and_cache_hit_values(self, client_cls, cache_cls):
        client = Mock()
        client.get_job_log.return_value = {"lines": ["a", "b"], "next_offset": 2}
        client_cls.return_value = client

        cache = Mock()
        cache.lookup.return_value = {"file": "/tmp/bar.py", "strategy_id": "bar"}
        cache_cls.return_value = cache

        runner = CliRunner()
        result = runner.invoke(cli, ["job", "log", "--job-id", "job_demo"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["job_id"], "job_demo")
        self.assertEqual(payload["data"]["file"], "/tmp/bar.py")
        self.assertEqual(payload["data"]["strategy_id"], "bar")
        self.assertEqual(payload["data"]["remote"]["lines"], ["a", "b"])

    @patch("app.cli.commands.job.JobCache")
    @patch("app.cli.commands.job.BackQuantClient")
    def test_job_show_returns_local_file_error_when_cache_lookup_permission_denied(self, client_cls, cache_cls):
        client = Mock()
        client_cls.return_value = client

        cache = Mock()
        cache.lookup.side_effect = PermissionError("permission denied")
        cache_cls.return_value = cache

        runner = CliRunner()
        result = runner.invoke(cli, ["job", "show", "--job-id", "job_demo"])

        self.assertEqual(result.exit_code, EXIT_LOCAL)
        payload = json.loads(result.output)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "LOCAL_FILE_ERROR")
