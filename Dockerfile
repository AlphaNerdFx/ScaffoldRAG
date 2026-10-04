# =============================================================================
# Stage 1: Dependency Builder (< 90 seconds build time)
# =============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    binutils \
    && rm -rf /var/lib/apt/lists/*

# Create isolated virtual environment
RUN python -m venv /build/.venv
ENV PATH="/build/.venv/bin:$PATH"

# Copy package metadata, frozen lockfile, and README
COPY pyproject.toml poetry.lock README.md ./
COPY app /build/app

# Direct wheel installation via pip
RUN pip install --no-cache-dir "poetry-core>=1.8.0" && \
    pip install --no-cache-dir .

# Strip debug symbols, delete tests/examples, and purge pip/setuptools from runtime venv
RUN find /build/.venv -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true && \
    find /build/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /build/.venv -type d -name "examples" -exec rm -rf {} + 2>/dev/null || true && \
    find /build/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /build/.venv -name "*.pyc" -delete && \
    pip uninstall -y pip setuptools wheel

# =============================================================================
# Stage 2: Hardened Minimal Production Runtime Image (Target: <= 450 MB)
# =============================================================================
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    FASTEMBED_CACHE_PATH="/app/.cache"

# Add unprivileged runtime user (UID 10001) - NO apt-get curl needed
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -d /app -s /sbin/nologin appuser

# Copy stripped virtual environment from builder stage
COPY --from=builder --chown=appuser:appuser /build/.venv /app/.venv

# Copy application source, data assets, and all documentation
COPY --chown=appuser:appuser app /app/app
COPY --chown=appuser:appuser data /app/data
COPY --chown=appuser:appuser docs /app/docs
COPY --chown=appuser:appuser README.md LICENSE SECURITY.md CODE_OF_CONDUCT.md CONTRIBUTING.md /app/

# Allocate writable directories for FastEmbed model cache and SQLite WAL journaling
RUN mkdir -p /app/data /app/.cache && \
    chown -R appuser:appuser /app/data /app/.cache && \
    chmod 775 /app/data /app/.cache

USER appuser

EXPOSE 8000

# Native standard library health check (avoids external curl dependency)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]