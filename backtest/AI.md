# AI 使用 `bq`

这个仓库的 AI 工作流假设 AI 运行在宿主机上，BackQuant 后端运行在 Docker 中。

## 初始化

在 `backtest` 目录执行：

```bash
uv sync
cp .env.bq.example .env.bq
```

这会为宿主机上的 `bq` 准备最小依赖环境。
`./bq` 会自动加载 `./.env.bq`。

## 环境变量

优先在 `./.env.bq` 中配置：

- `BQ_BASE_URL`
- `BQ_TOKEN`

如果没有 `BQ_TOKEN`，则配置：

- `BQ_USERNAME`
- `BQ_PASSWORD`

可选：

- `BQ_TIMEOUT_SECONDS`

如果当前 shell 已经设置了同名环境变量，则 shell 中的值优先，不会被 `.env.bq` 覆盖。

## 调用入口

统一在 `backtest` 目录中调用：

```bash
./bq ...
```

不要使用 `docker exec` 作为主调用路径。

## 常用命令

```bash
./bq strategy create --file ./strategies/demo.py
./bq strategy compile --file ./strategies/demo.py
./bq strategy run --file ./strategies/demo.py --start 2020-01-01 --end 2020-12-31
./bq job show --job-id <job_id>
./bq job result --job-id <job_id>
./bq job log --job-id <job_id>
```

## 工作目录约定

- `--file` 路径相对当前工作目录解释
- `./.bq/jobs.json` 写在当前工作目录下

因此 AI 应先进入 `backtest` 目录，再执行 `./bq ...`
