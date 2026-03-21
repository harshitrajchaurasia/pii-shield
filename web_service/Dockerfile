# syntax=docker/dockerfile:1.4
# PI Remover Web Service - Docker Image
# Enterprise-grade security hardened container
# Full mode with spaCy NER enabled by default
# Uses BuildKit cache for faster rebuilds

FROM python:3.11-slim

# Security: Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    LOG_LEVEL=INFO \
    # Security settings
    ENVIRONMENT=production \
    JWT_EXPIRY_MINUTES=30 \
    # Default dev credentials (override in production with secrets)
    AUTH_CLIENTS=dev-client:devsecret123456789012345678901234:development \
    RATE_LIMIT_ENABLED=true \
    AUDIT_LOGGING_ENABLED=true \
    MAX_FILE_SIZE=524288000 \
    QUARANTINE_SUSPICIOUS=true \
    # Hybrid mode: API service URL (override in docker-compose)
    API_URL=http://localhost:8080 \
    # Web service client credentials for API auth (override in production)
    WEB_CLIENT_ID=pi-internal-web-service \
    WEB_CLIENT_SECRET=change-me-in-production

# Set working directory
WORKDIR /app

# Install system dependencies (rarely changes - cached)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies FIRST (cached unless requirements.txt changes)
COPY web_service/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Download spaCy model (cached - only runs once)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install spacy && \
    python -m spacy download en_core_web_lg

# Create directories with secure permissions
RUN mkdir -p /app/uploads /app/logs && \
    chmod 700 /app/uploads /app/logs

# Security: Create non-root user with restricted shell
RUN useradd -m -u 1000 -s /usr/sbin/nologin appuser

# Copy application code LAST (changes frequently, but packages already cached)
# Core PI Remover modules (for local fallback)
COPY src/pi_remover/ ./pi_remover/
COPY security.py .
COPY data/ ./data/

# Web service files (hybrid mode with API + local fallback)
COPY web_service/app.py ./app.py
COPY web_service/api_client.py .
COPY web_service/templates templates/
COPY web_service/static static/

# Shared modules (config loading, logging)
COPY shared/ ./shared/
COPY config/ ./config/

# Set ownership and permissions
RUN chown -R appuser:appuser /app && \
    chmod -R 550 /app && \
    chmod -R 770 /app/uploads /app/logs && \
    chmod -R 555 /app/templates /app/static

# Security: Clean up
RUN apt-get remove -y gcc && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache

# Security: Switch to non-root user
USER appuser

# Set upload directory to the secure location
ENV UPLOAD_DIR=/app/uploads

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run the web service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
