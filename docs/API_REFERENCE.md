# PI Remover API Reference

> **API Version**: 2.12.0 | **PIRemover Core**: v2.12.0
> **Base URL**: `http://localhost:8080` (local) or your Cloud Run URL
> **Architecture**: Modular Microservices (Web Service → API Service)

---

## Overview

The PI Remover API provides real-time Personal Information (PI) redaction as a REST service. It's designed for:

1. **LLM Gateway** - Remove PI before sending data to LLMs (Claude, GPT, etc.)
2. **Application Integration** - Any app that needs real-time PI redaction
3. **Batch Processing** - Process multiple texts in a single request
4. **Web Service Backend** - Web Service calls the API Service via HTTP (Hybrid Mode)

### Key Features

- **Ultra-low latency**: <50ms for typical requests
- **Offline-capable**: No external API calls required
- **Docker-ready**: Single container deployment
- **Fast mode**: Optimized for real-time (no NER)
- **JWT Authentication**: Secure Bearer token authentication (required for all endpoints)
- **Model Selection**: Choose spaCy model per request
- **YAML Configuration**: All settings in config files
- **Circuit Breaker**: Resilience for service-to-service calls
- **Redis Rate Limiting**: Shared rate limiting across instances
- **Modular Architecture**: PIRemover Core split into 9 focused modules (v2.12.0)

---

## Architecture Changes

| Feature | Legacy | Current (v2.12.0) |
|---------|--------|--------|
| Configuration | Environment variables | YAML files in `config/` |
| Rate Limiting | In-memory | Redis (with fallback) |
| Logging | Text format | Structured JSON |
| Internal Client | N/A | `pi-internal-web-service` |
| Web→API Auth | N/A | JWT (automatic) |

### New Internal Client

The Web Service uses `pi-internal-web-service` to authenticate with the API:

```yaml
# config/clients.yaml
clients:
  pi-internal-web-service:
    secret: "YOUR_WEB_CLIENT_SECRET_HERE"
    rate_limit: 10000   # Higher limit for internal use
    environment: "internal"
```

---

## API Endpoints Summary

