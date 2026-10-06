FROM python:3.14.8-slim-bookworm AS base

# DECISION: dependencies are installed as root; the server process is not.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin ghostline

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

FROM base AS build

COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
RUN chown -R ghostline:ghostline /app

# Local reload (`docker-compose.dev.yml`) still calls `uv run`.
FROM build AS development

USER ghostline
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# DECISION: the production image does not include the uv binaries. Their Rust
# libraries currently carry fixed high-severity advisories, and the server only
# needs the synced virtualenv.
FROM base AS production

COPY --from=build --chown=ghostline:ghostline /app /app

USER ghostline
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
