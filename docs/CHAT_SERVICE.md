# PI Remover Chat Service — Design, API, and Deployment Guide

> **Version 2.12.0** - Modular Architecture | JWT authentication, BuildKit caching, and enterprise Web UI

This document describes how to expose the PI Removal project as a Chat Service so users can submit messages (or paste text) and receive redacted output in real time. Two complete approaches are provided:

- On-premises (self-hosted) — Docker / Docker Compose or Kubernetes, no cloud provider required. Suitable for strict data residency and offline environments.
- Google Cloud Platform (GCP) — fully managed, scalable architecture using Cloud Run, Pub/Sub, Firestore, and optional NER workers.

Each approach includes architecture diagrams, API specs (REST + WebSocket), message formats, auth & security, monitoring, scaling, deployment steps, testing, sample TODOs, and operational best practices.

---

**Goals and non-functional requirements**

- Real-time chat-style redaction: < 500ms response for fast mode; < 1-2s for full NER mode.
- Data privacy: never send user text outside approved environments; support on-prem and cloud deployments.
- Scalability: handle many concurrent users with autoscaling/backpressure.
- Auditability: keep optional audit logs (who requested, when, what was redacted) with configurable retention.
- Extensibility: pluggable detectors (regex layer, dictionary, spaCy NER, optional custom ML models).
- High availability and graceful degradation: degrade to fast mode (regex-only) if NER unavailable.

---

## Using the Unified PI Remover (v2.12.0)

```python
from pi_remover import PIRemover, PIRemoverConfig

# Fast mode (for low latency chat - recommended)
config = PIRemoverConfig(enable_ner=False)
remover = PIRemover(config)

# Full mode (when accuracy is more important than speed)
config_full = PIRemoverConfig(enable_ner=True)
remover_full = PIRemover(config_full)

# Redact text
result = remover.redact("Contact john@example.com at +44-1234567890")
# Result: "Contact [EMAIL] at [PHONE]"

# Note: "password reset" is NOT redacted as [CREDENTIAL]
result = remover.redact("User needs password reset")
# Result: "User needs password reset" (unchanged - not a credential)
```

---

## High-level service responsibilities

1. Accept user text (single messages or streaming conversation).
2. Run PI detection/redaction pipeline (configurable per request).
3. Return redacted text and a structured list of redactions (type, span, replacement). Optionally return confidence/diagnostics.
4. Optionally persist audit records and metrics.
5. Enforce authentication, authorization, rate limits, and retention policies.

---

## Two recommended deployment patterns

1. On-Premises (Self-hosted) - Docker Compose or Kubernetes
2. Google Cloud (Managed) - Cloud Run + Pub/Sub + Firestore + optional NER workers

Both approaches share the same API surface and worker code (reuse `src/pi_remover/`). Implementation differences focus on orchestration, storage, scaling, and authentication.

---

# API & Protocols (Common to both deployments)

Design the service with two complementary interfaces:

1. REST API (synchronous): submit a single message and get redacted result.
2. WebSocket API (interactive): support real-time chat and streaming redaction results.

Security: all requests require authentication (JWT/OAuth2) and TLS.

## REST endpoints (JSON)

- POST /v1/redact
  - Purpose: Synchronous redaction for a single message or small batch.
  - Auth: Bearer JWT
  - Request:
    {
      "request_id": "uuid-v4",            // optional client-supplied for tracing
      "text": "String to redact",
      "config": {                           // optional per-request overrides
         "enable_ner": false,
         "pi_types": { "emails": true, "phones": true, ... }
      },
      "audit": { "save": true, "user_id": "alice@example.com" }
    }
  - Response 200:
    {
      "request_id": "uuid-v4",
      "redacted_text": "...",
      "redactions": [
         {"type":"EMAIL","start":10,"end":25,"text":"user@example.com","replacement":"[EMAIL]"},
         ...
      ],
      "diagnostics": { "ner_used": false }
    }

