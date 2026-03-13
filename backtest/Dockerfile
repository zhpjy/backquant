FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        cron \
        curl \
        git \
        build-essential \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# Install vnpy 4.3.0 from source
RUN pip install --no-cache-dir \
        "vnpy @ https://github.com/vnpy/vnpy/archive/refs/tags/4.3.0.tar.gz" \
    && pip install --no-cache-dir \
        vnpy_ctastrategy vnpy_ctabacktester vnpy_datamanager \
        vnpy_sqlite vnpy_rqdata vnpy_tushare vnpy_mysql \
        mplfinance \
    && pip install --no-cache-dir numpy==1.26.4

# Install vnpy_ctp from source
RUN pip install --no-cache-dir \
        "vnpy_ctp @ git+https://github.com/vnpy/vnpy_ctp.git" \
    && pip install --no-cache-dir numpy==1.26.4

ENV RQALPHA_IMAGE_BUNDLE_PATH=/opt/rqalpha/bundle
RUN mkdir -p /opt/rqalpha/bundle

COPY . /app
RUN mkdir -p /app/.gunicorn \
    && chmod +x /app/docker-entrypoint.sh

EXPOSE 54321
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.docker.py", "wsgi:app"]
