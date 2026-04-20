import unittest
from unittest.mock import Mock, patch

import requests

from app.cli.client import BackQuantClient
from app.cli.config import CliSettings
from app.cli.errors import CliError, EXIT_ARGUMENT, EXIT_REMOTE


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
    def test_save_strategy_posts_expected_contract(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        save_response = Mock()
        save_response.status_code = 200
        save_response.json.return_value = {
            "ok": True,
            "data": {"id": "demo", "size": 17},
        }
        session.post.return_value = save_response

        settings = CliSettings(
            base_url="http://127.0.0.1:8088",
            username="",
            password="",
            token="jwt-token",
            timeout_seconds=10,
            jobs_cache_path=None,
        )
        client = BackQuantClient(settings)

        payload = client.save_strategy("demo", "def init(context):\n    pass\n")
        self.assertTrue(payload["ok"])
        self.assertEqual(session.headers["Authorization"], "jwt-token")
        self.assertEqual(
            session.post.call_args.args[0],
            "http://127.0.0.1:8088/api/backtest/strategies/demo",
        )
        self.assertEqual(
            session.post.call_args.kwargs["json"],
            {"code": "def init(context):\n    pass\n"},
        )

    @patch("app.cli.client.requests.Session")
    def test_get_strategy_success_calls_expected_endpoint(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {"ok": True, "data": {"id": "demo", "code": "print(1)\n"}}
        session.get.return_value = get_response

        settings = CliSettings(
            base_url="http://127.0.0.1:8088",
            username="",
            password="",
            token="jwt-token",
            timeout_seconds=10,
            jobs_cache_path=None,
        )
        client = BackQuantClient(settings)

        payload = client.get_strategy("demo")
        self.assertEqual(payload["data"]["id"], "demo")
        self.assertEqual(session.headers["Authorization"], "jwt-token")
        self.assertEqual(
            session.get.call_args.args[0],
            "http://127.0.0.1:8088/api/backtest/strategies/demo",
        )

    @patch("app.cli.client.requests.Session")
    def test_get_job_calls_expected_endpoint(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {"job_id": "job_demo", "status": "RUNNING"}
        session.get.return_value = get_response

        settings = CliSettings(
            base_url="http://127.0.0.1:8088",
            username="",
            password="",
            token="jwt-token",
            timeout_seconds=10,
            jobs_cache_path=None,
        )
        client = BackQuantClient(settings)

        payload = client.get_job("job_demo")
        self.assertEqual(payload, {"job_id": "job_demo", "status": "RUNNING"})
        self.assertEqual(session.headers["Authorization"], "jwt-token")
        self.assertEqual(
            session.get.call_args.args[0],
            "http://127.0.0.1:8088/api/backtest/jobs/job_demo",
        )

    @patch("app.cli.client.requests.Session")
    def test_get_job_result_calls_expected_endpoint(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {"summary": {}, "equity": {}, "trades": []}
        session.get.return_value = get_response

        settings = CliSettings(
            base_url="http://127.0.0.1:8088",
            username="",
            password="",
            token="jwt-token",
            timeout_seconds=10,
            jobs_cache_path=None,
        )
        client = BackQuantClient(settings)

        payload = client.get_job_result("job_demo")
        self.assertEqual(payload, {"summary": {}, "equity": {}, "trades": []})
        self.assertEqual(session.headers["Authorization"], "jwt-token")
        self.assertEqual(
            session.get.call_args.args[0],
            "http://127.0.0.1:8088/api/backtest/jobs/job_demo/result",
        )

    @patch("app.cli.client.requests.Session")
    def test_get_job_log_calls_expected_endpoint_with_offset(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {"job_id": "job_demo", "content": "line\n", "offset": 5}
        session.get.return_value = get_response

        settings = CliSettings(
            base_url="http://127.0.0.1:8088",
            username="",
            password="",
            token="jwt-token",
            timeout_seconds=10,
            jobs_cache_path=None,
        )
        client = BackQuantClient(settings)

        payload = client.get_job_log("job_demo", offset=5)
        self.assertEqual(payload, {"job_id": "job_demo", "content": "line\n", "offset": 5})
        self.assertEqual(session.headers["Authorization"], "jwt-token")
        self.assertEqual(
            session.get.call_args.args[0],
            "http://127.0.0.1:8088/api/backtest/jobs/job_demo/log",
        )
        self.assertEqual(session.get.call_args.kwargs["params"], {"offset": 5})

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

    @patch("app.cli.client.requests.Session")
    def test_post_transport_failure_is_wrapped_as_cli_error(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        session.post.side_effect = requests.exceptions.Timeout("connect timeout")

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
            client.save_strategy("demo", "print(1)\n")

        self.assertEqual(ctx.exception.code, "REMOTE_TRANSPORT_ERROR")
        self.assertEqual(ctx.exception.exit_code, EXIT_REMOTE)

    @patch("app.cli.client.requests.Session")
    def test_get_transport_failure_is_wrapped_as_cli_error(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        session.get.side_effect = requests.exceptions.ConnectionError("connection refused")

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
            client.get_job("job_demo")

        self.assertEqual(ctx.exception.code, "REMOTE_TRANSPORT_ERROR")
        self.assertEqual(ctx.exception.exit_code, EXIT_REMOTE)

    @patch("app.cli.client.requests.Session")
    def test_login_200_without_token_preserves_payload_code_and_message(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        login_response = Mock()
        login_response.status_code = 200
        login_response.json.return_value = {"code": "BUNDLE_NOT_READY", "message": "bundle is downloading"}
        session.post.return_value = login_response

        client = BackQuantClient(self._settings())

        with self.assertRaises(CliError) as ctx:
            client.compile_strategy("demo", "print(1)\n")

        self.assertEqual(ctx.exception.code, "BUNDLE_NOT_READY")
        self.assertEqual(ctx.exception.message, "bundle is downloading")
        self.assertEqual(ctx.exception.exit_code, EXIT_REMOTE)

    @patch("app.cli.client.requests.Session")
    def test_get_job_log_rejects_offset_and_tail_together(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
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
            client.get_job_log("job_demo", offset=1, tail=10)

        self.assertEqual(ctx.exception.code, "CLI_ARGUMENT_ERROR")
        self.assertEqual(ctx.exception.exit_code, EXIT_ARGUMENT)
