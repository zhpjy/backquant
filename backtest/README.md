# BackQuant Backend

## `bq` CLI（首版）

`bq` 用于“本地策略文件 + 远端 BackQuant API”的工作流：在本地维护策略文件，通过 CLI 调用服务端接口完成编译、运行和任务查询。

### 环境变量

- `BQ_BASE_URL`：BackQuant API 根地址（例如 `http://127.0.0.1:54321`）
- `BQ_USERNAME`：登录用户名（通常是手机号）
- `BQ_PASSWORD`：登录密码
- `BQ_TOKEN`：可选，直接使用已存在 token（设置后可跳过用户名/密码登录）
- `BQ_TIMEOUT_SECONDS`：可选，HTTP 请求超时秒数

### 示例命令

```bash
# 编译本地策略文件（远端编译检查）
./bq strategy compile demo ./strategies/demo.py

# 运行本地策略文件（提交回测任务）
./bq strategy run demo ./strategies/demo.py --start-date 2020-01-01 --end-date 2020-12-31

# 查看任务状态
./bq job show <job_id>

# 查看任务结果（支持分页）
./bq job result <job_id> --page 1 --page-size 100

# 查看任务日志（支持 offset / tail）
./bq job log <job_id> --tail 4096
```

### 本地缓存

`./.bq/jobs.json` 会保存 `job_id -> 本地策略文件路径` 的映射，供 `job` 相关命令在本地回溯任务来源。

## WSGI 环境变量

建议使用项目根目录的 `.env.wsgi` 管理 WSGI 运行变量，不依赖 `~/.bashrc`。

```bash
cp .env.wsgi.example .env.wsgi
```

`python3 wsgi.py` 和 `./restart.sh` 都会读取 `.env.wsgi`。

如果线上进程的 `PATH` 不包含 `rqalpha`，可以在 `.env.wsgi` 显式设置：

```bash
RQALPHA_COMMAND='/home/app/backquant/backtest/.venv/bin/rqalpha'
```

## 登录接口

`POST /api/login`

- 认证：不需要
- 请求头：`Content-Type: application/x-www-form-urlencoded`
- 请求体：`mobile`, `password`
- 成功响应：`token`, `userid`, `is_admin`
- 鉴权头：后续请求使用 `Authorization: <token>`（不是 Bearer）

示例：

```bash
curl -X POST "http://127.0.0.1:54321/api/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "mobile=13800138000&password=pass123456"
```

## Backtest API (RQAlpha MVP1)

Base URL: `http://127.0.0.1:54321/api/backtest`

除 `/api/login` 外，所有回测接口都需要请求头：`Authorization: <token>`。

### 1) 获取策略列表

```bash
curl -X GET "http://127.0.0.1:54321/api/backtest/strategies" \
  -H "Authorization: <token>"
```

支持查询参数：

- `q`：按策略 ID 模糊过滤
- `limit`：默认 `100`，最大 `500`
- `offset`：默认 `0`

带查询参数示例：

```bash
curl -X GET "http://127.0.0.1:54321/api/backtest/strategies?q=demo&limit=20&offset=0" \
  -H "Authorization: <token>"
```

返回示例：

```json
{
  "strategies": [
    {
      "id": "demo",
      "created_at": "2026-02-16T10:00:00Z",
      "updated_at": "2026-02-16T10:00:00Z",
      "size": 1234
    }
  ],
  "total": 1
}
```

字段说明：

- `created_at`：策略首次创建时间（ISO 8601，UTC）。若为历史数据且缺少创建时间元数据，返回 `null`（字段不省略）。
- `updated_at`：策略最近一次修改时间（ISO 8601，UTC）。

默认按 `updated_at` 倒序；无数据时返回：

```json
{"strategies": [], "total": 0}
```

### 2) 保存策略

```bash
curl -X POST "http://127.0.0.1:54321/api/backtest/strategies/demo" \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def init(context):\n    pass\n\ndef handle_bar(context, bar_dict):\n    pass\n"
  }'
```

### 2.1) 策略改名（后端事务 + 幂等）

接口：`POST /api/backtest/strategies/{from_id}/rename`

请求体：

