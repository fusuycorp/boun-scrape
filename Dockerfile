# Stage 1: Build virtual environment
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project manifest files
COPY pyproject.toml README.md ./
COPY src ./src

# Create virtualenv and install dependencies and package
RUN uv venv /app/.venv && \
    uv pip install --no-cache -e .

# Stage 2: Minimal production runtime image
FROM python:3.12-slim AS runner

WORKDIR /app

# Create unprivileged user and directories for persistent storage and exports
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -d /app -s /sbin/nologin appuser && \
    mkdir -p /data /app/exports && \
    chown -R appuser:appuser /data /app

# Environment configuration
ENV PATH="/app/.venv/bin:$PATH" \
    DB_PATH=/data/schedules.db \
    COOKIES_PATH=/data/cookies.txt \
    RECAPTCHA_TOKEN_PATH=/data/recaptcha_token.txt \
    EXPORT_DIR=/data/exports \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy virtual environment and source code
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser pyproject.toml README.md ./
COPY --chown=appuser:appuser src ./src

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --retries=3 --start-period=10s \
    CMD python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/")' || exit 1

CMD ["uvicorn", "boun_scrape.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
