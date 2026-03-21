# BackQuant Quantitative Backtesting Platform

English | [简体中文](README.md)

> Important: The demo site is live. Please use it gently: https://my.clawbot.help/

This repository includes a backend (Flask + RQAlpha) and a frontend (Vue 3), plus an integrated Research workspace (Jupyter Lab).
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

Docker Compose uses a named volume for the RQAlpha bundle (`rqalpha_bundle`). The download happens in the container entrypoint:
on first start it downloads to `/data/rqalpha/bundle`, and subsequent starts reuse the same volume without re-downloading.

```bash
cp .env.example .env
docker compose up --build -d
```

### RQAlpha & Daily Bundle Data

- The Docker image already includes RQAlpha (`rqalpha==6.1.2`).
- The image also preinstalls common quant libraries: `numpy`, `pandas`, `statsmodels`, `scikit-learn` (`datetime`/`math` are Python standard libraries).
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

![Screenshot 0](images/screen0.png)
![Screenshot 1](images/screen1.png)
![Screenshot 2](images/screen2.png)
![Screenshot 3](images/screen3.png)

## II. Configuration

Backend configuration is mainly in `backtest/.env.wsgi`:

- `SECRET_KEY` JWT signing key, must be changed
- `LOCAL_AUTH_MOBILE` / `LOCAL_AUTH_PASSWORD` default admin username/password (seeded into the auth database)
- `LOCAL_AUTH_PASSWORD_HASH` optional, bcrypt hash overrides plaintext password
- `AUTH_DB_PATH` optional, auth database path (defaults to `<BACKTEST_BASE_DIR>/auth.sqlite3`)
- `RESEARCH_NOTEBOOK_*` Jupyter-related settings
- Note: Jupyter token can be empty (empty means token auth disabled; only recommended for LAN/local use).

Frontend supports two ways to configure API base:

- Build-time environment variable `VUE_APP_API_BASE`
- Runtime `frontend/public/config.js` (no rebuild needed)

## III. Others

### Jupyter Examples

- Example Notebook: `docs/notebooks/example.ipynb`
- Details: `docs/jupyter.md`

### Nginx Reverse Proxy

See `docs/nginx.md` for production reference.

### API Docs

Backend API docs: `backtest/README.md`.

### License

Apache-2.0. See `LICENSE`.

### WeChat

Follow our WeChat public account: ETF量化老司机
