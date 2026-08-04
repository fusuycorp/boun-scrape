# Stage 1: Build virtual environment
FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency manifest files
COPY pyproject.toml uv.lock ./

# Create virtualenv and install dependencies using uv cache mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Stage 2: Minimal runtime image
FROM python:3.11-slim AS runner

WORKDIR /app

# Environment configuration
ENV PATH="/app/.venv/bin:$PATH" \
    DB_PATH=/data/schedules.db \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy application source files and seed data
COPY pyproject.toml ./
COPY departments_all.json* ./
COPY app ./app

# Create directory for SQLite database storage
RUN mkdir -p /data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
