# BackQuant AI CLI 设计

日期：2026-04-20
状态：待评审草案

## 目标

设计第一版用于 AI 辅助 RQAlpha 策略开发与调试的 CLI。

这个 CLI 面向 AI 调用，默认输出 JSON，目标是让 AI 围绕本地策略文件持续迭代，同时复用现有远端 BackQuant 服务提供的编译、执行、日志和结果能力。

## 范围

本设计第一版只覆盖：

- RQAlpha 策略开发与调试
- 本地 Python 策略文件作为权威源码
- 通过现有 BackQuant HTTP API 进行远端执行
- 用最小本地状态维护 `job_id -> 文件` 的映射

本设计不覆盖：

- 因子研究工作流
- Notebook 驱动的 AI 工作流
- VnPy CTA 工作流
- 多用户冲突管理
- 远端 API 改动
- 丰富的本地项目元数据或实验追踪

## 约束与要求

- AI 是第一调用者。
- CLI 采用本地代理式工具模型。
- 远端 BackQuant 逻辑保持不变。
- 策略执行沿用现有远端流程：
  1. 保存策略
  2. 按 `strategy_id` 运行
  3. 查看任务状态、结果和日志
- 本地文件是开发主副本。
- 远端策略只是本地文件的执行镜像。
- 命令默认输出 JSON。
- CLI 的本地状态尽量简单。

## 备选方案

### 方案 A：远端 API 的薄封装 CLI

几乎直接把 BackQuant HTTP API 暴露为 CLI 命令。

优点：

- 实现最快
- CLI 行为最少

缺点：

- 本地文件工作流弱
- 不利于 AI 围绕策略文件持续迭代
- 没有本地 `job -> 文件` 关联

### 方案 B：纯本地 CLI

完全围绕本地策略文件执行，不接入远端 BackQuant 任务体系。

优点：

- 运行模型简单
- 不需要远端协同

缺点：

- 与现有 BackQuant 运行方式脱节
- 丢失远端 job 历史、日志和结果
- 不符合 AI 与 BackQuant 分离部署的预期

### 方案 C：复用现有远端 API 的本地代理式 CLI

CLI 面向本地文件工作，但执行时调用现有远端 save/run/job API，不修改远端逻辑。

优点：

- 最符合 AI 围绕本地文件调试的目标
- 复用现有远端行为
- job/result/log 流程不变
- 远端改动风险最低

缺点：

- 需要一层很薄的本地状态
- 远端 `strategy_id` 依赖本地文件命名规则

### 推荐方案

选择方案 C。

它能让 AI 以本地文件为中心工作，同时保留现有 BackQuant 远端行为，并避免后端改造。

## 核心模型

### 权威源码

- 本地 `.py` 文件是唯一权威策略源码。
- 每次运行前，远端策略代码都由本地文件覆盖。

### 远端策略标识

- `strategy_id` 由本地文件名去掉扩展名得到。
- 例如：`foo.py -> foo`

第一版接受这个简单规则，不尝试解决不同目录下同名文件冲突。

### 远端任务标识

- Job 完全由远端 BackQuant 系统管理。
- CLI 从远端获得 `job_id`，不另外发明新的任务模型。

### 本地缓存

CLI 在本地维护一个极小缓存，用来记录某个 `job_id` 是从哪个本地文件提交的。

建议文件：

- `./.bq/jobs.json`

建议结构：

```json
{
  "jobs": {
    "job_20260420_001": {
      "file": "/abs/path/strategies/foo.py",
      "strategy_id": "foo",
      "recorded_at": "2026-04-20T10:30:00Z"
    }
  }
}
```

这份缓存不是权威来源，只是本地方便查询的辅助层。

## 命令模型

第一版 CLI 暴露这些命令：

- `bq strategy create --file PATH`
- `bq strategy list [--q TEXT] [--limit N] [--offset N]`
- `bq strategy compile --file PATH`
- `bq strategy delete --strategy-id ID [--cascade]`
- `bq strategy run --file PATH --start YYYY-MM-DD --end YYYY-MM-DD [--cash ...] [--benchmark ...] [--frequency ...]`
- `bq strategy pull --file PATH`
- `bq job show --job-id ID`
- `bq job result --job-id ID`
- `bq job log --job-id ID`

## 命令行为

### `bq strategy create --file PATH`

行为：

1. 根据 `PATH.stem` 推导 `strategy_id`。
2. 若本地文件已存在，则报错。
3. 在本地写入一份最小 RQAlpha 策略模板。
4. 输出 JSON。

说明：

- 这个命令只初始化本地文件。
- 这个命令不创建或修改远端策略。
- 远端同名策略是否存在，不影响本地 create。

### `bq strategy list`

行为：

1. 调用现有远端策略列表接口。
2. 支持透传 `q`、`limit`、`offset`。
3. 输出包含远端原始响应的 JSON。

说明：

- 这个命令用于查看远端当前有哪些策略。
- 第一版不做本地文件和远端策略的对账。

### `bq strategy compile --file PATH`

行为：

1. 读取本地文件。
2. 根据 `PATH.stem` 推导 `strategy_id`。
3. 调用现有远端编译接口，并把本地代码作为临时代码放入请求体。
4. 输出 JSON。

说明：

- 这个命令不会覆盖远端已保存策略。
- 这个命令用于在运行前做语法和依赖检查。

### `bq strategy run --file PATH ...`

行为：

1. 读取本地文件。
2. 根据 `PATH.stem` 推导 `strategy_id`。
3. 调用现有远端保存策略接口，用本地代码覆盖远端同名策略。
4. 调用现有远端运行接口，以该 `strategy_id` 启动回测。
5. 获得 `job_id`。
6. 将 `job_id -> file` 写入 `./.bq/jobs.json`。
7. 输出 JSON。

