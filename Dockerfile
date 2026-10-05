# Dockerfile — Saskia RMS (FastAPI + uv)
# Built for the ServaRica VPS Docker Swarm deployment (parallel run alongside Render).

# ── Stage 1: Build with uv ──
FROM python:3.13-slim AS builder
WORKDIR /build

# Install uv (10-100x faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests and source for layer caching
COPY pyproject.toml uv.lock* ./
COPY app/ ./app/
COPY docs/ ./docs/
COPY scripts/ ./scripts/
COPY README.md ./

# Use uv sync which understands the project layout (hatchling backend).
# We disable editable installs so the .pth files don't reference /build
# (we copy the venv to /opt/venv at runtime).
# The .venv lives at /build/.venv; we'll move it to /opt/venv at runtime
# so the shebangs all match the runtime path.
RUN uv sync --no-dev --no-install-project && \
    uv pip install --python /build/.venv/bin/python --no-editable --no-cache .

# ── Stage 2: Runtime ──
FROM python:3.13-slim AS runtime
WORKDIR /app

# Copy the installed venv (always at /opt/venv at runtime)
COPY --from=builder /build/.venv /opt/venv

# Fix entry-point shebangs: uv sync set them to /build/.venv/bin/python
# but the venv is now at /opt/venv at runtime. Patch all scripts.
RUN find /opt/venv/bin -type f -executable | xargs sed -i 's|#!/build/.venv/bin/python|#!/opt/venv/bin/python|g'

# Copy source (smaller — no .venv, no .git)
COPY --from=builder /build/app /app/app
COPY --from=builder /build/docs /app/docs
COPY --from=builder /build/scripts /app/scripts
COPY --from=builder /build/README.md /app/README.md

# Make venv the default python path
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AIW_SASKIA_DB_PATH=/data/rms.sqlite \
    PORT=8000 \
    BIND_HOST=0.0.0.0 \
    AIW_SASKIA_LOG_DIR=/var/log/sazon

# Create data + log dirs
RUN mkdir -p /data /var/log/sazon

EXPOSE 8000

# Health check via the unauthenticated /healthz endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).read()" || exit 1

# Run migrations on every boot (idempotent — uses schema_version), then start uvicorn.
# `--reload` is OFF in prod. The lifespan in app/rms/main.py also calls init_db() so this
# is a belt-and-suspenders to make sure migrations apply even if the lifespan fails.
CMD ["sh", "-c", "aiw-sazon migrate && exec uvicorn app.rms.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
