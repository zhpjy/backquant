# BackQuant Quantitative Backtesting Platform

English | [简体中文](README.md)

> Important: The demo site is live. Please use it gently: https://my.clawbot.help/
> Default username/password: `admin` / `pass123456`

<u>**Fully self-hosted: strategies and data run locally without relying on any third-party platform, which protects privacy and allows deep customization.**</u>

This repository includes a backend (Flask + RQAlpha) and a frontend (Vue 3), plus an integrated Research workspace (Jupyter Lab).
It supports **RQAlpha daily stock backtesting** and **VnPy futures CTA visual backtesting**, and can import futures data from the rqalpha bundle into MariaDB with one click.
**Docker is the recommended deployment** so you can pull the image and run it directly with Flask, Jupyter, Nginx, and the built frontend.

## I. Docker Installation & Deployment

### Install Docker

```bash
sudo curl -fsSL https://get.docker.com | sh
```

### Notes Before Install

1. **RQAlpha daily data covers 2005-01 through 2026-02.** The archive is about 1 GB, so download and extraction can take a while.
2. **After Docker build completes, wait for the bundle download to finish before logging in.**
3. **Prepare at least 5 GB of disk space for running the system.**

### Install & Start (Docker Compose)

Docker Compose uses named volumes to persist all data by default. The download logic runs inside the container entrypoint:
on first start it downloads market data to `/data/rqalpha/bundle`, and later restarts reuse the same volume without downloading again.

```bash
cp .env.example .env
docker compose up --build -d
```

### RQAlpha & Daily Bundle Data

- The Docker image already includes RQAlpha (`rqalpha==6.1.2`).
- The image also preinstalls VnPy 4.3.0 (including `vnpy_ctastrategy`, `vnpy_mysql`, etc.), with support for futures CTA strategy backtesting.
- The image preinstalls common quant libraries: `numpy`, `pandas`, `statsmodels`, `scikit-learn`
- A default `demo` strategy is preloaded and can be run directly from the strategy list.
- The daily bundle is updated monthly: on container start, a cron entry is created (`/etc/cron.d/rqalpha-bundle`, default is 03:00 on the 1st of each month).
- To change the schedule, set `RQALPHA_BUNDLE_CRON` (for example `0 4 1 * *`).
- To disable auto updates, set `RQALPHA_BUNDLE_CRON=off`.
- To skip the first-time download, set `RQALPHA_BUNDLE_BOOTSTRAP=0` (only recommended if you already have a bundle prepared).

### Access

- Frontend: `http://localhost:8088`
- First login credentials: `admin` / `pass123456` (change in `.env`)

Note: Backend API and Jupyter are reverse-proxied under the same domain (`/api`, `/jupyter`), so you typically do not need to access their ports directly.

### Screenshots

![Screenshot 0](images/screen0.png?v=2)
![Screenshot 1](images/screen1.png?v=2)
![Screenshot 3](images/screen3.png?v=2)

## II. Configuration

Backend configuration is mainly in `backtest/.env.wsgi`:

- `SECRET_KEY` JWT signing key, must be changed
- `LOCAL_AUTH_MOBILE` / `LOCAL_AUTH_PASSWORD` default admin username/password (seeded into the auth database)
- `LOCAL_AUTH_PASSWORD_HASH` optional, bcrypt hash overrides plaintext password
- `RESEARCH_NOTEBOOK_*` Jupyter-related settings
- Note: Jupyter token can be empty (empty means token auth disabled; only recommended for LAN/local use).

Frontend supports two ways to configure API base:

- Build-time environment variable `VUE_APP_API_BASE`
- Runtime `frontend/public/config.js` (no rebuild needed)

## III. Other Notes

### Docker Volume Persistence

All important data is stored in Docker named volumes. **Rebuilding images, upgrading, or restarting containers will not delete your data**:

| Volume Name | Mount Path | Contents |
|------------|---------|---------|
| `mariadb_data` | MariaDB `/var/lib/mysql` | Database data (users, market-data tasks, backtest metadata, etc.) |
| `backtest_data` | Container `/data/backtest` | Backtest results, strategy files, logs |
| `rqalpha_bundle` | Container `/data/rqalpha/bundle` | RQAlpha market data bundle |
| `notebooks` | Container `/data/notebooks` | Jupyter Notebook files |

**Impact of common operations on data:**

```bash
docker compose build          # ✅ Safe: rebuilds images only, volumes are untouched
docker compose up -d          # ✅ Safe: volumes are mounted back automatically when containers are recreated
docker compose down           # ✅ Safe: stops and removes containers, volumes are kept
docker compose down -v        # ⚠️ Dangerous: removes all volumes too, data is permanently lost
```

### Jupyter Examples

- Example Notebook: `docs/notebooks/example.ipynb`
- Details: `docs/jupyter.md`

### Nginx Reverse Proxy

See `docs/nginx.md` for production reference.

### API Docs

Backend API docs: `backtest/README.md`.

### License

Apache-2.0. See `LICENSE`.
