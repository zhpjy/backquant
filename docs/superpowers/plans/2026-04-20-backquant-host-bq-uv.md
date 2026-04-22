# BackQuant Host `bq` via `uv` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为宿主机上的 AI 提供直接的 `uv run --project backtest python backtest/bq ...` 调用方式，并使用 `backtest/pyproject.toml` 的最小 `uv` 环境运行现有 CLI。

**Architecture:** 保持 CLI 业务代码不变，只新增宿主机运行层。`backtest/pyproject.toml` 负责最小依赖，`backtest/AI.md` 负责宿主机使用说明，AI 与人工直接通过 `uv run --project backtest python backtest/bq ...` 调用现有入口。

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

### Task 2: 增加 AI 使用说明

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

统一从仓库根目录执行：

```bash
uv run --project backtest python backtest/bq ...
```
```

- [ ] **Step 2: 验证文档与实际入口一致**

Run: `cd /home/zhpjy/.paseo/worktrees/39as1sap/idiotic-chipmunk && uv run --project backtest python backtest/bq strategy --help`
Expected: 成功输出 `strategy` 子命令帮助