> **Note:** Some endpoints are disabled by default and controlled by feature flags.
> See [HOWTO - Manage API Endpoints](HOWTO.md#how-to-manage-api-endpoints) for details.

### Always-Enabled Endpoints

| Method | Endpoint | Auth Required | Description |
|--------|----------|:-------------:|-------------|
| POST | `/auth/token` | ❌ No | Get JWT bearer token |
| POST | `/v1/redact` | ✅ Yes | Redact PI from single text |
| GET | `/v1/pi-types` | ✅ Yes | List supported PI types |
| GET | `/v1/models` | ✅ Yes | List available spaCy models |
| GET | `/` | ✅ Yes | API info and endpoint listing |

### Optional Endpoints (Disabled by Default)

| Method | Endpoint | Auth Required | Feature Flag | Description |
|--------|----------|:-------------:|--------------|-------------|
| POST | `/v1/redact/batch` | ✅ Yes | `ENABLE_BATCH_ENDPOINT` | Redact multiple texts |
| GET | `/health` | ✅ Yes | `ENABLE_HEALTH_ENDPOINT` | Service health check and metrics |
| GET | `/docs` | ❌ No | `ENABLE_DOCS_ENDPOINT` | Swagger UI documentation |
| GET | `/redoc` | ❌ No | `ENABLE_DOCS_ENDPOINT` | ReDoc documentation |
| GET | `/livez` | ❌ No | `ENABLE_MONITORING_ENDPOINTS` | Kubernetes liveness probe |
| GET | `/readyz` | ❌ No | `ENABLE_MONITORING_ENDPOINTS` | Kubernetes readiness probe |
| GET | `/metrics` | ❌ No | `ENABLE_MONITORING_ENDPOINTS` | Prometheus metrics |

**To enable optional endpoints:** Set the feature flag environment variable to `true` before starting the service.

```powershell
# Example: Enable all optional endpoints
$env:ENABLE_BATCH_ENDPOINT = "true"
$env:ENABLE_HEALTH_ENDPOINT = "true"
$env:ENABLE_DOCS_ENDPOINT = "true"
$env:ENABLE_MONITORING_ENDPOINTS = "true"
```

### Environment-Specific Base URLs

| Environment | Base URL | Description |
|-------------|----------|-------------|
| **DEV** | `http://localhost:8080/dev` | Development environment |
| **PROD** | `http://localhost:9080/prod` | Production environment |

---

## Authentication

**All API endpoints require JWT Bearer token authentication** (except `/auth/token`).

### Obtaining a Token

```bash
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "your-client-id",
    "client_secret": "your-client-secret"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Using the Token

Include the token in the `Authorization` header for all API requests:

```bash
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact john@example.com"}'
```

### Token Details

| Property | Value |
|----------|-------|
| **Algorithm** | HMAC-SHA256 |
| **Expiry** | 30 minutes |
| **Header** | `Authorization: Bearer <token>` |

### Error Responses

| Status | Code | Description |
|--------|------|-------------|
| 401 | `missing_token` | No token provided |
| 401 | `invalid_token` | Token malformed or expired |
| 401 | `token_expired` | Token has expired |
| 401 | `invalid_credentials` | Client ID/secret incorrect |

### Client Credentials

Credentials are configured in `config/clients.yaml`:

```yaml
clients:
  pi-dev-client:
    secret: "YOUR_DEV_CLIENT_SECRET_HERE"
    rate_limit: 1000
    
  # pi-prod-client:  # Uncomment and configure for production
  #   secret: "<generate-unique-secret>"  # Run: python -c "import secrets; print(secrets.token_urlsafe(32))"
  #   rate_limit: 10000
```

### Development Credentials (Quick Start)

For local development and testing:

```
Client ID:     pi-dev-client
Client Secret: YOUR_DEV_CLIENT_SECRET_HERE
```

---

## Endpoints

### POST /v1/redact

Redact PI from a single text string.

#### Request

```http
POST /v1/redact HTTP/1.1
Authorization: Bearer YOUR_ACCESS_TOKEN
Content-Type: application/json

{
    "text": "Contact john@example.com at +91 9876543210",
    "config": {
        "redact_emails": true,
        "redact_phones": true,
        "redact_names": true,
        "redact_emp_ids": true,
        "use_typed_tokens": true
    },
    "include_details": false,
    "request_id": "client-request-123"
}
```

#### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | **Yes** | - | The text to redact |
| `enable_ner` | boolean | No | `true` | Enable spaCy NER (set `false` for 10x faster) |
| `spacy_model` | string | No | `en_core_web_lg` | spaCy model to use (sm/md/lg/trf) |
| `config` | object | No | All enabled | PI types to redact |
| `include_details` | boolean | No | `false` | Return detailed redaction info |
| `request_id` | string | No | Auto-generated | Client-provided request ID |

#### Available spaCy Models

| Model | Description | Speed | Accuracy |
|-------|-------------|-------|----------|
| `en_core_web_sm` | Small (12 MB) | Fastest | Lower |
| `en_core_web_md` | Medium (40 MB) | Fast | Good |
| `en_core_web_lg` | Large (560 MB) | Medium | High |
| `en_core_web_trf` | Transformer (438 MB) | Slowest | Highest |

#### Config Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enable_ner` | boolean | `true` | Enable spaCy NER for name detection (set `false` for 10x faster processing) |
| `redact_emails` | boolean | `true` | Redact email addresses |
| `redact_phones` | boolean | `true` | Redact phone numbers |
| `redact_names` | boolean | `true` | Redact personal names |
| `redact_emp_ids` | boolean | `true` | Redact employee IDs |
| `redact_asset_ids` | boolean | `true` | Redact asset IDs |
| `redact_ip_addresses` | boolean | `true` | Redact IP addresses |
| `redact_urls` | boolean | `true` | Redact URLs (HTTP, HTTPS, FTP) |
| `redact_credentials` | boolean | `true` | Redact passwords/credentials |
| `use_typed_tokens` | boolean | `true` | Use `[EMAIL]`, `[PHONE]` vs `[REDACTED]` |
| **IT/ITSM Options (v2.7)** |  |  |  |
| `redact_ticket_ids` | boolean | `true` | Redact ITSM tickets (INC, RITM, CHG, JIRA) |
| `redact_active_directory` | boolean | `true` | Redact AD names, SAMAccountName, SIDs |
| `redact_remote_access_ids` | boolean | `true` | Redact TeamViewer/AnyDesk IDs |
| `redact_database_strings` | boolean | `true` | Redact DB connection strings with credentials |
| `redact_session_tokens` | boolean | `true` | Redact JWT, session IDs, OAuth tokens |
| `redact_encryption_keys` | boolean | `true` | Redact BitLocker/recovery keys |
| `redact_workplace_info` | boolean | `true` | Redact desk/seat locations, badge numbers |
| `redact_cloud_ids` | boolean | `true` | Redact Azure/AWS/GCP identifiers |
| `redact_license_keys` | boolean | `true` | Redact software license/product keys |
| `redact_chat_handles` | boolean | `true` | Redact @mentions (Slack/Teams) |
| `redact_audit_info` | boolean | `true` | Redact user references in audit logs |

> **Note**: Setting `enable_ner: false` gives ~10x faster processing. The credential detection now properly ignores phrases like "password reset", "forgot password", and "password policy".
>
> **Context Preservation (v2.7)**: IT/ITSM patterns preserve labels and structure. For example, `INC0012345` becomes `INC[TICKET_NUM]` (keeps ticket type).

#### Response (Basic)

```json
{
    "redacted_text": "Contact [EMAIL] at [PHONE]",
    "request_id": "client-request-123",
    "processing_time_ms": 8.5,
    "mode": "full",
    "spacy_model": "en_core_web_lg",
    "used_fallback": false
}
```

#### Response (Fast Mode - No NER)

When `enable_ner: false`:

```json
{
    "redacted_text": "Contact [EMAIL] at [PHONE]",
    "request_id": "client-request-123",
    "processing_time_ms": 2.1,
    "mode": "fast",
    "spacy_model": null,
    "used_fallback": false
}
```

#### Response (With Details)

When `include_details: true`:

```json
{
    "redacted_text": "Contact [EMAIL] at [PHONE]",
    "redactions": [
        {
            "original": "john@example.com",
            "replacement": "[EMAIL]",
            "type": "EMAIL",
            "start": 8,
            "end": 24,
            "confidence": 1.0,
            "method": "regex"
        },
        {
            "original": "+91 9876543210",
            "replacement": "[PHONE]",
            "type": "PHONE",
            "start": 28,
            "end": 43,
            "confidence": 1.0,
            "method": "regex"
        }
    ],
    "request_id": "client-request-123",
    "processing_time_ms": 12.3
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `redacted_text` | string | Text with PI replaced by tokens |
| `redactions` | array | List of redactions (if `include_details: true`) |
| `request_id` | string | Request identifier for tracking |
| `processing_time_ms` | float | Processing time in milliseconds |
| `mode` | string | Processing mode: `full` (with NER) or `fast` (regex only) |
| `spacy_model` | string/null | spaCy model used (null if `enable_ner: false`) |
| `used_fallback` | boolean | `true` if requested model unavailable, fell back to default |

#### Redaction Object

| Field | Type | Description |
|-------|------|-------------|
| `original` | string | Original text that was redacted |
| `replacement` | string | Replacement token used |
| `type` | string | PI type (EMAIL, PHONE, NAME, etc.) |
| `start` | int | Start position in original text |
| `end` | int | End position in original text |
| `confidence` | float | Confidence score (0.0 - 1.0) |
| `method` | string | Detection method (regex, dictionary, context) |

---

### POST /v1/redact/batch

Redact PI from multiple text strings in a single request.

#### Request

```http
POST /v1/redact/batch HTTP/1.1
Content-Type: application/json

{
    "texts": [
        "Email: john@example.com",
        "Phone: +91 9876543210",
        "Contact Rahul Sharma at 1234567"
    ],
    "config": {},
    "include_details": false
}
```

#### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `texts` | array | **Yes** | - | Array of texts to redact |
| `config` | object | No | All enabled | PI types to redact |
| `include_details` | boolean | No | `false` | Return detailed redaction info |

#### Response

```json
{
    "results": [
        {
            "redacted_text": "Email: [EMAIL]",
            "index": 0
        },
        {
            "redacted_text": "Phone: [PHONE]",
            "index": 1
        },
        {
            "redacted_text": "Contact [NAME] at [EMP_ID]",
            "index": 2
        }
    ],
    "request_id": "uuid-v4",
    "total_count": 3,
    "processing_time_ms": 15.2
}
```

---

### GET /health

Health check endpoint for monitoring and load balancers. **Requires authentication.**

#### Request

```http
GET /health HTTP/1.1
Authorization: Bearer YOUR_ACCESS_TOKEN
```

#### Response

```json
{
    "status": "healthy",
    "version": "2.12.0",
    "mode": "full",
    "ner_available": true,
    "available_models": ["en_core_web_lg", "en_core_web_md"],
    "default_model": "en_core_web_lg",
    "uptime_seconds": 3600,
    "requests_processed": 15000,
    "avg_latency_ms": 8.5,
    "errors": 0
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `healthy` or `unhealthy` |
| `version` | string | API version |
| `mode` | string | `fast` (regex-only) or `full` (with NER) |
| `ner_available` | boolean | Whether NER model is loaded |
| `available_models` | array | List of installed spaCy models |
| `default_model` | string | Default spaCy model |
| `uptime_seconds` | int | Seconds since startup |
| `requests_processed` | int | Total requests handled |
| `avg_latency_ms` | float | Average processing time |
| `errors` | int | Total error count |

---

### GET /v1/pi-types

Get list of supported PI types and their tokens. **Requires authentication.**

#### Request

```http
GET /v1/pi-types HTTP/1.1
Authorization: Bearer YOUR_ACCESS_TOKEN
```

#### Response

```json
{
    "pi_types": [
        {"type": "EMAIL", "token": "[EMAIL]", "description": "Email addresses"},
        {"type": "PHONE", "token": "[PHONE]", "description": "Phone numbers"},
        {"type": "NAME", "token": "[NAME]", "description": "Personal names"},
        {"type": "EMP_ID", "token": "[EMP_ID]", "description": "Employee IDs"},
        {"type": "ASSET_ID", "token": "[ASSET_ID]", "description": "Asset IDs"},
        {"type": "IP", "token": "[IP]", "description": "IP addresses"},
        {"type": "URL", "token": "[URL]", "description": "URLs"},
        {"type": "CREDENTIAL", "token": "[CREDENTIAL]", "description": "Passwords/credentials"},
        {"type": "AADHAAR", "token": "[AADHAAR]", "description": "Aadhaar numbers"},
        {"type": "PAN", "token": "[PAN]", "description": "PAN card numbers"},
        {"type": "UPI", "token": "[UPI]", "description": "UPI IDs"}
    ]
}
```

---

### GET /v1/models

Get list of available spaCy NER models and their installation status. **Requires authentication.**

#### Request

```http
GET /v1/models HTTP/1.1
Authorization: Bearer YOUR_ACCESS_TOKEN
```

#### Response

```json
{
    "models": [
        {
            "name": "en_core_web_sm",
            "installed": false,
            "is_default": false,
            "description": "Small English model (~12MB) - fastest, lower accuracy"
        },
        {
            "name": "en_core_web_md",
            "installed": false,
            "is_default": false,
            "description": "Medium English model (~40MB) - balanced speed/accuracy"
        },
        {
            "name": "en_core_web_lg",
            "installed": true,
            "is_default": true,
            "description": "Large English model (~560MB) - best balance, recommended"
        },
        {
            "name": "en_core_web_trf",
            "installed": false,
            "is_default": false,
            "description": "Transformer English model (~400MB) - highest accuracy, slowest"
        }
    ],
    "installed_count": 1,
    "default_model": "en_core_web_lg",
    "ner_enabled": true
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `models` | array | List of all supported spaCy models |
| `models[].name` | string | Model name (e.g., `en_core_web_lg`) |
| `models[].installed` | boolean | Whether model is installed on server |
| `models[].is_default` | boolean | Whether this is the default model |
| `models[].description` | string | Model description with size/speed info |
| `installed_count` | int | Number of installed models |
| `default_model` | string | Default model used when not specified |
| `ner_enabled` | boolean | Whether NER is enabled in current config |

---

### GET /

Root endpoint - API info and available endpoints. **Requires authentication.**

#### Request

```http
GET / HTTP/1.1
Authorization: Bearer YOUR_ACCESS_TOKEN
```

#### Response

```json
{
    "name": "PI Remover API",
    "version": "2.12.0",
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

## Error Responses

### 400 Bad Request

```json
{
    "error": "validation_error",
    "message": "Request body must contain 'text' field",
    "request_id": "uuid-v4"
}
```

### 413 Payload Too Large

```json
{
    "error": "payload_too_large",
    "message": "Text exceeds maximum length of 100000 characters",
    "request_id": "uuid-v4"
}
```

### 429 Too Many Requests

```json
{
    "error": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Try again in 60 seconds.",
    "retry_after": 60,
    "request_id": "uuid-v4"
}
```

### 500 Internal Server Error

```json
{
    "error": "internal_error",
    "message": "An unexpected error occurred",
    "request_id": "uuid-v4"
}
```

---

## Usage Examples

### cURL

```bash
# Single text redaction
curl -X POST http://localhost:8080/v1/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact john@example.com at +91 9876543210"}'

# Batch redaction
curl -X POST http://localhost:8080/v1/redact/batch \
  -H "Content-Type: application/json" \
  -d '{"texts": ["Email: test@test.com", "Phone: +91 9876543210"]}'

# With details
curl -X POST http://localhost:8080/v1/redact \
  -H "Content-Type: application/json" \
  -d '{"text": "john@test.com", "include_details": true}'

# Health check
curl http://localhost:8080/health
```

### Python

```python
import requests

PI_GATEWAY = "http://localhost:8080"

# Single redaction
def redact_text(text: str) -> str:
    response = requests.post(
        f"{PI_GATEWAY}/v1/redact",
        json={"text": text}
    )
    return response.json()["redacted_text"]

# Batch redaction
def redact_batch(texts: list) -> list:
    response = requests.post(
        f"{PI_GATEWAY}/v1/redact/batch",
        json={"texts": texts}
    )
    return [r["redacted_text"] for r in response.json()["results"]]

# With details
def redact_with_details(text: str) -> dict:
    response = requests.post(
        f"{PI_GATEWAY}/v1/redact",
        json={"text": text, "include_details": True}
    )
    return response.json()

# Example: Safe LLM call
def safe_llm_call(user_message: str) -> str:
    # Remove PI before sending to LLM
    safe_message = redact_text(user_message)

    # Now safe to send to LLM
    llm_response = call_your_llm(safe_message)
    return llm_response
```

### JavaScript/Node.js

```javascript
const PI_GATEWAY = "http://localhost:8080";

// Single redaction
async function redactText(text) {
    const response = await fetch(`${PI_GATEWAY}/v1/redact`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
    });
    const data = await response.json();
    return data.redacted_text;
}

// Batch redaction
async function redactBatch(texts) {
    const response = await fetch(`${PI_GATEWAY}/v1/redact/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texts })
    });
    const data = await response.json();
    return data.results.map(r => r.redacted_text);
}

