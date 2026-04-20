import unittest
from unittest.mock import Mock, patch

from app.cli.client import BackQuantClient
from app.cli.config import CliSettings
from app.cli.errors import CliError, EXIT_REMOTE


class BackQuantClientTestCase(unittest.TestCase):
    def _settings(self) -> CliSettings:
        return CliSettings(
            base_url="http://127.0.0.1:8088",
            username="admin",
            password="pass123456",
            token="",
            timeout_seconds=10,
            jobs_cache_path=None,
        )

    @patch("app.cli.client.requests.Session")
    def test_compile_strategy_logs_in_and_posts_temporary_code(self, session_cls):
        session = Mock()
        login_response = Mock()
        login_response.status_code = 200
        login_response.json.return_value = {"token": "jwt-token", "userid": 1, "is_admin": True}

        compile_response = Mock()
        compile_response.status_code = 200
        compile_response.json.return_value = {"ok": True, "stdout": "syntax ok", "stderr": "", "diagnostics": []}

        session.post.side_effect = [login_response, compile_response]
        session_cls.return_value = session

        client = BackQuantClient(self._settings())
        payload = client.compile_strategy("demo", "def init(context):\n    pass\n")

        self.assertTrue(payload["ok"])
        self.assertEqual(session.post.call_args_list[0].args[0], "http://127.0.0.1:8088/api/login")
        self.assertEqual(
            session.post.call_args_list[0].kwargs["json"],
            {"mobile": "admin", "password": "pass123456"},
        )
        self.assertEqual(
            session.post.call_args_list[1].args[0],
            "http://127.0.0.1:8088/api/backtest/strategies/demo/compile",
        )
        self.assertEqual(
            session.post.call_args_list[1].kwargs["json"],
            {"code": "def init(context):\n    pass\n"},
        )

    @patch("app.cli.client.requests.Session")
    def test_run_strategy_posts_run_payload_with_bearerless_authorization(self, session_cls):
        session = Mock()
        login_response = Mock()
        login_response.status_code = 200
        login_response.json.return_value = {"token": "jwt-token", "userid": 1, "is_admin": True}

        run_response = Mock()
        run_response.status_code = 200
        run_response.json.return_value = {"job_id": "job_demo"}

        session.post.side_effect = [login_response, run_response]
        session_cls.return_value = session

        client = BackQuantClient(self._settings())
        payload = client.run_strategy(
            strategy_id="demo",
            start_date="2026-01-01",
            end_date="2026-01-31",
            cash=100000,
            benchmark="000300.XSHG",
            frequency="1d",
        )

        self.assertEqual(payload, {"job_id": "job_demo"})
        self.assertEqual(session.headers["Authorization"], "jwt-token")
        self.assertEqual(session.post.call_args_list[0].args[0], "http://127.0.0.1:8088/api/login")
        self.assertEqual(
            session.post.call_args_list[0].kwargs["json"],
            {"mobile": "admin", "password": "pass123456"},
        )
        self.assertEqual(session.post.call_args_list[1].args[0], "http://127.0.0.1:8088/api/backtest/run")
        self.assertEqual(
            session.post.call_args_list[1].kwargs["json"],
            {
                "strategy_id": "demo",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
                "cash": 100000,
                "benchmark": "000300.XSHG",
                "frequency": "1d",
            },
        )

    @patch("app.cli.client.requests.Session")
    def test_get_strategy_raises_cli_error_on_remote_http_error(self, session_cls):
        session = Mock()
        session.headers = {}
        session_cls.return_value = session
        error_response = Mock()
        error_response.status_code = 404
        error_response.json.return_value = {"error": {"code": "NOT_FOUND", "message": "strategy not found"}}
        session.get.return_value = error_response

        settings = CliSettings(
            base_url="http://127.0.0.1:8088",
            username="",
            password="",
            token="jwt-token",
            timeout_seconds=10,
            jobs_cache_path=None,
        )
        client = BackQuantClient(settings)

        with self.assertRaises(CliError) as ctx:
            client.get_strategy("missing")

        self.assertEqual(ctx.exception.code, "NOT_FOUND")
        self.assertEqual(ctx.exception.exit_code, EXIT_REMOTE)
        self.assertEqual(ctx.exception.details, {"error": {"code": "NOT_FOUND", "message": "strategy not found"}})

    @patch("app.cli.client.requests.Session")
    def test_decode_response_returns_non_dict_json_as_is_for_success(self, session_cls):
        session = Mock()
        session_cls.return_value = session

        settings = CliSettings(
            base_url="http://127.0.0.1:8088",
            username="",
            password="",
            token="jwt-token",
            timeout_seconds=10,
            jobs_cache_path=None,
        )
        client = BackQuantClient(settings)

        response = Mock()
        response.status_code = 200
        response.json.return_value = [{"job_id": "job-1"}]

        payload = client._decode_response(response)
        self.assertEqual(payload, [{"job_id": "job-1"}])
