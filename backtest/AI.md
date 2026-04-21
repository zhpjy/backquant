# AI 使用 `bq`

这个仓库的 AI 工作流假设 AI 运行在宿主机上，BackQuant 后端运行在 Docker 中。

## 初始化

在仓库根目录执行：

```bash
uv sync --project backtest
```

这会为宿主机上的 `bq` 准备最小依赖环境。

## 环境变量

运行前需要配置：

- `BQ_BASE_URL`
- `BQ_TOKEN`

如果没有 `BQ_TOKEN`，则配置：

- `BQ_USERNAME`
- `BQ_PASSWORD`

可选：

- `BQ_TIMEOUT_SECONDS`

## 调用入口

统一从仓库根目录调用：

```bash
./bin/bq ...
```

不要使用 `docker exec` 作为主调用路径。

## 常用命令

```bash
./bin/bq strategy create --file ./strategies/demo.py
./bin/bq strategy compile --file ./strategies/demo.py
./bin/bq strategy run --file ./strategies/demo.py --start 2020-01-01 --end 2020-12-31
./bin/bq job show --job-id <job_id>
./bin/bq job result --job-id <job_id>
./bin/bq job log --job-id <job_id>
```

## 工作目录约定

- `--file` 路径相对当前工作目录解释
- `./.bq/jobs.json` 写在当前工作目录下

因此 AI 应在策略项目目录中执行 `./bin/bq ...`
