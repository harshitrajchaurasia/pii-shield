# PI Remover API Service (LLM Gateway)

> **Real-time Personal Information (PI) removal API for LLM safety**
> 
> **Architecture:** v2.12.0 Modular Microservices | **PIRemover Core:** v2.12.0

This API service provides real-time PI redaction designed specifically for use as a gateway before sending data to LLMs (Claude, GPT, etc.).

## Key Features

- **YAML Configuration**: All settings in `config/*.yaml` (no environment variables)
- **Redis Rate Limiting**: Shared rate limits across instances (with in-memory fallback)
- **Internal Client**: `pi-internal-web-service` for Web Service communication
- **Structured Logging**: JSON format for ELK/Splunk integration
- **Modular PIRemover Core**: 9 focused modules for maintainability (v2.12.0)

## Quick Start

### Using Docker Compose (Recommended)

```bash
cd api_service
docker-compose up -d

# Get auth token
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id": "pi-dev-client", "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"}'

# Test with token
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" http://localhost:8080/dev/health

curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact john@example.com at +91 9876543210"}'
```

### Using Docker

```bash
# Build
docker build -t pi-gateway -f api_service/Dockerfile .

# Run
docker run -d -p 8080:8080 --name pi-gateway pi-gateway

# Get token first, then test
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id": "pi-dev-client", "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"}'
```

### Local Development

```bash
# Install dependencies
pip install -r api_service/requirements.txt

# Run
cd api_service
uvicorn app:app --host 0.0.0.0 --port 8080 --reload

# Or directly
python app.py
```

### v2.9.0 Microservices Mode

When running with the Web Service:

```bash
# Terminal 1: Redis (optional but recommended)
docker run --rm -p 6379:6379 redis:alpine

# Terminal 2: API Service
cd api_service
uvicorn app:app --reload --port 8080

# Terminal 3: Web Service (calls API)
cd web_service
uvicorn app:app --reload --port 8082
```

## Configuration

Settings are in `config/api_service.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8080
  environment: "development"

pi_remover:
  enable_ner: false         # Set true for full NER mode
  use_typed_tokens: true

cors:
  allowed_origins:
    - "http://localhost:8082"
    - "http://localhost:3000"
```

Client credentials in `config/clients.yaml`:

```yaml
clients:
  pi-dev-client:
    secret: "YOUR_DEV_CLIENT_SECRET_HERE"
    rate_limit: 1000
    
  pi-internal-web-service:   # Used by Web Service
    secret: "YOUR_WEB_CLIENT_SECRET_HERE"
    rate_limit: 10000
```

## Authentication

**All API endpoints require JWT Bearer token authentication** (except `/auth/token`).

### Get Access Token

```bash
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "pi-dev-client",
    "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"
  }'

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Use Token in Requests

```bash
export TOKEN="your-access-token"

curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Email: test@example.com"}'
```

---

## API Endpoints

### Complete Endpoint Reference

| Method | Endpoint | Auth Required | Description |
|--------|----------|:-------------:|-------------|
| POST | `/auth/token` | ❌ No | Get JWT bearer token |
| POST | `/v1/redact` | ✅ Yes | Redact PI from single text |
| POST | `/v1/redact/batch` | ✅ Yes | Redact PI from multiple texts |
| GET | `/health` | ✅ Yes | Service health check and metrics |
| GET | `/v1/pi-types` | ✅ Yes | List supported PI types |
| GET | `/v1/models` | ✅ Yes | List available spaCy models |
| GET | `/` | ✅ Yes | API info and endpoint listing |

### Environment Base URLs

| Environment | Base URL | Ports |
|-------------|----------|-------|
| **DEV** | `http://localhost:8080/dev` | API: 8080, Web: 8082 |
| **PROD** | `http://localhost:9080/prod` | API: 9080, Web: 9082 |

---

### POST /auth/token

Get JWT access token. **No authentication required.**

```bash
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id": "pi-dev-client", "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"}'
```

Redact PI from a single text. **Requires authentication.**

```bash
# Basic request
curl -X POST http://localhost:8080/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Email me at john@example.com"}'

# Response:
{
  "redacted_text": "Email me at [EMAIL]",
  "request_id": "uuid",
  "processing_time_ms": 8.5,
  "mode": "full",
  "spacy_model": "en_core_web_lg",
  "used_fallback": false
}
```

#### Model Selection (v2.7.1)

```bash
# Fast mode - no NER (10x faster)
curl -X POST http://localhost:8080/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Email: test@example.com", "enable_ner": false}'

# Use specific spaCy model
curl -X POST http://localhost:8080/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact John Smith", "spacy_model": "en_core_web_trf"}'
```