```json
{
  "to_id": "new_strategy_id",
  "code": "可选，若传入则覆盖目标策略代码"
}
```

示例：

```bash
curl -X POST "http://127.0.0.1:54321/api/backtest/strategies/demo/rename" \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "to_id": "alpha"
  }'
```

返回示例：

```json
{
  "ok": true,
  "data": {
    "from_id": "demo",
    "to_id": "alpha",
    "deleted_old": true,
    "warning": ""
  }
}
```

语义：

- `from_id` / `to_id` 校验规则与 `strategy_id` 一致（长度 `1~64`，仅允许中文/CJK、字母、数字、`_`、`-`，不允许空白）
- `from_id == to_id` 返回 `200`，`warning` 带 `noop`（幂等）
- 源策略不存在返回 `404`
- 目标策略已存在或冲突返回 `409`
- ID 非法返回 `422`，并在错误消息中定位字段（如 `from_id contains invalid characters` / `to_id contains invalid characters`）
- 成功后会写入改名映射表，并执行链路压缩（如 `A->B`, `B->C` 自动压缩为 `A->C`, `B->C`）

### 2.2) 策略改名映射（兼容前端历史路径）

获取映射：`GET /api/backtest/strategy-renames`

写入映射：`POST /api/backtest/strategy-renames`

写入请求体：

```json
{
  "from_id": "legacy_id",
  "to_id": "current_id"
}
```

返回结构（GET/POST 一致）：

```json
{
  "ok": true,
  "data": {
    "map": {
      "legacy_a": "current_a",
      "legacy_b": "current_a"
    }
  }
}
```

### 3) 策略编译调试

接口：`POST /api/backtest/strategies/{id}/compile`

- 鉴权：需要 `Authorization: <token>` 且 `is_admin=true`，否则返回 `403 FORBIDDEN`
- 请求体：`{ "code"?: string }`
- `code` 为空（缺失、`null`、空串、全空白）时，使用服务端已保存策略代码进行编译检查
- `code` 非空时，仅进行临时编译调试，不会覆盖或落库存量策略代码

示例（使用已保存代码）：

```bash
curl -X POST "http://127.0.0.1:54321/api/backtest/strategies/demo/compile" \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

示例（临时代码调试，不落库）：

```bash
curl -X POST "http://127.0.0.1:54321/api/backtest/strategies/demo/compile" \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "import rqalpha\n\ndef init(context):\n    pass\n"
  }'
```

成功与业务失败（`400/403/422/500`）统一返回结构（`401` 由鉴权中间件返回标准错误体）：

```json
{
  "ok": true,
  "stdout": "syntax check passed\ndependency check passed",
  "stderr": "",
  "diagnostics": []
}
```

`diagnostics` 元素结构：

```json
{
  "line": 1,
  "column": 1,
  "level": "error",
  "message": "dependency 'xxx' is not installed"
}
```

编译检查阶段：

- Python 语法检查：`ast.parse`
- 依赖可用性检查：扫描 `import`/`from ... import ...`，检查依赖是否可解析
- 在独立子进程与沙箱目录执行，默认超时 `10` 秒（`BACKTEST_COMPILE_TIMEOUT`）
- 编译检查只做静态分析，不执行策略代码；并禁用外网代理环境变量

失败码定义（本接口）：

- `400 INVALID_ARGUMENT`：请求体非法、`code` 类型非法、策略 ID 非法、且未提供临时代码时找不到已保存策略
- `401 UNAUTHORIZED`：缺少 token、token 无效或过期
- `403 FORBIDDEN`：非管理员用户调用
- `422 UNPROCESSABLE_ENTITY`：语法错误或依赖不可用
- `500 INTERNAL_ERROR`：编译子进程超时或内部异常

### 4) 获取策略回测历史

```bash
curl -X GET "http://127.0.0.1:54321/api/backtest/strategies/demo/jobs?limit=20&offset=0" \
  -H "Authorization: <token>"
