# syntax=docker/dockerfile:1
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first so this layer is cached until the lockfile changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-install-project
COPY app ./app

FROM python:3.13-slim
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8000
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health/live',timeout=2)"
# --proxy-headers: trust X-Forwarded-For from the host's load balancer so rate limits see real client IPs.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
