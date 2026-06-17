FROM python:3.11-slim

# Copy uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy package management files first to leverage build cache
COPY pyproject.toml uv.lock ./

# Install dependencies using uv into a virtualenv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy the backend code
COPY . .

# Set environment variables (prepend virtualenv to PATH)
ENV PATH="/app/.venv/bin:$PATH"
ENV DB_PATH=/data/schedules.db
ENV PYTHONUNBUFFERED=1

# Create data directory for SQLite
RUN mkdir -p /data

EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