```

支持查询参数：

- `status`：可选，`QUEUED | RUNNING | FAILED | CANCELLED | FINISHED`
- `limit`：默认 `100`，最大 `1000`
- `offset`：默认 `0`

返回示例：

```json
{
  "ok": true,
  "data": {
    "strategy_id": "demo",
    "jobs": [
      {
        "job_id": "f0123456789abcdef0123456789abcd",
        "strategy_id": "demo",
        "status": "FINISHED",
        "error": null,
        "created_at": "2026-02-16T10:00:00+08:00",
        "updated_at": "2026-02-16T10:01:15+08:00",
        "params": {
          "start_date": "2020-01-01",
          "end_date": "2020-12-31",
          "cash": 100000,
          "benchmark": "000300.XSHG",
          "frequency": "1d"
        }
      }
    ],
    "total": 1
  }
}
```

### 4.1) 删除单个回测任务

接口：`DELETE /api/backtest/jobs/{job_id}`

```bash
curl -X DELETE "http://127.0.0.1:54321/api/backtest/jobs/<job_id>" \
  -H "Authorization: <token>"
```

成功返回示例：

```json
{
  "ok": true,
  "data": {
    "job_id": "<job_id>",
    "deleted": true
  }
}
```

幂等语义（当前实现）：任务不存在时返回 `404 NOT_FOUND`（JSON 错误体）。

### 4.2) 删除策略

接口：`DELETE /api/backtest/strategies/{strategy_id}`

- 默认（不带 `cascade`）：若存在关联任务，返回 `409 CONFLICT`，并在 `data.job_ids` 返回阻塞删除的任务 ID 列表
- 级联删除：`DELETE /api/backtest/strategies/{strategy_id}?cascade=true`
  - 删除该策略（含别名映射到该 canonical id）的历史任务
  - 删除策略代码文件
  - 清理 rename map 中与该策略相关的旧映射

级联删除成功示例：

```json
{
  "ok": true,
  "data": {
    "strategy_id": "alpha",
    "deleted_jobs": 123
  }
}
```

### 5) 提交回测

```bash
curl -X POST "http://127.0.0.1:54321/api/backtest/run" \
  -H "Authorization: <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "demo",
    "start_date": "2020-01-01",
    "end_date": "2020-12-31",
    "cash": 100000,
    "benchmark": "000300.XSHG",
    "frequency": "1d"
  }'
```

返回示例：

```json
{"job_id":"f0123456789abcdef0123456789abcd"}
```

请求参数校验（入队前执行，校验失败不会创建任务）：

- `strategy_id`：必填，长度 `1~64`，仅允许中文（CJK）、`A-Z`、`a-z`、`0-9`、`_`、`-`（不允许空白）；不存在时返回 `404 NOT_FOUND`
- `start_date` / `end_date`：必填，格式 `YYYY-MM-DD`
- `end_date >= start_date`
- `frequency`：仅允许 `BACKTEST_ALLOWED_FREQUENCIES` 白名单中的值（默认仅 `1d`）
- `cash`：正数（`>0`）
- `benchmark`：非空字符串

幂等去重说明：

- 默认启用短窗口去重（`BACKTEST_IDEMPOTENCY_WINDOW_SECONDS`，默认 `30` 秒）
- 同一策略代码 + 相同参数（`strategy_id/start_date/end_date/cash/benchmark/frequency`）在窗口内重复提交时，会直接返回已有 `job_id`
- `FAILED` / `CANCELLED` 任务不会复用，重复提交会创建新任务

### 6) 轮询状态

```bash
curl "http://127.0.0.1:54321/api/backtest/jobs/<job_id>" \
  -H "Authorization: <token>"
```

返回示例：

```json
{
  "job_id": "<job_id>",
  "status": "RUNNING",
  "error": null,
  "error_message": null
}
```

状态值：`QUEUED | RUNNING | FAILED | CANCELLED | FINISHED`

失败时 `error` 统一为结构化对象：

```json
{
  "code": "RQALPHA_TIMEOUT",
  "message": "rqalpha timeout after 900s; see run.log"
}
```

### 7) 获取结果 JSON

仅在 `FINISHED` 后可用：

```bash
curl "http://127.0.0.1:54321/api/backtest/jobs/<job_id>/result" \
  -H "Authorization: <token>"
```

可选分页参数（用于大体量 `trades`）：

```bash
curl "http://127.0.0.1:54321/api/backtest/jobs/<job_id>/result?page=1&page_size=100" \
  -H "Authorization: <token>"