// Example usage
const userMessage = "Contact john@example.com";
const safeMessage = await redactText(userMessage);
console.log(safeMessage); // "Contact [EMAIL]"
```

### Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "net/http"
)

const PI_GATEWAY = "http://localhost:8080"

type RedactRequest struct {
    Text string `json:"text"`
}

type RedactResponse struct {
    RedactedText     string  `json:"redacted_text"`
    ProcessingTimeMs float64 `json:"processing_time_ms"`
}

func RedactText(text string) (string, error) {
    reqBody, _ := json.Marshal(RedactRequest{Text: text})

    resp, err := http.Post(
        PI_GATEWAY+"/v1/redact",
        "application/json",
        bytes.NewBuffer(reqBody),
    )
    if err != nil {
        return "", err
    }
    defer resp.Body.Close()

    var result RedactResponse
    json.NewDecoder(resp.Body).Decode(&result)

    return result.RedactedText, nil
}
```

---

## Rate Limits

| Tier | Requests/Minute | Burst |
|------|-----------------|-------|
| Default | 100 | 20 |
| Standard | 1000 | 100 |
| Enterprise | Unlimited | 1000 |

---

## Performance

### Latency Targets

| Percentile | Target | Typical |
|------------|--------|---------|
| p50 | <20ms | ~8ms |
| p95 | <50ms | ~25ms |
| p99 | <100ms | ~45ms |

