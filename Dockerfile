# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project manifest files
COPY pyproject.toml README.md ./
COPY src ./src

# Create virtualenv and install dependencies and package
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv && \
    uv pip install --no-cache -e .

# Stage 2: Minimal production runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Environment configuration
ENV PATH="/app/.venv/bin:$PATH" \
    DB_PATH=/data/schedules.db \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy virtual environment and source code
COPY --from=builder /app/.venv /app/.venv
COPY pyproject.toml README.md ./
COPY src ./src

# Create directory for persistent SQLite database storage and exports
RUN mkdir -p /data /app/exports

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --retries=3 --start-period=10s \
    CMD python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/")' || exit 1

CMD ["uvicorn", "boun_scrape.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
