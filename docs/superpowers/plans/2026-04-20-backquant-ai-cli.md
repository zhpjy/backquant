# BackQuant AI CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为本地策略文件驱动的 AI 调试流程实现第一版 `bq` CLI，复用现有远端 BackQuant API 完成编译、运行、拉取、任务查询和本地 `job -> 文件` 缓存。

**Architecture:** 在 `backtest/app/cli` 下新增一个小型 CLI 包，分成配置、远端 API client、本地缓存、命令处理四层。命令层通过 `click` 暴露 `strategy` 和 `job` 两组命令，所有输出统一包装成 JSON；远端逻辑保持不变，只调用现有登录、策略和 job 接口。

**Tech Stack:** Python 3.10, Click, Requests, unittest, click.testing.CliRunner

---

## 文件结构

### 新建文件

- `backtest/app/cli/__init__.py`
  - CLI 包导出。
- `backtest/app/cli/config.py`
  - 读取 `BQ_BASE_URL`、`BQ_USERNAME`、`BQ_PASSWORD`、`BQ_TOKEN`、`BQ_TIMEOUT_SECONDS`，并计算 `./.bq/jobs.json` 路径。
- `backtest/app/cli/errors.py`
  - 定义 CLI 业务异常和退出码。
- `backtest/app/cli/output.py`
  - 统一 JSON 输出。
- `backtest/app/cli/client.py`
  - 包装远端登录、保存策略、拉取策略、编译、运行、查 job、查 result、查 log。
- `backtest/app/cli/cache.py`
  - 维护 `./.bq/jobs.json`。
- `backtest/app/cli/commands/__init__.py`
  - 命令模块导出。
- `backtest/app/cli/commands/strategy.py`
  - 实现 `strategy compile/run/pull`。
- `backtest/app/cli/commands/job.py`
  - 实现 `job show/result/log`。
- `backtest/app/cli/main.py`
  - 创建 `click` 根命令，注册子命令，统一错误输出。
- `backtest/bq`
  - CLI 可执行入口脚本。
- `backtest/tests/test_bq_cli_client.py`
  - 远端 client 单元测试。
- `backtest/tests/test_bq_cli_cache.py`
  - 本地缓存单元测试。
- `backtest/tests/test_bq_cli_strategy.py`
  - `strategy` 命令测试。
- `backtest/tests/test_bq_cli_job.py`
  - `job` 命令测试。

### 修改文件

- `backtest/README.md`
  - 补充 `bq` CLI 的环境变量、命令示例和缓存说明。

## 实现原则

- 所有命令默认输出 JSON。
- 本地文件是源码主副本。
- `strategy_id = PATH.stem`。
- `run` 永远执行 `save -> run`。
- 本地缓存只保存 `job_id -> file/strategy_id/recorded_at`。
- `job` 命令优先透传远端响应，只额外补充本地映射。

### Task 1: CLI 基础设施

**Files:**
- Create: `backtest/app/cli/__init__.py`
- Create: `backtest/app/cli/config.py`
- Create: `backtest/app/cli/errors.py`
- Create: `backtest/app/cli/output.py`
- Create: `backtest/app/cli/main.py`
- Create: `backtest/bq`
- Test: `backtest/tests/test_bq_cli_cache.py`

- [ ] **Step 1: 写失败测试，锁定配置默认值和 JSON 输出基础行为**

