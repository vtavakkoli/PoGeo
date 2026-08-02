# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system --gid 10001 pogeo \
    && adduser --system --uid 10001 --ingroup pogeo --home /app pogeo

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip \
    && python -m pip install . \
    && python -m compileall -q /usr/local/lib/python3.12/site-packages/pogeo

COPY config ./config
COPY web ./web

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=5s --timeout=3s --start-period=30s --start-interval=2s --retries=8 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=2)"

CMD ["uvicorn", "pogeo.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--loop", "uvloop", "--http", "httptools", "--no-access-log", "--timeout-keep-alive", "5", "--limit-concurrency", "1000", "--backlog", "2048"]

FROM runtime AS test
USER root
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install ".[dev]"
COPY tests ./tests
COPY scripts ./scripts
RUN mkdir -p /reports && chown -R 10001:10001 /reports
USER 10001:10001
CMD ["pytest"]
