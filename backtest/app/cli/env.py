from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path


def bq_env_file_path(repo_root: Path) -> Path:
    return repo_root / "backtest" / ".env.bq"


def load_env_file(path: Path, *, env: Mapping[str, str] | None = None) -> dict[str, str]:
    merged: dict[str, str] = dict(env or {})
    if not path.exists():
        return merged

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in merged:
            continue
        merged[key] = value.strip()
    return merged


def apply_env_file(path: Path, *, env: MutableMapping[str, str]) -> None:
    loaded = load_env_file(path, env=env)
    env.update(loaded)
