# Git Tag GHCR 镜像发布设计

## 背景

当前仓库包含三个需要发布的运行镜像：

- `backend`
- `jupyter`
- `frontend`

其中：

- `backend` 与 `jupyter` 共享 `backtest/Dockerfile`
- `frontend` 使用 `frontend/Dockerfile`

目标是在 GitHub 仓库打版本标签时，由 GitHub Actions 自动构建并推送这三个镜像到 GHCR，避免手工构建和手工发布。

## 目标

- 仅在 push `v*` 格式的 Git tag 时触发发布流程
- 自动构建并推送以下三个 GHCR 镜像
  - `ghcr.io/zhpjy/backquant-backend`
  - `ghcr.io/zhpjy/backquant-jupyter`
  - `ghcr.io/zhpjy/backquant-frontend`
- 每个镜像至少发布两个 tag
  - 当前 Git tag，例如 `v1.2.3`
  - `latest`
- 使用 GitHub Actions 内置凭据完成 GHCR 登录，不引入额外个人令牌

## 非目标

- 不在该流程中执行 `docker compose` 启动、重启或部署
- 不发布 `mariadb`、`db-init` 等非目标服务镜像
- 不在本次变更中引入多架构构建
- 不在本次变更中增加自动发布 Release Note

## 方案选型

### 方案 A：单个 workflow，显式定义三个镜像构建步骤

为三个镜像分别写清楚构建参数和推送目标，在一个 workflow 中顺序执行。

优点：

- 与当前仓库结构最直接对应
- `backend` 与 `jupyter` 共用 Dockerfile 但镜像名不同，显式写法更清晰
- 后续增加构建参数、缓存或单镜像特殊逻辑时更容易维护

缺点：

- YAML 会比 matrix 略长

### 方案 B：单个 workflow，使用 matrix 构建三个镜像

将镜像名、context、Dockerfile 放进矩阵统一处理。

优点：

- YAML 更短

缺点：

- 当前只有三个目标，抽象收益有限
- 共享 Dockerfile 但区分逻辑镜像时，可读性不如显式写法

### 方案 C：拆成三个独立 workflow

优点：

- 完全隔离，单镜像问题不会影响其他 YAML 文件

缺点：

- 重复配置过多
- 权限、触发器、登录和 tag 规则需要重复维护

## 选定方案

采用方案 A：单个 workflow，显式定义三个镜像的构建和推送。

原因：

- 当前需求简单明确，只有三个目标镜像
- 仓库内已有两个 Dockerfile，对应关系固定
- 显式配置更方便后续排查失败构建和调整单镜像逻辑

## 工作流设计

### 触发规则

GitHub Actions workflow 仅在以下条件触发：

- `push.tags: ['v*']`

这保证只有版本标签会触发发布，普通分支提交和非版本 tag 不参与发布。

### 权限

workflow 顶层权限声明为：

- `contents: read`
- `packages: write`

用途：

- 读取仓库代码以执行 Docker build
- 登录 GHCR 并推送镜像

### 登录方式

使用 `docker/login-action`，通过：

- 用户名：`${{ github.actor }}`
- 密码：`${{ secrets.GITHUB_TOKEN }}`

登录 `ghcr.io`。

前提：

- 仓库 Actions 有权限向当前仓库所属命名空间发布 GHCR 包

### Tag 生成规则

从 `github.ref_name` 提取当前 Git tag，例如：

- `v1.2.3`

每个镜像发布两个 tag：

- `${GIT_TAG}`
- `latest`

示例：

- `ghcr.io/zhpjy/backquant-backend:v1.2.3`
- `ghcr.io/zhpjy/backquant-backend:latest`

同样规则适用于 `jupyter` 和 `frontend`。

## 镜像构建设计

### backend

- context：`./backtest`
- dockerfile：`./backtest/Dockerfile`
- image：`ghcr.io/zhpjy/backquant-backend`

### jupyter

- context：`./backtest`
- dockerfile：`./backtest/Dockerfile`
- image：`ghcr.io/zhpjy/backquant-jupyter`

说明：

- `jupyter` 当前在 `docker-compose.yml` 中没有单独 Dockerfile，而是复用 `backtest` 构建产物
- 本次发布流程保持这个事实，不人为拆分 Dockerfile

### frontend

- context：`./frontend`
- dockerfile：`./frontend/Dockerfile`
- image：`ghcr.io/zhpjy/backquant-frontend`

## 参数与环境约束

`frontend/Dockerfile` 支持以下构建参数：

- `VUE_APP_API_BASE`
- `VUE_APP_API_SERVER`

本次工作流先采用空值默认构建，不在 workflow 中额外注入环境特定地址。原因如下：

- 当前需求是做版本镜像发布，不是环境部署
- 仓库现有 compose 配置也允许这些参数为空
- 若未来需要面向特定环境固化前端接口地址，应在后续单独设计

## 失败与可观测性

若任意一个镜像构建或推送失败，workflow 应整体失败，避免版本 tag 下只有部分镜像发布成功。

工作流日志需要能直接看出：

- 当前处理的是哪个 Git tag
- 正在构建哪个镜像
- 推送目标是哪个 GHCR 包名

## 测试与验证

本次实现至少验证以下内容：

1. workflow YAML 语法正确
2. 镜像名与 tag 拼接逻辑正确
3. `backend` 和 `jupyter` 确实分别推送到不同 GHCR 仓库名
4. 触发器限制为 `v*`

由于本地环境不能真实触发 GitHub-hosted Actions，本次验证以静态检查、文件审阅和必要的命令级校验为主。

## 计划修改文件

- 新增 `.github/workflows/release-images.yml`
- 视需要补充 `README` 或相关文档中的发布说明

## 风险与后续演进

### 风险

- `latest` 会在每次 `v*` 发布时被覆盖，这是预期行为，但要求使用者理解其含义是“最近一次标签发布”
- `backend` 与 `jupyter` 共享同一 Dockerfile，意味着二者镜像内容当前应保持一致；如果未来运行时职责发生明显分化，需要重新拆分 Dockerfile
- 若仓库包权限未开启，GHCR 推送会在 Actions 中失败

### 后续可演进项

- 为镜像增加 `sha` 标签
- 增加 Buildx 缓存以加快重复构建
- 增加多架构发布
- 在 README 中加入 GHCR 拉取示例
