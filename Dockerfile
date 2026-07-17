FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HR6107_LISTEN_IP=0.0.0.0 \
    HR6107_WEB_HOST=0.0.0.0 \
    HR6107_DATA_DIR=/data

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 hr6107 \
    && mkdir -p /data \
    && chown -R hr6107:hr6107 /app /data

COPY --chown=hr6107:hr6107 hr6107 ./hr6107
COPY --chown=hr6107:hr6107 run_hr6107.py protocol_profile.json haier_dashboard_v2.html ./

USER hr6107

EXPOSE 8088/tcp 46752/tcp 46753/udp 46754/udp

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8088/health',timeout=3)); raise SystemExit(0 if d.get('ok') else 1)"

CMD ["python", "run_hr6107.py"]
