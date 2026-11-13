# cropseq backend image.
# 1. Python 3.14 is required, so we do not rely on a host default.
# 2. uv installs exactly the lockfile, without dev dependencies.
# 3. The BARC database and JSON data are copied in; the SQLite cache is runtime only.
# 4. uvicorn listens on $PORT so the host can choose it.

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY data ./data

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["sh", "-c", "uvicorn cropseq.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