```

结果结构固定包含以下字段（缺失时返回空结构）：

- `summary`（对象）
- `equity`（对象，包含 `dates/nav/returns/benchmark_nav` 四个数组）
- `trades`（数组）
- `trade_columns`（数组）
- `trades_total`（整数）
- `raw_keys`（数组）

就绪语义：

- 任务状态非 `FINISHED`（`QUEUED/RUNNING/FAILED/CANCELLED`）时，返回 `409`，错误码 `RESULT_NOT_READY`
- 任务已 `FINISHED` 且结果文件有效时，返回 `200`（即使 `trades` 为空数组）
- 任务已 `FINISHED` 但结果文件丢失或损坏时，返回 `500`

### 8) 获取运行日志

```bash
curl "http://127.0.0.1:54321/api/backtest/jobs/<job_id>/log" \
  -H "Authorization: <token>"
```

支持增量读取：

```bash
curl "http://127.0.0.1:54321/api/backtest/jobs/<job_id>/log?offset=1024" \
  -H "Authorization: <token>"
curl "http://127.0.0.1:54321/api/backtest/jobs/<job_id>/log?tail=4096" \
  -H "Authorization: <token>"
```

- 不带参数时返回完整纯文本日志（兼容旧行为）
- 带 `offset` 或 `tail` 时返回 JSON：
  - `content`: 本次日志片段
  - `offset`: 本次起始偏移
  - `next_offset`: 下次增量拉取可使用的偏移
  - `size`: 当前日志文件大小

### 9) 兼容约定（前端）

- `/api/backtest/strategies`：推荐返回 `{ "strategies": [...] }`
- `/api/backtest/strategies/{id}`：推荐返回 `{ "code": "..." }` 或包含 `code` 字段的对象
- `/api/backtest/run`：必须返回 `job_id`（或 `jobId`）
- `/api/backtest/jobs/{job_id}/result`：任务未完成返回 `409`，前端会继续轮询
- `/api/backtest/jobs/{job_id}/log`：支持纯文本或 JSON（含 `log`/`content`）

## 统一错误响应

所有错误统一返回 JSON：

```json
{
  "ok": false,
  "error": {
    "code": "SOME_CODE",
    "message": "human readable"
  }
}
```

覆盖状态码：`400/401/403/404/405/409/422/500`。未匹配路由、方法不支持、非法路径参数等场景不再返回 HTML。

## 存储目录

- 基础目录：`BACKTEST_BASE_DIR`（默认 `/home/app/rqalpha_platform_storage`）
- 策略目录：`<BACKTEST_BASE_DIR>/strategies/<strategy_id>.py`
- 回测目录按日期分桶：`<BACKTEST_BASE_DIR>/runs/YYYY-MM-DD/<job_id>/`
- 任务索引：`<BACKTEST_BASE_DIR>/runs_index/<job_id>.json`

每个任务目录至少包含：

- `strategy.py`
- `config.yml`
- `job_meta.json`
- `status.json`
- `run.log`
- `result.pkl`
- `extracted.json`

## 自动清理

创建新任务时会调用清理逻辑，删除 `runs/` 下超过 `BACKTEST_KEEP_DAYS`（默认 30）天的日期桶目录（`YYYY-MM-DD`）。

## 关键配置

在 `app/config.py` 中提供默认值（可通过环境变量覆盖）：

- `CONFIG_ENV=development`
- `LOCAL_AUTH_MOBILE=13800138000`
- `LOCAL_AUTH_PASSWORD=...` 或 `LOCAL_AUTH_PASSWORD_HASH=...`
- `LOCAL_AUTH_USER_ID=1`
- `LOCAL_AUTH_IS_ADMIN=true`
- `JWT_EXPIRES_HOURS=24`
- `SECRET_KEY=...`
- `RQALPHA_BUNDLE_PATH=/home/app/.rqalpha/bundle`
- `RQALPHA_COMMAND=`（可选，例：`/home/app/backquant/backtest/.venv/bin/rqalpha` 或 `python -m rqalpha`）
- `BACKTEST_BASE_DIR=/home/app/rqalpha_platform_storage`
- `BACKTEST_RENAME_DB_PATH=`（可选，默认 `<BACKTEST_BASE_DIR>/backtest_meta.sqlite3`）
- `BACKTEST_TIMEOUT=900`
- `BACKTEST_COMPILE_TIMEOUT=10`
- `BACKTEST_KEEP_DAYS=30`
- `BACKTEST_IDEMPOTENCY_WINDOW_SECONDS=30`
- `BACKTEST_ALLOWED_FREQUENCIES=1d`（可配置为逗号分隔白名单）

## Research API (Jupyter 工作台)

Base URL: `http://127.0.0.1:54321/api/research`

