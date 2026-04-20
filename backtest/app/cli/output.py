from __future__ import annotations

import json
from typing import Any


def json_ok(data: Any) -> str:
    return json.dumps({"ok": True, "data": data}, ensure_ascii=False)


def json_error(code: str, message: str, details: Any | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return json.dumps(payload, ensure_ascii=False)
