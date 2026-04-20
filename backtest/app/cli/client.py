from __future__ import annotations

from collections.abc import MutableMapping
from urllib.parse import quote

import requests

from .config import CliSettings
from .errors import CliError, EXIT_ARGUMENT, EXIT_REMOTE


class BackQuantClient:
    def __init__(self, settings: CliSettings) -> None:
        self.settings = settings
        self.session = requests.Session()
        headers = getattr(self.session, "headers", None)
        if not isinstance(headers, MutableMapping):
            headers = {}
            self.session.headers = headers
        headers["Content-Type"] = "application/json"

    def _url(self, path: str) -> str:
        return f"{self.settings.base_url}{path}"

    def _decode_response(self, response: requests.Response) -> dict:
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}

        if response.status_code >= 400:
            error = payload.get("error") if isinstance(payload, dict) else None
            code = "REMOTE_HTTP_ERROR"
            message = f"remote request failed with HTTP {response.status_code}"
            if isinstance(error, dict):
                code = str(error.get("code") or code)
                message = str(error.get("message") or message)
            raise CliError(code=code, message=message, exit_code=EXIT_REMOTE, details=payload)

        return payload if isinstance(payload, dict) else {"data": payload}

    def _ensure_auth(self) -> None:
        auth_header = self.session.headers.get("Authorization")
        if auth_header:
            return

        if self.settings.token:
            self.session.headers["Authorization"] = self.settings.token
            return

        if not self.settings.username or not self.settings.password:
            raise CliError(
                code="CLI_ARGUMENT_ERROR",
                message="BQ_USERNAME and BQ_PASSWORD are required when BQ_TOKEN is not set",
                exit_code=EXIT_ARGUMENT,
            )

        response = self.session.post(
            self._url("/api/login"),
            json={"mobile": self.settings.username, "password": self.settings.password},
            timeout=self.settings.timeout_seconds,
        )
        payload = self._decode_response(response)
        token = payload.get("token")
        if not token:
            raise CliError(
                code="REMOTE_HTTP_ERROR",
                message="remote login succeeded but token is missing",
                exit_code=EXIT_REMOTE,
                details=payload,
            )
        self.session.headers["Authorization"] = str(token)

    def _post(self, path: str, *, json: dict) -> dict:
        self._ensure_auth()
        response = self.session.post(
            self._url(path),
            json=json,
            timeout=self.settings.timeout_seconds,
        )
        return self._decode_response(response)

    def _get(self, path: str, *, params: dict | None = None) -> dict:
        self._ensure_auth()
        response = self.session.get(
            self._url(path),
            params=params,
            timeout=self.settings.timeout_seconds,
        )
        return self._decode_response(response)

    @staticmethod
    def _quote(value: str) -> str:
        return quote(value, safe="")

    def save_strategy(self, strategy_id: str, code: str) -> dict:
        return self._post(f"/api/backtest/strategies/{self._quote(strategy_id)}", json={"code": code})

    def get_strategy(self, strategy_id: str) -> dict:
        return self._get(f"/api/backtest/strategies/{self._quote(strategy_id)}")

    def compile_strategy(self, strategy_id: str, code: str | None = None) -> dict:
        payload = {"code": code} if code is not None else {}
        return self._post(f"/api/backtest/strategies/{self._quote(strategy_id)}/compile", json=payload)

    def run_strategy(
        self,
        *,
        strategy_id: str,
        start_date: str,
        end_date: str,
        cash: int | float,
        benchmark: str,
        frequency: str,
    ) -> dict:
        return self._post(
            "/api/backtest/run",
            json={
                "strategy_id": strategy_id,
                "start_date": start_date,
                "end_date": end_date,
                "cash": cash,
                "benchmark": benchmark,
                "frequency": frequency,
            },
        )

    def get_job(self, job_id: str) -> dict:
        return self._get(f"/api/backtest/jobs/{self._quote(job_id)}")

    def get_job_result(self, job_id: str) -> dict:
        return self._get(f"/api/backtest/jobs/{self._quote(job_id)}/result")

    def get_job_log(self, job_id: str, *, offset: int | None = None, tail: int | None = None) -> dict:
        params: dict[str, int] | None = None
        if offset is not None:
            params = {"offset": offset}
        elif tail is not None:
            params = {"tail": tail}
        return self._get(f"/api/backtest/jobs/{self._quote(job_id)}/log", params=params)