说明：

- 这个命令本质上是 `save -> run`。
- 第一版没有单独的 publish 步骤。
- 远端策略被视为本地文件当前可执行镜像。

### `bq strategy pull --file PATH`

行为：

1. 根据 `PATH.stem` 推导 `strategy_id`。
2. 拉取当前远端策略代码。
3. 覆盖写入本地文件。
4. 输出 JSON。

说明：

- 这个命令用于同步或恢复。
- 第一版不提供 merge 行为。

### `bq strategy delete --strategy-id ID [--cascade]`

行为：

1. 调用现有远端删除策略接口。
2. 若指定 `--cascade`，则请求远端连带删除关联 job。
3. 输出包含远端原始响应的 JSON。

说明：

- 这个命令只删除远端策略。
- 第一版不会自动删除任何本地文件。
- 如果远端策略仍被历史 job 引用且未使用 `--cascade`，CLI 直接返回远端错误。

### `bq job show --job-id ID`

行为：

1. 查询现有远端任务状态接口。
2. 从 `./.bq/jobs.json` 查找本地文件映射。
3. 返回包含本地映射和远端原始响应的 JSON。

### `bq job result --job-id ID`

行为：

1. 查询现有远端结果接口。
2. 从 `./.bq/jobs.json` 查找本地文件映射。
3. 返回包含本地映射和远端原始响应的 JSON。

第一版故意保持远端透传，不在 CLI 侧做结果摘要。

### `bq job log --job-id ID`

行为：

1. 查询现有远端日志接口。
2. 从 `./.bq/jobs.json` 查找本地文件映射。
3. 返回包含本地映射和远端原始响应的 JSON。

## JSON 契约

### `run` 成功

```json
{
  "ok": true,
  "data": {
    "job_id": "job_20260420_001",
    "file": "/abs/path/strategies/foo.py",
    "strategy_id": "foo",
    "status": "QUEUED"
  }
}
```

### `run` 失败

```json
{
  "ok": false,
  "error": {
    "code": "REMOTE_ERROR",
    "message": "strategy not found"
  }
}
```

### `compile` 成功

```json
{
  "ok": true,
  "data": {
    "file": "/abs/path/strategies/foo.py",
    "strategy_id": "foo",
    "compile": {
      "ok": true,
      "stdout": "syntax check passed\ndependency check passed",
      "stderr": "",
      "diagnostics": []
    }
  }
}
```

### `compile` 失败

```json
{
  "ok": false,
  "error": {
    "code": "COMPILE_ERROR",
    "message": "syntax error",
    "details": {
      "file": "/abs/path/strategies/foo.py",
      "strategy_id": "foo",
      "stdout": "",
      "stderr": "SyntaxError: invalid syntax",
      "diagnostics": [
        {
          "line": 12,
          "column": 8,
          "level": "error",
          "message": "invalid syntax"
        }
      ]
    }
  }
}
```

### `job` 命令成功返回形态

```json
{
  "ok": true,
  "data": {
    "job_id": "job_20260420_001",
    "file": "/abs/path/strategies/foo.py",
    "strategy_id": "foo",
    "remote": {}
  }
}
```

如果本地缓存中没有对应映射，`file` 返回 `null`。

## 错误处理

建议退出码：

- `0`：成功
- `2`：CLI 参数错误
- `3`：本地文件或本地缓存错误
- `4`：远端请求失败或远端业务错误

CLI 应始终优先返回结构化 JSON，而不是面向人类的自由文本。

## 数据流

### 编译流程

1. 读取本地文件
2. 推导 `strategy_id`
3. 将临时代码提交到远端编译接口
4. 返回结构化编译结果

### 运行流程

1. 读取本地文件
2. 推导 `strategy_id`
3. 覆盖远端策略代码
4. 请求远端运行
5. 获得 `job_id`
6. 更新本地缓存
7. 返回结构化运行结果

### Job 查询流程

1. 查询远端接口
2. 读取本地缓存
3. 返回本地映射和远端原始载荷

## 测试策略

第一版应至少验证：

- 文件名到 `strategy_id` 的推导
- 本地文件读取错误
- 本地缓存创建和更新
- 远端编译透传
- 远端 save 后再 run 的流程
- job 映射查询
- 本地缓存缺失时的行为
- JSON 输出稳定性

第一版应优先做小而确定的 CLI 测试，而不是大范围集成测试。

## 风险与取舍

### 同名文件冲突

两个不同文件如果文件名去扩展名后相同，就会映射到同一个远端 `strategy_id`。

第一版接受这个取舍，以换取简单性。

### 远端策略被覆盖

每次运行本地文件都会覆盖远端同名策略。

这是第一版有意接受的行为，因为远端策略在此模型下是执行镜像，不是独立维护的正式产物。

### 本地缓存不完整

如果 `./.bq/jobs.json` 丢失或不完整，远端 job 查询仍然可用，但 CLI 可能无法报告该 job 对应的本地文件。

这个风险可接受，因为缓存本来就不是权威来源。

## 明确不做的事情

第一版不包括：

- 因子评估命令
- Notebook 编排
- publish/promote 工作流
- 远端策略名前缀
- 基于目录的冲突处理
- CLI 侧结果摘要
- 本地实验数据库
- 双向同步冲突处理

## 下一步

在这份设计被评审和确认之后，下一份产物应当是实现计划，明确 CLI 包结构、API client 层、本地缓存模块和命令处理器的拆分方式。