```python
import json
import os
import tempfile
import unittest
from pathlib import Path

from app.cli.config import CliSettings
from app.cli.output import json_error, json_ok


class BqCliFoundationTestCase(unittest.TestCase):
    def test_settings_default_jobs_cache_path_under_cwd(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cwd = Path(tmpdir)
            old_cwd = Path.cwd()
            os.chdir(cwd)
            try:
                settings = CliSettings.from_env({})
            finally:
                os.chdir(old_cwd)

        self.assertEqual(settings.jobs_cache_path, cwd / ".bq" / "jobs.json")
        self.assertEqual(settings.timeout_seconds, 10)

    def test_settings_accepts_token_without_username_password(self):
        settings = CliSettings.from_env(
            {
                "BQ_BASE_URL": "http://127.0.0.1:8088",
                "BQ_TOKEN": "token-123",
            }
        )

        self.assertEqual(settings.base_url, "http://127.0.0.1:8088")
        self.assertEqual(settings.token, "token-123")
        self.assertEqual(settings.username, "")
        self.assertEqual(settings.password, "")

    def test_json_helpers_render_expected_shape(self):
        success_text = json_ok({"job_id": "job_demo"})
        error_text = json_error("LOCAL_FILE_ERROR", "cannot read file")

        self.assertEqual(json.loads(success_text), {"ok": True, "data": {"job_id": "job_demo"}})
        self.assertEqual(
            json.loads(error_text),
            {"ok": False, "error": {"code": "LOCAL_FILE_ERROR", "message": "cannot read file"}},
        )
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_cache.BqCliFoundationTestCase -v
```

Expected:

```text
ERROR: Failed to import test module: test_bq_cli_cache
```

- [ ] **Step 3: 写最小实现，建立 CLI 基础设施**

`backtest/app/cli/__init__.py`

```python
from .main import main

__all__ = ["main"]
```

`backtest/app/cli/config.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CliSettings:
    base_url: str
    username: str
    password: str
    token: str
    timeout_seconds: int
    jobs_cache_path: Path

    @classmethod
    def from_env(cls, environ: dict[str, str]) -> "CliSettings":
        raw_timeout = environ.get("BQ_TIMEOUT_SECONDS", "10").strip() or "10"
        timeout_seconds = int(raw_timeout)
        jobs_cache_path = Path.cwd() / ".bq" / "jobs.json"
        return cls(
            base_url=environ.get("BQ_BASE_URL", "").rstrip("/"),
            username=environ.get("BQ_USERNAME", ""),
            password=environ.get("BQ_PASSWORD", ""),
            token=environ.get("BQ_TOKEN", ""),
            timeout_seconds=timeout_seconds,
            jobs_cache_path=jobs_cache_path,
        )
```

`backtest/app/cli/errors.py`

```python
from __future__ import annotations


class CliError(Exception):
    def __init__(self, code: str, message: str, exit_code: int, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.details = details


EXIT_OK = 0
EXIT_ARGUMENT = 2
EXIT_LOCAL = 3
EXIT_REMOTE = 4
```

`backtest/app/cli/output.py`

```python
from __future__ import annotations

import json


def json_ok(data: dict) -> str:
    return json.dumps({"ok": True, "data": data}, ensure_ascii=False)


def json_error(code: str, message: str, *, details: dict | None = None) -> str:
    payload = {"ok": False, "error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return json.dumps(payload, ensure_ascii=False)
```

`backtest/app/cli/commands/__init__.py`

```python
from .job import register_job_commands
from .strategy import register_strategy_commands

__all__ = ["register_job_commands", "register_strategy_commands"]
```

`backtest/app/cli/main.py`

```python
from __future__ import annotations

import os

import click

from app.cli.config import CliSettings
from app.cli.errors import CliError, EXIT_ARGUMENT
from app.cli.output import json_error


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    ctx.obj["settings"] = CliSettings.from_env(dict(os.environ))


def main(argv: list[str] | None = None) -> int:
    try:
        cli.main(args=argv, prog_name="bq", standalone_mode=False)
        return 0
    except CliError as exc:
        click.echo(json_error(exc.code, exc.message, details=exc.details))
        return exc.exit_code
    except click.ClickException as exc:
        click.echo(json_error("CLI_ARGUMENT_ERROR", exc.format_message()))
        return EXIT_ARGUMENT
```

`backtest/bq`

```python
#!/usr/bin/env python3
from app.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_cache.BqCliFoundationTestCase -v
```

Expected:

```text
OK
```

