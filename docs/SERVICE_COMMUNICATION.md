# Service Communication Guide

> **Architecture Version:** 2.12.0 | **PIRemover Core:** v2.12.0
>
> Purpose: a detailed technical reference explaining how the Web Service and API Service communicate, how authentication is performed and managed, how file uploads are validated and processed, and what failure‑handling, retry, and observability mechanisms are in place.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Design Goals & Assumptions](#design-goals--assumptions)
3. [Communication Flow & Sequence Diagrams](#communication-flow--sequence-diagrams)
4. [Authentication & Token Lifecycle](#authentication--token-lifecycle)
5. [PIRemoverAPIClient — internals & resilience](#piremoverapiclient---internals--resilience)
6. [File Upload & Background Processing](#file-upload--background-processing)
7. [Hybrid Redaction routing (API first, local fallback)](#hybrid-redaction-routing-api-first-local-fallback)
8. [Health checks, caching & background monitoring](#health-checks-caching--background-monitoring)
9. [Rate limiting, quotas and configuration](#rate-limiting-quotas-and-configuration)
10. [Logging, Correlation IDs & Audit events](#logging-correlation-ids--audit-events)
11. [Troubleshooting & common failure modes](#troubleshooting--common-failure-modes)
12. [Quick test commands & examples](#quick-test-commands--examples)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER / BROWSER                                      │
│                                    │                                             │
│                    ┌───────────────┴───────────────┐                            │
│                    ▼                               ▼                            │
│            Web Interface                    Direct API Access                   │
│          (HTML Forms/UI)                   (Postman/curl/LLM)                  │
└────────────────────┬───────────────────────────────┬────────────────────────────┘
                     │                               │
                     ▼                               │
┌─────────────────────────────────────────┐          │
│         WEB SERVICE (Port 8082)         │          │
│  - Serves UI, accepts uploads,          │          │
│    orchestrates background processing   │          │
│  - Implements hybrid routing (API first,│          │
│    local fallback), caching & audit     │          │
│                                         │          │
│  Key internal pieces:                   │          │
│   • `PIRemoverAPIClient` (auth, retries)│          │
│   • Upload subsystem (validation, jobs) │          │
│   • Background workers (processing)     │          │
└─────────────────────────────────────────┘          │
                     │  HTTP + JWT Bearer Token    │
                     │  (when calling API)         │
                     ▼                           ▼  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        API SERVICE (Port 8080)                                   │
│  - Core redaction engine (regex, dictionaries, spaCy)                             │
│  - Requires JWT auth for redaction endpoints                                      │
│  - Exposes token endpoint for clients to obtain tokens                            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Design Goals & Assumptions

1. **Separation of concerns** — The Web Service handles UI, file validation, job management, and user interaction; the API Service owns the core redaction logic (regex patterns, dictionary lookups, spaCy NER).
2. **Stateless API** — Each API request is self-contained. The API Service does not persist sessions; the JWT token encodes identity and expiry.
3. **Hybrid resilience** — When the API Service is unavailable, the Web Service falls back to local `PIRemover` library (bundled). This ensures the system never fully blocks user requests.
4. **Configuration hierarchy** — Credentials and settings are loaded in order: Environment Variables → `config/clients.yaml` → hardcoded fallback constants (development only). In production, always configure via YAML or ENV.
5. **Minimal trust boundary** — The Web Service authenticates to the API Service using its own `pi-internal-web-service` identity; external users never receive raw API tokens.
6. **Audit & observability** — Every redaction request is logged with a correlation ID, timing metrics, and success/failure outcome, enabling tracing and audit.

---

## Communication Flow & Sequence Diagrams

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION FLOW                                        │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  Web Service                                              API Service             │
│       │                                                        │                  │
│       │  1. POST /dev/auth/token                              │                  │
│       │     {"client_id": "pi-internal-web-service",          │                  │
│       │      "client_secret": "VjK8mN..."}                    │                  │
│       │ ─────────────────────────────────────────────────────►│                  │
│       │                                                        │                  │
│       │  2. {"access_token": "eyJhbG...",                     │                  │
│       │      "token_type": "bearer",                          │                  │
│       │      "expires_in": 1800}                              │                  │
│       │ ◄─────────────────────────────────────────────────────│                  │
│       │                                                        │                  │
│       │  3. POST /dev/v1/redact                               │                  │
│       │     Authorization: Bearer eyJhbG...                   │                  │
│       │     {"text": "John's SSN is 123-45-6789"}            │                  │
│       │ ─────────────────────────────────────────────────────►│                  │
│       │                                                        │                  │
│       │  4. {"redacted_text": "[NAME]'s SSN is [SSN]",       │                  │
│       │      "entities_found": [...]}                         │                  │
│       │ ◄─────────────────────────────────────────────────────│                  │
│       │                                                        │                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Web Service Endpoints

**Base URL:** `http://localhost:8082` (DEV) | `http://localhost:9082` (PROD)

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| GET | `/` | ❌ | Serve HTML web interface |
| POST | `/api/redact-text` | ❌ | Redact PI from text (calls API Service) |
| POST | `/api/upload` | ❌ | Upload file for processing |
| POST | `/api/process/{job_id}` | ❌ | Start processing uploaded file |
| GET | `/api/status/{job_id}` | ❌ | Get job processing status |
| GET | `/api/download/{job_id}` | ❌ | Download processed file |
| DELETE | `/api/job/{job_id}` | ❌ | Delete job and files |
| GET | `/health` | ❌ | Web service health check |
| GET | `/api/service-info` | ❌ | Service information |
| GET | `/api/status` | ❌ | Overall API connection status |

### Endpoint Details

#### POST `/api/redact-text`
Redact PI from a single text string.

**Request:**
```json
{
  "text": "Contact John Smith at john@example.com or 555-123-4567",
  "enable_ner": true,
  "use_typed_tokens": true
}
```

**Response:**
```json
{
  "redacted_text": "Contact [NAME] at [EMAIL] or [PHONE]",
  "entities_found": [
    {"type": "NAME", "value": "John Smith", "start": 8, "end": 18},
    {"type": "EMAIL", "value": "john@example.com", "start": 22, "end": 38},
    {"type": "PHONE", "value": "555-123-4567", "start": 42, "end": 54}
  ],
  "processing_time_ms": 45.2,
  "mode": "api"
}
```

#### POST `/api/upload`
Upload a file for batch processing.

**Request:** `multipart/form-data` with file

**Response:**
```json
{
  "job_id": "abc123-def456",
  "filename": "data.csv",
  "columns": ["name", "email", "phone", "notes"],
  "row_count": 1500
}
```

#### POST `/api/process/{job_id}`
Start processing an uploaded file.

**Request:**
```json
{
  "columns": ["name", "email", "notes"],
  "enable_ner": false,
  "pi_types": ["EMAIL", "PHONE", "SSN"]
}
```

---

## API Service Endpoints

**Base URL:** `http://localhost:8080/dev` (DEV) | `http://localhost:9080/prod` (PROD)

| Method | Endpoint | Auth | Description |
|--------|----------|:----:|-------------|
| POST | `/auth/token` | ❌ | Obtain JWT access token |
| POST | `/v1/redact` | ✅ | Redact PI from single text |
| POST | `/v1/redact/batch` | ✅ | Redact PI from multiple texts |
| GET | `/health` | ✅ | Health check with metrics |
| GET | `/v1/pi-types` | ✅ | List supported PI types |
| GET | `/v1/models` | ✅ | List available spaCy models |
| GET | `/` | ✅ | API info and endpoint listing |

> **Note:** All endpoints except `/auth/token` require JWT Bearer token authentication.

### Endpoint Details

#### POST `/auth/token`
Obtain a JWT access token.

**Request:**
```json
{
  "client_id": "pi-dev-client",
  "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### POST `/v1/redact`
Redact PI from a single text.

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request:**
```json
{
  "text": "My SSN is 123-45-6789 and email is test@example.com",
  "enable_ner": true,
  "use_typed_tokens": true,
  "spacy_model": "en_core_web_sm"
}
```

**Response:**
```json
{
  "redacted_text": "My SSN is [SSN] and email is [EMAIL]",
  "entities_found": [
    {"type": "SSN", "value": "123-45-6789", "start": 10, "end": 21},
    {"type": "EMAIL", "value": "test@example.com", "start": 35, "end": 51}
  ],
  "processing_time_ms": 12.5,
  "model_used": "en_core_web_sm"
}
```

#### POST `/v1/redact/batch`
Redact PI from multiple texts in one request.

**Request:**
```json
{
  "texts": [
    "Email: john@example.com",
    "Phone: 555-123-4567",
    "SSN: 123-45-6789"
  ],
  "enable_ner": false
}
```

**Response:**
```json
{
  "results": [
    {"redacted_text": "Email: [EMAIL]", "entities_found": [...]},
    {"redacted_text": "Phone: [PHONE]", "entities_found": [...]},
    {"redacted_text": "SSN: [SSN]", "entities_found": [...]}
  ],
  "total_processing_time_ms": 25.3
}
```

---

## Authentication & Token Lifecycle

### Credentials

| Client | ID | Purpose | Rate Limit |
|--------|----|---------|-----------:|
| Internal | `pi-internal-web-service` | Web Service → API Service | 10,000/min |
| Development | `pi-dev-client` | Testing and development | 1,000/min |
| Production | `pi-prod-client` | Production API access | Configure |

### Configuration hierarchy

Credentials are resolved in this order (first match wins):

1. **Environment Variables** — `PI_CLIENT_ID`, `PI_CLIENT_SECRET`, `JWT_SECRET_KEY`
2. **YAML file** — `config/clients.yaml` (preferred in production)
3. **Fallback constants** — hardcoded in code (development only, never production)

```
config/
└── clients.yaml    ← Primary credential storage
```

**Example `config/clients.yaml`:**
```yaml
clients:
  pi-internal-web-service:
    secret: "YOUR_WEB_CLIENT_SECRET_HERE"
    rate_limit: 10000
    
  pi-dev-client:
    secret: "YOUR_DEV_CLIENT_SECRET_HERE"
    rate_limit: 1000

  # Production client — generate a strong secret!
  # pi-prod-client:
  #   secret: "<generate with: openssl rand -base64 32>"
  #   rate_limit: 5000

jwt:
  secret_key: "YOUR_DEV_JWT_SECRET_HERE"
  algorithm: "HS256"
  expiry_minutes: 30
```

### Token lifecycle in PIRemoverAPIClient

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                            TOKEN LIFECYCLE                                      │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  1. INITIAL REQUEST                                                             │
│     ┌───────────────┐   No token     ┌───────────────────────────────────┐     │
│     │ redact_text() │ ──────────────► │ _ensure_token() checks cache      │     │
│     └───────────────┘                 │   → token is None or expired      │     │
│                                       └───────────────────────────────────┘     │
│                                                 │                               │
│  2. TOKEN FETCH                                 ▼                               │
│     ┌─────────────────────────────────────────────────────────────────────┐    │
│     │ POST /dev/auth/token                                                 │    │
│     │   {"client_id": "pi-internal-web-service", "client_secret": "..."}   │    │
│     └─────────────────────────────────────────────────────────────────────┘    │
│                                                 │                               │
│  3. CACHE TOKEN                                 ▼                               │
│     ┌─────────────────────────────────────────────────────────────────────┐    │
│     │ Store: self._token = "eyJ..."                                         │    │
│     │        self._token_expiry = now + expires_in - 60 (buffer)            │    │
│     └─────────────────────────────────────────────────────────────────────┘    │
│                                                 │                               │
│  4. PROCEED WITH ORIGINAL REQUEST               ▼                               │
│     ┌─────────────────────────────────────────────────────────────────────┐    │
│     │ POST /dev/v1/redact                                                   │    │
│     │   Authorization: Bearer eyJ...                                        │    │
│     └─────────────────────────────────────────────────────────────────────┘    │
│                                                                                │
│  5. SUBSEQUENT REQUESTS                                                        │
│     ┌───────────────┐   token valid  ┌───────────────────────────────────┐     │
│     │ redact_text() │ ──────────────► │ _ensure_token() → reuse cached   │     │
│     └───────────────┘   (skip fetch) └───────────────────────────────────┘     │
│                                                                                │
│  6. REFRESH (when expiry < now + 60s)                                          │
│     → Automatically re-fetch before the token actually expires                 │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Key points:**
- Token cached in-memory; survives across requests until expiry (minus 60s buffer).
- On 401 during a request, client automatically re-fetches token and retries once.
- Token refresh is synchronous; concurrent requests wait on the same lock.

---

## PIRemoverAPIClient — internals & resilience

The Web Service uses `PIRemoverAPIClient` (file: `web_service/api_client.py`) to communicate with the API Service. This section documents the internal mechanisms.

### Class signature and construction

```python
class PIRemoverAPIClient:
    def __init__(
        self,
        base_url: str,              # e.g. "http://localhost:8080"
        client_id: str,             # e.g. "pi-internal-web-service"
        client_secret: str,         # secret from config/clients.yaml
        timeout: float = 30.0,      # request timeout in seconds
        max_retries: int = 3,       # retry attempts on transient errors
        circuit_threshold: int = 5, # failures before circuit opens
        circuit_timeout: float = 30 # seconds before half-open
    ): ...
```

### Feature breakdown

| Feature | Description | Config |
|---------|-------------|---------|
| **JWT Token Management** | Fetches token on first call; caches until expiry minus 60 s buffer; auto-refreshes transparently | N/A (automatic) |
| **Circuit Breaker** | Opens after `circuit_threshold` consecutive failures; rejects fast for `circuit_timeout` seconds; then half-open (one probe); if probe succeeds, closes | `circuit_threshold`, `circuit_timeout` |
| **Retry with Backoff** | Retries transient errors (5xx, timeouts) up to `max_retries` times with exponential delay (1s, 2s, 4s …) | `max_retries` |
| **Connection Pooling** | Uses `httpx.AsyncClient` with keep-alive; reuses TCP connections across calls | `limits` param |
| **Correlation IDs** | Generates a UUID per request; sent as `X-Correlation-ID` header; logs include this ID | Automatic |

### Internal methods

| Method | Purpose |
|--------|---------|
| `detect_api_prefix()` | Probes `/dev/` and `/prod/` paths to determine the environment prefix |
| `_ensure_token()` | Checks token cache; fetches new token if expired or missing |
| `_request(method, path, **kwargs)` | Core HTTP call wrapper; applies auth, retries, circuit breaker |
| `redact_text(text, **opts)` | High-level call to `/v1/redact` |
| `redact_batch(texts, **opts)` | High-level call to `/v1/redact/batch` |
| `health_check()` | Calls `/health` to verify API is up |

### Pseudocode: _request() flow

```
_request(method, path, body):
    if circuit_breaker.is_open:
        raise CircuitOpenError

    for attempt in range(max_retries + 1):
        await _ensure_token()                 # refresh token if needed
        headers = {"Authorization": f"Bearer {token}", "X-Correlation-ID": uuid4()}
        try:
            response = await http_client.request(method, url, headers, json=body, timeout)
            if response.status == 401:
                invalidate_token(); continue  # force token refresh & retry
            if response.status >= 500:
                raise TransientError
            circuit_breaker.record_success()
            return response.json()
        except (Timeout, TransientError):
            if attempt < max_retries:
                await sleep(2 ** attempt)     # exponential backoff
            else:
                circuit_breaker.record_failure()
                raise
```

### Usage example

```python
from api_client import PIRemoverAPIClient

async with PIRemoverAPIClient(
    base_url="http://localhost:8080",
    client_id="pi-internal-web-service",
    client_secret="YOUR_WEB_CLIENT_SECRET_HERE"
) as client:
    
    # Redact single text (token obtained automatically)
    result = await client.redact_text(
        text="Contact john@example.com",
        enable_ner=True
    )
    print(result["redacted_text"])   # "Contact [EMAIL]"
    
    # Batch redaction
    batch_result = await client.redact_batch(
        texts=["Call 555-1234", "Email foo@bar.com"],
        enable_ner=False
    )
    for r in batch_result["results"]:
        print(r["redacted_text"])
```

---

## Example Flows

### Text Redaction Flow

```
User Browser                Web Service                    API Service
     │                           │                              │
     │  1. Submit text           │                              │
     │  POST /api/redact-text    │                              │
     │  {"text": "Call John      │                              │
     │   at 555-1234"}           │                              │
     │ ─────────────────────────►│                              │
     │                           │                              │
     │                           │  2. (If needed) Get token    │
     │                           │  POST /dev/auth/token        │
     │                           │ ─────────────────────────────►│
     │                           │                              │
     │                           │  3. Token response           │
     │                           │ ◄─────────────────────────────│
     │                           │                              │
     │                           │  4. Redact request           │
     │                           │  POST /dev/v1/redact         │
     │                           │  Authorization: Bearer xxx   │
     │                           │ ─────────────────────────────►│
     │                           │                              │
     │                           │  5. Redacted response        │
     │                           │  {"redacted_text":           │
     │                           │   "Call [NAME] at [PHONE]"}  │
     │                           │ ◄─────────────────────────────│
     │                           │                              │
     │  6. Return to user        │                              │
     │  {"redacted_text": ...}   │                              │
     │ ◄─────────────────────────│                              │
     │                           │                              │
```

### File Processing Flow

```
User Browser                Web Service                    API Service
     │                           │                              │
     │  1. Upload file           │                              │
     │  POST /api/upload         │                              │
     │ ─────────────────────────►│                              │
     │                           │                              │
     │  2. Return job_id         │                              │
     │  {"job_id": "abc123"}     │                              │
     │ ◄─────────────────────────│                              │
     │                           │                              │
     │  3. Start processing      │                              │
     │  POST /api/process/abc123 │                              │
     │ ─────────────────────────►│                              │
     │                           │                              │
     │                           │  4. For each row:            │
     │                           │  POST /dev/v1/redact         │
     │                           │ ─────────────────────────────►│
     │                           │ ◄─────────────────────────────│
     │                           │         (repeated)           │
     │                           │                              │
     │  5. Poll status           │                              │
     │  GET /api/status/abc123   │                              │
     │ ─────────────────────────►│                              │
     │  {"progress": 75}         │                              │
     │ ◄─────────────────────────│                              │
     │                           │                              │
     │  6. Download result       │                              │
     │  GET /api/download/abc123 │                              │
     │ ─────────────────────────►│                              │
     │  (file download)          │                              │
     │ ◄─────────────────────────│                              │
```

---

## File Upload & Background Processing

### Upload validation steps (Web Service)

1. **Size check** — file must be ≤ configured max (default 50 MB).
2. **Extension whitelist** — only `.csv`, `.txt`, `.json` accepted.
3. **MIME type verification** — content-type header checked against whitelist.
4. **Safe filename** — original filename sanitized (path traversal protection).
5. **Job directory created** — unique folder under `uploads/<job_id>/` for isolation.
6. **File saved** — stored as `<job_id>/<safe_filename>`.

### Job lifecycle

| State | Meaning |
|-------|---------|
| `uploaded` | File received, awaiting processing start |
| `processing` | Background worker iterating rows/cells |
| `completed` | All redaction done; output file ready |
| `failed` | Unrecoverable error during processing |
| `deleted` | User deleted job and files |

### Background worker behavior

- Spawned via `asyncio.create_task()` per job.
- Reads file in streaming/chunked mode (configurable batch size).
- For each text cell, calls `PIRemoverAPIClient.redact_text()` (or local fallback).
- Updates progress percentage in memory; frontend polls `/api/status/{job_id}`.
- On completion, writes output file to `uploads/<job_id>/<filename>_redacted.<ext>`.
- On failure, marks state as `failed` with error message.

### Cleanup / expiry

- Jobs older than TTL (default 1 hour) may be garbage-collected by a periodic sweep.
- Explicit `DELETE /api/job/{job_id}` removes files immediately.

---

## Hybrid Redaction routing (API first, local fallback)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                       HYBRID ROUTING DECISION                                  │
│                                                                               │
│   ┌──────────────────────────────────────────────────────────┐                │
│   │ Incoming redact request                                   │                │
│   └──────────────────────────┬───────────────────────────────┘                │
│                              ▼                                                │
│                   Is _api_status.available?                                   │
│                      (cached bool from health check)                          │
│                    /          \                                               │
│                 YES            NO                                             │
│                  │              │                                             │
│                  ▼              ▼                                             │
│        Call API via       Use local PIRemover                                 │
│        PIRemoverAPIClient  (src/pi_remover/remover.py)                        │
│                  │              │                                             │
│          success?           returns result                                    │
│         /      \                │                                             │
│       YES      NO ──────────────┤                                             │
│        │     (fallback)         │                                             │
│        ▼              ▼         ▼                                             │
│   return result    use local fallback                                         │
│                              │                                                │
│                              ▼                                                │
│                       return result + "mode": "local"                          │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Code reference:** see `web_service/app.py` function `redact_text()`.

---

## Health checks, caching & background monitoring

### Background health-check task

- Runs every **30 seconds** (configurable).
- Prefers authenticated call via `PIRemoverAPIClient.health_check()` if client is initialized.
- Falls back to unauthenticated `GET /<env>/health` during initial startup.
- Result stored in `_api_status` object; queried by hybrid routing logic.

### _api_status cache

| Property | Meaning |
|----------|---------|
| `available` | `True` if last health check succeeded |
| `version` | API version string from health response |
| `latency_ms` | Round-trip time of last successful probe |
| `last_check` | Timestamp of last check |
| `consecutive_failures` | Counter; resets on success |

### Metrics exposed at `/api/service-info`

```json
{
  "web_version": "2.12.0",
  "api_available": true,
  "api_version": "2.12.0",
  "api_latency_ms": 12,
  "mode": "api"
}
```

---

## Rate limiting, quotas and configuration

### API Service rate limits

- Defined per-client in `config/clients.yaml` under `rate_limit` key (requests/minute).
- Optionally backed by Redis (`config/redis.yaml`) for distributed deployments.
- When exceeded, returns `HTTP 429 Too Many Requests`.

### Web Service upload quotas

- Max file size: 50 MB (configurable in `config/web_service.yaml`).
- Max concurrent jobs per IP: 5 (optional, not enforced by default).

---

## Logging, Correlation IDs & Audit events

### Correlation IDs

- Generated at Web Service entry point for each incoming request.
- Propagated to API Service via `X-Correlation-ID` header.
- Logged in both services; enables end-to-end tracing.

### Structured log format

```
{"timestamp": "2025-12-14T10:30:00Z", "level": "INFO", "correlation_id": "abc123", "event": "redact_request", "client": "pi-internal-web-service", "duration_ms": 45, "entities_found": 3}
```

### Audit events (security-sensitive)

| Event | When logged |
|-------|-------------|
| `auth_success` | Token issued |
| `auth_failure` | Invalid credentials |
| `redact_request` | Each redaction call |
| `file_upload` | File received |
| `file_download` | Redacted file served |
| `job_deleted` | Job removed by user |

Audit logs written to `logs/audit.log` (configurable path).

---

## Troubleshooting & common failure modes

| Symptom | Likely cause | Resolution |
|---------|--------------|------------|
| `401 Unauthorized` repeatedly | Wrong secret, expired token, or mismatched `client_id` | Verify `config/clients.yaml` secrets match; restart services |
| API unreachable; falling back to local | API Service down or network issue | Check API container/process; inspect firewall/ports |
| Circuit breaker open | 5+ consecutive API failures | Wait 30 s; fix underlying API issue; circuit will half-open |
| `429 Too Many Requests` | Rate limit exceeded | Reduce request rate or increase limit in `clients.yaml` |
| File upload rejected | Size, extension, or MIME mismatch | Check file against allowed list; increase max size if needed |
| Token refresh loops | Clock skew between services | Sync clocks (NTP); check expiry buffer |

---

### Health Check Flow

```
Web Service                                         API Service
     │                                                   │
     │  Background task (every 30s)                     │
     │                                                   │
     │  1. GET /dev/health                              │
     │     Authorization: Bearer <token>                │
     │ ─────────────────────────────────────────────────►│
     │                                                   │
     │  2. {"status": "healthy",                        │
     │      "version": "2.12.0",                        │
     │      "uptime_seconds": 3600}                     │
     │ ◄─────────────────────────────────────────────────│
     │                                                   │
     │  3. Update internal status cache                 │
     │     _api_status.mark_available()                 │
     │                                                   │
```

---

## Port Reference

| Service | DEV Port | PROD Port | Description |
|---------|:--------:|:---------:|-------------|
| API Service | 8080 | 9080 | Core redaction API |
| Web Service | 8082 | 9082 | Web UI and file processing |
| Redis | 6379 | 6379 | Rate limiting (optional) |

---

## Quick test commands & examples

### PowerShell — API Service

```powershell
# Get token
$token = (Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" `
  -Method POST -ContentType "application/json" `
  -Body '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}').access_token

# Redact text
Invoke-RestMethod -Uri "http://localhost:8080/dev/v1/redact" `
  -Method POST -Headers @{Authorization="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"text":"Email: test@example.com"}'
```

### PowerShell — Web Service

```powershell
# Redact text (no auth needed — Web Service handles API auth internally)
Invoke-RestMethod -Uri "http://localhost:8082/api/redact-text" `
  -Method POST -ContentType "application/json" `
  -Body '{"text":"Email: test@example.com"}'

# Health check
Invoke-RestMethod -Uri "http://localhost:8082/health"

# Service info (API connection status)
Invoke-RestMethod -Uri "http://localhost:8082/api/service-info"
```

### Bash / curl — API Service

```bash
# Get token
TOKEN=$(curl -s -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}' | jq -r .access_token)

# Redact text
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"SSN: 123-45-6789"}'
```

### Bash / curl — Web Service

```bash
# Redact via Web Service (no auth needed)
curl -X POST http://localhost:8082/api/redact-text \
  -H "Content-Type: application/json" \
  -d '{"text":"Email: foo@bar.com"}'

# Health
curl http://localhost:8082/health
```

---

## Related Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [API_REFERENCE.md](./API_REFERENCE.md) - Complete API documentation
- [SECURITY.md](./SECURITY.md) - Security and authentication details
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Deployment instructions
