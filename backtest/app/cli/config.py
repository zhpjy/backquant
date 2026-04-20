from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class CliSettings:
    base_url: str
    username: str
    password: str
    token: str
    timeout_seconds: int
    jobs_cache_path: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "CliSettings":
        source = os.environ if env is None else env
        timeout_value = source.get("BQ_TIMEOUT_SECONDS", "10")
        try:
            timeout_seconds = int(timeout_value)
        except (TypeError, ValueError):
            timeout_seconds = 10

        return cls(
            base_url=source.get("BQ_BASE_URL", "").strip().rstrip("/"),
            username=source.get("BQ_USERNAME", ""),
            password=source.get("BQ_PASSWORD", ""),
            token=source.get("BQ_TOKEN", ""),
            timeout_seconds=timeout_seconds,
            jobs_cache_path=Path.cwd() / ".bq" / "jobs.json",
        )