除 `/api/login` 外，接口需携带 `Authorization: <token>`。

### 1) 研究对象管理

- `GET /api/research/items`
- `POST /api/research/items`
- `GET /api/research/items/{id}`
- `PUT /api/research/items/{id}`
- `DELETE /api/research/items/{id}`

`Research` 字段结构：

```json
{
  "id": "factor_rotation_v1",
  "title": "因子轮动研究",
  "description": "...",
  "notebook_path": "factor_rotation_v1.ipynb",
  "kernel": "python3",
  "status": "ACTIVE",
  "session_status": null,
  "tags": ["alpha", "rqalpha"],
  "created_at": "2026-02-18T07:00:00+00:00",
  "updated_at": "2026-02-18T07:10:00+00:00"
}
```

### 2) Notebook 会话管理

- `GET /api/research/items/{id}/notebook/session`
- `POST /api/research/items/{id}/notebook/session`
- `POST /api/research/items/{id}/notebook/session/refresh`
- `DELETE /api/research/items/{id}/notebook/session?session_id=sess_xxx`

会话返回结构：

```json
{
  "session": {
    "session_id": "sess_xxx",
    "notebook_url": "https://<same-host>/jupyter/lab/tree/factor_rotation_v1.ipynb?token=...",
    "embed_url": "https://<same-host>/jupyter/lab/tree/factor_rotation_v1.ipynb?token=...",
    "status": "RUNNING",
    "started_at": "2026-02-18T07:00:00+00:00",
    "last_active_at": "2026-02-18T07:05:00+00:00",
    "expires_at": "2026-02-18T09:00:00+00:00"
  }
}
```

说明：

- 默认通过同域路径拼接 `notebook_url`（`RESEARCH_NOTEBOOK_PROXY_BASE`，默认 `/jupyter`）。
- `notebook_path` 必须是相对安全路径，且以 `.ipynb` 结尾。未提供或为默认占位路径（`research/notebooks/workbench.ipynb` 或 `workbench.ipynb`）时，会回退到 `<research_id>.ipynb`。
- 创建会话时会确保 notebook 文件存在且可写（不存在时自动创建最小模板）。
- 推荐在网关层把该路径反向代理到 Jupyter 服务，以避免跨域 cookie 与 iframe 限制。
- 该 Blueprint 对自身响应移除了 `X-Frame-Options`，并设置 `Content-Security-Policy: frame-ancestors 'self'`（若未设置）。
- 列表接口会为每个 item 补充 `session_status`（无会话时为 `null`）。

### 3) Research 错误格式

Research API 错误统一：

```json
{
  "message": "..."
}
```

常见状态码：`400/401/404/409/500`。

### 4) Research 相关配置

- `RESEARCH_PUBLIC_BASE_URL=`（可选，未设置时使用请求 Host）
- `RESEARCH_NOTEBOOK_PROXY_BASE=/jupyter`
- `RESEARCH_NOTEBOOK_API_BASE=`（可选，默认使用同域 `/jupyter`）
- `RESEARCH_NOTEBOOK_API_TOKEN=`（可选，Jupyter 开启 token 时需要）
- `RESEARCH_NOTEBOOK_ROOT_DIR=`（可选，默认项目根目录；用于 notebook 文件读写路径解析）
- `RESEARCH_NOTEBOOK_DEFAULT_DIR=`（可选，相对目录；未设置时如果 `RESEARCH_NOTEBOOK_ROOT_DIR` 配置了则使用根目录，否则默认 `research/notebooks`）
- `RESEARCH_SESSION_TTL_SECONDS=7200`