- POST /v1/redact/batch
  - Purpose: Submit multiple messages in a single request (JSON array) for bulk redaction.
  - Use for small batches (< 1k messages) synchronous; larger batches should use async job API.

- POST /v1/jobs
  - Purpose: Start an async job for very large inputs or files.
  - Request: include storage reference (on-prem path or cloud bucket) or attach a file.
  - Response: job_id; status polled via GET /v1/jobs/{job_id}

- GET /v1/jobs/{job_id}
  - Return status, progress, and download link for results.

- GET /v1/health
  - Liveness and readiness probes; include `ner_ready` boolean.

## WebSocket API (for chat)

- Connect to `wss://{host}/v1/chat` with Bearer JWT in `Sec-WebSocket-Protocol` or `Authorization` header.
- Protocol: JSON messages; client sends `message` frames and receives `response` frames.

Client -> Server:
{ "type": "message", "request_id": "...", "text": "Hi, my phone is +44...", "config": {...} }

Server -> Client (immediate):
{ "type": "ack", "request_id": "...", "received_at": "..." }

Server -> Client (result):
{ "type": "result", "request_id": "...", "redacted_text": "...", "redactions": [...] }

Optional streaming: send partial `result.partial` frames for large docs or NER incremental updates.

## Response Data Model

- `redacted_text` — final redacted string
- `redactions` — list of objects {type, start, end, original_text, replacement}
- `diagnostics` — optional: which layers ran, duration per layer, model version

Include `request_id` echoed back for tracing across systems.

---

# Architecture: On-Prem Design (detailed)

Overview: Provide a lightweight, self-contained deployment that can run on a single server or a private data center. Two variants provided:

- Small-scale: Docker Compose stack (single node)
- Enterprise: Kubernetes (K8s) cluster deployment

### Components

- API Gateway (optional): Traefik / Nginx ingress for TLS termination and routing
- Auth Service: OAuth2 provider (Keycloak) or lightweight JWT issuer; or integrate with existing SSO
- Chat API Service (FastAPI/uvicorn or FastAPI + Gunicorn): handles REST + WebSocket
- PI Remover Worker(s): Python service running `pi_remover.PIRemover` for redaction
  - Two modes: `fast` (regex-only) and `ner` (spaCy). Worker exposes local gRPC/HTTP worker API.
- Queue: Redis Streams or RabbitMQ for async jobs / backpressure
- Storage: Local filesystem or NFS for uploaded files and results
- Audit DB: PostgreSQL (or SQLite for tiny installs) to store audit logs and job metadata
- Observability: Prometheus + Grafana, Loki for logs
- Optional: Rate limiter (Redis-based), API key store

### Data flow (sync request)

Client -> API Service -> (if fast mode) local worker call -> return result

If NER disabled or fast path chosen, API calls local regex worker directly for minimal latency.

### Data flow (async heavy job)

Client -> API Service -> enqueue job in Redis/RabbitMQ -> Worker(s) pull job -> process -> write result to storage -> update DB -> notify (webhook or pollable status)

### Deployment Options

1. Docker Compose (single host)
- Services: redis, postgres, api-service, worker-fast, worker-ner (optional), nginx, prometheus, grafana
- Use volumes to persist models (spaCy) and results

2. Kubernetes
- Deploy as Deployments + Services + HPA
- Use persistent volumes (NFS/Ceph) for models and output
- Ingress via Nginx ingress or Traefik

### Authentication & Authorization (on-prem)

- Use Keycloak or corporate SSO if available. Otherwise issue JWTs with private keys.
- API authenticates JWT, checks scopes: `redact:write`, `audit:read`.
- Role-based access for `admin`, `user`, `auditor`.

### Security & Privacy

