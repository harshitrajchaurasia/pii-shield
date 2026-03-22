FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    STANDALONE_MODE=true \
    ENVIRONMENT=production \
    LOG_LEVEL=WARNING \
    FILE_UPLOAD_ENABLED=false

WORKDIR /app

# Install core package + web dependencies
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[api,excel]" && \
    pip install --no-cache-dir httpx pdfplumber python-docx python-pptx beautifulsoup4 lxml python-multipart

# Copy web service
COPY web_service/app.py web_service/api_client.py ./web_service/
COPY web_service/templates ./web_service/templates/
COPY web_service/static ./web_service/static/

# Copy shared modules and config
COPY shared/ ./shared/
COPY config/ ./config/
COPY data/ ./data/

# Non-root user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/uploads && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

CMD ["sh", "-c", "cd web_service && uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
