from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JobCache:
    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path

    def _load(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {"jobs": {}}

        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        if "jobs" not in payload or not isinstance(payload["jobs"], dict):
            payload["jobs"] = {}
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_run(self, job_id: str, file_path: Path, strategy_id: str) -> None:
        payload = self._load()
        payload["jobs"][job_id] = {
            "file": str(file_path),
            "strategy_id": strategy_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(payload)

    def lookup(self, job_id: str) -> dict[str, Any] | None:
        payload = self._load()
        return payload["jobs"].get(job_id)