- TLS mandatory (Let’s Encrypt via Ingress or corporate TLS certs)
- Private networks / VPN recommended for on-prem deployments
- Do not persist input text unless `audit.save=true` explicitly requested
- Encrypt storage at rest (LUKS / disk encryption)
- Provide data retention configuration for audit logs

### Scaling & HA

- For interactive traffic, run multiple API replicas behind ingress; use sticky sessions for WebSockets or use an external message bus (Redis) for session routing.
- Workers: scale based on CPU and memory; NER workers need more memory and should be scaled differently.
- Use Redis streams/RabbitMQ for backpressure and to decouple API from workers.

### Observability

- Expose Prometheus metrics from API and workers (requests/sec, latency, redactions/sec, errors, ner_latency)
- Use Grafana dashboards for SLA, and Loki/ELK for searching logs
- Health and readiness endpoints for K8s probes

### Example On-Prem Docker Compose snippet (conceptual)

```yaml
version: '3.7'
services:
  redis:
    image: redis:7
    restart: unless-stopped
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_PASSWORD=changeme
  api:
    build: ./api
    ports: ["8080:8080"]
    depends_on: [redis, postgres]
    environment:
      - REDIS_URL=redis://redis:6379
  worker-fast:
    build: ./worker-fast
    environment:
      - MODE=fast
    depends_on: [redis]
  worker-ner:
    build: ./worker-ner
    environment:
      - MODE=ner
    deploy:
      resources:
        limits:
          memory: 4g

volumes:
  spaCy_models:
```

### Operational TODOs (On-Prem)

- [ ] Provide installation playbook (Ansible/Terraform for infra)
- [ ] Containerize `pi_remover` as `worker-fast` and `worker-ner`
- [ ] Build Helm chart or Docker Compose for quick demo
- [ ] Add Keycloak recipes for SSO integration
- [ ] Provide backup and retention scripts for audit DB

---

# Architecture: Google Cloud Design (detailed)

This section builds on `GOOGLE_CLOUD.md` and adapts it for chat interactions. The GCP design focuses on managed services to reduce operational overhead.

### Components (GCP)

- Cloud Run (API): serves REST + WebSocket (via Cloud Run with WebSocket support or using Cloud Run + WebSocket proxy) or App Engine flexible
- Cloud Run Workers: `fast` and `ner` variants (stateless) invoked directly or via Pub/Sub
- Pub/Sub: job queue for async processing and for pub/sub responses (push to workers)
- Firestore: job metadata and session state (chat session tracking)
- Cloud Storage: optional for large file inputs and processed outputs
- Memorystore (Redis): optional for session routing, rate limiting, and small caches
- IAM & IAP: control access, secrets stored in Secret Manager
- Cloud Monitoring / Logging / Trace

### Two modes for interactive chat

1. Synchronous low-latency: Cloud Run API directly calls in-process `pi_remover` for regex-only redaction (fast). For NER mode, Cloud Run may call a separate NER worker (gRPC/HTTP) or process in the same container with higher memory.
2. Asynchronous NER pipeline: Cloud Run publishes message to Pub/Sub, NER workers subscribed to topic process and write back results to Firestore or Cloud Storage; API notifies client via polling or server-sent events (SSE) or push notifications.

### WebSocket support on GCP

- Cloud Run now supports WebSockets (verify region/limits). Alternative: use a WebSocket server on Compute Engine or GKE.
- For large scale, consider Cloud Run for API + Memorystore for session state and a separate WebSocket gateway if needed.

### Security

- Enforce TLS via Cloud Run and use IAM for service-to-service access
- Use signed URLs for file downloads in Cloud Storage
- Use Cloud KMS / Secret Manager for model keys and credentials

### Autoscaling considerations

- Cloud Run autoscaling will spin up new instances for load; ensure cold-starts for NER are mitigated by warm pools or minimum instances
- Prefer `fast` workers on Cloud Run for immediate response and send NER-intensive jobs to Pub/Sub

### Cost and sizing

