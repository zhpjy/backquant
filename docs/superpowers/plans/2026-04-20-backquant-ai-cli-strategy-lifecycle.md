# BackQuant Strategy Lifecycle CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `bq strategy` 增加 `create/list/delete`，补齐本地策略初始化和远端策略管理的最小闭环。

**Architecture:** `create` 只负责本地文件初始化，保持“本地文件是权威源码”的模型；`list/delete` 只透传现有远端 BackQuant 策略接口，不引入额外同步层。实现集中在 CLI client、strategy 命令和对应单测，README 同步真实语法。

**Tech Stack:** Python 3, Click, requests, unittest

---

### Task 1: 扩展 client 层策略列表与删除接口

**Files:**
- Modify: `backtest/app/cli/client.py`
- Test: `backtest/tests/test_bq_cli_client.py`

- [ ] **Step 1: 写失败测试**

```python
    @patch("app.cli.client.requests.Session")
    def test_list_strategies_calls_expected_endpoint_with_filters(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        get_response = Mock()
        get_response.status_code = 200
        get_response.json.return_value = {"ok": True, "data": {"strategies": [], "total": 0}}
        session.get.return_value = get_response

        client = BackQuantClient(
            CliSettings(
                base_url="http://127.0.0.1:8088",
                username="",
                password="",
                token="jwt-token",
                timeout_seconds=10,
                jobs_cache_path=None,
            )
        )

        payload = client.list_strategies(q="demo", limit=20, offset=5)
        self.assertEqual(payload["data"]["total"], 0)
        self.assertEqual(
            session.get.call_args.args[0],
            "http://127.0.0.1:8088/api/backtest/strategies",
        )
        self.assertEqual(session.get.call_args.kwargs["params"], {"q": "demo", "limit": 20, "offset": 5})

    @patch("app.cli.client.requests.Session")
    def test_delete_strategy_calls_expected_endpoint_with_cascade(self, session_cls):
        session = Mock()
        session_cls.return_value = session
        session.headers = {}
        delete_response = Mock()
        delete_response.status_code = 200
        delete_response.json.return_value = {"ok": True, "data": {"strategy_id": "demo", "deleted": True}}
        session.delete.return_value = delete_response

        client = BackQuantClient(
            CliSettings(
                base_url="http://127.0.0.1:8088",
                username="",
                password="",
                token="jwt-token",
                timeout_seconds=10,
                jobs_cache_path=None,
            )
        )

        payload = client.delete_strategy("demo", cascade=True)
        self.assertTrue(payload["data"]["deleted"])
        self.assertEqual(
            session.delete.call_args.args[0],
            "http://127.0.0.1:8088/api/backtest/strategies/demo",
        )
        self.assertEqual(session.delete.call_args.kwargs["params"], {"cascade": "true"})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_client.BackQuantClientTestCase.test_list_strategies_calls_expected_endpoint_with_filters tests.test_bq_cli_client.BackQuantClientTestCase.test_delete_strategy_calls_expected_endpoint_with_cascade -v`
Expected: FAIL，提示 `BackQuantClient` 缺少 `list_strategies` / `delete_strategy` 或 `Session` 不支持当前调用。

- [ ] **Step 3: 写最小实现**

```python
    def _delete(self, path: str, *, params: dict | None = None) -> Any:
        self._ensure_auth()
        try:
            response = self.session.delete(
                self._url(path),
                params=params,
                timeout=self.settings.timeout_seconds,
            )
        except requests.RequestException as exc:
            self._raise_transport_error(exc)
        return self._decode_response(response)

    def list_strategies(self, *, q: str | None = None, limit: int | None = None, offset: int | None = None) -> dict:
        params: dict[str, int | str] = {}
        if q is not None:
            params["q"] = q
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._get("/api/backtest/strategies", params=params or None)

    def delete_strategy(self, strategy_id: str, *, cascade: bool = False) -> dict:
        params = {"cascade": "true"} if cascade else None
        return self._delete(f"/api/backtest/strategies/{self._quote(strategy_id)}", params=params)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_client.BackQuantClientTestCase.test_list_strategies_calls_expected_endpoint_with_filters tests.test_bq_cli_client.BackQuantClientTestCase.test_delete_strategy_calls_expected_endpoint_with_cascade -v`
Expected: PASS

### Task 2: 扩展 strategy 命令 create/list/delete

**Files:**
- Modify: `backtest/app/cli/commands/strategy.py`
- Test: `backtest/tests/test_bq_cli_strategy.py`

- [ ] **Step 1: 写失败测试**

