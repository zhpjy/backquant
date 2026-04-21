# BackQuant Host `bq` via `uv` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为宿主机上的 AI 提供稳定的 `./bin/bq` 入口，并使用 `backtest/pyproject.toml` 的最小 `uv` 环境运行现有 CLI。

**Architecture:** 保持 CLI 业务代码不变，只新增宿主机运行层。`backtest/pyproject.toml` 负责最小依赖，`bin/bq` 负责统一入口，`backtest/AI.md` 负责宿主机使用说明。

**Tech Stack:** Python, uv, shell script, Click, requests

---

### Task 1: 增加宿主机最小依赖定义

**Files:**
- Create: `backtest/pyproject.toml`

- [ ] **Step 1: 写最小依赖定义**

```toml
[project]
name = "backquant-bq-cli"
version = "0.1.0"
description = "Host-side uv environment for the BackQuant bq CLI"
requires-python = ">=3.10"
dependencies = [
  "click>=8.3.1",
  "requests>=2.32.5",
]

[tool.uv]
package = false
```

- [ ] **Step 2: 运行依赖安装验证**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && uv sync --project backtest`
Expected: 成功创建或更新 `backtest/.venv`

### Task 2: 增加统一入口脚本

**Files:**
- Create: `bin/bq`

- [ ] **Step 1: 写入口脚本**

```sh
#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

exec uv run --project "$REPO_ROOT/backtest" python "$REPO_ROOT/backtest/bq" "$@"
```

- [ ] **Step 2: 设置可执行权限**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && chmod +x bin/bq`
Expected: `bin/bq` 可直接执行

- [ ] **Step 3: 运行帮助命令验证**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && ./bin/bq --help`
Expected: 输出 `bq` 顶层帮助

### Task 3: 增加 AI 使用说明

**Files:**
- Create: `backtest/AI.md`

- [ ] **Step 1: 写说明文件**

```md
# AI 使用 `bq`

## 初始化

在宿主机执行：

```bash
uv sync --project backtest
```

## 环境变量

- `BQ_BASE_URL`
- `BQ_TOKEN`
- 或 `BQ_USERNAME` / `BQ_PASSWORD`

## 调用方式

统一使用仓库根目录下的：

```bash
./bin/bq ...
```
```

- [ ] **Step 2: 验证文档与实际入口一致**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && ./bin/bq strategy --help`
Expected: 成功输出 `strategy` 子命令帮助
