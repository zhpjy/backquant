from __future__ import annotations

from dataclasses import dataclass
from typing import Any

EXIT_OK = 0
EXIT_ARGUMENT = 2
EXIT_LOCAL = 3
EXIT_REMOTE = 4


@dataclass
class CliError(Exception):
    code: str
    message: str
    exit_code: int
    details: Any | None = None

    def __str__(self) -> str:
        return self.message