### Throughput

- **Single instance**: ~1000 requests/second
- **Auto-scaling**: Up to 100 instances on Cloud Run

### Text Size Limits

| Limit | Value |
|-------|-------|
| Max text length | 100,000 characters |
| Max batch size | 100 texts |
| Max request body | 10 MB |

---

## Docker Deployment

### Quick Start

```bash
# Pull and run
docker run -d -p 8080:8080 --name pi-gateway pi-gateway:latest

# Or with docker-compose
cd api_service
docker-compose up -d
```

### Build

```bash
# Build image
docker build -t pi-gateway -f api_service/Dockerfile .

# Run
docker run -d -p 8080:8080 \
  -e LOG_LEVEL=INFO \
  --name pi-gateway \
  pi-gateway
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `WORKERS` | `4` | Number of uvicorn workers |
| `MAX_TEXT_LENGTH` | `100000` | Maximum text length |
| `ENABLE_METRICS` | `true` | Enable Prometheus metrics |

---

## Cloud Run Deployment

```bash
# Deploy to Cloud Run
gcloud run deploy pi-gateway \
  --source api_service/ \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 1 \
  --max-instances 10 \
  --timeout 60s
```

---

## Changelog

### v2.12.0 (Current)
- **Modular Architecture** - 9 focused modules for maintainability
- **Hybrid Microservices** - API-first with local fallback
- **Enhanced Observability** - Prometheus metrics, correlation IDs
- **Auto-Scaling** - Platform-aware multiprocessing

### v2.9.0
- **Hybrid Microservices** - Circuit breaker, Redis rate limiting
- **YAML Configuration** - Centralized config files

### v2.5.0
- **JWT Authentication** - Mandatory Bearer token auth
- **Auth endpoint** - POST /auth/token for token generation
- **BuildKit caching** - Faster Docker rebuilds
- **Security hardening** - Auth always enabled

### v2.4.0
- Initial API release
- Single and batch redaction endpoints
- Health check with metrics
- Docker support

---

*Last Updated: 2025-12-16*
