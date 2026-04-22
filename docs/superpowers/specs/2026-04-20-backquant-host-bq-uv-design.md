# BackQuant 宿主机 `bq` + `uv` 设计

日期：2026-04-20
状态：已确认

## 目标

让运行在宿主机上的 AI 可以直接调用 `bq`，而不依赖 `docker exec` 进入容器。

## 背景

- AI 运行在宿主机上，不在容器内。
- `bq` 的工作对象是本地策略文件。
- `bq` 当前通过 HTTP 调用远端 BackQuant API，不需要直接进入后端容器执行。

在这个模型下，如果仍通过 `docker exec` 运行 `bq`，会引入文件路径、工作目录和本地缓存位置不一致的问题。

## 设计选择

### 方案 A：`backtest/pyproject.toml` + 宿主机直接 `uv run`

选用此方案。

做法：

- 在 `backtest/` 下新增一个只服务 `bq` CLI 的 `pyproject.toml`。
- 依赖仅包含 `click` 和 `requests`。
- AI 与人工统一使用 `uv run --project <repo>/backtest python <repo>/backtest/bq ...` 启动 CLI。

优点：

- 宿主机和 AI 直接使用同一份本地文件。
- 不影响 Docker 后端现有 `requirements.txt` 和镜像构建。
- `pyproject.toml` 范围限定在 `backtest/`，不会误导为整个仓库切换到 `uv`。
- 不额外引入包装脚本，结构更简单。

缺点：

- 同时存在 `requirements.txt` 和 `pyproject.toml` 两套依赖定义。

### 方案 B：根目录 `pyproject.toml`

不选。

原因：

- 会让人误以为整个仓库都迁移到 `uv`。
- 与当前 Docker 依赖管理边界不够清晰。

## 文件职责

### `backtest/pyproject.toml`

- 定义宿主机运行 `bq` 的最小 Python 依赖。
- 不参与 Docker 镜像依赖安装。

### `backtest/AI.md`

- 面向 AI 使用场景说明宿主机运行方式。
- 说明如何初始化 `uv` 环境、需要哪些环境变量、如何调用 `uv run --project backtest python backtest/bq ...`。

## 行为约束

- 不改现有 CLI 业务逻辑。
- 不改 `backtest/requirements.txt`。
- 不改 Docker Compose。
- 不在 README 中新增本次说明，统一写入 `backtest/AI.md`。

## 使用方式

1. 在宿主机执行 `uv sync --project backtest` 初始化最小依赖。
2. 配置 `BQ_BASE_URL` 与鉴权环境变量。
3. AI 与人工统一使用 `uv run --project backtest python backtest/bq ...`。

## 风险与取舍

### 远端 API 地址可达性

宿主机版 `bq` 依赖 `BQ_BASE_URL` 可访问后端 API。若后端未暴露宿主机可达地址，CLI 无法工作。

本次实现不处理网络暴露问题，只约定通过环境变量传入。

### 双依赖文件并存

`requirements.txt` 和 `pyproject.toml` 会短期并存。

这是刻意接受的取舍，因为两者服务对象不同：

- `requirements.txt` 服务 Docker 后端镜像
- `pyproject.toml` 服务宿主机 `bq`
