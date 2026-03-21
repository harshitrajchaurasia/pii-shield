# PI Remover — DEV/PROD Environment Strategy

> **Enterprise-Grade Deployment Architecture**
> 
> **Version:** 2.12.0 | Modular Microservices Architecture
>
> This document outlines the complete strategy for maintaining separate DEV and PROD environments, including API endpoints, testing workflows, and promotion pipelines.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Approach Options Analysis](#3-approach-options-analysis)
4. [Recommended Approach: Multi-Environment Docker Compose](#4-recommended-approach-multi-environment-docker-compose)
5. [Environment-Specific Configurations](#5-environment-specific-configurations)
6. [API Endpoint Strategy](#6-api-endpoint-strategy)
7. [Authentication & Security per Environment](#7-authentication--security-per-environment)
8. [Testing Strategy for DEV](#8-testing-strategy-for-dev)
9. [CI/CD Pipeline Design](#9-cicd-pipeline-design)
10. [Promotion Workflow: DEV → PROD](#10-promotion-workflow-dev--prod)
11. [Monitoring & Observability](#11-monitoring--observability)
12. [Rollback Strategy](#12-rollback-strategy)
13. [Implementation Checklist](#13-implementation-checklist)

---

## 1. Executive Summary

### The Challenge

For enterprise deployments, we need:
- **Separate DEV and PROD endpoints** — Different URLs, configurations, and security levels
- **Isolated testing** — All changes validated in DEV before touching PROD
- **Controlled promotion** — Clear workflow to move tested code to PROD
- **Audit trail** — Track what was deployed, when, and by whom
- **Zero-downtime deployments** — PROD must remain available during updates

### The Solution

We will implement a **multi-environment architecture** with:

| Environment | Purpose | URL Pattern | Security Level |
|-------------|---------|-------------|----------------|
| **DEV** | Development, testing, integration | `http://localhost:8080` or `https://dev-pi.example.com` | Relaxed (verbose logs, debug endpoints) |
| **PROD** | Production traffic | `https://pi.example.com` | Hardened (minimal logs, rate limits, WAF) |

---

## 2. Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ENTERPRISE DEPLOYMENT                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────┐       ┌─────────────────────────┐              │
│  │      DEV ENVIRONMENT    │       │     PROD ENVIRONMENT    │              │
│  │  ─────────────────────  │       │  ─────────────────────  │              │
│  │                         │       │                         │              │
│  │  ┌─────────────────┐    │       │  ┌─────────────────┐    │              │
│  │  │ Load Balancer   │    │       │  │ Load Balancer   │    │              │
│  │  │ (optional)      │    │       │  │ + WAF           │    │              │
│  │  └────────┬────────┘    │       │  └────────┬────────┘    │              │
│  │           │             │       │           │             │              │
│  │  ┌────────┴────────┐    │       │  ┌────────┴────────┐    │              │
│  │  │ pi-gateway-dev  │    │       │  │ pi-gateway-prod │    │              │
│  │  │ Port: 8080      │    │       │  │ Port: 8080      │    │              │
│  │  │ NER: ON         │    │       │  │ NER: ON         │    │              │
│  │  │ Debug: ON       │    │       │  │ Debug: OFF      │    │              │
│  │  └────────┬────────┘    │       │  └────────┬────────┘    │              │
│  │           │             │       │           │             │              │
│  │  ┌────────┴────────┐    │       │  ┌────────┴────────┐    │              │
│  │  │ pi-web-dev      │    │       │  │ pi-web-prod     │    │              │
│  │  │ Port: 8082      │    │       │  │ Port: 8082      │    │              │
│  │  └─────────────────┘    │       │  └─────────────────┘    │              │
│  │                         │       │                         │              │
│  │  Config: config.dev.yaml│       │  Config: config.prod.yaml              │
│  │  Clients: dev-client    │       │  Clients: prod-client-* │              │
│  │  Rate Limit: 1000/min   │       │  Rate Limit: 100/min    │              │
│  │  Logs: DEBUG            │       │  Logs: WARNING          │              │
│  └─────────────────────────┘       └─────────────────────────┘              │
│                                                                              │
│                    ┌─────────────────────────────┐                          │
│                    │      SHARED COMPONENTS      │                          │
│                    │  ─────────────────────────  │                          │
│                    │  • Docker Registry          │                          │
│                    │  • CI/CD Pipeline           │                          │
│                    │  • Secrets Manager          │                          │
│                    │  • Log Aggregator           │                          │
│                    │  • Metrics/Monitoring       │                          │
│                    └─────────────────────────────┘                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Container Naming Convention

| Service | DEV Container | PROD Container |
|---------|---------------|----------------|
| API Gateway | `pi-gateway-dev` | `pi-gateway-prod` |
| Web Service | `pi-web-dev` | `pi-web-prod` |

### Port Allocation

| Service | DEV Port | PROD Port | Notes |
|---------|----------|-----------|-------|
| API Gateway | 8080 | 9080 (or via reverse proxy) | Different ports for local; same port in isolated networks |
| Web Service | 8082 | 9082 (or via reverse proxy) | Different ports for local |

---

## 3. Approach Options Analysis

### Option A: Single Codebase, Environment Variables

**How it works**: Same Docker image, different env vars for DEV vs PROD.

```yaml
# DEV
docker run -e ENVIRONMENT=development -e LOG_LEVEL=DEBUG pi-gateway

# PROD
docker run -e ENVIRONMENT=production -e LOG_LEVEL=WARNING pi-gateway
```

| Pros | Cons |
|------|------|
| Simple to implement | Same image in DEV and PROD (less isolation) |
| Single image to manage | Risk of env var misconfiguration |
| Fast deployments | Harder to test PROD config in DEV |

**Verdict**: ✅ Good for small teams, quick iteration

---

### Option B: Separate Docker Compose Files

**How it works**: Different compose files for each environment.

```
docker-compose.dev.yml   → DEV configuration
docker-compose.prod.yml  → PROD configuration
```

| Pros | Cons |
|------|------|
| Clear separation | Duplicate configuration |
| Environment-specific settings | Need to sync changes across files |
| Easy local testing | More files to maintain |

**Verdict**: ✅ **RECOMMENDED** — Best balance of isolation and simplicity

---

### Option C: Kubernetes with Namespaces

**How it works**: K8s namespaces (`pi-dev`, `pi-prod`) with separate configs.

```yaml
# DEV namespace
kubectl apply -f k8s/dev/ -n pi-dev

# PROD namespace
kubectl apply -f k8s/prod/ -n pi-prod
```

| Pros | Cons |
|------|------|
| Full isolation | Requires K8s infrastructure |
| Production-grade scaling | More complex setup |
| Built-in secrets management | Overkill for small deployments |

**Verdict**: ⚠️ For large-scale enterprise only

---

### Option D: Cloud Run Services (GCP)

**How it works**: Separate Cloud Run services for DEV and PROD.

```bash
gcloud run deploy pi-gateway-dev --image gcr.io/project/pi-gateway:dev
gcloud run deploy pi-gateway-prod --image gcr.io/project/pi-gateway:v2.5.0
```

| Pros | Cons |
|------|------|
| Managed infrastructure | Vendor lock-in |
| Auto-scaling | Cost per environment |
| Easy rollback via revisions | Requires GCP setup |

**Verdict**: ✅ Good for cloud-native deployments

---

## 4. Recommended Approach: Multi-Environment Docker Compose

### File Structure

```
PI_Removal/
├── docker/
│   ├── docker-compose.base.yml    # Shared configuration
│   ├── docker-compose.dev.yml     # DEV overrides
│   ├── docker-compose.prod.yml    # PROD overrides
│   └── .env.dev                   # DEV environment variables
│   └── .env.prod                  # PROD environment variables (template)
│
├── config/
│   ├── config.dev.yaml            # DEV runtime config
│   └── config.prod.yaml           # PROD runtime config
│
├── api_service/
│   └── Dockerfile                 # Single Dockerfile (multi-stage)
│
└── scripts/
    ├── deploy-dev.ps1             # DEV deployment script
    ├── deploy-prod.ps1            # PROD deployment script
    └── promote-to-prod.ps1        # Promotion workflow
```

### docker-compose.base.yml (Shared)

```yaml
version: '3.8'

x-common-env: &common-env
  PYTHONDONTWRITEBYTECODE: 1
  PYTHONUNBUFFERED: 1
  ENABLE_NER: "true"

x-healthcheck: &healthcheck
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s

services:
  pi-gateway:
    build:
      context: ..
      dockerfile: api_service/Dockerfile
    environment:
      <<: *common-env
    healthcheck:
      <<: *healthcheck
    restart: unless-stopped

  pi-web-service:
    build:
      context: ..
      dockerfile: web_service/Dockerfile
    environment:
      <<: *common-env
    healthcheck:
      <<: *healthcheck
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
    restart: unless-stopped
```

### docker-compose.dev.yml

```yaml
version: '3.8'

services:
  pi-gateway:
    extends:
      file: docker-compose.base.yml
      service: pi-gateway
    container_name: pi-gateway-dev
    ports:
      - "8080:8080"
    environment:
      ENVIRONMENT: development
      LOG_LEVEL: DEBUG
      JWT_SECRET_KEY: ${DEV_JWT_SECRET:-dev-secret-key-not-for-production}
      AUTH_CLIENTS: "dev-client:devsecret123456789012345678901234:development"
      RATE_LIMIT_REQUESTS: 1000
      RATE_LIMIT_WINDOW_SECONDS: 60
      ENABLE_METRICS: "true"
      # DEV-specific: Enable debug endpoints
      ENABLE_DEBUG_ENDPOINTS: "true"
      # DEV-specific: Relaxed CORS
      CORS_ORIGINS: "*"
    volumes:
      - ../logs/dev:/app/logs
    labels:
      environment: development
      version: ${VERSION:-dev}

  pi-web-service:
    extends:
      file: docker-compose.base.yml
      service: pi-web-service
    container_name: pi-web-dev
    ports:
      - "8082:8080"
    environment:
      ENVIRONMENT: development
      LOG_LEVEL: DEBUG
    volumes:
      - ../logs/dev:/app/logs
    labels:
      environment: development
```

### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  pi-gateway:
    extends:
      file: docker-compose.base.yml
      service: pi-gateway
    container_name: pi-gateway-prod
    ports:
      - "9080:8080"
    environment:
      ENVIRONMENT: production
      LOG_LEVEL: WARNING
      JWT_SECRET_KEY: ${PROD_JWT_SECRET}  # Required, no default
      AUTH_CLIENTS: ${PROD_AUTH_CLIENTS}  # Required, no default
      RATE_LIMIT_REQUESTS: 100
      RATE_LIMIT_WINDOW_SECONDS: 60
      ENABLE_METRICS: "true"
      # PROD-specific: Disable debug endpoints
      ENABLE_DEBUG_ENDPOINTS: "false"
      # PROD-specific: Restricted CORS
      CORS_ORIGINS: "https://your-app.example.com,https://internal.example.com"
    volumes:
      - ../logs/prod:/app/logs
    labels:
      environment: production
      version: ${VERSION:-latest}
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  pi-web-service:
    extends:
      file: docker-compose.base.yml
      service: pi-web-service
    container_name: pi-web-prod
    ports:
      - "9082:8080"
    environment:
      ENVIRONMENT: production
      LOG_LEVEL: WARNING
    volumes:
      - ../logs/prod:/app/logs
    labels:
      environment: production
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

---

## 5. Environment-Specific Configurations

### config.dev.yaml

```yaml
# =============================================================================
# PI REMOVER - DEVELOPMENT CONFIGURATION
# =============================================================================
environment: development

general:
  output_dir: "output/dev"
  log_level: "DEBUG"
  show_progress: true

security:
  jwt_expiry_minutes: 60  # Longer for dev convenience
  rate_limit_requests: 1000
  rate_limit_window_seconds: 60
  cors_origins: "*"
  enable_debug_endpoints: true

features:
  enable_ner: true
  enable_metrics: true
  enable_audit_logging: true
  audit_log_file: "logs/dev/audit.log"

# DEV-only: Test clients
clients:
  - id: dev-client
    secret: devsecret123456789012345678901234
    name: Development Client
    rate_limit: 1000
  - id: test-client
    secret: testsecret12345678901234567890123
    name: Test Automation Client
    rate_limit: 5000
```

### config.prod.yaml

```yaml
# =============================================================================
# PI REMOVER - PRODUCTION CONFIGURATION
# =============================================================================
environment: production

general:
  output_dir: "output/prod"
  log_level: "WARNING"
  show_progress: false

security:
  jwt_expiry_minutes: 30  # Shorter for security
  rate_limit_requests: 100
  rate_limit_window_seconds: 60
  cors_origins: "https://your-app.example.com"
  enable_debug_endpoints: false

features:
  enable_ner: true
  enable_metrics: true
  enable_audit_logging: true
  audit_log_file: "logs/prod/audit.log"

# PROD clients loaded from secrets manager (not in file)
clients: []  # Loaded from AUTH_CLIENTS env var or secrets file
```

---

## 6. API Endpoint Strategy

### Option 6A: Separate Ports (Recommended for Local)

```
DEV:  http://localhost:8080  (API Gateway)
      http://localhost:8082  (Web Service)

PROD: http://localhost:9080  (API Gateway)
      http://localhost:9082  (Web Service)
```

### Option 6B: Separate Hostnames (Recommended for Cloud)

```
DEV:  https://dev-pi-gateway.example.com
      https://dev-pi-web.example.com

PROD: https://pi-gateway.example.com
      https://pi-web.example.com
```

### Option 6C: Same Host, Different Paths

```
DEV:  https://api.example.com/dev/v1/redact
PROD: https://api.example.com/v1/redact
```

Not recommended — mixing environments on same host increases risk.

### API Versioning Strategy

```
/v1/redact        → Current stable API
/v2/redact        → Next version (in DEV only until stable)
/health           → No version (always available)
/auth/token       → No version (auth is separate)
```

---

## 7. Authentication & Security per Environment

### DEV Environment

| Setting | Value | Reason |
|---------|-------|--------|
| JWT Secret | Static dev key | Consistent for testing |
| JWT Expiry | 60 minutes | Longer for dev convenience |
| Rate Limit | 1000 req/min | High limit for testing |
| CORS | `*` | Allow any origin for testing |
| Debug Endpoints | Enabled | `/debug/config`, `/debug/stats` |
| Audit Logs | Verbose | Full request/response logging |

### PROD Environment

| Setting | Value | Reason |
|---------|-------|--------|
| JWT Secret | From secrets manager | Never in code/config |
| JWT Expiry | 30 minutes | Short for security |
| Rate Limit | 100 req/min | Prevent abuse |
| CORS | Specific domains | Only trusted origins |
| Debug Endpoints | Disabled | Security hardening |
| Audit Logs | Minimal | Only security events |

### Client Credential Management

```
DEV Clients:
├── dev-client (for manual testing)
├── test-client (for automated tests)
└── integration-client (for CI/CD)

PROD Clients:
├── service-a (LLM gateway)
├── service-b (batch processor)
└── admin-client (operations)
```

---

## 8. Testing Strategy for DEV

### Test Levels

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TESTING PYRAMID                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                        ┌───────────────┐                                    │
│                        │   E2E Tests   │  ← Run in DEV environment          │
│                        │   (Selenium)  │    before promotion                │
│                        └───────────────┘                                    │
│                                                                              │
│                   ┌─────────────────────────┐                               │
│                   │   Integration Tests     │  ← API contract tests         │
│                   │   (pytest + requests)   │    against DEV endpoints      │
│                   └─────────────────────────┘                               │
│                                                                              │
│              ┌───────────────────────────────────┐                          │
│              │        Unit Tests                 │  ← Run before Docker     │
│              │   (pytest, fast, no dependencies) │    build                 │
│              └───────────────────────────────────┘                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Test Categories

#### 1. Unit Tests (Pre-Build)

```bash
# Run before any deployment
pytest tests/test_remover.py tests/test_comprehensive_pi.py -v
```

**What they test**:
- Core redaction logic
- Regex patterns
- Configuration parsing
- Data cleaning

#### 2. Integration Tests (DEV Environment)

```bash
# Run against DEV API
pytest tests/test_api.py -v --base-url=http://localhost:8080
```

**What they test**:
- API endpoints respond correctly
- Authentication works
- Rate limiting functions
- Error handling

#### 3. Contract Tests (API Schema)

```python
# tests/test_api_contract.py
def test_redact_response_schema():
    """Verify API response matches expected schema."""
    response = client.post("/v1/redact", json={"text": "test@test.com"})
    assert "redacted_text" in response.json()
    assert "request_id" in response.json()
    assert "processing_time_ms" in response.json()
```

#### 4. Performance Tests (DEV Only)

```bash
# Load test against DEV
locust -f tests/load_test.py --host=http://localhost:8080
```

**Criteria**:
- p99 latency < 100ms
- Throughput > 100 req/sec
- No errors under load

#### 5. Security Tests (DEV Only)

```bash
# OWASP ZAP scan against DEV
docker run -t owasp/zap2docker-stable zap-baseline.py -t http://localhost:8080
```

### Test Automation Script

```powershell
# scripts/test-dev.ps1

Write-Host "🧪 Running PI Remover Test Suite" -ForegroundColor Cyan

# Step 1: Unit Tests
Write-Host "`n📋 Step 1: Unit Tests" -ForegroundColor Yellow
python -m pytest tests/test_remover.py tests/test_comprehensive_pi.py -v
if ($LASTEXITCODE -ne 0) { exit 1 }

# Step 2: Start DEV containers
Write-Host "`n🐳 Step 2: Starting DEV containers" -ForegroundColor Yellow
docker-compose -f docker/docker-compose.dev.yml up -d
Start-Sleep -Seconds 10

# Step 3: Health Check
Write-Host "`n❤️ Step 3: Health Check" -ForegroundColor Yellow
$health = Invoke-RestMethod -Uri "http://localhost:8080/health" -ErrorAction Stop
Write-Host "Status: $($health.status)"

# Step 4: Integration Tests
Write-Host "`n🔗 Step 4: Integration Tests" -ForegroundColor Yellow
python -m pytest tests/test_api.py -v --base-url=http://localhost:8080

# Step 5: Cleanup
Write-Host "`n🧹 Step 5: Cleanup" -ForegroundColor Yellow
docker-compose -f docker/docker-compose.dev.yml down

Write-Host "`n✅ All tests passed!" -ForegroundColor Green
```

---

## 9. CI/CD Pipeline Design

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CI/CD PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  COMMIT → BUILD → TEST → DEPLOY DEV → TEST DEV → APPROVE → DEPLOY PROD     │
│     │       │       │         │           │          │           │          │
│     │       │       │         │           │          │           │          │
│     ▼       ▼       ▼         ▼           ▼          ▼           ▼          │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────────┐ ┌─────────┐ ┌───────┐ ┌─────────┐     │
│  │Git  │ │Docker│ │Unit │ │ DEV    │ │ Integ  │ │Manual │ │ PROD   │      │
│  │Push │ │Build │ │Tests│ │ Deploy │ │ Tests  │ │Review │ │ Deploy │      │
│  └─────┘ └─────┘ └─────┘ └─────────┘ └─────────┘ └───────┘ └─────────┘     │
│                                                                              │
│  Automatic ─────────────────────────────►  Manual Gate  ─────► Automatic   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### GitHub Actions Workflow

```yaml
# .github/workflows/ci-cd.yml

name: PI Remover CI/CD

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # =========================================================================
  # STAGE 1: BUILD & UNIT TEST
  # =========================================================================
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run unit tests
        run: pytest tests/test_remover.py tests/test_comprehensive_pi.py -v --cov=src/pi_remover

      - name: Build Docker images
        run: |
          docker build -t pi-gateway:${{ github.sha }} -f api_service/Dockerfile .
          docker build -t pi-web-service:${{ github.sha }} -f web_service/Dockerfile .

      - name: Push to registry
        if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop'
        run: |
          echo ${{ secrets.GITHUB_TOKEN }} | docker login ghcr.io -u ${{ github.actor }} --password-stdin
          docker tag pi-gateway:${{ github.sha }} ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}/pi-gateway:${{ github.sha }}
          docker push ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}/pi-gateway:${{ github.sha }}

  # =========================================================================
  # STAGE 2: DEPLOY TO DEV
  # =========================================================================
  deploy-dev:
    needs: build-and-test
    if: github.ref == 'refs/heads/develop'
    runs-on: ubuntu-latest
    environment: development
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to DEV
        run: |
          # Deploy to DEV environment
          docker-compose -f docker/docker-compose.dev.yml up -d
        env:
          IMAGE_TAG: ${{ github.sha }}

      - name: Wait for health
        run: |
          sleep 30
          curl -f http://localhost:8080/health || exit 1

  # =========================================================================
  # STAGE 3: INTEGRATION TESTS ON DEV
  # =========================================================================
  test-dev:
    needs: deploy-dev
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run integration tests
        run: |
          pip install pytest requests
          pytest tests/test_api.py -v --base-url=http://localhost:8080

  # =========================================================================
  # STAGE 4: DEPLOY TO PROD (Manual Approval Required)
  # =========================================================================
  deploy-prod:
    needs: test-dev
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: production  # Requires manual approval in GitHub settings
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to PROD
        run: |
          # Deploy to PROD environment
          docker-compose -f docker/docker-compose.prod.yml up -d
        env:
          IMAGE_TAG: ${{ github.sha }}
          PROD_JWT_SECRET: ${{ secrets.PROD_JWT_SECRET }}
          PROD_AUTH_CLIENTS: ${{ secrets.PROD_AUTH_CLIENTS }}

      - name: Smoke test PROD
        run: |
          sleep 30
          curl -f http://localhost:9080/health || exit 1
```

---

## 10. Promotion Workflow: DEV → PROD

### Manual Promotion Steps

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PROMOTION WORKFLOW: DEV → PROD                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 1: VERIFY DEV IS STABLE                                        │    │
│  │ ─────────────────────────────                                       │    │
│  │ □ All unit tests passing                                            │    │
│  │ □ All integration tests passing                                     │    │
│  │ □ No critical errors in DEV logs (last 24 hours)                   │    │
│  │ □ Performance metrics within acceptable range                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 2: CREATE RELEASE TAG                                          │    │
│  │ ──────────────────────────                                          │    │
│  │ git tag -a v2.5.1 -m "Release 2.5.1 - PI Remover"                  │    │
│  │ git push origin v2.5.1                                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 3: BUILD RELEASE IMAGE                                         │    │
│  │ ───────────────────────────                                         │    │
│  │ docker build -t pi-gateway:v2.5.1 -f api_service/Dockerfile .      │    │
│  │ docker tag pi-gateway:v2.5.1 registry.example.com/pi-gateway:v2.5.1│    │
│  │ docker push registry.example.com/pi-gateway:v2.5.1                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 4: DEPLOY TO PROD (with approval)                              │    │
│  │ ──────────────────────────────────────                              │    │
│  │ □ Get approval from: Tech Lead + Security                          │    │
│  │ □ Schedule deployment window (if required)                          │    │
│  │ □ Notify stakeholders                                               │    │
│  │                                                                      │    │
│  │ docker-compose -f docker/docker-compose.prod.yml up -d             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 5: VERIFY PROD                                                  │    │
│  │ ──────────────────                                                   │    │
│  │ □ Health check passes                                               │    │
│  │ □ Smoke tests pass                                                  │    │
│  │ □ Monitor error rate for 15 minutes                                 │    │
│  │ □ Confirm with stakeholders                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ STEP 6: DOCUMENT DEPLOYMENT                                         │    │
│  │ ──────────────────────────                                          │    │
│  │ □ Update CHANGELOG.md                                               │    │
│  │ □ Close related tickets/issues                                      │    │
│  │ □ Send deployment notification                                      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Promotion Script

```powershell
# scripts/promote-to-prod.ps1

param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

Write-Host "🚀 PI Remover - Promote to PROD" -ForegroundColor Cyan
Write-Host "Version: $Version" -ForegroundColor Yellow

# Step 1: Verify DEV is healthy
Write-Host "`n📋 Step 1: Verifying DEV environment..." -ForegroundColor Yellow
$devHealth = Invoke-RestMethod -Uri "http://localhost:8080/health" -ErrorAction Stop
if ($devHealth.status -ne "healthy") {
    Write-Host "❌ DEV is not healthy. Aborting." -ForegroundColor Red
    exit 1
}
Write-Host "✅ DEV is healthy" -ForegroundColor Green

# Step 2: Run final tests
Write-Host "`n🧪 Step 2: Running final tests..." -ForegroundColor Yellow
python -m pytest tests/test_remover.py -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Tests failed. Aborting." -ForegroundColor Red
    exit 1
}
Write-Host "✅ All tests passed" -ForegroundColor Green

# Step 3: Tag release
Write-Host "`n🏷️ Step 3: Creating release tag..." -ForegroundColor Yellow
if (-not $DryRun) {
    git tag -a "v$Version" -m "Release $Version"
    git push origin "v$Version"
}
Write-Host "✅ Tagged v$Version" -ForegroundColor Green

# Step 4: Build and push image
Write-Host "`n🐳 Step 4: Building PROD image..." -ForegroundColor Yellow
if (-not $DryRun) {
    docker build -t pi-gateway:$Version -f api_service/Dockerfile .
    docker build -t pi-web-service:$Version -f web_service/Dockerfile .
}
Write-Host "✅ Images built" -ForegroundColor Green

# Step 5: Deploy to PROD
Write-Host "`n🚀 Step 5: Deploying to PROD..." -ForegroundColor Yellow
if (-not $DryRun) {
    $env:VERSION = $Version
    docker-compose -f docker/docker-compose.prod.yml up -d
}
Write-Host "✅ Deployed to PROD" -ForegroundColor Green

# Step 6: Verify PROD
Write-Host "`n❤️ Step 6: Verifying PROD..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
$prodHealth = Invoke-RestMethod -Uri "http://localhost:9080/health" -ErrorAction Stop
if ($prodHealth.status -ne "healthy") {
    Write-Host "❌ PROD health check failed!" -ForegroundColor Red
    Write-Host "⚠️ Consider rollback: docker-compose -f docker/docker-compose.prod.yml down" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ PROD is healthy" -ForegroundColor Green

Write-Host "`n✨ Promotion to PROD complete! Version: $Version" -ForegroundColor Cyan
```

---

## 11. Monitoring & Observability

### Metrics to Track

| Metric | DEV Threshold | PROD Threshold | Action if Exceeded |
|--------|---------------|----------------|-------------------|
| Error Rate | < 5% | < 0.1% | Alert + Investigate |
| p99 Latency | < 500ms | < 100ms | Scale or optimize |
| Request Rate | N/A | > 1000/min sustained | Auto-scale |
| Memory Usage | < 80% | < 70% | Investigate leak |
| CPU Usage | < 90% | < 80% | Scale horizontally |

### Log Aggregation

```yaml
# DEV: Verbose logs to local files
logs/dev/
├── api.log          # All API requests
├── audit.log        # Security events
└── error.log        # Errors only

# PROD: Structured logs to central system
# - Send to CloudWatch / Stackdriver / ELK
# - Retain for 90 days
# - Alert on ERROR level
```

---

## 12. Rollback Strategy

### Immediate Rollback (< 5 minutes)

```powershell
# If PROD deployment fails, rollback to previous version

# Option 1: Docker Compose (if using version labels)
$env:VERSION = "previous-version"
docker-compose -f docker/docker-compose.prod.yml up -d

# Option 2: Direct container rollback
docker stop pi-gateway-prod
docker run -d --name pi-gateway-prod -p 9080:8080 pi-gateway:previous-version
```

### Rollback Checklist

```
□ Stop new traffic (if using load balancer)
□ Deploy previous version
□ Verify health check
□ Resume traffic
□ Notify stakeholders
□ Create incident report
```

---

## 13. Implementation Checklist

### Phase 1: Infrastructure Setup (Week 1)

- [ ] Create `docker/` folder structure
- [ ] Create `docker-compose.base.yml`
- [ ] Create `docker-compose.dev.yml`
- [ ] Create `docker-compose.prod.yml`
- [ ] Create `.env.dev` and `.env.prod.template`
- [ ] Create `config/config.dev.yaml`
- [ ] Create `config/config.prod.yaml`

### Phase 2: Security Configuration (Week 1)

- [ ] Set up DEV client credentials
- [ ] Configure PROD secrets management (e.g., Azure Key Vault, AWS Secrets Manager)
- [ ] Configure environment-specific rate limits
- [ ] Configure environment-specific CORS

### Phase 3: Testing Infrastructure (Week 2)

- [ ] Update `tests/test_api.py` to accept `--base-url` parameter
- [ ] Create `tests/test_api_contract.py` for schema validation
- [ ] Create `tests/load_test.py` for performance testing
- [ ] Create `scripts/test-dev.ps1`

### Phase 4: CI/CD Pipeline (Week 2)

- [ ] Create `.github/workflows/ci-cd.yml`
- [ ] Configure GitHub environments (development, production)
- [ ] Set up manual approval for PROD deployments
- [ ] Configure secrets in GitHub

### Phase 5: Scripts & Documentation (Week 3)

- [ ] Create `scripts/deploy-dev.ps1`
- [ ] Create `scripts/deploy-prod.ps1`
- [ ] Create `scripts/promote-to-prod.ps1`
- [ ] Update README.md with new deployment instructions
- [ ] Create runbook for operations team

### Phase 6: Validation (Week 3)

- [ ] Test full DEV deployment
- [ ] Test full PROD deployment (staging)
- [ ] Test rollback procedure
- [ ] Test promotion workflow
- [ ] Security review

---

## Summary

This document outlines a comprehensive DEV/PROD strategy that:

1. **Separates environments** with different ports, configurations, and security levels
2. **Uses Docker Compose** for consistent deployments across environments
3. **Implements a testing pyramid** with unit, integration, and E2E tests
4. **Provides a clear promotion workflow** with manual approval gates
5. **Includes monitoring and rollback** strategies for production safety

The approach balances enterprise requirements (security, auditability, control) with developer productivity (fast iteration, clear workflows).

---

*Document Version: 1.0*
*Last Updated: December 13, 2025*
*Author: PI Remover DevOps Team*
