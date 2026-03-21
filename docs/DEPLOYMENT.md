# PI Remover - Comprehensive Deployment Guide

> **Complete deployment instructions for WSL2, RHEL Linux, and Google Cloud Platform**
>
> **Version**: 2.12.0 | Modular Hybrid Microservices Architecture
>
> This guide uses **Docker Engine** (free for commercial use) instead of Docker Desktop.

---

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [All Service Startup Options](#all-service-startup-options)
3. [Docker Licensing Overview](#docker-licensing-overview)
4. [Deployment Options Summary](#deployment-options-summary)
5. [Option 1: WSL2 + Docker Engine (Windows Development)](#option-1-wsl2--docker-engine-windows-development)
6. [Option 2: RHEL Linux (On-Premise/VM)](#option-2-rhel-linux-on-premisevm)
7. [Option 3: Google Cloud Platform](#option-3-google-cloud-platform)
8. [Environment Reference (DEV vs PROD)](#environment-reference-dev-vs-prod)
9. [Scripts Reference](#scripts-reference)
10. [Troubleshooting](#troubleshooting)

---

# Deployment Overview

## Architecture

The system uses a **Hybrid Microservices Architecture** with automatic local fallback:

```
┌─────────────────┐              ┌─────────────────┐     ┌─────────┐
│   Web Service   │── HTTP+JWT ─▶│   API Service   │────▶│  Redis  │
│   (Port 8082)   │              │   (Port 8080)   │     │         │
│                 │              └─────────────────┘     └─────────┘
│ ┌─────────────┐ │
│ │Local Fallbck│ │ ◄── Automatic if API unavailable
│ └─────────────┘ │
└─────────────────┘
```

## Services to Deploy

| Service | Port | Required | Description |
|---------|------|----------|-------------|
| API Service | 8080 | Optional* | Core PI redaction + authentication |
| Web Service | 8082 | ✅ Yes | Web UI (hybrid mode: API + local fallback) |
| Redis | 6379 | Optional | Shared rate limiting (has fallback) |

> *API Service is optional because Web Service can run standalone with local PIRemover

## Configuration Files

All configuration is in YAML files (no environment variables needed):

```
config/
├── api_service.yaml    # API host, port, CORS
├── web_service.yaml    # Web host, port, API URL, circuit breaker
├── clients.yaml        # JWT secrets, client credentials
├── redis.yaml          # Redis connection
└── logging.yaml        # Logging settings
```

## Quick Start (v2.12.0)

```powershell
# Option 1: Full stack with script
.\scripts\run_comprehensive_tests.ps1 -SkipCleanup

# Option 2: Web only (hybrid mode - API optional)
cd web_service && uvicorn app:app --reload --port 8082

# Option 3: Web only (force local - no API)
cd web_service && python app.py --standalone

# Option 4: Manual full stack
# Terminal 1: Redis
docker run --rm -p 6379:6379 redis:alpine

# Terminal 2: API Service
cd api_service && uvicorn app:app --port 8080

# Terminal 3: Web Service (hybrid mode)
cd web_service && uvicorn app:app --port 8082
```

---

# All Service Startup Options

## Complete Reference Table

| Mode | Command | API Required | Port | Use Case |
|------|---------|:------------:|:----:|----------|
| **CLI** | `python -m pi_remover -i data.csv` | ❌ | - | Batch file processing |
| **Web Hybrid** | `cd web_service && uvicorn app:app` | Optional | 8082 | Production (recommended) |
| **Web Force Local** | `cd web_service && python app.py --standalone` | ❌ | 8082 | Offline/air-gapped |
| **API Only** | `cd api_service && uvicorn app:app` | - | 8080 | Programmatic access |
| **Full Stack Script** | `.\scripts\run_comprehensive_tests.ps1` | ✅ | 8080, 8082 | Development |
| **Docker DEV** | `docker-compose -f docker/docker-compose.dev.yml up` | ✅ | 8080, 8082 | Dev testing |
| **Docker PROD** | `docker-compose -f docker/docker-compose.prod.yml up` | ✅ | 8080, 8082 | Production |

## Recommended for Each Environment

| Environment | Recommended Mode | Why |
|-------------|------------------|-----|
| **Development** | Web Hybrid | Fast iteration, auto-fallback |
| **Testing** | Full Stack Script | Comprehensive coverage |
| **Production** | Docker PROD | Container orchestration |
| **Offline/Air-gapped** | Web Standalone | No external dependencies |

## Hybrid Mode Explanation

The Web Service (`app.py`) implements hybrid mode:
1. **Tries API first** - Uses API Service for redaction
2. **Falls back to local** - If API unavailable, uses local PIRemover
3. **No downtime** - Users experience no interruption

---

# Docker Licensing Overview

## What's Free vs Paid

| Component | License | Commercial Use | Platform |
|-----------|---------|----------------|----------|
| **Docker Engine** | Apache 2.0 | ✅ **FREE** | Linux |
| **Docker CLI** | Apache 2.0 | ✅ **FREE** | All |
| **Docker Compose** | Apache 2.0 | ✅ **FREE** | All |
| **containerd** | Apache 2.0 | ✅ **FREE** | All |
| **Docker Desktop** | Proprietary | ❌ **PAID** for enterprises >250 employees OR >$10M revenue | Windows, macOS |

## Our Approach

This guide uses **Docker Engine directly** (not Docker Desktop) to ensure:
- ✅ 100% free for commercial use
- ✅ No licensing concerns
- ✅ Production-ready setup

---

# Deployment Options Summary

| Option | Best For | Docker Installation | OS |
|--------|----------|--------------------|----|
| **WSL2 + Docker Engine** | Windows developers who can't use Docker Desktop | Install Docker Engine inside WSL2 Ubuntu | Windows 10/11 with WSL2 |
| **RHEL Linux** | On-premise servers, VMs, enterprise Linux | Native Docker Engine/Podman | RHEL 8/9 |
| **Google Cloud Platform** | Scalable cloud deployment | Cloud Run (managed containers) | N/A (managed) |

---

# Option 1: WSL2 + Docker Engine (Windows Development)

## Prerequisites

- Windows 10 version 2004+ or Windows 11
- WSL2 enabled
- Admin access to install WSL2 and Ubuntu

## Step 1: Enable WSL2

Open PowerShell as Administrator:

```powershell
# Enable WSL
wsl --install

# Set WSL2 as default
wsl --set-default-version 2

# Restart your computer
Restart-Computer
```

## Step 2: Install Ubuntu in WSL2

```powershell
# Install Ubuntu 22.04
wsl --install -d Ubuntu-22.04

# Launch Ubuntu and create your user account
wsl -d Ubuntu-22.04
```

## Step 3: Install Docker Engine in WSL2

Run these commands **inside WSL2 Ubuntu**:

```bash
#!/bin/bash
# === DOCKER ENGINE INSTALLATION FOR WSL2 UBUNTU ===

# Update package index
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add your user to docker group (no sudo needed for docker commands)
sudo usermod -aG docker $USER

# Start Docker service
sudo service docker start

# Enable Docker to start on WSL launch
echo "sudo service docker start" >> ~/.bashrc

# Verify installation
docker --version
docker compose version
```

**Important:** Close and reopen your WSL2 terminal for group changes to take effect.

## Step 4: Clone Project and Deploy

```bash
# Navigate to Windows filesystem (accessible from WSL2)
cd /mnt/c/Users/YourUsername/Downloads/PI_Removal

# Or clone fresh
git clone https://github.com/your-repo/PI_Removal.git
cd PI_Removal

# Make scripts executable
chmod +x scripts/*.sh

# Deploy DEV environment
./scripts/deploy-dev.sh

# Deploy PROD environment (after configuring secrets)
./scripts/deploy-prod.sh
```

## Step 5: Access Services

From Windows browser:
- **DEV API Gateway:** http://localhost:8080
- **DEV Web UI:** http://localhost:8082
- **PROD API Gateway:** http://localhost:9080
- **PROD Web UI:** http://localhost:9082

## Step 6: Test Endpoints

```bash
# DEV - Get auth token
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}'

# DEV - Redact text (use token from above)
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"text":"Contact john@email.com at +91 98765 43210"}'

# PROD - Get auth token
curl -X POST http://localhost:9080/prod/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-prod-client","client_secret":"YOUR_PROD_CLIENT_SECRET_HERE"}'

# PROD - Redact text
curl -X POST http://localhost:9080/prod/v1/redact \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"text":"Contact john@email.com at +91 98765 43210"}'
```

---

# Option 2: RHEL Linux (On-Premise/VM)

## Prerequisites

- RHEL 8 or RHEL 9
- Root or sudo access
- Minimum 4GB RAM (8GB recommended for NER)
- 10GB free disk space

## Step 1: Install Docker Engine on RHEL

### Option A: Docker CE (Community Edition)

```bash
#!/bin/bash
# === DOCKER ENGINE INSTALLATION FOR RHEL 8/9 ===

# Remove old versions
sudo yum remove -y docker docker-client docker-client-latest docker-common \
    docker-latest docker-latest-logrotate docker-logrotate docker-engine podman runc

# Install required packages
sudo yum install -y yum-utils

# Add Docker repository
sudo yum-config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo

# Install Docker Engine
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group
sudo usermod -aG docker $USER

# Verify installation
docker --version
docker compose version

# Log out and back in for group changes to take effect
```

### Option B: Podman (Native RHEL Alternative)

Podman is Docker-compatible and pre-installed on RHEL 8/9:

```bash
#!/bin/bash
# === PODMAN SETUP FOR RHEL ===

# Install podman and podman-compose
sudo dnf install -y podman podman-compose

# Enable podman socket for Docker compatibility
systemctl --user enable --now podman.socket

# Create Docker CLI alias (optional)
echo 'alias docker=podman' >> ~/.bashrc
echo 'alias docker-compose=podman-compose' >> ~/.bashrc
source ~/.bashrc

# Verify installation
podman --version
podman-compose --version
```

## Step 2: Configure Firewall

```bash
# Open ports for DEV environment
sudo firewall-cmd --permanent --add-port=8080/tcp  # DEV API
sudo firewall-cmd --permanent --add-port=8082/tcp  # DEV Web

# Open ports for PROD environment
sudo firewall-cmd --permanent --add-port=9080/tcp  # PROD API
sudo firewall-cmd --permanent --add-port=9082/tcp  # PROD Web

# Reload firewall
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

## Step 3: Clone and Deploy

```bash
# Clone project
cd /opt
sudo git clone https://github.com/your-repo/PI_Removal.git
sudo chown -R $USER:$USER PI_Removal
cd PI_Removal

# Make scripts executable
chmod +x scripts/*.sh

# Deploy DEV
./scripts/deploy-dev.sh

# Deploy PROD (after configuring secrets)
cp docker/.env.prod.template docker/.env.prod
vi docker/.env.prod  # Edit with production secrets
./scripts/deploy-prod.sh
```

## Step 4: Configure as Systemd Service (Optional)

Create `/etc/systemd/system/pi-remover.service`:

```ini
[Unit]
Description=PI Remover Service
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/PI_Removal
ExecStart=/usr/bin/docker compose -f docker/docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker/docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-remover
sudo systemctl start pi-remover
sudo systemctl status pi-remover
```

## Step 5: Test Endpoints

```bash
# Health check
curl http://localhost:8080/dev/health
curl http://localhost:9080/prod/health

# DEV - Get token
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}'

# PROD - Get token
curl -X POST http://localhost:9080/prod/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-prod-client","client_secret":"YOUR_PROD_CLIENT_SECRET_HERE"}'
```

---

# Option 3: Google Cloud Platform

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         GOOGLE CLOUD PLATFORM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ARTIFACT REGISTRY                                 │   │
│  │  └── gcr.io/PROJECT_ID/pi-gateway:v2.12.0                          │   │
│  │  └── gcr.io/PROJECT_ID/pi-web:v2.12.0                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────┐    ┌──────────────────────────┐              │
│  │   CLOUD RUN: DEV         │    │   CLOUD RUN: PROD        │              │
│  │   ─────────────────────  │    │   ─────────────────────  │              │
│  │                          │    │                          │              │
│  │   pi-gateway-dev         │    │   pi-gateway-prod        │              │
│  │   └─ /dev/v1/redact      │    │   └─ /prod/v1/redact     │              │
│  │   └─ /dev/auth/token     │    │   └─ /prod/auth/token    │              │
│  │                          │    │                          │              │
│  │   pi-web-dev             │    │   pi-web-prod            │              │
│  │   └─ Web UI              │    │   └─ Web UI              │              │
│  │                          │    │                          │              │
│  │   Memory: 2GB            │    │   Memory: 4GB            │              │
│  │   CPU: 2                 │    │   CPU: 4                 │              │
│  │   Min Instances: 0       │    │   Min Instances: 1       │              │
│  └──────────────────────────┘    └──────────────────────────┘              │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SECRET MANAGER                                    │   │
│  │  └── pi-jwt-secret-dev                                              │   │
│  │  └── pi-jwt-secret-prod                                             │   │
│  │  └── pi-client-credentials-dev                                      │   │
│  │  └── pi-client-credentials-prod                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI installed
- Project created in GCP

## Step 1: Initial GCP Setup

```bash
#!/bin/bash
# === GCP INITIAL SETUP ===

# Install gcloud CLI (if not installed)
# https://cloud.google.com/sdk/docs/install

# Login to GCP
gcloud auth login

# Create new project (or use existing)
export PROJECT_ID="pi-remover-prod"  # Change this
gcloud projects create $PROJECT_ID --name="PI Remover"

# Set as default project
gcloud config set project $PROJECT_ID

# Enable billing (required for Cloud Run)
# Do this in GCP Console: https://console.cloud.google.com/billing

# Enable required APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com

# Set default region
export REGION="us-central1"  # Change to your preferred region
gcloud config set run/region $REGION
```

## Step 2: Create Secrets in Secret Manager

```bash
#!/bin/bash
# === CREATE SECRETS ===

# DEV JWT Secret
echo -n "YOUR_DEV_JWT_SECRET_HERE" | \
  gcloud secrets create pi-jwt-secret-dev --data-file=-

# PROD JWT Secret (generate a new one for production!)
echo -n "YOUR_PROD_JWT_SECRET_HERE" | \
  gcloud secrets create pi-jwt-secret-prod --data-file=-

# DEV Client Credentials
echo -n "pi-dev-client:YOUR_DEV_CLIENT_SECRET_HERE:development" | \
  gcloud secrets create pi-client-creds-dev --data-file=-

# PROD Client Credentials
echo -n "pi-prod-client:YOUR_PROD_CLIENT_SECRET_HERE:production" | \
  gcloud secrets create pi-client-creds-prod --data-file=-

# List secrets
gcloud secrets list
```

## Step 3: Create Artifact Registry Repository

```bash
#!/bin/bash
# === CREATE ARTIFACT REGISTRY ===

export REGION="us-central1"

# Create Docker repository
gcloud artifacts repositories create pi-remover \
    --repository-format=docker \
    --location=$REGION \
    --description="PI Remover Docker images"

# Configure Docker authentication
gcloud auth configure-docker ${REGION}-docker.pkg.dev
```

## Step 4: Build and Push Docker Images

```bash
#!/bin/bash
# === BUILD AND PUSH IMAGES ===

export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"
export REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/pi-remover"
export VERSION="v2.12.0"

# Navigate to project root
cd /path/to/PI_Removal

# Build API Gateway image
docker build -t ${REGISTRY}/pi-gateway:${VERSION} -f api_service/Dockerfile .
docker push ${REGISTRY}/pi-gateway:${VERSION}

# Build Web Service image
docker build -t ${REGISTRY}/pi-web:${VERSION} -f web_service/Dockerfile .
docker push ${REGISTRY}/pi-web:${VERSION}

# Tag as latest
docker tag ${REGISTRY}/pi-gateway:${VERSION} ${REGISTRY}/pi-gateway:latest
docker tag ${REGISTRY}/pi-web:${VERSION} ${REGISTRY}/pi-web:latest
docker push ${REGISTRY}/pi-gateway:latest
docker push ${REGISTRY}/pi-web:latest

# Verify images
gcloud artifacts docker images list ${REGISTRY}
```

## Step 5: Deploy DEV Environment to Cloud Run

```bash
#!/bin/bash
# === DEPLOY DEV SERVICES ===

export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"
export REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/pi-remover"

# Deploy DEV API Gateway
gcloud run deploy pi-gateway-dev \
    --image=${REGISTRY}/pi-gateway:latest \
    --platform=managed \
    --region=$REGION \
    --memory=2Gi \
    --cpu=2 \
    --timeout=300 \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=5 \
    --allow-unauthenticated \
    --set-env-vars="ENVIRONMENT=development" \
    --set-env-vars="LOG_LEVEL=DEBUG" \
    --set-env-vars="ENABLE_NER=true" \
    --set-env-vars="RATE_LIMIT_REQUESTS=1000" \
    --set-env-vars="CORS_ORIGINS=*" \
    --set-secrets="JWT_SECRET_KEY=pi-jwt-secret-dev:latest" \
    --set-secrets="AUTH_CLIENTS=pi-client-creds-dev:latest"

# Deploy DEV Web Service
gcloud run deploy pi-web-dev \
    --image=${REGISTRY}/pi-web:latest \
    --platform=managed \
    --region=$REGION \
    --memory=1Gi \
    --cpu=1 \
    --timeout=300 \
    --concurrency=80 \
    --min-instances=0 \
    --max-instances=3 \
    --allow-unauthenticated \
    --set-env-vars="ENVIRONMENT=development" \
    --set-env-vars="LOG_LEVEL=DEBUG"

# Get service URLs
echo ""
echo "=== DEV SERVICES DEPLOYED ==="
gcloud run services describe pi-gateway-dev --region=$REGION --format='value(status.url)'
gcloud run services describe pi-web-dev --region=$REGION --format='value(status.url)'
```

## Step 6: Deploy PROD Environment to Cloud Run

```bash
#!/bin/bash
# === DEPLOY PROD SERVICES ===

export PROJECT_ID=$(gcloud config get-value project)
export REGION="us-central1"
export REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/pi-remover"

# Deploy PROD API Gateway
gcloud run deploy pi-gateway-prod \
    --image=${REGISTRY}/pi-gateway:latest \
    --platform=managed \
    --region=$REGION \
    --memory=4Gi \
    --cpu=4 \
    --timeout=300 \
    --concurrency=100 \
    --min-instances=1 \
    --max-instances=10 \
    --allow-unauthenticated \
    --set-env-vars="ENVIRONMENT=production" \
    --set-env-vars="LOG_LEVEL=WARNING" \
    --set-env-vars="ENABLE_NER=true" \
    --set-env-vars="RATE_LIMIT_REQUESTS=100" \
    --set-env-vars="CORS_ORIGINS=https://your-domain.com" \
    --set-secrets="JWT_SECRET_KEY=pi-jwt-secret-prod:latest" \
    --set-secrets="AUTH_CLIENTS=pi-client-creds-prod:latest"

# Deploy PROD Web Service
gcloud run deploy pi-web-prod \
    --image=${REGISTRY}/pi-web:latest \
    --platform=managed \
    --region=$REGION \
    --memory=2Gi \
    --cpu=2 \
    --timeout=300 \
    --concurrency=100 \
    --min-instances=1 \
    --max-instances=5 \
    --allow-unauthenticated \
    --set-env-vars="ENVIRONMENT=production" \
    --set-env-vars="LOG_LEVEL=WARNING"

# Get service URLs
echo ""
echo "=== PROD SERVICES DEPLOYED ==="
gcloud run services describe pi-gateway-prod --region=$REGION --format='value(status.url)'
gcloud run services describe pi-web-prod --region=$REGION --format='value(status.url)'
```

## Step 7: Test GCP Endpoints

```bash
#!/bin/bash
# === TEST GCP ENDPOINTS ===

# Get service URLs
DEV_API=$(gcloud run services describe pi-gateway-dev --region=us-central1 --format='value(status.url)')
PROD_API=$(gcloud run services describe pi-gateway-prod --region=us-central1 --format='value(status.url)')

echo "DEV API: $DEV_API"
echo "PROD API: $PROD_API"

# Test DEV health
curl ${DEV_API}/dev/health

# Test PROD health
curl ${PROD_API}/prod/health

# Get DEV token
curl -X POST ${DEV_API}/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}'

# Get PROD token
curl -X POST ${PROD_API}/prod/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-prod-client","client_secret":"YOUR_PROD_CLIENT_SECRET_HERE"}'
```

## Step 8: Set Up Custom Domain (Optional)

```bash
# Map custom domain to Cloud Run service
gcloud beta run domain-mappings create \
    --service=pi-gateway-prod \
    --domain=api.your-domain.com \
    --region=us-central1

gcloud beta run domain-mappings create \
    --service=pi-web-prod \
    --domain=pi.your-domain.com \
    --region=us-central1

# Follow DNS instructions provided by gcloud
```

---

# Environment Reference (DEV vs PROD)

## Endpoint URLs

### Local Deployment (WSL2/RHEL)

| Service | DEV URL | PROD URL |
|---------|---------|----------|
| API Gateway | `http://localhost:8080` | `http://localhost:9080` |
| Web UI | `http://localhost:8082` | `http://localhost:9082` |
| API Docs (Swagger) | `http://localhost:8080/docs` | Disabled |
| Health Check | `http://localhost:8080/dev/health` | `http://localhost:9080/prod/health` |

### Google Cloud Platform

| Service | DEV URL | PROD URL |
|---------|---------|----------|
| API Gateway | `https://pi-gateway-dev-HASH.run.app` | `https://pi-gateway-prod-HASH.run.app` |
| Web UI | `https://pi-web-dev-HASH.run.app` | `https://pi-web-prod-HASH.run.app` |
| Custom Domain | N/A | `https://api.your-domain.com` |

## API Endpoints

### DEV Environment (prefix: `/dev`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dev/auth/token` | POST | Get JWT authentication token |
| `/dev/v1/redact` | POST | Redact single text |
| `/dev/v1/redact/batch` | POST | Redact multiple texts |
| `/dev/v1/pi-types` | GET | List supported PI types |
| `/dev/health` | GET | Health check |

### PROD Environment (prefix: `/prod`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/prod/auth/token` | POST | Get JWT authentication token |
| `/prod/v1/redact` | POST | Redact single text |
| `/prod/v1/redact/batch` | POST | Redact multiple texts |
| `/prod/v1/pi-types` | GET | List supported PI types |
| `/prod/health` | GET | Health check |

## Credentials

### DEV Credentials (Hardcoded)

```
Client ID:     pi-dev-client
Client Secret: YOUR_DEV_CLIENT_SECRET_HERE
JWT Secret:    YOUR_DEV_JWT_SECRET_HERE
```

### PROD Credentials (Hardcoded - Change for Real Production!)

```
Client ID:     pi-prod-client
Client Secret: YOUR_PROD_CLIENT_SECRET_HERE
JWT Secret:    YOUR_PROD_JWT_SECRET_HERE
```

### Test Credentials

```
Client ID:     pi-test-client
Client Secret: TestClientSecret1234567890ABCDEF
```

## Environment Differences

| Setting | DEV | PROD |
|---------|-----|------|
| Log Level | DEBUG | WARNING |
| Rate Limit | 1000 req/min | 100 req/min |
| JWT Expiry | 60 minutes | 30 minutes |
| CORS | `*` (all origins) | Restricted domains |
| Swagger UI | Enabled (`/docs`) | Disabled |
| Debug Endpoints | Enabled | Disabled |
| Min Instances (GCP) | 0 (scale to zero) | 1 (always on) |

---

# Scripts Reference

## Shell Scripts for Linux/WSL2

The following scripts are located in `scripts/` directory:

| Script | Description |
|--------|-------------|
| `setup-docker-wsl2.sh` | Install Docker Engine in WSL2 Ubuntu |
| `setup-docker-rhel.sh` | Install Docker Engine/Podman on RHEL 8/9 |
| `deploy-dev.sh` | Deploy DEV environment (ports 8080/8082) |
| `deploy-prod.sh` | Deploy PROD environment (ports 9080/9082) |
| `deploy-gcp.sh` | Deploy to Google Cloud Run |
| `promote-to-prod.sh` | Promote DEV → PROD (Linux/WSL2) |
| `promote-to-prod-gcp.sh` | Promote DEV → PROD on GCP with rollback support |

## PowerShell Scripts for Windows

| Script | Description |
|--------|-------------|
| `deploy-dev.ps1` | Deploy DEV environment (Windows/Docker Desktop) |
| `deploy-prod.ps1` | Deploy PROD environment (Windows/Docker Desktop) |
| `promote-to-prod.ps1` | Promote DEV → PROD (Windows) |

## Promotion Scripts

### Linux/WSL2 Promotion

```bash
# Full promotion with tests and confirmation
./scripts/promote-to-prod.sh

# Skip tests (not recommended)
./scripts/promote-to-prod.sh --skip-tests

# Skip confirmation prompt
./scripts/promote-to-prod.sh --skip-confirmation
```

The promotion script:
1. Runs pre-flight checks (Docker, env files, secrets)
2. Executes pytest tests
3. Tests DEV health endpoints
4. Prompts for confirmation
5. Deploys to PROD (with --build)
6. Verifies PROD health

### GCP Promotion

```bash
# Full promotion DEV → PROD on Cloud Run
./scripts/promote-to-prod-gcp.sh

# Skip tests
./scripts/promote-to-prod-gcp.sh --skip-tests

# Rollback to previous PROD revision
./scripts/promote-to-prod-gcp.sh --rollback

# Specify project/region
./scripts/promote-to-prod-gcp.sh --project my-project --region us-east1
```

The GCP promotion script:
1. Verifies gcloud authentication
2. Checks DEV services exist
3. Runs pytest tests
4. Tests DEV Cloud Run health
5. Shows current PROD status
6. Deploys DEV images to PROD services
7. Verifies PROD health
8. Provides rollback instructions

---

# Troubleshooting

## Common Issues

### Docker daemon not running (WSL2)

```bash
# Start Docker service
sudo service docker start

# Check status
sudo service docker status

# If using systemd in WSL2
sudo systemctl start docker
```

### Permission denied when running docker

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker
```

### Port already in use

```bash
# Find process using port
sudo lsof -i :8080
# or
sudo netstat -tulpn | grep 8080

# Kill process
sudo kill -9 <PID>

# Or stop existing containers
docker compose -f docker/docker-compose.dev.yml down
```

### Container won't start (out of memory)

```bash
# Check container logs
docker logs pi-gateway-dev

# Increase memory limit in docker-compose.yml
# Or disable NER for smaller memory footprint
docker run -e ENABLE_NER=false ...
```

### GCP: Permission denied for Secret Manager

```bash
# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding pi-jwt-secret-prod \
    --member="serviceAccount:$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### GCP: Image not found

```bash
# Verify image exists
gcloud artifacts docker images list $REGISTRY

# Re-push image
docker push ${REGISTRY}/pi-gateway:latest
```

---

*Document Version: 1.0*  
*Last Updated: December 2025*  
*Covers: WSL2, RHEL 8/9, Google Cloud Platform*