**Available Models:** `en_core_web_sm`, `en_core_web_md`, `en_core_web_lg` (default), `en_core_web_trf`

### POST /v1/redact/batch

Redact PI from multiple texts. **Requires authentication.**

```bash
curl -X POST http://localhost:8080/dev/v1/redact/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["email: test@test.com", "phone: +91 9876543210"]}'

# Response:
{
  "results": [
    {"redacted_text": "email: [EMAIL]", "index": 0},
    {"redacted_text": "phone: [PHONE]", "index": 1}
  ],
  "request_id": "uuid",
  "total_count": 2,
  "processing_time_ms": 12.3,
  "mode": "full",
  "spacy_model": "en_core_web_lg",
  "used_fallback": false
}
```

**Model selection:** Use `enable_ner` and `spacy_model` parameters same as single redact.

---

### GET /health

Health check for monitoring. **Requires authentication.**

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/dev/health

# Response:
{
  "status": "healthy",
  "version": "2.8.0",
  "mode": "full",
  "ner_available": true,
  "available_models": ["en_core_web_lg"],
  "default_model": "en_core_web_lg",
  "uptime_seconds": 3600,
  "requests_processed": 1500,
  "avg_latency_ms": 8.5,
  "errors": 0
}
```

---

### GET /v1/pi-types

List supported PI types. **Requires authentication.**

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/dev/v1/pi-types
```

---

### GET /v1/models

List available spaCy NER models. **Requires authentication.**

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/dev/v1/models

# Response:
{
  "models": [
    {"name": "en_core_web_sm", "installed": false, "is_default": false, "description": "Small English model (~12MB)"},
    {"name": "en_core_web_md", "installed": false, "is_default": false, "description": "Medium English model (~40MB)"},
    {"name": "en_core_web_lg", "installed": true, "is_default": true, "description": "Large English model (~560MB)"},
    {"name": "en_core_web_trf", "installed": false, "is_default": false, "description": "Transformer model (~400MB)"}
  ],
  "installed_count": 1,
  "default_model": "en_core_web_lg",
  "ner_enabled": true
}
```

---

### GET /

Root endpoint - API info and available endpoints. **Requires authentication.**

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/

# Response:
{
  "name": "PI Remover API",
  "version": "2.8.0",
  "environment": "DEV",
  "api_prefix": "/dev",
  "endpoints": {
    "auth": "/dev/auth/token",
    "redact": "/dev/v1/redact",
    "batch": "/dev/v1/redact/batch",
    "health": "/dev/health",
    "pi_types": "/dev/v1/pi-types",
    "models": "/dev/v1/models"
  },
  "docs": "/docs"
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ENABLE_NER` | `true` | Enable spaCy NER (set `false` for 10x faster processing) |
| `SPACY_MODEL` | `en_core_web_lg` | Default spaCy model (sm/md/lg/trf) |
| `MAX_TEXT_LENGTH` | `100000` | Max text length |
| `MAX_BATCH_SIZE` | `100` | Max batch size |
| `ENABLE_METRICS` | `true` | Enable metrics |

> **Tip**: Set `ENABLE_NER=false` for production deployments where speed is critical. NER provides better name detection but adds latency.
>
> **Model Selection (v2.7.1)**: You can also select models per-request using the `spacy_model` parameter.

## Python Integration

```python
import requests

PI_GATEWAY = "http://localhost:8080"

def redact_for_llm(text: str) -> str:
    """Remove PI before sending to LLM."""
    response = requests.post(
        f"{PI_GATEWAY}/v1/redact",
        json={"text": text}
    )
    return response.json()["redacted_text"]

# Usage
user_message = "My email is john@company.com"
safe_message = redact_for_llm(user_message)
# safe_message: "My email is [EMAIL]"

# Now safe to send to LLM
llm_response = call_your_llm(safe_message)
```

## Performance

| Metric | Target | Actual |
|--------|--------|--------|
| p50 latency | <20ms | ~8ms |
| p95 latency | <50ms | ~25ms |
| p99 latency | <100ms | ~45ms |
| Throughput | 1000+ req/s | ~1500 req/s |

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│ Application │────▶│ PI Gateway API  │────▶│    LLM      │
│             │     │                 │     │  (Claude,   │
│ "Contact    │     │ Removes PI      │     │   GPT,      │
│  john@..."  │     │ before sending  │     │   etc.)     │
└─────────────┘     │                 │     └─────────────┘
                    │ "Contact        │
                    │  [EMAIL]..."    │
                    └─────────────────┘
```

## Files

```
api_service/
├── app.py              # FastAPI application
├── Dockerfile          # Docker image
├── docker-compose.yml  # Docker Compose config
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Cloud Run Deployment

```bash
gcloud run deploy pi-gateway \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 10
```
