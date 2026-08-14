FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HRS_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    HRS_DB_PATH=/data/hrs.db \
    HRS_SEED_DEMO=false

WORKDIR /app

COPY docs/setup/text/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY .code /app/.code
RUN mkdir -p /data

WORKDIR /app/.code

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=3)"

CMD ["python", "-m", "scripts.startup.server"]