- [ ] **Step 5: 提交**

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && git add backtest/app/cli backtest/bq backtest/tests/test_bq_cli_cache.py && git commit -m "feat: scaffold bq cli foundation"
```

### Task 2: 远端 API Client

**Files:**
- Create: `backtest/app/cli/client.py`
- Test: `backtest/tests/test_bq_cli_client.py`

- [ ] **Step 1: 写失败测试，锁定登录和核心 API 调用**

```python
import unittest
from unittest.mock import Mock, patch

from app.cli.client import BackQuantClient
from app.cli.config import CliSettings


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
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_client.BackQuantClientTestCase -v
```

Expected:

```text
ModuleNotFoundError: No module named 'app.cli.client'
```

- [ ] **Step 3: 写最小实现，封装远端调用**

`backtest/app/cli/client.py`

```python
from __future__ import annotations

from typing import Any

import requests

from app.cli.config import CliSettings
from app.cli.errors import CliError, EXIT_REMOTE


class BackQuantClient:
    def __init__(self, settings: CliSettings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.settings.base_url}{path}"

    def _decode_response(self, response: requests.Response) -> dict[str, Any]:
        payload = response.json()
        if response.status_code >= 400:
            error = payload.get("error") if isinstance(payload, dict) else None
            code = error.get("code", "REMOTE_ERROR") if isinstance(error, dict) else "REMOTE_ERROR"
            message = error.get("message", f"remote request failed: {response.status_code}") if isinstance(error, dict) else f"remote request failed: {response.status_code}"
            raise CliError(code, message, EXIT_REMOTE, details=payload if isinstance(payload, dict) else None)
        return payload

    def _ensure_auth(self) -> None:
        if self.session.headers.get("Authorization"):
            return
        if self.settings.token:
            self.session.headers["Authorization"] = self.settings.token
            return
        if not self.settings.username or not self.settings.password:
            raise CliError("REMOTE_AUTH_ERROR", "BQ_USERNAME/BQ_PASSWORD or BQ_TOKEN is required", EXIT_REMOTE)

        response = self.session.post(
            self._url("/api/login"),
            json={"mobile": self.settings.username, "password": self.settings.password},
            timeout=self.settings.timeout_seconds,
        )
        payload = self._decode_response(response)
        token = payload.get("token")
        if not isinstance(token, str) or not token:
            raise CliError("REMOTE_AUTH_ERROR", "login did not return token", EXIT_REMOTE)
        self.session.headers["Authorization"] = token

    def _post(self, path: str, *, json_payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_auth()
        response = self.session.post(self._url(path), json=json_payload, timeout=self.settings.timeout_seconds)
        return self._decode_response(response)

    def _get(self, path: str) -> dict[str, Any]:
        self._ensure_auth()
        response = self.session.get(self._url(path), timeout=self.settings.timeout_seconds)
        return self._decode_response(response)

    def save_strategy(self, strategy_id: str, code: str) -> dict[str, Any]:
        return self._post(f"/api/backtest/strategies/{strategy_id}", json_payload={"code": code})

    def get_strategy(self, strategy_id: str) -> dict[str, Any]:
        return self._get(f"/api/backtest/strategies/{strategy_id}")

    def compile_strategy(self, strategy_id: str, code: str) -> dict[str, Any]:
        return self._post(f"/api/backtest/strategies/{strategy_id}/compile", json_payload={"code": code})

    def run_strategy(
        self,
        *,
        strategy_id: str,
        start_date: str,
        end_date: str,
        cash: int | float,
        benchmark: str,
        frequency: str,
    ) -> dict[str, Any]:
        return self._post(
            "/api/backtest/run",
            json_payload={
                "strategy_id": strategy_id,
                "start_date": start_date,
                "end_date": end_date,
                "cash": cash,
                "benchmark": benchmark,
                "frequency": frequency,
            },
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._get(f"/api/backtest/jobs/{job_id}")

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        return self._get(f"/api/backtest/jobs/{job_id}/result")

    def get_job_log(self, job_id: str) -> dict[str, Any]:
        return self._get(f"/api/backtest/jobs/{job_id}/log")
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_client.BackQuantClientTestCase -v
```

Expected:

```text
OK
```

- [ ] **Step 5: 提交**

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && git add backtest/app/cli/client.py backtest/tests/test_bq_cli_client.py && git commit -m "feat: add backquant cli api client"
```

### Task 3: 本地缓存模块

**Files:**
- Create: `backtest/app/cli/cache.py`
- Modify: `backtest/tests/test_bq_cli_cache.py`

- [ ] **Step 1: 写失败测试，锁定 jobs.json 创建和读取行为**

```python
import json
import tempfile
import unittest
from pathlib import Path

from app.cli.cache import JobCache


class JobCacheTestCase(unittest.TestCase):
    def test_record_run_creates_jobs_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = JobCache(Path(tmpdir) / ".bq" / "jobs.json")
            cache.record_run("job_demo", Path("/tmp/demo.py"), "demo")

            payload = json.loads((Path(tmpdir) / ".bq" / "jobs.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["jobs"]["job_demo"]["file"], "/tmp/demo.py")
        self.assertEqual(payload["jobs"]["job_demo"]["strategy_id"], "demo")

    def test_lookup_returns_none_when_job_not_cached(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = JobCache(Path(tmpdir) / ".bq" / "jobs.json")
            self.assertIsNone(cache.lookup("job_missing"))
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_cache.JobCacheTestCase -v
```

Expected:

```text
ModuleNotFoundError: No module named 'app.cli.cache'
```

- [ ] **Step 3: 写最小实现，持久化 job 映射**

`backtest/app/cli/cache.py`

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class JobCache:
    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict:
        if not self.path.exists():
            return {"jobs": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_run(self, job_id: str, file_path: Path, strategy_id: str) -> None:
        payload = self._load()
        jobs = payload.setdefault("jobs", {})
        jobs[job_id] = {
            "file": str(file_path),
            "strategy_id": strategy_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(payload)

    def lookup(self, job_id: str) -> dict | None:
        payload = self._load()
        jobs = payload.get("jobs", {})
        entry = jobs.get(job_id)
        return entry if isinstance(entry, dict) else None
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_cache.JobCacheTestCase -v
```

Expected:

```text
OK
```

- [ ] **Step 5: 提交**

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && git add backtest/app/cli/cache.py backtest/tests/test_bq_cli_cache.py && git commit -m "feat: add bq job cache"
```

### Task 4: `strategy compile/run/pull` 命令

**Files:**
- Create: `backtest/app/cli/commands/strategy.py`
- Modify: `backtest/app/cli/main.py`
- Test: `backtest/tests/test_bq_cli_strategy.py`

- [ ] **Step 1: 写失败测试，锁定 compile/run/pull 的 JSON 契约**

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

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
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_strategy.BqStrategyCommandTestCase -v
```

Expected:

```text
ImportError or AttributeError because strategy commands are not registered yet
```

- [ ] **Step 3: 写最小实现，完成 strategy 命令**

`backtest/app/cli/commands/strategy.py`

```python
from __future__ import annotations

from pathlib import Path

import click

from app.cli.cache import JobCache
from app.cli.client import BackQuantClient
from app.cli.config import CliSettings
from app.cli.errors import CliError, EXIT_LOCAL, EXIT_REMOTE
from app.cli.output import json_ok


def _read_strategy_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError("LOCAL_FILE_ERROR", f"cannot read file: {file_path}", EXIT_LOCAL) from exc


def _strategy_id_from_path(file_path: Path) -> str:
    return file_path.stem


def register_strategy_commands(root: click.Group) -> None:
    @root.group("strategy")
    @click.pass_context
    def strategy_group(ctx: click.Context) -> None:
        ctx.ensure_object(dict)

    @strategy_group.command("compile")
    @click.option("--file", "file_path", type=click.Path(path_type=Path, exists=True), required=True)
    @click.pass_context
    def compile_command(ctx: click.Context, file_path: Path) -> None:
        settings: CliSettings = ctx.obj["settings"]
        client = BackQuantClient(settings)
        strategy_id = _strategy_id_from_path(file_path)
        code = _read_strategy_file(file_path)
        remote = client.compile_strategy(strategy_id, code)
        if remote.get("ok") is False:
            raise CliError(
                "COMPILE_ERROR",
                str(remote.get("stderr") or "compile failed"),
                EXIT_REMOTE,
                details={
                    "file": str(file_path.resolve()),
                    "strategy_id": strategy_id,
                    "stdout": remote.get("stdout", ""),
                    "stderr": remote.get("stderr", ""),
                    "diagnostics": remote.get("diagnostics", []),
                },
            )
        click.echo(
            json_ok(
                {
                    "file": str(file_path.resolve()),
                    "strategy_id": strategy_id,
                    "compile": remote,
                }
            )
        )

    @strategy_group.command("run")
    @click.option("--file", "file_path", type=click.Path(path_type=Path, exists=True), required=True)
    @click.option("--start", "start_date", required=True)
    @click.option("--end", "end_date", required=True)
    @click.option("--cash", default=100000)
    @click.option("--benchmark", default="000300.XSHG")
    @click.option("--frequency", default="1d")
    @click.pass_context
    def run_command(
        ctx: click.Context,
        file_path: Path,
        start_date: str,
        end_date: str,
        cash: int,
        benchmark: str,
        frequency: str,
    ) -> None:
        settings: CliSettings = ctx.obj["settings"]
        client = BackQuantClient(settings)
        cache = JobCache(settings.jobs_cache_path)
        strategy_id = _strategy_id_from_path(file_path)
        code = _read_strategy_file(file_path)
        client.save_strategy(strategy_id, code)
        remote = client.run_strategy(
            strategy_id=strategy_id,
            start_date=start_date,
            end_date=end_date,
            cash=cash,
            benchmark=benchmark,
            frequency=frequency,
        )
        job_id = str(remote["job_id"])
        cache.record_run(job_id, file_path.resolve(), strategy_id)
        click.echo(
            json_ok(
                {
                    "job_id": job_id,
                    "file": str(file_path.resolve()),
                    "strategy_id": strategy_id,
                    "status": "QUEUED",
                }
            )
        )

    @strategy_group.command("pull")
    @click.option("--file", "file_path", type=click.Path(path_type=Path), required=True)
    @click.pass_context
    def pull_command(ctx: click.Context, file_path: Path) -> None:
        settings: CliSettings = ctx.obj["settings"]
        client = BackQuantClient(settings)
        strategy_id = _strategy_id_from_path(file_path)
        payload = client.get_strategy(strategy_id)
        code = payload["data"]["code"]
        file_path.write_text(code, encoding="utf-8")
        click.echo(
            json_ok(
                {
                    "file": str(file_path.resolve()),
                    "strategy_id": strategy_id,
                }
            )
        )
```

`backtest/app/cli/main.py`

```python
from __future__ import annotations

import os

import click

from app.cli.config import CliSettings
from app.cli.commands.strategy import register_strategy_commands
from app.cli.errors import CliError, EXIT_ARGUMENT
from app.cli.output import json_error


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    ctx.obj["settings"] = CliSettings.from_env(dict(os.environ))


register_strategy_commands(cli)


def main(argv: list[str] | None = None) -> int:
    try:
        cli.main(args=argv, prog_name="bq", standalone_mode=False)
        return 0
    except CliError as exc:
        click.echo(json_error(exc.code, exc.message, details=exc.details))
        return exc.exit_code
    except click.ClickException as exc:
        click.echo(json_error("CLI_ARGUMENT_ERROR", exc.format_message()))
        return EXIT_ARGUMENT
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_strategy.BqStrategyCommandTestCase -v
```

Expected:

```text
OK
```

- [ ] **Step 5: 提交**

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && git add backtest/app/cli/commands/strategy.py backtest/app/cli/main.py backtest/tests/test_bq_cli_strategy.py && git commit -m "feat: add bq strategy commands"
```

### Task 5: `job show/result/log` 命令

**Files:**
- Create: `backtest/app/cli/commands/job.py`
- Create: `backtest/app/cli/commands/__init__.py`
- Modify: `backtest/app/cli/main.py`
- Test: `backtest/tests/test_bq_cli_job.py`

- [ ] **Step 1: 写失败测试，锁定 job 透传和本地映射补充行为**

```python
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

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
```

- [ ] **Step 2: 运行测试，确认失败**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_job.BqJobCommandTestCase -v
```

Expected:

```text
ImportError or AttributeError because job commands are not implemented yet
```

- [ ] **Step 3: 写最小实现，完成 job 命令**

`backtest/app/cli/commands/job.py`

```python
from __future__ import annotations

import click

from app.cli.cache import JobCache
from app.cli.client import BackQuantClient
from app.cli.config import CliSettings
from app.cli.output import json_ok


def _build_job_response(job_id: str, entry: dict | None, remote: dict) -> str:
    file_path = entry.get("file") if isinstance(entry, dict) else None
    strategy_id = entry.get("strategy_id") if isinstance(entry, dict) else None
    return json_ok(
        {
            "job_id": job_id,
            "file": file_path,
            "strategy_id": strategy_id,
            "remote": remote,
        }
    )


def register_job_commands(root: click.Group) -> None:
    @root.group("job")
    @click.pass_context
    def job_group(ctx: click.Context) -> None:
        ctx.ensure_object(dict)

    @job_group.command("show")
    @click.option("--job-id", required=True)
    @click.pass_context
    def show_command(ctx: click.Context, job_id: str) -> None:
        settings: CliSettings = ctx.obj["settings"]
        client = BackQuantClient(settings)
        cache = JobCache(settings.jobs_cache_path)
        click.echo(_build_job_response(job_id, cache.lookup(job_id), client.get_job(job_id)))

    @job_group.command("result")
    @click.option("--job-id", required=True)
    @click.pass_context
    def result_command(ctx: click.Context, job_id: str) -> None:
        settings: CliSettings = ctx.obj["settings"]
        client = BackQuantClient(settings)
        cache = JobCache(settings.jobs_cache_path)
        click.echo(_build_job_response(job_id, cache.lookup(job_id), client.get_job_result(job_id)))

    @job_group.command("log")
    @click.option("--job-id", required=True)
    @click.pass_context
    def log_command(ctx: click.Context, job_id: str) -> None:
        settings: CliSettings = ctx.obj["settings"]
        client = BackQuantClient(settings)
        cache = JobCache(settings.jobs_cache_path)
        click.echo(_build_job_response(job_id, cache.lookup(job_id), client.get_job_log(job_id)))
```

`backtest/app/cli/commands/__init__.py`

```python
from .job import register_job_commands
from .strategy import register_strategy_commands

__all__ = ["register_job_commands", "register_strategy_commands"]
```

`backtest/app/cli/main.py`

```python
from __future__ import annotations

import os

import click

from app.cli.commands.job import register_job_commands
from app.cli.commands.strategy import register_strategy_commands
from app.cli.config import CliSettings
from app.cli.errors import CliError, EXIT_ARGUMENT
from app.cli.output import json_error


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    ctx.ensure_object(dict)
    ctx.obj["settings"] = CliSettings.from_env(dict(os.environ))


register_strategy_commands(cli)
register_job_commands(cli)


def main(argv: list[str] | None = None) -> int:
    try:
        cli.main(args=argv, prog_name="bq", standalone_mode=False)
        return 0
    except CliError as exc:
        click.echo(json_error(exc.code, exc.message, details=exc.details))
        return exc.exit_code
    except click.ClickException as exc:
        click.echo(json_error("CLI_ARGUMENT_ERROR", exc.format_message()))
        return EXIT_ARGUMENT
```

- [ ] **Step 4: 运行测试，确认通过**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_job.BqJobCommandTestCase -v
```

Expected:

```text
OK
```

- [ ] **Step 5: 提交**

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && git add backtest/app/cli/commands/job.py backtest/tests/test_bq_cli_job.py && git commit -m "feat: add bq job commands"
```

### Task 6: 文档与整体验证

**Files:**
- Modify: `backtest/README.md`
- Verify: `backtest/tests/test_bq_cli_cache.py`
- Verify: `backtest/tests/test_bq_cli_client.py`
- Verify: `backtest/tests/test_bq_cli_strategy.py`
- Verify: `backtest/tests/test_bq_cli_job.py`

- [ ] **Step 1: 写 README 更新，明确环境变量和命令用法**

```markdown
## BQ CLI（AI 调试入口）

`bq` CLI 面向本地策略文件工作，运行时复用远端 BackQuant API。

### 环境变量

- `BQ_BASE_URL`：BackQuant 服务根地址，例如 `http://127.0.0.1:8088`
- `BQ_USERNAME`：登录用户名，默认可用 `admin`
- `BQ_PASSWORD`：登录密码
- `BQ_TOKEN`：可选，若提供则跳过登录
- `BQ_TIMEOUT_SECONDS`：可选，请求超时，默认 `10`

### 命令示例

```bash
cd /app/backtest
./bq strategy compile --file /workspace/strategies/foo.py
./bq strategy run --file /workspace/strategies/foo.py --start 2026-01-01 --end 2026-01-31
./bq job show --job-id job_20260420_001
./bq job result --job-id job_20260420_001
./bq job log --job-id job_20260420_001
```

### 本地缓存

CLI 会在当前工作目录下写入 `./.bq/jobs.json`，记录 `job_id -> 本地文件` 的映射，便于结果查询时回溯来源文件。
```

- [ ] **Step 2: 运行 CLI 测试全集**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_cache tests.test_bq_cli_client tests.test_bq_cli_strategy tests.test_bq_cli_job -v
```

Expected:

```text
OK
```

- [ ] **Step 3: 做一次最小手工冒烟，确认入口脚本可执行**

Run:

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && chmod +x ./bq && ./bq --help
```

Expected:

```text
Usage: bq [OPTIONS] COMMAND [ARGS]...
```

- [ ] **Step 4: 提交**

```bash
cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && git add backtest/README.md backtest/bq backtest/app/cli backtest/tests/test_bq_cli_* && git commit -m "docs: add bq cli usage"
```

## 自检

### Spec 覆盖检查

- 本地文件为权威源码：Task 4 的 `run/pull/compile` 全部围绕 `--file PATH`。
- 远端逻辑不改：Task 2 只调用现有 `/api/login`、`/api/backtest/strategies/...`、`/api/backtest/run`、`/api/backtest/jobs/...`。
- `strategy_id = PATH.stem`：Task 4 明确通过 `_strategy_id_from_path()` 固定该规则。
- `run = save -> run`：Task 4 的 `run_command()` 先 `save_strategy()` 再 `run_strategy()`。
- 本地 `job -> 文件` 缓存：Task 3 和 Task 4 一起实现。
- `job` 命令远端透传：Task 5 的 `remote` 字段直接放远端返回。
- JSON-first：Task 1 的输出层和 Task 4/5 的命令输出都走 JSON。

### 占位符检查

- 没有 `TODO`、`TBD`、`later` 之类占位词。
- 每个任务都给了精确文件路径、测试命令和提交命令。
- 每个代码步骤都给了完整文件内容或完整函数内容。

### 类型一致性检查

- 所有命令共享 `CliSettings`、`BackQuantClient`、`JobCache`。
- `job` 返回结构统一为 `job_id/file/strategy_id/remote`。
- `strategy` 返回结构统一为 `file/strategy_id` 加具体动作字段。
