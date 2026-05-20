FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly
# (Extracted from pyproject.toml)
RUN pip install --no-cache-dir \
    beautifulsoup4>=4.14.3 \
    fastapi>=0.136.1 \
    "passlib[bcrypt]>=1.7.4" \
    "bcrypt<4.1" \
    "python-jose[cryptography]>=3.5.0" \
    python-multipart>=0.0.29 \
    requests>=2.33.1 \
    uvicorn>=0.47.0

# Copy the backend code
COPY . .

# Set environment variables
ENV DB_PATH=/data/schedules.db
ENV PYTHONUNBUFFERED=1

# Create data directory for SQLite
RUN mkdir -p /data

EXPOSE 8000

# Start the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
