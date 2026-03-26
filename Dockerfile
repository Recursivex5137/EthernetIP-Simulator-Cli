FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-headless.txt /app/requirements-headless.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install -r /app/requirements-headless.txt

COPY sim_cli.py /app/sim_cli.py
COPY src /app/src
COPY examples /app/examples

RUN mkdir -p /data && useradd -m -u 10001 appuser && chown -R appuser:appuser /app /data
USER appuser

VOLUME ["/data"]
EXPOSE 44818/tcp 44818/udp

ENTRYPOINT ["python", "sim_cli.py"]
CMD ["--db-path", "/data/tags.db", "serve", "--host", "0.0.0.0", "--port", "44818", "--status-interval", "30"]
