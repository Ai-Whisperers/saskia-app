FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for openpyxl + psycopg (Postgres driver)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer)
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install \
    "fastapi>=0.115,<0.116" \
    "uvicorn[standard]>=0.32,<0.33" \
    "sqlalchemy>=2.0,<2.1" \
    "psycopg[binary]>=3.1,<4" \
    "openpyxl>=3.1,<4" \
    "jinja2>=3.1,<4" \
    "python-multipart>=0.0.20" \
    "pydantic>=2.9,<3" \
    "loguru>=0.7,<0.8" \
    "cryptography>=42,<50" \
    "boto3>=1.34,<2" \
    "bcrypt>=4.1,<5" \
    "itsdangerous>=2.2,<3" \
    "apscheduler>=3.10,<4" \
    "supabase>=2.31.0"

# App code
COPY app ./app
COPY installer ./installer

# Non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check for Render
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz').read()" \
    || exit 1

# Render / Fly.io entry point
CMD ["uvicorn", "app.rms.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
