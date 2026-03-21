# syntax=docker/dockerfile:1.4
# PI Remover API - Docker Image
# Enterprise-grade security hardened container
# Full mode with spaCy NER enabled by default
# Uses BuildKit cache for faster rebuilds

FROM python:3.11-slim

# Security: Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    LOG_LEVEL=INFO \
    MAX_TEXT_LENGTH=100000 \
    MAX_BATCH_SIZE=100 \
    ENABLE_NER=true \
    # Security settings
    ENVIRONMENT=production \
    JWT_EXPIRY_MINUTES=30 \
    # Default dev credentials (override in production with secrets)
    AUTH_CLIENTS=dev-client:devsecret123456789012345678901234:development \
    RATE_LIMIT_ENABLED=true \
    RATE_LIMIT_REQUESTS=100 \
    RATE_LIMIT_WINDOW_SECONDS=60 \
    AUDIT_LOGGING_ENABLED=true

# Set working directory
WORKDIR /app

# Security: Install dependencies first (for better caching)
# Uses BuildKit cache mount to persist pip cache across builds
COPY api_service/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Install spaCy and download the English model (cached)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install spacy && \
    python -m spacy download en_core_web_lg

# Copy core PI Remover library package
COPY src/pi_remover/ ./pi_remover/

# Copy security module (root level for backwards compatibility)
COPY security.py .

# Copy data files (names dictionary)
COPY data/ ./data/

# Copy shared modules (config loading)
COPY shared/ ./shared/
COPY config/ ./config/

# Copy API application
COPY api_service/app.py .

# Security: Create audit log directory
RUN mkdir -p /app/logs

# Security: Create non-root user with restricted permissions
RUN useradd -m -u 1000 -s /usr/sbin/nologin appuser && \
    chown -R appuser:appuser /app && \
    chmod -R 550 /app && \
    chmod 770 /app/logs

# Security: Remove unnecessary packages and clean up
RUN apt-get update && \
    apt-get remove -y --auto-remove && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache

# Security: Switch to non-root user
USER appuser

# Security: Set read-only filesystem hint (use with --read-only in docker run)
# docker run --read-only --tmpfs /tmp pi-gateway

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Security: Don't run as PID 1 (use tini or dumb-init in production)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