- Fast worker: small mem (512Mi–1Gi), cheap and fast
- NER worker: larger mem (4Gi), more costly; keep these as a separate service and scale differently

### Example flow (interactive NER via Pub/Sub)

Client -> Cloud Run API (accepts message) -> publish to Pub/Sub -> NER worker picks up -> process -> write results to Firestore -> client polls GET /v1/chat/{session}/messages or receives SSE

### Operational TODOs (GCP)

- [ ] Implement Cloud Run API with REST + WebSocket support
- [ ] Implement Pub/Sub topics/subscriptions for NER jobs
- [ ] Create Firestore schema for chat sessions and job metadata
- [ ] Create IAM roles and service accounts with least privilege
- [ ] Setup CI/CD with Cloud Build; automate container builds and deploys
- [ ] Add Cloud Monitoring dashboards and alerting

---

# Implementation notes — Reusing `pi_remover` code

- Expose a worker API in Python that wraps `PIRemover.redact(text, config)` with a thin HTTP or gRPC wrapper
- Keep `PIRemoverConfig` serializable to JSON for cross-process configuration
- For low-latency, load `PIRemover` at process startup and keep it in memory (reuse across requests)
- Provide two Docker images:
  - `pi-remover:fast` — lightweight, regex-only (no spaCy) for <512Mi memory
  - `pi-remover:ner` — includes spaCy model and higher memory

---

# Reliability & Degradation Strategies

- Circuit breaker: If NER worker latency exceeds threshold, API should automatically route to fast (regex-only) worker and return a diagnostics flag: `ner_used:false, degraded:true`.
- Queue length monitoring: if Pub/Sub or Redis queue length grows beyond threshold, reject new requests with `429` or return degraded mode.
- Retry policies: idempotent retries for job submissions, exponential backoff.

---

# Security, Privacy, and GDPR considerations

- Keep PII within boundary: for on-prem deployment, no external networks. For cloud deployments, customers must consent to cloud processing.
- Provide an opt-out toggle to NOT persist any raw input in audit logs.
- Store audit trails in encrypted DB; redact original text after X days per policy.
- Provide data deletion APIs for compliance (right to be forgotten): delete audit records and blob storage entries.

---

# Monitoring, Logging, & Auditing

- Metrics: request rate, latency (p50/p95/p99), redactions per request, NER model load time, worker memory usage
- Tracing: attach `request_id` to logs and traces through the pipeline
- Audit: store `request_id`, `user_id`, timestamp, `redactions` metadata (not raw text unless opted in)
- Alerts: high error rate, queue depth, memory saturation on NER workers, model load failures

---

# Developer experience & DX

- Provide SDKs (Python/Node) for client integration (minimal wrapper to call REST/WebSocket)
- Provide example web chat widget that connects to WebSocket and supports streaming
- Provide `docker-compose.yaml` and `helm` charts for quick local dev
- Provide unit tests and integration tests that run with sample datasets

---

# API Rate Limiting & Abuse Protection

- Apply per-user and per-IP rate limits
- Implement quotas per API key or per JWT scope
- Use token bucket or leaky bucket algorithm; implement via Redis or Cloud Armor (GCP)

---

# Testing strategy

- Unit tests for `PIRemover` logic (existing tests)
- Integration tests for API endpoints (use test containers)
- Load tests using `k6` or `locust` for chat throughput and concurrency
- End-to-end tests: sample inputs that verify redaction fidelity

---

# CI/CD recommendations

- Use GitHub Actions / Cloud Build to run tests, build images, and deploy
- Run security scans on images (Trivy)
- Automatically run unit/integration tests and static analysis

---

# Example quickstart: On-Prem (developer walkthrough)

1. Clone repo
2. Build images

```bash
# from repo root
docker build -t pi-remover-fast -f worker-fast/Dockerfile .
docker build -t pi-remover-ner -f worker-ner/Dockerfile .
```