```python
    def test_create_writes_minimal_rqalpha_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_path = Path(tmpdir) / "demo.py"
            runner = CliRunner()

            result = runner.invoke(cli, ["strategy", "create", "--file", str(strategy_path)])

            self.assertEqual(result.exit_code, 0)
            self.assertTrue(strategy_path.exists())
            self.assertIn("def init(context):", strategy_path.read_text(encoding="utf-8"))
            payload = json.loads(result.output)
            self.assertEqual(payload["data"]["strategy_id"], "demo")

    def test_create_returns_local_file_error_when_file_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            strategy_path = Path(tmpdir) / "demo.py"
            strategy_path.write_text("print('exists')\n", encoding="utf-8")
            runner = CliRunner()

            result = runner.invoke(cli, ["strategy", "create", "--file", str(strategy_path)])

            self.assertEqual(result.exit_code, EXIT_LOCAL)

    @patch("app.cli.commands.strategy.BackQuantClient")
    def test_list_returns_remote_payload(self, client_cls):
        client = Mock()
        client.list_strategies.return_value = {"ok": True, "data": {"strategies": [{"id": "demo"}], "total": 1}}
        client_cls.return_value = client

        runner = CliRunner()
        result = runner.invoke(cli, ["strategy", "list", "--q", "de", "--limit", "20", "--offset", "5"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["remote"]["data"]["total"], 1)
        client.list_strategies.assert_called_once_with(q="de", limit=20, offset=5)

    @patch("app.cli.commands.strategy.BackQuantClient")
    def test_delete_calls_remote_with_cascade(self, client_cls):
        client = Mock()
        client.delete_strategy.return_value = {"ok": True, "data": {"strategy_id": "demo", "deleted": True}}
        client_cls.return_value = client

        runner = CliRunner()
        result = runner.invoke(cli, ["strategy", "delete", "--strategy-id", "demo", "--cascade"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["remote"]["data"]["strategy_id"], "demo")
        client.delete_strategy.assert_called_once_with("demo", cascade=True)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_strategy.BqStrategyCommandTestCase.test_create_writes_minimal_rqalpha_template tests.test_bq_cli_strategy.BqStrategyCommandTestCase.test_create_returns_local_file_error_when_file_exists tests.test_bq_cli_strategy.BqStrategyCommandTestCase.test_list_returns_remote_payload tests.test_bq_cli_strategy.BqStrategyCommandTestCase.test_delete_calls_remote_with_cascade -v`
Expected: FAIL，因为命令尚未注册或行为未实现。

- [ ] **Step 3: 写最小实现**

```python
_DEFAULT_TEMPLATE = """from rqalpha.api import *


def init(context):
    pass


def handle_bar(context, bar_dict):
    pass
"""


def _create_strategy_file(file_path: Path) -> None:
    if file_path.exists():
        raise CliError(
            code="LOCAL_FILE_ERROR",
            message="local strategy file already exists",
            exit_code=EXIT_LOCAL,
            details={"file": str(file_path)},
        )
    _write_strategy_file(file_path, _DEFAULT_TEMPLATE)


    @strategy_group.command(name="create")
    @click.option("--file", "file_path", required=True, type=click.Path(path_type=Path, dir_okay=False))
    @click.pass_context
    def create_command(ctx: click.Context, file_path: Path) -> None:
        def _impl() -> None:
            _create_strategy_file(file_path)
            click.echo(json_ok({"file": str(file_path), "strategy_id": _strategy_id_from_path(file_path), "created": True}))

        _run_with_json_error(_impl)

    @strategy_group.command(name="list")
    @click.option("--q")
    @click.option("--limit", type=click.IntRange(min=1, max=500))
    @click.option("--offset", type=click.IntRange(min=0))
    @click.pass_context
    def list_command(ctx: click.Context, q: str | None, limit: int | None, offset: int | None) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)
            click.echo(json_ok({"remote": client.list_strategies(q=q, limit=limit, offset=offset)}))

        _run_with_json_error(_impl)

    @strategy_group.command(name="delete")
    @click.option("--strategy-id", required=True)
    @click.option("--cascade", is_flag=True)
    @click.pass_context
    def delete_command(ctx: click.Context, strategy_id: str, cascade: bool) -> None:
        def _impl() -> None:
            settings = ctx.obj["settings"]
            assert isinstance(settings, CliSettings)
            client = BackQuantClient(settings)
            click.echo(json_ok({"strategy_id": strategy_id, "remote": client.delete_strategy(strategy_id, cascade=cascade)}))

        _run_with_json_error(_impl)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_strategy.BqStrategyCommandTestCase.test_create_writes_minimal_rqalpha_template tests.test_bq_cli_strategy.BqStrategyCommandTestCase.test_create_returns_local_file_error_when_file_exists tests.test_bq_cli_strategy.BqStrategyCommandTestCase.test_list_returns_remote_payload tests.test_bq_cli_strategy.BqStrategyCommandTestCase.test_delete_calls_remote_with_cascade -v`
Expected: PASS

### Task 3: 更新 README 并做回归验证

**Files:**
- Modify: `backtest/README.md`
- Test: `backtest/tests/test_bq_cli_client.py`
- Test: `backtest/tests/test_bq_cli_strategy.py`

- [ ] **Step 1: 更新文档**

```markdown
# 新增示例
./bq strategy create --file ./strategies/demo.py
./bq strategy list
./bq strategy delete --strategy-id demo
./bq strategy delete --strategy-id demo --cascade
```

- [ ] **Step 2: 跑完整相关测试**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && python -m unittest tests.test_bq_cli_client tests.test_bq_cli_strategy -v`
Expected: PASS

- [ ] **Step 3: 跑 CLI 帮助确认命令暴露**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk/backtest && ./bq strategy --help`
Expected: 输出中包含 `create`、`list`、`delete`、`compile`、`run`、`pull`
