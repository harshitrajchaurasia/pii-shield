# PI Remover Security Guide

> **Architecture Version:** 2.12.0 | **PIRemover Core:** v2.12.0
> JWT Bearer Token Authentication with YAML Configuration

This document describes the security architecture, controls, and best practices for deploying the PI Remover services in enterprise environments.

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Security Features](#security-features)
3. [Authentication](#authentication)
4. [API Endpoints Authentication](#api-endpoints-authentication)
5. [Client Configuration (YAML)](#client-configuration-yaml)
6. [Service-to-Service Authentication](#service-to-service-authentication)
7. [Input Validation](#input-validation)
8. [File Upload Security](#file-upload-security)
9. [Data Leakage Prevention](#data-leakage-prevention)
10. [Rate Limiting](#rate-limiting)
11. [Security Headers](#security-headers)
12. [Docker Security](#docker-security)
13. [Audit Logging](#audit-logging)
14. [Environment Configuration](#environment-configuration)
15. [Deployment Checklist](#deployment-checklist)

---

## Security Overview

The PI Remover implements defense-in-depth security with multiple layers of protection:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Security Layers                          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Network         │ TLS/HTTPS, Firewall, IP Filtering   │
│  Layer 2: Rate Limiting   │ Redis (shared) + fallback           │
│  Layer 3: Authentication  │ JWT Bearer Token (30-min expiry)    │
│  Layer 4: Circuit Breaker │ Prevents cascading failures         │
│  Layer 5: Input Validation│ Size limits, type checks, sanitize  │
│  Layer 6: File Security   │ Extension, MIME, magic bytes, scan  │
│  Layer 7: Audit Logging   │ Structured JSON (PI-safe)           │
│  Layer 8: Container       │ Non-root, read-only, minimal image  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Security Features

| Feature | Legacy | Current |
|---------|--------|--------|
| Credential Storage | Environment variables | YAML (`config/clients.yaml`) |
| Rate Limiting | In-memory per instance | Redis (shared across instances) |
| Service Auth | N/A | `pi-internal-web-service` client |
| Logging | Text format | Structured JSON with correlation IDs |
| Secrets | Scattered | Centralized in `config/clients.yaml` |

### Security File Locations

```
config/
├── clients.yaml      ← 🔐 SECRETS: JWT keys, client credentials
├── redis.yaml        ← Connection settings (may include password)
└── logging.yaml      ← Log configuration
```

⚠️ **Important**: Add `config/clients.yaml` to `.gitignore` in production!

---

## Authentication

### JWT Bearer Token Authentication

The API service uses JWT Bearer tokens for authentication. Tokens expire after **30 minutes** (configurable).

**All API endpoints require authentication** (except `/auth/token`).

### Authentication Flow

```
┌──────────────┐     1. POST /auth/token          ┌──────────────┐
│              │     {client_id, client_secret}   │              │
│    Client    │ ─────────────────────────────────►   API Server │
│              │                                   │              │
│              │ ◄─────────────────────────────────│              │
│              │     {access_token, expires_in}   │              │
└──────────────┘                                   └──────────────┘
       │
       │  2. POST /v1/redact
       │     Authorization: Bearer <token>
       ▼
┌──────────────┐                                   ┌──────────────┐
│              │ ─────────────────────────────────►│              │
│    Client    │     {text: "..."}                 │   API Server │
│              │ ◄─────────────────────────────────│              │
│              │     {redacted_text: "..."}        │              │
└──────────────┘                                   └──────────────┘
```

---

## API Endpoints Authentication

**All endpoints require JWT Bearer token authentication** except for the token endpoint itself.

### Complete Endpoint Reference

| Method | Endpoint | Auth Required | Purpose |
|--------|----------|:-------------:|---------|
| POST | `/auth/token` | ❌ No | Obtain JWT access token |
| POST | `/v1/redact` | ✅ Yes | Redact PI from single text |
| POST | `/v1/redact/batch` | ✅ Yes | Redact PI from multiple texts |
| GET | `/health` | ✅ Yes | Service health check and metrics |
| GET | `/v1/pi-types` | ✅ Yes | List supported PI types |
| GET | `/v1/models` | ✅ Yes | List available spaCy NER models |
| GET | `/` | ✅ Yes | API info and endpoint listing |

### Environment-Specific Base URLs

| Environment | Base URL | Description |
|-------------|----------|-------------|
| **DEV** | `http://localhost:8080/dev` | Development (relaxed rate limits) |
| **PROD** | `http://localhost:9080/prod` | Production (strict rate limits) |

### Unauthenticated Access Response

Requests without valid JWT receive 401 Unauthorized:

```json
{
    "error": "missing_token",
    "message": "Authorization header missing or invalid",
    "request_id": "abc123..."
}
```

---

## Client Configuration (YAML)

### config/clients.yaml

```yaml
clients:
  # Development client
  pi-dev-client:
    secret: "YOUR_DEV_CLIENT_SECRET_HERE"
    rate_limit: 1000          # requests per minute
    environment: "development"
    
  # Production client (uncomment and configure for production)
  # pi-prod-client:
  #   secret: "<generate-unique-secret-for-production>"
  #   rate_limit: 10000
  #   environment: "production"
    
  # Internal service-to-service client
  pi-internal-web-service:
    secret: "YOUR_WEB_CLIENT_SECRET_HERE"
    rate_limit: 10000         # Higher limit for internal use
    environment: "internal"

jwt:
  secret_key: "YOUR_DEV_JWT_SECRET_HERE"
  algorithm: "HS256"
  expiry_minutes: 30
```

### Adding a New Client

```yaml
clients:
  # ... existing clients ...
  
  my-new-app:
    secret: "generate-with-secrets.token_urlsafe(32)"
    rate_limit: 500
    environment: "development"
```

### Generate Secure Secrets

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Service-to-Service Authentication

The Web Service authenticates with the API Service using JWT:

```
Web Service                          API Service
     │                                    │
     │  1. POST /auth/token               │
     │     client_id: pi-internal-web-    │
     │                service             │
     │────────────────────────────────────►
     │                                    │
     │  2. JWT Token (cached)             │
     │◄────────────────────────────────────
     │                                    │
     │  3. POST /v1/redact                │
     │     Authorization: Bearer <token>  │
     │────────────────────────────────────►
     │                                    │
```

The internal client has:
- Higher rate limits (10,000 req/min)
- Same JWT expiration (30 min)
- Token cached and auto-renewed

---

## Using Authentication

### Step 1: Obtain Token

**Request:**
```bash
curl -X POST https://api.example.com/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "your-client-id",
    "client_secret": "your-client-secret"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Step 2: Use Token for API Calls

**Request:**
```bash
curl -X POST https://api.example.com/v1/redact \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{"text": "Contact john@example.com for help"}'
```

**Response:**
```json
{
  "redacted_text": "Contact [EMAIL] for help",
  "request_id": "abc123",
  "processing_time_ms": 12.5
}
```

### Token Expiry Handling

When a token expires, you'll receive a `401 Unauthorized` response:

```json
{
  "error": "http_error",
  "message": "Token has expired. Please obtain a new token.",
  "request_id": "xyz789"
}
```

**Best Practice**: Track token expiry and refresh proactively before expiration.

### Client Credentials Configuration

**Environment Variables:**
```bash
# JWT signing secret (MUST be set in production)
JWT_SECRET_KEY=your-256-bit-secret-key-here

# Token expiry in minutes (default: 30)
JWT_EXPIRY_MINUTES=30

# Client credentials (format: client_id:client_secret:name)
AUTH_CLIENTS=prod-app:secret123:production,staging-app:secret456:staging
```

> **Note:** Authentication is always enabled and cannot be disabled. This ensures enterprise-grade security.

**Clients File Format (clients.json):**
```json
{
  "prod-client-id": {
    "secret": "your-secure-64-char-hex-secret",
    "name": "production-app",
    "created": "2024-01-01T00:00:00Z",
    "rate_limit": 1000
  },
  "staging-client-id": {
    "secret": "another-secure-secret",
    "name": "staging-app",
    "created": "2024-01-01T00:00:00Z",
    "rate_limit": 100
  }
}
```

### Security Best Practices

| Practice | Recommendation |
|----------|----------------|
| Client Secret Length | 64+ hex characters (256 bits) |
| JWT Secret Key | 64+ hex characters, cryptographically random |
| Secret Rotation | Every 90 days |
| Token Storage | Never store in localStorage; use httpOnly cookies or memory |
| HTTPS | Always use TLS in production |
| Secret Management | Use Vault, AWS Secrets Manager, or similar |

### Python Client Example

```python
import requests
import time

class PIRemoverClient:
    def __init__(self, base_url, client_id, client_secret):
        self.base_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = 0
    
    def _ensure_token(self):
        """Get or refresh the auth token."""
        # Refresh 60 seconds before expiry
        if self.token and time.time() < self.token_expiry - 60:
            return
        
        response = requests.post(
            f"{self.base_url}/auth/token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        )
        response.raise_for_status()
        data = response.json()
        
        self.token = data["access_token"]
        self.token_expiry = time.time() + data["expires_in"]
    
    def redact(self, text):
        """Redact PI from text."""
        self._ensure_token()
        
        response = requests.post(
            f"{self.base_url}/v1/redact",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"text": text}
        )
        response.raise_for_status()
        return response.json()["redacted_text"]

# Usage
client = PIRemoverClient(
    "https://api.example.com",
    "your-client-id",
    "your-client-secret"
)

result = client.redact("Contact john@example.com")
print(result)  # "Contact [EMAIL]"
```

---

## Input Validation

### Text Input Validation

All text inputs are validated before processing:

| Check | Limit | Error Code |
|-------|-------|------------|
| Maximum length | 100,000 characters | 413 |
| Null bytes | Not allowed | 400 |
| Empty text | Not allowed | 400 |

**Configuration:**
```bash
MAX_TEXT_LENGTH=100000
MAX_BATCH_SIZE=100
MAX_REQUEST_SIZE=10485760  # 10MB
```

### Request ID Validation

Client-provided request IDs must be alphanumeric with hyphens/underscores only.

### Batch Request Validation

- Maximum 100 texts per batch (configurable)
- Each text validated individually
- Total request size limited

---

## File Upload Security

The web service implements comprehensive file upload security:

### 1. Extension Validation
```
Allowed: .csv, .xlsx, .xls, .json, .txt
```

### 2. MIME Type Verification
```
text/csv, text/plain, application/json,
application/vnd.ms-excel,
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

### 3. Magic Byte Verification
Binary files (.xlsx, .xls) are verified by checking file signatures:
- XLSX: `PK\x03\x04` (ZIP format)
- XLS: `\xd0\xcf\x11\xe0` (OLE compound document)

### 4. Malicious Content Scanning
Text files are scanned for:
- `<script>` tags (XSS)
- `javascript:` URIs
- DDE/formula injection (`=cmd|`, `=DDE(`, `=HYPERLINK(`)
- Template injection patterns

### 5. Secure File Storage
- Files stored in isolated directories per job
- Safe filenames generated (no path traversal)
- Automatic cleanup of old files
- Configurable retention period

**Configuration:**
```bash
MAX_FILE_SIZE=524288000  # 500MB
QUARANTINE_SUSPICIOUS=true
UPLOAD_DIR=/app/uploads
```

---

## Data Leakage Prevention

### Log Sanitization

**CRITICAL**: PI is NEVER logged. All logging functions sanitize sensitive data:

```python
# Example: What gets logged
Input: "Contact john.doe@company.com at 555-123-4567"
Log:   "[45 chars] Contact [EMAIL] at [PHONE]..."
```

**Sanitization includes:**
- Email addresses → `[EMAIL]`
- Phone numbers → `[PHONE]`
- Credit cards → `[CARD]`
- Text content → length only, truncated preview

### Error Response Sanitization

Error messages never include:
- Stack traces (in production)
- Internal file paths
- Database connection strings
- Original input text
- Client secrets or tokens

**Example Error Response:**
```json
{
  "error": "internal_error",
  "message": "An unexpected error occurred. Please try again.",
  "request_id": "a1b2c3d4e5f6"
}
```

### Secure Defaults

| Setting | Development | Production |
|---------|-------------|------------|
| Swagger UI | Enabled | Disabled |
| Detailed errors | Enabled | Disabled |
| Stack traces | Shown | Hidden |
| Debug logging | Allowed | Restricted |

---

## Rate Limiting

Token bucket algorithm with configurable limits:

**Configuration:**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100      # requests per window
RATE_LIMIT_WINDOW_SECONDS=60 # window duration
RATE_LIMIT_BURST=20          # burst allowance
```

**Response Headers:**
```
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 45
```

**429 Response:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please slow down.",
  "retry_after": 45
}
```

**Per-Client Limits:**
Clients can have custom rate limits defined in their configuration.

---

## Security Headers

All responses include security headers:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | XSS filter |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS |
| `Content-Security-Policy` | (see below) | Prevent injection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer info |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Disable features |
| `Cache-Control` | `no-store, no-cache, must-revalidate` | Prevent caching |

**CSP Policy:**
```
default-src 'self'; 
script-src 'self' 'unsafe-inline'; 
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; 
font-src 'self' https://fonts.gstatic.com; 
img-src 'self' data:;
```

---

## Docker Security

### Security Features

1. **Non-root User**
   ```dockerfile
   RUN useradd -m -u 1000 -s /usr/sbin/nologin appuser
   USER appuser
   ```

2. **Minimal Base Image**
   - Uses `python:3.11-slim`
   - Removes build tools after compilation
   - Cleans package caches

3. **Read-Only Filesystem**
   ```bash
   docker run --read-only --tmpfs /tmp pi-gateway
   ```

4. **Resource Limits**
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 4G
   ```

5. **No Capabilities**
   ```bash
   docker run --cap-drop=ALL pi-gateway
   ```

### Secure Docker Compose

```yaml
version: '3.8'
services:
  pi-gateway:
    image: pi-gateway:latest
    read_only: true
    tmpfs:
      - /tmp
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    environment:
      - ENVIRONMENT=production
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    secrets:
      - auth_clients
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G

secrets:
  auth_clients:
    file: ./secrets/clients.json
```

---

## Audit Logging

All security-relevant events are logged:

### Logged Events

| Event | Data Logged |
|-------|-------------|
| Token Request | timestamp, client_id, success/failure |
| API Request | timestamp, action, client_id, path, method |
| File Upload | job_id, operation, filename, success |
| File Download | job_id, operation, filename |
| Rate Limit Hit | timestamp, client_ip, path |
| Auth Failure | timestamp, client_ip, path |
| Token Expiry | timestamp, client_id |

### Log Format

```json
{
  "timestamp": "2024-12-13T10:30:00Z",
  "action": "redact_single",
  "client_id": "prod-client",
  "client_name": "production",
  "path": "/v1/redact",
  "method": "POST",
  "details": {
    "text_length": 500,
    "include_details": false
  }
}
```

**Configuration:**
```bash
AUDIT_LOGGING_ENABLED=true
AUDIT_LOG_FILE=audit.log
AUDIT_RETENTION_DAYS=90
```

---

## Environment Configuration

### Required for Production

```bash
# Core
ENVIRONMENT=production
LOG_LEVEL=WARNING

# Authentication (always enabled - cannot be disabled)
JWT_SECRET_KEY=your-256-bit-secret-key-generate-with-openssl-rand-hex-32
JWT_EXPIRY_MINUTES=30
AUTH_CLIENTS_FILE=/run/secrets/clients.json

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100

# Audit
AUDIT_LOGGING_ENABLED=true

# CORS (restrict to your domains)
CORS_ORIGINS=https://app.example.com,https://admin.example.com
```

### Generate Secure Keys

```bash
# Generate JWT secret key
openssl rand -hex 32

# Generate client secret
openssl rand -hex 32

# Generate client ID
openssl rand -hex 8
```

### Optional Security Settings

```bash
# IP Filtering (comma-separated)
IP_BLOCKLIST=192.168.1.100,10.0.0.50
IP_ALLOWLIST=192.168.1.0/24  # If set, only these allowed

# File Upload
MAX_FILE_SIZE=524288000
QUARANTINE_SUSPICIOUS=true
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Generate JWT_SECRET_KEY with `openssl rand -hex 32`
- [ ] Create client credentials with secure secrets
- [ ] Configure secrets management
- [ ] Set `ENVIRONMENT=production`
- [ ] Disable Swagger UI
- [ ] Configure CORS for specific origins
- [ ] Set up TLS termination (HTTPS)
- [ ] Configure firewall rules
- [ ] Set up log aggregation
- [ ] Configure monitoring/alerting

### Container Security

- [ ] Run as non-root user
- [ ] Use read-only filesystem where possible
- [ ] Drop all capabilities (`--cap-drop=ALL`)
- [ ] Set resource limits (CPU, memory)
- [ ] Use `--no-new-privileges`
- [ ] Scan image for vulnerabilities

### Network Security

- [ ] Use private network for backend services
- [ ] TLS 1.3 only
- [ ] Configure proper DNS
- [ ] Set up DDoS protection
- [ ] Use reverse proxy (nginx, traefik)

### Monitoring

- [ ] Monitor token issuance rates
- [ ] Alert on auth failures
- [ ] Track error rates
- [ ] Review audit logs regularly
- [ ] Set up anomaly detection

---

## Security Updates

| Version | Date | Security Changes |
|---------|------|------------------|
| 2.12.0 | 2025-12-16 | Modular architecture refactoring |
| - | - | Enhanced observability (Prometheus) |
| - | - | Platform-aware auto-scaling |
| 2.9.0 | 2025-12-15 | Hybrid microservices architecture |
| - | - | Circuit breaker pattern |
| - | - | YAML configuration files |
| - | - | Redis-backed distributed rate limiting |
| 2.5.0 | 2024-12-13 | JWT Bearer Token authentication |
| - | - | 30-minute token expiry |
| - | - | Client credentials flow |
| - | - | Removed static API keys |
| 2.4.0 | 2024-12-13 | Initial security implementation |
| - | - | Rate limiting |
| - | - | File upload security |
| - | - | Audit logging |
| - | - | Security headers |
| - | - | Docker hardening |

---

*This document is part of the PI Remover Enterprise Security Guide.*

*Last updated: December 16, 2025*