3. Start minimal stack (Redis + API + fast worker)

```bash
docker-compose up -d redis api worker-fast
```

4. Test REST endpoint

```bash
curl -X POST https://localhost:8080/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Call me on +44 2030028019"}'
```

---

# Example quickstart: GCP (developer walkthrough)

1. Build and push images to Artifact Registry or Container Registry
2. Deploy Cloud Run services (`api`, `worker-fast`, `worker-ner`) with appropriate memory settings
3. Create Pub/Sub topics/subscriptions and Firestore collections
4. Deploy frontend and configure OAuth/IAM

Commands omitted here; see `GOOGLE_CLOUD.md` for full steps.

---

# Detailed TODO list (comprehensive)

Core implementation
- [ ] Create `chat-api/` service (FastAPI) with REST + WebSocket endpoints
- [ ] Implement JSON schema for request/response and validation (Pydantic)
- [ ] Add authentication middleware (JWT validation, Keycloak/OIDC client)
- [ ] Add rate limiting middleware (Redis or in-memory for PoC)
- [ ] Integrate `pi_remover` as worker module and expose internal worker API

Workers & processing
- [ ] Containerize `worker-fast` and `worker-ner` with health endpoints
- [ ] Implement Pub/Sub/Redis queue consumer for async NER jobs
- [ ] Implement circuit-breaker for NER fallback to fast mode

Storage & audit
- [ ] Design Firestore/Postgres schema for jobs, sessions, audit logs
- [ ] Implement optional persistent audit logging with retention policy
- [ ] Implement data deletion API for GDPR

Operations & infra
- [ ] Build Docker Compose and Helm charts
- [ ] Setup Prometheus metrics and Grafana dashboards
- [ ] Setup CI/CD for tests and deploys (GitHub Actions / Cloud Build)
- [ ] Create runbooks for incidents and capacity planning

Security & compliance
- [ ] Integrate Keycloak / OIDC for authentication
- [ ] Harden containers, scan images, sign images
- [ ] Ensure TLS, encrypted storage, and minimal IAM roles

Clients & UX
- [ ] Build a sample React chat widget + Node/TS SDK
- [ ] Build CLI client for batch redaction
- [ ] Provide example integrations (Slack/Teams bot) if desired

Testing & validation
- [ ] Create test suite for redaction fidelity with expected outputs
- [ ] Add load tests (k6) and document expected throughput
- [ ] Add chaos tests for degradation behavior

Documentation
- [ ] Create `CHAT_SERVICE.md` (this file)
- [ ] Provide `README` for each component with run steps
- [ ] Publish architecture diagrams and runbooks

---

# Operational runbook (short)

- If API latency increases: check worker queue, memory usage on NER workers, restart stalled workers.
- If NER model fails to load: verify spaCy model files, ensure sufficient memory (>= 4Gi recommended).
- If many `429` responses: increase rate limits cautiously or add capacity; notify client owners.
- For data-deletion requests: run deletion job that removes audit records and storage blobs; log operation.

---

# Final notes and recommendations

1. **Start with on-prem PoC** using Docker Compose and `worker-fast` to validate latency and UX. Add `worker-ner` later to assess memory and cost impact.
2. **Separate concerns**: keep API (ingress + auth) separate from workers; use a queue to decouple for reliability.
3. **Make NER optional per-request** so clients can choose speed vs accuracy tradeoff.
4. **Audit & privacy by design**: default to not storing raw inputs; allow audited storage only by explicit consent and compliance.

---

If you want, I can now:

- Scaffold a minimal `chat-api` FastAPI service that wraps `PIRemover.redact` (sync REST + WebSocket).
- Create Dockerfiles and a `docker-compose.yaml` dev stack for on-prem quickstart.
- Build Helm manifests for Kubernetes and a deployment plan for GCP Cloud Run.

Which of these would you like me to implement next? (I can start scaffolding code and run quick local tests.)
