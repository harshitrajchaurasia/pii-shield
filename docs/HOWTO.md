# PI Remover - Complete How-To Guide

> **The Ultimate Reference** for running, configuring, updating, and troubleshooting PI Remover.
> Every question answered. Every scenario covered.
> 
> **Architecture:** v2.12.0 Modular Hybrid Microservices | **PIRemover Core:** v2.12.0
>
> **v2.12.0 Update:** This version introduces **Modular Architecture** (9 focused modules) with **Hybrid Microservices** and automatic local fallback. See [Hybrid Mode](#hybrid-mode-automatic-fallback) for details.

---

## 📑 Table of Contents

### Getting Started
- [Quick Start (30 seconds)](#quick-start-30-seconds)
- [Project Structure](#project-structure)
- [Installation Options](#installation-options)

### Hybrid Microservices Architecture (v2.9.0+, v2.12.0)
- [Understanding the Architecture](#understanding-the-architecture)
- [Hybrid Mode (Automatic Fallback)](#hybrid-mode-automatic-fallback)
- [All Service Startup Options](#all-service-startup-options)
- [YAML Configuration](#yaml-configuration)
- [How to Start All Services](#how-to-start-all-services)
- [Circuit Breaker Configuration](#circuit-breaker-configuration)
- [Redis Rate Limiting](#redis-rate-limiting)

### Running PI Remover
- [How to Run CLI](#how-to-run-cli)
- [How to Run Web UI](#how-to-run-web-ui)
- [How to Run API Gateway](#how-to-run-api-gateway)
- [How to Run with Docker](#how-to-run-with-docker)

### DEV/PROD Environments
- [DEV vs PROD Endpoints](#dev-vs-prod-endpoints)
- [How to Deploy DEV](#how-to-deploy-dev)
- [How to Deploy PROD](#how-to-deploy-prod)
- [How to Promote DEV to PROD](#how-to-promote-dev-to-prod)

### Configuration
- [How to Change Detection Settings](#how-to-change-detection-settings)
- [How to Add Custom Patterns](#how-to-add-custom-patterns)
- [How to Whitelist Domains/Phones](#how-to-whitelist-domainsphones)
- [How to Change Replacement Tokens](#how-to-change-replacement-tokens)
- [How to Enable/Disable PI Types](#how-to-enabledisable-pi-types)

### Security & Authentication
- [How to Update Credentials (YAML)](#how-to-update-credentials-yaml)
- [How to Change JWT Secret](#how-to-change-jwt-secret)
- [How to Add API Clients](#how-to-add-api-clients)
- [How to Change Rate Limits](#how-to-change-rate-limits)
- [How to Get Auth Token](#how-to-get-auth-token)
- [How to Configure CORS](#how-to-configure-cors)

### API Endpoint Management
- [How to Manage API Endpoints](#how-to-manage-api-endpoints)
- [How to Enable Endpoints](#how-to-enable-endpoints)
- [How to Disable Endpoints](#how-to-disable-endpoints)
- [How to Add a New API Endpoint](#how-to-add-a-new-api-endpoint)
- [How to Remove an API Endpoint](#how-to-remove-an-api-endpoint)

### Performance
- [How to Enable Fast Mode](#how-to-enable-fast-mode)
- [How to Select spaCy Model](#how-to-select-spacy-model-v271)
- [How to Improve Performance](#how-to-improve-performance)
- [How to Handle Large Files](#how-to-handle-large-files)

### File Processing
- [How to Process CSV Files](#how-to-process-csv-files)
- [How to Process Excel Files](#how-to-process-excel-files)
- [How to Process JSON Files](#how-to-process-json-files)
- [How to Process Text Files](#how-to-process-text-files)
- [How to Process Multiple Columns](#how-to-process-multiple-columns)

### Docker & Deployment
- [How to Build Docker Images](#how-to-build-docker-images)
- [How to Change Docker Ports](#how-to-change-docker-ports)
- [How to Set Memory Limits](#how-to-set-memory-limits)
- [How to View Docker Logs](#how-to-view-docker-logs)
- [How to Deploy to Google Cloud](#how-to-deploy-to-google-cloud)

### Testing
- [How to Run Tests](#how-to-run-tests)
- [How to Run Comprehensive Tests](#how-to-run-comprehensive-tests)
- [How to Test API Endpoints](#how-to-test-api-endpoints)
- [How to Validate Redaction](#how-to-validate-redaction)

### Maintenance
- [How to Update Dependencies](#how-to-update-dependencies)
- [How to Update spaCy Model](#how-to-update-spacy-model)
- [How to View Audit Logs](#how-to-view-audit-logs)
- [How to Generate Reports](#how-to-generate-reports)

### Troubleshooting
- [Common Errors & Fixes](#common-errors--fixes)
- [Microservices Troubleshooting](#microservices-troubleshooting)
- [Debug Mode](#debug-mode)
- [Health Checks](#health-checks)

### Reference
- [All Environment Variables](#all-environment-variables)
- [All CLI Options](#all-cli-options)
- [All API Endpoints](#all-api-endpoints)
- [Supported PI Types](#supported-pi-types)
- [Quick Reference Card](#quick-reference-card)

### Management & Business FAQ
- [What is PI Remover and why do we need it?](#what-is-pi-remover-and-why-do-we-need-it)
- [What types of data can PI Remover detect?](#what-types-of-data-can-pi-remover-detect)
- [How accurate is the detection?](#how-accurate-is-the-detection)
- [What happens if PI is missed?](#what-happens-if-pi-is-missed)
- [What happens if non-PI is incorrectly redacted?](#what-happens-if-non-pi-is-incorrectly-redacted)
- [Can we use this with LLMs like ChatGPT/Claude?](#can-we-use-this-with-llms-like-chatgptclaude)
- [Is this tool compliant with GDPR/HIPAA/PCI-DSS?](#is-this-tool-compliant-with-gdprhipaapci-dss)
- [How fast is the processing?](#how-fast-is-the-processing)
- [Can this scale for enterprise use?](#can-this-scale-for-enterprise-use)
- [What if we need to detect new PI types?](#what-if-we-need-to-detect-new-pi-types)
- [How do we know the tool is working correctly?](#how-do-we-know-the-tool-is-working-correctly)
- [What are the infrastructure requirements?](#what-are-the-infrastructure-requirements)
- [What is the total cost of ownership?](#what-is-the-total-cost-of-ownership)
- [How is the tool secured?](#how-is-the-tool-secured)
- [Can we audit who used the tool?](#can-we-audit-who-used-the-tool)
- [What happens during an outage?](#what-happens-during-an-outage)
- [How do we maintain this tool?](#how-do-we-maintain-this-tool)
- [Can this be customized for our organization?](#can-this-be-customized-for-our-organization)

---

# Getting Started

## Quick Start (30 seconds)

```powershell
# CLI - Process a file (v2.12.0 modular CLI)
python -m pi_remover -i data.csv -c "Description" --fast

# Web UI - Start browser interface
cd web_service && uvicorn app:app --port 8082
# Open http://localhost:8082

# API Gateway - Start REST API
cd api_service && uvicorn app:app --port 8080
# Access http://localhost:8080/docs
```

---

## Project Structure

```
PI_Removal/
├── src/pi_remover/           # 📦 Core Python package (v2.12.0 Modular)
│   ├── __init__.py           # Package exports
│   ├── __main__.py           # CLI: python -m pi_remover
│   ├── core.py               # Facade module (re-exports)
│   ├── config.py             # PIRemoverConfig, YAML loading
│   ├── patterns.py           # PIPatterns (125+ regex)
│   ├── dictionaries.py       # Name dictionaries
│   ├── data_classes.py       # Redaction, RedactionResult
│   ├── utils.py              # Logging, multiprocessing
│   ├── ner.py                # SpacyNER, SpacyModelManager
│   ├── remover.py            # Main PIRemover class
│   ├── sanitizer.py          # Input sanitization
│   ├── security.py           # JWT, rate limiting
│   └── processors/           # File processors (CSV, JSON, TXT)
│
├── api_service/              # 🔌 REST API Gateway (port 8080)
├── web_service/              # 🌐 Web UI Service (port 8082)
│   ├── app.py                # Hybrid mode (API + local fallback)
│   └── api_client.py         # HTTP client + circuit breaker
│
├── config/                   # YAML configuration
│   ├── api_service.yaml      # API settings
│   ├── web_service.yaml      # Web + circuit breaker settings
│   ├── clients.yaml          # JWT secrets, rate limits
│   ├── redis.yaml            # Redis connection
│   └── logging.yaml          # Logging configuration
│
├── shared/                   # Shared infrastructure
│   ├── config_loader.py      # YAML config loader
│   ├── logging_config.py     # Structured JSON logging
│   └── redis_client.py       # Redis + in-memory fallback
│
├── docker/                   # 🐳 Docker configs (DEV/PROD)
├── scripts/                  # 🚀 Deployment & test scripts
├── docs/                     # 📚 Documentation (15+ files)
├── tests/                    # 🧪 Test suite (61 tests pass)
├── data/                     # 📊 Name dictionaries
├── others/                   # 📁 Archived files
│
├── config.yaml               # ⚙️ PI patterns configuration
├── pyproject.toml            # 📦 Python packaging
├── requirements.txt          # 📋 Dependencies
├── CHANGELOG.md              # 📜 Version history
└── SECURITY.md               # 🔐 Security documentation
```

---

## Installation Options

### Option 1: Install as Package (Recommended)

```powershell
# Basic install
pip install -e .

# With all features (NER, Excel, API)
pip install -e ".[all]"

# Specific features
pip install -e ".[full]"    # NER support
pip install -e ".[excel]"   # Excel support
pip install -e ".[api]"     # API dependencies
pip install -e ".[dev]"     # Development tools
```

### Option 2: Install from requirements.txt

```powershell
pip install -r requirements.txt
python -m spacy download en_core_web_lg  # For NER
```

### Option 3: Docker (No installation needed)

```powershell
# API Gateway
docker-compose -f docker/docker-compose.dev.yml up

# Web Service
docker-compose -f web_service/docker-compose.yml up
```

---

# Microservices Architecture (v2.9.0+)

## Understanding the Architecture

The system uses a **Hybrid Microservices Architecture** (introduced in v2.9.0, current in v2.12.0):

```
┌─────────────────┐              ┌─────────────────┐     ┌─────────┐
│   Web Service   │── HTTP+JWT ─▶│   API Service   │────▶│  Redis  │
│   (Port 8082)   │              │   (Port 8080)   │     │         │
│                 │              │                 │     └─────────┘
│ ┌─────────────┐ │              │ ┌─────────────┐ │
│ │ API Client  │ │              │ │ PIRemover   │ │ ◄── v2.12.0 Modular
│ │ + Circuit   │ │              │ │ (9 modules) │ │
│ │   Breaker   │ │              │ └─────────────┘ │
│ └─────────────┘ │              │                 │
│                 │              └─────────────────┘
│ ┌─────────────┐ │
│ │   Local     │ │ ◄── Automatic Fallback
│ │  PIRemover  │ │
│ └─────────────┘ │
└─────────────────┘
```

**Key Features:**
- **Hybrid Mode**: API first with automatic local fallback
- Web Service tries API → falls back to local PIRemover if API unavailable
- All configuration in YAML files (no environment variables needed)
- Circuit breaker protects against cascading failures
- Redis provides shared rate limiting (with in-memory fallback)
- **v2.12.0**: PIRemover Core now has modular architecture (9 modules)
- Structured JSON logging for ELK/Splunk

---

## Hybrid Mode (Automatic Fallback)

The Web Service (`app.py`) implements **hybrid mode** - it tries the API first and automatically falls back to local processing if the API is unavailable.

### How It Works

```
Request arrives at Web Service
          │
          ▼
    ┌─────────────────────────────┐
    │  Is --standalone flag set?  │
    └─────────────────────────────┘
          │
     ┌────┴────┐
    Yes       No
     │         │
     │         ▼
     │   ┌──────────────┐
     │   │ Try API Call │
     │   └──────┬───────┘
     │          │
     │    ┌─────┴─────┐
     │    │ API OK?   │
     │    └─────┬─────┘
     │     ┌────┴────┐
     │    Yes       No
     │     │         │
     ▼     ▼         ▼
┌──────────────────────────┐
│   Use Local PIRemover    │
│  (automatic fallback)    │
└──────────────────────────┘
```

### Benefits

| Scenario | API Running | API Down |
|----------|:-----------:|:--------:|
| **Normal Mode** | Uses API (fast, centralized logging) | Auto-fallback to local |
| **Standalone Mode** | Always uses local | Always uses local |
| **User Experience** | No interruption | No interruption |

### When to Use Which Mode

| Mode | Command | Best For |
|------|---------|----------|
| **Hybrid** (default) | `uvicorn app:app` | Production - best of both worlds |
| **Standalone** | `python app.py --standalone` | Offline/disconnected environments |

---

## All Service Startup Options

### 📊 Quick Comparison Table

| Mode | Command | API Required | Port | Use Case |
|------|---------|:------------:|:----:|----------|
| **CLI** | `python -m pi_remover` | ❌ | - | Batch file processing |
| **Web Hybrid** | `cd web_service && uvicorn app:app` | Optional | 8082 | Production (recommended) |
| **Web Force Local** | `cd web_service && python app.py --standalone` | ❌ | 8082 | Offline/disconnected |
| **API Only** | `cd api_service && uvicorn app:app` | - | 8080 | Programmatic access |
| **Full Stack** | Manual or script | ✅ | 8080, 8082 | Enterprise deployment |
| **Docker DEV** | `docker-compose -f docker/docker-compose.dev.yml up` | ✅ | 8080, 8082 | Development testing |
| **Docker PROD** | `docker-compose -f docker/docker-compose.prod.yml up` | ✅ | 8080, 8082 | Production deployment |

---

### 1. CLI Mode (No Server)

Process files directly from command line:

```powershell
# Basic usage (v2.12.0 modular CLI)
python -m pi_remover -i data.csv -c "Description"

# Fast mode (regex only, no NER)
python -m pi_remover -i data.csv -c "Description" --fast

# With full NER mode
python -m pi_remover -i data.csv -c "Description" --full

# Standalone CLI (from others/standalone/)
cd others/standalone
python pi_remover_standalone.py -i data.csv -c "Column" --full --model en_core_web_lg
```

---

### 2. Web Service - Hybrid Mode (Recommended)

Tries API first, falls back to local if API unavailable:

```powershell
cd web_service
uvicorn app:app --reload --port 8082
```

- **URL**: http://localhost:8082
- **File**: `web_service/app.py`
- **Behavior**: API unavailable? Automatically uses local PIRemover

---

### 3. Web Service - Force Local Mode

Use `app.py` but skip API entirely:

```powershell
cd web_service
python app.py --standalone
```

- **URL**: http://localhost:8082
- **Behavior**: Never calls API, always uses local PIRemover

---

### 4. API Service Only (Backend)

Run just the API gateway for programmatic access:

```powershell
cd api_service
uvicorn app:app --reload --port 8080
```

- **DEV Endpoints**: http://localhost:8080/dev/...
- **PROD Endpoints**: http://localhost:8080/prod/...
- **Swagger Docs**: http://localhost:8080/docs

---

### 6. Full Microservices Stack (Manual)

Run all services in separate terminals:

```powershell
# Terminal 1: Redis (optional, for rate limiting)
docker run --rm -p 6379:6379 redis:alpine

# Terminal 2: API Service
cd api_service
uvicorn app:app --reload --port 8080

# Terminal 3: Web Service (hybrid mode)
cd web_service
uvicorn app:app --reload --port 8082
```

---

### 7. Full Stack via Script

Use the comprehensive test script:

```powershell
.\scripts\run_comprehensive_tests.ps1
```

Automatically starts Redis, API, and Web services.

---

### 8. Docker - DEV Environment

```powershell
docker-compose -f docker/docker-compose.dev.yml up -d
```

---

### 9. Docker - PROD Environment

```powershell
docker-compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod up -d
```

---

## YAML Configuration (v2.9.0+)

All configuration is now in the `config/` directory:

```
config/
├── api_service.yaml    # API host, port, CORS, PI remover settings
├── web_service.yaml    # Web host, port, API URL, circuit breaker
├── clients.yaml        # JWT secrets, client credentials, rate limits
├── redis.yaml          # Redis connection settings
└── logging.yaml        # Log format, level, handlers
```

### Edit API Service Settings

```yaml
# config/api_service.yaml
server:
  host: "0.0.0.0"
  port: 8080           # Change API port here
  environment: "development"

pi_remover:
  enable_ner: false    # Set true for full NER mode
  use_typed_tokens: true

cors:
  allowed_origins:
    - "http://localhost:8082"
    - "http://localhost:3000"  # Add your frontend URL
```

### Edit Web Service Settings

```yaml
# config/web_service.yaml
server:
  host: "0.0.0.0"
  port: 8082           # Change Web port here

api:
  base_url: "http://localhost:8080"  # API service URL
  timeout_seconds: 30

circuit_breaker:
  failure_threshold: 5      # Open after 5 failures
  recovery_timeout: 30      # Try again after 30 seconds
  half_open_requests: 3     # Test requests in half-open state
```

### Edit Client Credentials

```yaml
# config/clients.yaml
clients:
  pi-dev-client:
    secret: "YOUR_DEV_CLIENT_SECRET_HERE"
    rate_limit: 1000
    environment: "development"
    
  pi-prod-client:
    secret: "YOUR_PROD_CLIENT_SECRET_HERE"
    rate_limit: 10000
    environment: "production"
    
  # Add new clients here!
  my-new-client:
    secret: "generate-a-32-char-secret-here-1234"
    rate_limit: 500
    environment: "development"

jwt:
  secret_key: "YOUR_DEV_JWT_SECRET_HERE"
  algorithm: "HS256"
  expiry_minutes: 30
```

### Edit Redis Settings

```yaml
# config/redis.yaml
redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null        # Set for production
  
  pool:
    max_connections: 10
```

---

## How to Start All Services

> **See [All Service Startup Options](#all-service-startup-options)** for the complete reference of all startup modes.

### Quick Start Options

| Goal | Command |
|------|---------|
| **Full Stack (Script)** | `.\scripts\run_comprehensive_tests.ps1` |
| **Web Hybrid** | `cd web_service && uvicorn app:app --port 8082` |
| **Web Force Local** | `cd web_service && python app.py --standalone` |
| **API Only** | `cd api_service && uvicorn app:app --port 8080` |
| **Docker DEV** | `docker-compose -f docker/docker-compose.dev.yml up -d` |

### Option 1: Using Comprehensive Test Script (Recommended)

```powershell
# This starts Redis, API, and Web in separate terminals
.\scripts\run_comprehensive_tests.ps1
```

### Option 2: Manual Startup (Hybrid Mode)

```powershell
# Terminal 1: Redis (optional, but recommended)
docker run --rm -p 6379:6379 redis:alpine

# Terminal 2: API Service
cd api_service
uvicorn app:app --reload --port 8080

# Terminal 3: Web Service (hybrid mode - API + local fallback)
cd web_service
uvicorn app:app --reload --port 8082
```

### Option 3: Standalone Mode (No API)

```powershell
# Web Service only - uses local PIRemover (force local mode)
cd web_service
python app.py --standalone
```

### Option 4: Using Docker Compose

```powershell
docker-compose -f docker/docker-compose.dev.yml up -d
```

### Verify All Services

```powershell
# Check API
curl http://localhost:8080/dev/health

# Check Web
curl http://localhost:8082/health

# Check Redis
redis-cli ping
```

---

## Circuit Breaker Configuration

The circuit breaker prevents cascading failures when the API service is unavailable.

### States

```
CLOSED (normal) ──5 failures──▶ OPEN (fail fast)
                                     │
                              30 seconds
                                     │
                                     ▼
                              HALF_OPEN (testing)
                                     │
                        ┌────────────┴────────────┐
                   3 successes              1 failure
                        │                        │
                        ▼                        ▼
                     CLOSED                    OPEN
```

### Configure Circuit Breaker

```yaml
# config/web_service.yaml
circuit_breaker:
  failure_threshold: 5      # Open after N consecutive failures
  recovery_timeout: 30      # Seconds to wait before trying again
  half_open_requests: 3     # Requests allowed in half-open state
```

### Make Circuit Breaker More Tolerant

```yaml
# For unstable networks
circuit_breaker:
  failure_threshold: 10     # More failures before opening
  recovery_timeout: 60      # Wait longer before retry
  half_open_requests: 5     # More test requests
```

---

## Redis Rate Limiting

Redis provides shared rate limiting across multiple instances.

### With Redis Running

```
Web Service 1 ──┐
                ├──▶ Redis ──▶ Shared rate limit counters
Web Service 2 ──┘
```

### Without Redis (In-Memory Fallback)

If Redis is unavailable, the system automatically uses in-memory rate limiting:

```
Web Service 1 ──▶ Local counter (instance 1)
Web Service 2 ──▶ Local counter (instance 2)
```

> ⚠️ **Note:** In-memory fallback means each instance tracks limits separately.

### Start Redis

```powershell
# Docker (easiest)
docker run --rm -p 6379:6379 redis:alpine

# Or install Redis locally
```

### Configure Redis

```yaml
# config/redis.yaml
redis:
  host: "redis-server"    # Change for production
  port: 6379
  password: "secure-password"  # Add for production
```

---

# Running PI Remover

## How to Run CLI

### Basic Usage

```powershell
# Process single column
python -m pi_remover -i data.csv -c "Description"

# Fast mode (no NER)
python -m pi_remover -i data.csv -c "Description" --fast

# With audit report
python -m pi_remover -i data.csv -c "Description" --audit

# Custom output directory
python -m pi_remover -i data.csv -c "Description" -o ./cleaned/
```

### As Python Module

```powershell
python -m pi_remover -i data.csv -c "Description" --fast
```

### Multiple Columns

```powershell
python -m pi_remover -i data.csv -c "Description" -c "Notes" -c "Comments"
```

---

## How to Run Web UI

### Without Docker

```powershell
cd web_service
pip install -r requirements.txt
python app.py
```

Access: **http://localhost:8082**

### With Docker

```powershell
cd web_service
docker-compose up -d
```

Access: **http://localhost:8082**

### Features
- Paste text directly or upload files
- Toggle Fast Mode checkbox
- Dark/Light theme
- Download cleaned files

---

## How to Run API Gateway

### Without Docker

```powershell
cd api_service
pip install -r requirements.txt
python app.py
```

### With Docker

```powershell
cd api_service
docker-compose up -d
```

### Quick Test

```powershell
# Get token
$response = Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" `
  -Method POST -ContentType "application/json" `
  -Body '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}'

# Redact text
Invoke-RestMethod -Uri "http://localhost:8080/dev/v1/redact" `
  -Method POST -Headers @{Authorization="Bearer $($response.access_token)"} `
  -ContentType "application/json" `
  -Body '{"text":"Email: john@example.com"}'
```

---

## How to Run with Docker

### Build Images

```powershell
# API Gateway
docker build -t pi-gateway -f api_service/Dockerfile .

# Web Service
docker build -t pi-web -f web_service/Dockerfile .
```

### Run Containers

```powershell
# API Gateway (Full mode)
docker run -d -p 8080:8080 --name pi-gateway pi-gateway

# API Gateway (Fast mode)
docker run -d -p 8080:8080 -e ENABLE_NER=false --name pi-gateway-fast pi-gateway

# Web Service
docker run -d -p 8082:8080 --name pi-web pi-web
```

### Using Docker Compose

```powershell
# DEV environment
docker-compose -f docker/docker-compose.dev.yml up -d

# PROD environment
docker-compose -f docker/docker-compose.prod.yml --env-file docker/.env.prod up -d
```

---

# DEV/PROD Environments

## DEV vs PROD Endpoints

### DEV Environment (Port 8080)

| Endpoint | URL | Auth |
|----------|-----|:----:|
| Auth Token | `POST http://localhost:8080/dev/auth/token` | ❌ |
| Redact | `POST http://localhost:8080/dev/v1/redact` | ✅ |
| Batch Redact | `POST http://localhost:8080/dev/v1/redact/batch` | ✅ |
| Health | `GET http://localhost:8080/dev/health` | ✅ |
| PI Types | `GET http://localhost:8080/dev/v1/pi-types` | ✅ |
| Models | `GET http://localhost:8080/dev/v1/models` | ✅ |
| Swagger | `GET http://localhost:8080/docs` | ❌ |

**DEV Credentials:**
- Client ID: `pi-dev-client`
- Client Secret: `YOUR_DEV_CLIENT_SECRET_HERE`

### PROD Environment (Port 9080)

| Endpoint | URL | Auth |
|----------|-----|:----:|
| Auth Token | `POST http://localhost:9080/prod/auth/token` | ❌ |
| Redact | `POST http://localhost:9080/prod/v1/redact` | ✅ |
| Batch Redact | `POST http://localhost:9080/prod/v1/redact/batch` | ✅ |
| Health | `GET http://localhost:9080/prod/health` | ✅ |
| PI Types | `GET http://localhost:9080/prod/v1/pi-types` | ✅ |
| Models | `GET http://localhost:9080/prod/v1/models` | ✅ |

**PROD Credentials:** Configured in `docker/.env.prod`

### Environment Differences

| Setting | DEV | PROD |
|---------|-----|------|
| API Port | 8080 | 9080 |
| Web Port | 8082 | 9082 |
| Log Level | DEBUG | WARNING |
| Rate Limit | 1000/min | 100/min |
| JWT Expiry | 60 min | 30 min |
| Debug Endpoints | ✅ Enabled | ❌ Disabled |
| CORS | `*` (all) | Restricted |
| Swagger UI | ✅ Enabled | ❌ Disabled |

---

## How to Deploy DEV

### Using Script

```powershell
.\scripts\deploy-dev.ps1
```

### Manual

```powershell
docker-compose -f docker/docker-compose.dev.yml up -d
```

### Verify

```powershell
curl http://localhost:8080/dev/health
```

---

## How to Deploy PROD

### Step 1: Configure Secrets

```powershell
# Copy template
cp docker\.env.prod.template docker\.env.prod

# Edit secrets
notepad docker\.env.prod
```

**Required in .env.prod:**
```
PROD_JWT_SECRET=your-256-bit-secret-here
PROD_AUTH_CLIENTS=prod-client:your-32-char-secret:production
PROD_CORS_ORIGINS=https://your-app.com
```

### Step 2: Deploy

```powershell
.\scripts\deploy-prod.ps1
```

### Step 3: Verify

```powershell
curl http://localhost:9080/prod/health
```

---

## How to Promote DEV to PROD

### Using Script (Recommended)

```powershell
.\scripts\promote-to-prod.ps1
```

This will:
1. ✅ Run pre-flight checks
2. ✅ Run all tests
3. ✅ Verify DEV health
4. ✅ Ask for confirmation
5. ✅ Deploy to PROD
6. ✅ Run health checks

### Manual Promotion

```powershell
# 1. Run tests
python -m pytest tests/ -v

# 2. Verify DEV works
curl http://localhost:8080/dev/health

# 3. Deploy PROD
.\scripts\deploy-prod.ps1

# 4. Verify PROD
curl http://localhost:9080/prod/health
```

---

# Configuration

## How to Change Detection Settings

Edit `config.yaml`:

```yaml
# Enable/disable detection engines
engines:
  regex: true           # Pattern matching
  ner: true             # AI-based (spaCy)
  dictionaries: true    # Name dictionaries
  context_rules: true   # Signature blocks
```

---

## How to Add Custom Patterns

This is a **comprehensive guide** to adding new PI detection patterns to increase capture percentage.

### Understanding the Pattern Architecture

PI Remover uses a **multi-layer detection strategy**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     PI DETECTION ARCHITECTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Layer 1: REGEX PATTERNS (PIPatterns class)                                 │
│  ├── Static patterns: EMAIL, PHONE, IP, etc.                               │
│  ├── Contextual patterns: NAME_WITH_TITLE, NAME_CONTEXT_FROM_BY            │
│  └── Organization-specific: RFC, CR, ASSET_ID_EXTENDED                     │
│                                                                              │
│  Layer 2: NER (Named Entity Recognition)                                    │
│  ├── spaCy model: PERSON, ORG, GPE, LOC entities                           │
│  └── False positive blocklist filtering                                    │
│                                                                              │
│  Layer 3: DICTIONARY-BASED                                                  │
│  ├── data/names.txt: Common first names                                    │
│  ├── data/names.json: Names with metadata                                  │
│  └── Context-aware matching                                                │
│                                                                              │
│  Layer 4: CONTEXTUAL RULES                                                  │
│  ├── "From:", "By:", "Caller:", "Assigned to:" triggers                   │
│  ├── Signature block detection                                             │
│  └── Email-to-name correlation                                             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Step-by-Step: Adding a New Pattern

#### Step 1: Identify the Pattern

First, analyze your data to find undetected PI:

```python
# Quick analysis script
import pandas as pd
import re

df = pd.read_csv('your_data.csv')
column = df['Description'].dropna()

# Find potential patterns
# Example: Find strings matching "PROJECT-XXXX"
pattern = r'\bPROJECT-\d{4,6}\b'
matches = column.str.findall(pattern).explode().dropna()
print(f"Found {len(matches)} matches")
print(matches.value_counts().head(20))
```

#### Step 2: Design the Regex

Key regex principles for PI detection:

| Element | Purpose | Example |
|---------|---------|---------|
| `\b` | Word boundary | `\bEMP\d+\b` matches "EMP123" not "TEMP123" |
| `(?:...)` | Non-capturing group | `(?:Inc\|INC)` for case variations |
| `[A-Z]` | Capital letters | `[A-Z][a-z]+` for proper names |
| `\d{n,m}` | Digit range | `\d{7,10}` for 7-10 digit IDs |
| `(?i)` | Case insensitive | `(?i)ticket` matches "Ticket", "TICKET" |
| `(?=...)` | Lookahead | `(?=.*@)` ensures @ exists ahead |

**Common pattern templates:**

```python
# ID with prefix
ID_PATTERN = r'\bPREFIX[-_]?\d{6,10}\b'

# ID with labeled context
LABELED_PATTERN = r'\b(?:Label|ID|No)[:\s]*(\w+)\b'

# Format with separators
FORMATTED_PATTERN = r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'

# Case-insensitive with variations
FLEXIBLE_PATTERN = r'(?i)\b(?:var1|var2|var3)\s*[:#]?\s*(\S+)\b'
```

#### Step 3: Add Pattern to PIPatterns Class

Edit `src/pi_remover/patterns.py`:

```python
class PIPatterns:
    """Compiled regex patterns for PI detection."""
    
    # ... existing patterns ...
    
    # === YOUR NEW PATTERN (v2.12.X) ===
    # Description: What this pattern detects
    # Examples: EXAMPLE-12345, EXAMPLE:67890
    YOUR_NEW_PATTERN = re.compile(
        r'\bYOUR_REGEX_HERE\b',
        re.IGNORECASE  # Optional: add flags as needed
    )
```

**Location in file:** `src/pi_remover/patterns.py` (656 lines) - Add after related patterns.

**Naming convention:**
- Use SCREAMING_SNAKE_CASE
- Be descriptive: `RFC_NUMBER`, `ASSET_ID_EXTENDED`, `SERVICE_ACCOUNT_NT`
- Add version comment: `# v2.8.X`

#### Step 4: Create Detection Method (if needed)

For simple patterns, add to an existing detection method. For complex patterns, create a new method in `src/pi_remover/remover.py`:

```python
# In src/pi_remover/remover.py (PIRemover class)
def _redact_your_new_type(self, text: str) -> List[Tuple[int, int, str]]:
    """Detect and mark YOUR_NEW_TYPE for redaction.
    
    Patterns detected:
    - EXAMPLE-12345 (example format)
    - EXAMPLE:67890 (alternate format)
    
    Returns:
        List of (start, end, replacement_token) tuples
    """
    positions = []
    token = self._get_typed_token("YOUR_TYPE")
    
    # Simple pattern matching
    for match in self.patterns.YOUR_NEW_PATTERN.finditer(text):
        positions.append((match.start(), match.end(), token))
    
    # If pattern has capture groups
    for match in self.patterns.YOUR_LABELED_PATTERN.finditer(text):
        if match.group(1):  # The captured group
            value = match.group(1)
            # Find the position of the captured value
            value_start = match.start() + match.group(0).index(value)
            positions.append((value_start, value_start + len(value), token))
    
    return positions
```

#### Step 5: Call Detection Method from redact()

Find the `redact()` method and add your detection call:

```python
def redact(self, text: str) -> RedactionResult:
    """Main redaction entry point."""
    # ... existing code ...
    
    all_positions = []
    
    # ... existing pattern calls ...
    
    # Your new detection (add with config check if applicable)
    if self.config.redact_your_type:  # Add config flag first
        all_positions.extend(self._redact_your_new_type(text))
    
    # ... rest of method ...
```

#### Step 6: Add Configuration Flag (Optional)

If your pattern should be toggleable, add to `PIRemoverConfig` in `src/pi_remover/config.py`:

```python
# In src/pi_remover/config.py
@dataclass
class PIRemoverConfig:
    """Configuration for PI removal."""
    
    # ... existing fields ...
    
    # Your new type (v2.12.X)
    redact_your_type: bool = True
```

#### Step 7: Add Token Mapping

If using typed tokens, add mapping in `_get_typed_token()`:

```python
def _get_typed_token(self, pi_type: str) -> str:
    """Get replacement token for PI type."""
    if not self.config.use_typed_tokens:
        return "[REDACTED]"
    
    token_map = {
        # ... existing mappings ...
        "YOUR_TYPE": "[YOUR_TYPE]",
        "YOUR_TYPE_ALT": "[YOUR_TYPE]",  # Multiple types → same token
    }
    return token_map.get(pi_type, "[PI]")
```

#### Step 8: Add Tests

Create test cases in `tests/test_comprehensive_pi.py`:

```python
def test_your_new_pattern():
    """Test YOUR_NEW_PATTERN detection."""
    config = PIRemoverConfig(enable_ner=False)
    remover = PIRemover(config)
    
    # Positive tests (should be redacted)
    test_cases = [
        ("Contact EXAMPLE-12345 for help", "[YOUR_TYPE]"),
        ("Reference: EXAMPLE:67890", "[YOUR_TYPE]"),
    ]
    
    for text, expected_token in test_cases:
        result = remover.redact(text)
        assert expected_token in result.redacted_text, f"Failed: {text}"
    
    # Negative tests (should NOT be redacted)
    false_positives = [
        "This is not an EXAMPLE",
        "Random EXAMPLE123 without hyphen",
    ]
    
    for text in false_positives:
        result = remover.redact(text)
        assert "[YOUR_TYPE]" not in result.redacted_text, f"False positive: {text}"
```

#### Step 9: Update Documentation

1. **CHANGELOG.md**: Add to current version section
2. **KEBD.md**: Add KEBD entry if fixing an issue
3. **Version number**: Update `__version__` in `src/pi_remover/remover.py` and `core.py`

#### Step 10: Sync to Standalone (if applicable)

Copy pattern to `others/standalone/pi_remover_standalone.py`:
- Add pattern to `PIPatterns` class
- Add to `redact()` method
- Update version number

### Complete Example: Adding RFC Pattern

Here's the actual implementation of the RFC pattern (v2.8.1):

**1. Pattern Definition (in `src/pi_remover/patterns.py`):**
```python
# In PIPatterns class
# RFC/Change Request numbers (v2.8.1)
# Examples: RFC # 25224330, RFC No: 25228602, RFC-12345678
RFC_NUMBER = re.compile(
    r'\bRFC\s*(?:#|No[:\s.]*|[-:])\s*(\d{7,10})\b',
    re.IGNORECASE
)
```

**2. Detection Method (in `src/pi_remover/remover.py`):**
```python
def _redact_ticket_ids(self, text: str) -> List[Tuple[int, int, str]]:
    # ... existing code ...
    
    # RFC numbers (v2.8.1)
    for match in self.patterns.RFC_NUMBER.finditer(text):
        positions.append((match.start(), match.end(), self._get_typed_token("RFC")))
    
    return positions
```

**3. Token Mapping (in `src/pi_remover/remover.py`):**
```python
token_map = {
    # ... existing ...
    "RFC": "[RFC]",
}
```

**4. Test:**
```python
def test_rfc_numbers():
    remover = PIRemover(PIRemoverConfig(enable_ner=False))
    
    assert "[RFC]" in remover.redact("RFC # 25224330").redacted_text
    assert "[RFC]" in remover.redact("RFC No: 25228602").redacted_text
    assert "[RFC]" in remover.redact("RFC-12345678").redacted_text
```

### Pattern Debugging Tips

**1. Test pattern in isolation:**
```python
import re
pattern = re.compile(r'\bYOUR_PATTERN\b', re.IGNORECASE)
test_texts = ["text1", "text2", "text3"]
for text in test_texts:
    matches = pattern.findall(text)
    print(f"'{text}' -> {matches}")
```

**2. Check for overlaps:**
```python
# Patterns may conflict - longer patterns should be checked first
# The system automatically handles overlaps by taking the longest match
```

**3. Avoid catastrophic backtracking:**
```python
# BAD: Can cause exponential time
r'(a+)+b'

# GOOD: Use possessive/atomic groups or limit repetition
r'a+b'
```

**4. Test edge cases:**
- Beginning/end of string
- Multiple matches in one text
- Adjacent to punctuation
- Mixed case
- Unicode characters

### Adding to Blocklists (False Positive Prevention)

If a pattern causes false positives, add words to blocklists in `src/pi_remover/remover.py`:

**1. For contextual name detection:**
```python
# In remover.py → _redact_names_contextual() (line ~486)
common_word_exclusions = {
    'existing', 'words',
    'your_new_word',  # Add here
}
```

**2. For NER false positives:**
```python
# In remover.py → _redact_names_ner() (line ~421)
ner_false_positive_blocklist = {
    'existing', 'words',
    'your_new_word',  # Add here
}
```

**3. For dictionary-based detection:**
```python
# In remover.py → _redact_names_dictionary() (line ~601)
non_name_prefixes = {
    'existing', 'words',
    'your_new_word',  # Add here
}
```

### Quick Reference: Pattern Categories

All detection methods are in `src/pi_remover/remover.py`, patterns in `src/pi_remover/patterns.py`:

| Category | Method in remover.py | Token | Examples |
|----------|---------------------|-------|----------|
| Personal IDs | `_redact_emp_ids()` | [EMP_ID] | 1234567, E12345 |
| Emails | `_redact_emails()` | [EMAIL] | user@domain.com |
| Phones | `_redact_phones()` | [PHONE] | +91-9876543210 |
| Names | `_redact_names_*()` | [NAME] | John Doe |
| Assets | `_redact_asset_ids()` | [ASSET_ID] | 19HW12345678 |
| IPs | `_redact_ip_addresses()` | [IP] | 192.168.1.1 |
| Tickets | `_redact_ticket_ids()` | [TICKET] | INC00012345 |
| RFC/CR | `_redact_ticket_ids()` | [RFC], [CR] | RFC # 12345 |
| Locations | `_redact_workplace_info()` | [LOCATION] | TCB4/ODC1/WSN/100 |
| Credentials | `_redact_credentials()` | [CREDENTIAL] | password=xxx |

---

## How to Whitelist Domains/Phones

Edit `config.yaml`:

```yaml
exclusions:
  # Emails that should NOT be redacted
  domains:
    - "support@yourcompany.com"
    - "helpdesk@yourcompany.com"
    - "noreply@yourcompany.com"
  
  # Phone prefixes to preserve
  phones:
    - "1800"      # Toll-free
    - "+1-800"
    - "1-800"
  
  # Terms to never redact
  terms:
    - "ServiceNow"
    - "Microsoft"
    - "Google"
```

---

## How to Change Replacement Tokens

Edit `config.yaml`:

```yaml
tokens:
  # Use typed tokens [EMAIL], [PHONE], etc.
  use_typed: true
  
  # Or use generic token
  # use_typed: false
  # default: "[REDACTED]"
  
  # Custom tokens per type
  custom:
    email: "[EMAIL_REMOVED]"
    phone: "[PHONE_REMOVED]"
    name: "[NAME_REMOVED]"
```

---

## How to Enable/Disable PI Types

Edit `config.yaml`:

```yaml
pi_types:
  # Personal
  names: true
  emails: true
  phones: true
  employee_ids: true
  
  # Infrastructure
  asset_ids: true
  ip_addresses: true      # Set false to keep IPs
  hostnames: true
  urls: false             # Set false to keep URLs
  
  # Government/Financial
  government_ids: true    # Aadhaar, PAN, Passport
  credit_cards: true
  upi_ids: true
  
  # Security
  credentials: true       # Passwords, API keys
  
  # Other
  signature_blocks: true
  companies: false        # Set false to keep company names
  locations: false        # Set false to keep locations
```

---

# Security & Authentication

## Authentication Configuration Guide

This section provides a comprehensive guide to **all places where authentication is configured** and **how to update credentials**.

---

## Where Authentication Is Defined (Complete Reference)

### 🎯 Primary Configuration (YAML - Recommended)

| File | What It Contains | Priority |
|------|-----------------|:--------:|
| **`config/clients.yaml`** | All client credentials + JWT settings | **1 (Highest)** |

### 📦 Docker/Container Configuration

| File | What It Contains | When Used |
|------|-----------------|-----------|
| `docker/docker-compose.dev.yml` | DEV environment variables (AUTH_CLIENTS) | Docker DEV deployment |
| `docker/docker-compose.prod.yml` | PROD environment variables (AUTH_CLIENTS) | Docker PROD deployment |
| `docker/.env.dev` | DEV secrets (reference) | Docker DEV with --env-file |
| `docker/.env.prod` | PROD secrets (reference) | Docker PROD with --env-file |

### 🔧 Fallback Defaults

| File | What It Contains | When Used |
|------|-----------------|-----------|
| `src/pi_remover/security.py` | Hardcoded defaults | When no config found |
| `security.py` (root) | Hardcoded defaults | When no config found |

---

## Configuration Loading Order

The system loads credentials in this order (first found wins):

```
1. Environment Variable: AUTH_CLIENTS
       ↓ (if not set)
2. YAML File: config/clients.yaml
       ↓ (if not found)
3. JSON File: clients.json
       ↓ (if not found)
4. Hardcoded Defaults in security.py
```

---

## How to Update Credentials (YAML) ✅ RECOMMENDED

### Step 1: Edit config/clients.yaml

```yaml
# config/clients.yaml - PRIMARY CONFIGURATION FILE

# JWT Configuration (used to sign/verify tokens)
jwt:
  secret_key: "YOUR_DEV_JWT_SECRET_HERE"  # Change this!
  algorithm: "HS256"
  expiry_minutes: 30

# Client Credentials (used to get tokens)
clients:
  # Internal service-to-service client (Web → API)
  pi-internal-web-service:
    secret: "YOUR_WEB_CLIENT_SECRET_HERE"
    name: "Web Service Internal"
    rate_limit: 10000
    description: "Internal client for web service to API communication"

  # Development client
  pi-dev-client:
    secret: "YOUR_DEV_CLIENT_SECRET_HERE"
    name: "Development Client"
    rate_limit: 1000
    description: "General development and testing"

  # Test client (for automated tests)
  pi-test-client:
    secret: "TestClientSecret1234567890ABCDEF"
    name: "Testing Client"
    rate_limit: 1000

  # Production client (UNCOMMENT and configure for production)
  # pi-prod-client:
  #   secret: "<GENERATE_NEW_SECRET>"
  #   name: "Production Client"
  #   rate_limit: 10000
```

### Step 2: Generate New Secrets

```powershell
# Generate new JWT secret (32+ bytes)
python -c "import secrets; print('JWT Secret:', secrets.token_urlsafe(32))"

# Generate new client secret (32+ bytes)
python -c "import secrets; print('Client Secret:', secrets.token_urlsafe(32))"
```

### Step 3: Restart Services

```powershell
# If running locally
# Just restart the Python process

# If using Docker
docker-compose -f docker/docker-compose.dev.yml restart
```

### Step 4: Test New Credentials

```powershell
$response = Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" `
  -Method POST -ContentType "application/json" `
  -Body '{"client_id":"pi-dev-client","client_secret":"YOUR_NEW_SECRET"}'

Write-Host "Token obtained successfully: $($response.access_token.Substring(0, 20))..."
```

---

## How to Update Docker Environment Variables

If you prefer using environment variables (legacy approach or Docker-only):

### docker/docker-compose.dev.yml

```yaml
pi-gateway-dev:
  environment:
    # JWT Secret for signing tokens
    JWT_SECRET_KEY: "your-new-jwt-secret"
    
    # Token expiry in minutes
    JWT_EXPIRY_MINUTES: 60
    
    # Client credentials (format: client_id:secret:name,client2:secret2:name2)
    AUTH_CLIENTS: "pi-dev-client:your-new-secret:development,pi-test-client:TestSecret123:testing"
```

### docker/docker-compose.prod.yml

```yaml
pi-gateway-prod:
  environment:
    JWT_SECRET_KEY: "strong-production-jwt-secret-256-bit"
    JWT_EXPIRY_MINUTES: 30
    AUTH_CLIENTS: "pi-prod-client:strong-prod-secret:production"
```

---

## Add New API Client

### Option 1: YAML (Recommended)

```yaml
# Add to config/clients.yaml under 'clients:'
clients:
  # ... existing clients ...
  
  my-new-app:
    secret: "generate-with-secrets-token-urlsafe-32"
    name: "My Application"
    rate_limit: 500
    description: "API access for my application"
```

### Option 2: Environment Variable

```powershell
# Add to existing AUTH_CLIENTS (comma-separated)
$env:AUTH_CLIENTS = "existing-client:secret:name,my-new-app:newsecret32chars:My App"
```

---

## Change JWT Secret

### In YAML (Recommended)

```yaml
# config/clients.yaml
jwt:
  secret_key: "your-new-256-bit-jwt-secret"
```

### Via Environment Variable

```powershell
$env:JWT_SECRET_KEY = "your-new-256-bit-jwt-secret"
```

### In Docker Compose

```yaml
environment:
  JWT_SECRET_KEY: "your-new-256-bit-jwt-secret"
```

---

## Change Rate Limits

### In YAML (Per-Client)

```yaml
# config/clients.yaml
clients:
  my-client:
    secret: "..."
    rate_limit: 2000  # requests per minute
```

### Via Environment Variables (Global)

```powershell
$env:RATE_LIMIT_REQUESTS = "200"        # Requests per window
$env:RATE_LIMIT_WINDOW_SECONDS = "60"   # Window size
$env:RATE_LIMIT_BURST = "30"            # Burst allowance
$env:RATE_LIMIT_ENABLED = "true"        # Enable/disable
```

### In Docker Compose

```yaml
environment:
  RATE_LIMIT_REQUESTS: 1000
  RATE_LIMIT_WINDOW_SECONDS: 60
  RATE_LIMIT_ENABLED: "true"
```

---

## How to Get Auth Token

### PowerShell

```powershell
# Get token
$response = Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" `
  -Method POST -ContentType "application/json" `
  -Body '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}'

$token = $response.access_token
Write-Host "Token expires in: $($response.expires_in) seconds"

# Use token
Invoke-RestMethod -Uri "http://localhost:8080/dev/v1/redact" `
  -Method POST -Headers @{Authorization="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"text":"Email: test@example.com"}'
```

### cURL (Linux/WSL)

```bash
# Get token
TOKEN=$(curl -s -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}' \
  | jq -r .access_token)

# Use token
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Email: test@example.com"}'
```

### Token Expiry

| Environment | Default Expiry |
|-------------|:--------------:|
| DEV | 60 minutes |
| PROD | 30 minutes |

---

## How to Configure CORS

### In YAML

```yaml
# config/api_service.yaml
security:
  cors_origins:
    - "https://your-frontend.com"
    - "https://your-app.com"
  cors_allow_credentials: true
```

### Via Environment Variable

```powershell
$env:CORS_ORIGINS = "https://app1.com,https://app2.com"
```

### In Docker Compose

```yaml
environment:
  CORS_ORIGINS: "https://your-frontend.com"
```

---

## Quick Credential Reference

### DEV Environment

| Setting | Value | Location |
|---------|-------|----------|
| Client ID | `pi-dev-client` | config/clients.yaml |
| Client Secret | `YOUR_DEV_CLIENT_SECRET_HERE` | config/clients.yaml |
| JWT Secret | `YOUR_DEV_JWT_SECRET_HERE` | config/clients.yaml |
| Token Expiry | 60 minutes | config/clients.yaml |
| API Port | 8080 | docker-compose.dev.yml |

### Internal Service-to-Service

| Setting | Value | Location |
|---------|-------|----------|
| Client ID | `pi-internal-web-service` | config/clients.yaml |
| Client Secret | `YOUR_WEB_CLIENT_SECRET_HERE` | config/clients.yaml |
| Rate Limit | 10,000/min | config/clients.yaml |

### PROD Environment (Configure Before Use)

| Setting | Default | Location |
|---------|---------|----------|
| Client ID | `pi-prod-client` | config/clients.yaml (uncomment) |
| Client Secret | Generate new | config/clients.yaml |
| JWT Secret | Generate new | config/clients.yaml |
| Token Expiry | 30 minutes | config/clients.yaml |
| API Port | 9080 | docker-compose.prod.yml |

---

# Performance

## How to Enable Fast Mode

Fast mode disables NER (Named Entity Recognition) for ~10x faster processing.

### CLI

```powershell
python -m pi_remover -i data.csv -c "Column" --fast
```

### Standalone

```powershell
# Fast mode is DEFAULT for standalone
python pi_remover_standalone.py -i data.csv -c "Column"

# Explicitly use fast mode
python pi_remover_standalone.py -i data.csv -c "Column" --fast

# Enable NER with --full (slower but better name detection)
python pi_remover_standalone.py -i data.csv -c "Column" --full

# Choose specific spaCy model with --full
python pi_remover_standalone.py -i data.csv -c "Column" --full --model en_core_web_lg
```

### API Request (v2.7.1)

```json
{
  "text": "Contact john@example.com",
  "enable_ner": false
}
```

### API (Environment Variable)

```powershell
$env:ENABLE_NER = "false"
```

### Docker

```powershell
docker run -p 8080:8080 -e ENABLE_NER=false pi-gateway
```

### Web UI

Check the "Fast Mode" checkbox in the browser.

---

## How to Select spaCy Model (v2.7.1)

You can choose which spaCy NER model to use for name detection.

### Standalone CLI

```powershell
# Use large model (default, recommended)
python pi_remover_standalone.py -i data.csv --full --model en_core_web_lg

# Use transformer model (highest accuracy)
python pi_remover_standalone.py -i data.csv --full --model en_core_web_trf

# Use small model (fastest)
python pi_remover_standalone.py -i data.csv --full --model en_core_web_sm
```

### API Request

```json
{
  "text": "Contact John Smith at john@example.com",
  "enable_ner": true,
  "spacy_model": "en_core_web_trf"
}
```

### Model Comparison

| Model | Install Command | Size | Speed | Accuracy |
|-------|-----------------|------|-------|----------|
| en_core_web_sm | `python -m spacy download en_core_web_sm` | 12 MB | Fastest | Lower |
| en_core_web_md | `python -m spacy download en_core_web_md` | 40 MB | Fast | Good |
| **en_core_web_lg** | `python -m spacy download en_core_web_lg` | 560 MB | Medium | High |
| en_core_web_trf | `python -m spacy download en_core_web_trf` | 438 MB | Slowest | Highest |

---

## How to Improve Performance

### 1. Use Fast Mode

```powershell
--fast  # Disables NER, 10x faster
```

### 2. Choose Lighter Model

```powershell
--model en_core_web_sm  # Faster than lg/trf but less accurate
```

### 3. Increase Workers

Edit `config.yaml`:
```yaml
general:
  num_workers: 4  # Or 0 for auto-detect
```

### 4. Increase Batch Size

Edit `config.yaml`:
```yaml
general:
  batch_size: 10000  # Default is 5000
```

### 5. Enable Caching

Edit `config.yaml`:
```yaml
performance:
  enable_cache: true
  max_cache_size: 10000
```

### 5. Disable Unused PI Types

Edit `config.yaml`:
```yaml
pi_types:
  companies: false
  locations: false
  urls: false
```

---

## How to Handle Large Files

### Increase Chunk Size

Edit `config.yaml`:
```yaml
performance:
  chunk_size: 50000  # Default is 10000
```

### Increase Memory (Docker)

```powershell
docker run -p 8080:8080 --memory=4g pi-gateway
```

### Use CLI with Progress

```powershell
python -m pi_remover -i large_file.csv -c "Column" --fast
# Progress bar will show status
```

---

# File Processing

## How to Process CSV Files

```powershell
# Single column
python -m pi_remover -i data.csv -c "Description"

# Multiple columns
python -m pi_remover -i data.csv -c "Description" -c "Notes"

# With encoding
python -m pi_remover -i data.csv -c "Column" --encoding utf-8
```

**Config options** (`config.yaml`):
```yaml
files:
  csv:
    encoding: "utf-8"
    on_bad_lines: "skip"  # skip, warn, or error
```

---

## How to Process Excel Files

```powershell
# Process .xlsx
python -m pi_remover -i data.xlsx -c "Sheet1!Description"

# Specific sheet
python -m pi_remover -i data.xlsx -c "MySheet!Column"
```

**Config options** (`config.yaml`):
```yaml
files:
  excel:
    engine: "openpyxl"  # openpyxl for .xlsx
    sheet_name: 0       # Or "Sheet1"
```

---

## How to Process JSON Files

```powershell
# JSON with specific field
python -m pi_remover -i data.json -c "description"

# Nested JSON
python -m pi_remover -i data.json -c "data.comments"
```

---

## How to Process Text Files

```powershell
# Process entire file
python -m pi_remover -i notes.txt
```

---

## How to Process Multiple Columns

```powershell
python -m pi_remover -i data.csv `
  -c "Short_Description" `
  -c "Long_Description" `
  -c "Comments" `
  -c "Notes" `
  --fast
```

---

# Docker & Deployment

## How to Build Docker Images

```powershell
# API Gateway
docker build -t pi-gateway -f api_service/Dockerfile .

# Web Service
docker build -t pi-web -f web_service/Dockerfile .

# With version tag
docker build -t pi-gateway:1.0.0 -f api_service/Dockerfile .
```

---

## How to Change Docker Ports

### DEV

Edit `docker/docker-compose.dev.yml`:
```yaml
services:
  pi-gateway-dev:
    ports:
      - "8888:8080"  # Change 8888 to your port
```

### PROD

Edit `docker/docker-compose.prod.yml`:
```yaml
services:
  pi-gateway-prod:
    ports:
      - "9999:8080"  # Change 9999 to your port
```

### Direct Docker Run

```powershell
docker run -p 3000:8080 pi-gateway  # Exposes on port 3000
```

---

## How to Set Memory Limits

### Docker Run

```powershell
docker run -p 8080:8080 --memory=2g --memory-swap=4g pi-gateway
```

### Docker Compose

```yaml
services:
  pi-gateway:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## How to View Docker Logs

```powershell
# Live logs
docker logs -f pi-gateway-dev

# Last 100 lines
docker logs --tail 100 pi-gateway-dev

# With timestamps
docker logs -t pi-gateway-dev

# Docker Compose logs
docker-compose -f docker/docker-compose.dev.yml logs -f
```

---

## How to Deploy to Google Cloud

### Cloud Run

```powershell
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/pi-gateway

# Deploy
gcloud run deploy pi-gateway `
  --image gcr.io/PROJECT_ID/pi-gateway `
  --platform managed `
  --region us-central1 `
  --memory 2Gi `
  --set-env-vars "ENABLE_NER=true,JWT_SECRET_KEY=your-secret"
```

📚 **Full guide:** [docs/GOOGLE_CLOUD.md](docs/GOOGLE_CLOUD.md)

---

# Testing

## How to Run Tests

```powershell
# All tests
python -m pytest tests/ -v

# Core tests only (fast)
python -m pytest tests/test_remover.py tests/test_comprehensive_pi.py -v

# API tests
python -m pytest tests/test_api.py -v

# With coverage
python -m pytest tests/ --cov=src/pi_remover --cov-report=html
```

---

## How to Run Comprehensive Tests

v2.9.0 includes new comprehensive test scripts that start all services and run all tests.

### PowerShell (Windows)

```powershell
# Full test run (starts Redis, API, Web, runs all tests)
.\scripts\run_comprehensive_tests.ps1

# Skip Redis (if already running)
.\scripts\run_comprehensive_tests.ps1 -SkipRedis

# Run tests only (services already running)
.\scripts\run_comprehensive_tests.ps1 -TestOnly

# Keep services running after tests
.\scripts\run_comprehensive_tests.ps1 -SkipCleanup

# Wait longer for startup
.\scripts\run_comprehensive_tests.ps1 -StartupWaitSeconds 15
```

### Bash (Linux/WSL)

```bash
# Full test run
./scripts/run_comprehensive_tests.sh

# Skip Redis
./scripts/run_comprehensive_tests.sh --skip-redis

# Run tests only
./scripts/run_comprehensive_tests.sh --test-only
```

### Component Tests Only (No Services Needed)

```powershell
# Run component tests without starting any services
python scripts\test_components.py

# With services already running
python scripts\test_components.py --with-services

# Custom service URLs
python scripts\test_components.py --with-services --api-url http://localhost:8080 --web-url http://localhost:8082
```

### What the Comprehensive Tests Cover

| Test Category | Description |
|---------------|-------------|
| Module Imports | Verify all modules load correctly |
| Config Files | Validate all YAML configs are valid |
| CircuitBreaker | Test state transitions and recovery |
| InMemoryFallback | Test rate limiting when Redis is down |
| Security | Test token generation and verification |
| API Endpoints | Test all API endpoints (if services running) |
| Web Endpoints | Test all web endpoints (if services running) |
| Integration | Test Web → API communication |

---

## How to Test API Endpoints

### Health Check

```powershell
curl http://localhost:8080/dev/health
```

### Redact Text

```powershell
# Get token first
$token = (Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" `
  -Method POST -ContentType "application/json" `
  -Body '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}').access_token

# Redact
Invoke-RestMethod -Uri "http://localhost:8080/dev/v1/redact" `
  -Method POST -Headers @{Authorization="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"text":"Contact john@example.com or call 9876543210"}'
```

### Batch Redact

```powershell
Invoke-RestMethod -Uri "http://localhost:8080/dev/v1/redact/batch" `
  -Method POST -Headers @{Authorization="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"texts":["Email: a@b.com","Phone: 1234567890"]}'
```

---

## How to Validate Redaction

### Python Script

```python
from pi_remover import PIRemover, PIRemoverConfig

config = PIRemoverConfig(enable_ner=False)
remover = PIRemover(config)

text = "Email john@example.com for help"
result = remover.redact(text)
print(f"Original: {text}")
print(f"Redacted: {result}")
# Output: Email [EMAIL] for help
```

### CLI Dry Run

```powershell
python -m pi_remover -i data.csv -c "Column" --dry-run
```

---

# Maintenance

## How to Update Dependencies

```powershell
# Update all
pip install --upgrade -r requirements.txt

# Update specific package
pip install --upgrade pandas

# Update with extras
pip install --upgrade -e ".[all]"
```

---

## How to Update spaCy Model

```powershell
# Download latest
python -m spacy download en_core_web_lg

# Verify
python -c "import spacy; nlp = spacy.load('en_core_web_lg'); print(nlp.meta['version'])"
```

---

## How to View Audit Logs

### API Audit Logs

```powershell
# View recent logs
docker logs pi-gateway-dev 2>&1 | Select-String "AUDIT"

# Log file (if configured)
cat logs/dev/audit.log
```

### CLI Audit Report

```powershell
python -m pi_remover -i data.csv -c "Column" --audit
# Creates: output/audit_report_YYYYMMDD_HHMMSS.json
```

---

## How to Generate Reports

### JSON Report

```powershell
python -m pi_remover -i data.csv -c "Column" --audit --report-format json
```

### HTML Report

Edit `config.yaml`:
```yaml
audit:
  report_format: "html"
```

---

# Troubleshooting

## Common Errors & Fixes

### Error: "spaCy model not found"

```powershell
# Solution: Download the model
python -m spacy download en_core_web_lg

# Alternative: Use fast mode
python -m pi_remover -i data.csv -c "Column" --fast
```

### Error: "Out of memory"

```powershell
# Solution 1: Use fast mode
--fast

# Solution 2: Increase Docker memory
docker run --memory=4g ...

# Solution 3: Reduce batch size
# In config.yaml: batch_size: 2000
```

### Error: "401 Unauthorized"

```powershell
# Solution: Check your token
# 1. Token may be expired (30-60 min)
# 2. Wrong endpoint (use /dev/ for DEV, /prod/ for PROD)
# 3. Wrong credentials
```

### Error: "429 Too Many Requests"

```powershell
# Solution 1: Wait and retry
Start-Sleep -Seconds 60

# Solution 2: Increase rate limit
$env:RATE_LIMIT_REQUESTS = "1000"
```

### Error: "Connection refused"

```powershell
# Check if service is running
docker ps

# Start if not running
.\scripts\deploy-dev.ps1
```

### Error: "Invalid column name"

```powershell
# List available columns
python -c "import pandas as pd; print(pd.read_csv('data.csv').columns.tolist())"

# Use exact column name (case-sensitive)
python -m pi_remover -i data.csv -c "Exact_Column_Name"
```

### Error: "File encoding error"

```powershell
# Specify encoding
python -m pi_remover -i data.csv -c "Column" --encoding utf-8

# Or try
--encoding latin-1
--encoding cp1252
```

### Error: "Docker build failed"

```powershell
# Clear Docker cache
docker system prune -f

# Rebuild without cache
docker build --no-cache -t pi-gateway -f api_service/Dockerfile .
```

### Error: "Port already in use"

```powershell
# Find what's using the port
netstat -ano | findstr :8080

# Kill the process
taskkill /PID <PID> /F

# Or use different port
docker run -p 8081:8080 pi-gateway
```

### Error: "CORS blocked"

```powershell
# Add your origin to allowed list
$env:CORS_ORIGINS = "http://localhost:3000,https://your-app.com"
```

### Error: "Token expired"

```powershell
# Request new token
$response = Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" ...
```

---

## Microservices Troubleshooting

### Error: "Config file not found"

```powershell
# Make sure config directory exists
Test-Path config\api_service.yaml

# Verify you're in the project root
cd C:\path\to\PI_Removal

# Create missing configs (copy from examples)
```

### Error: "Web service can't connect to API"

The web service now calls the API service via HTTP. Check:

```powershell
# 1. Is API service running?
curl http://localhost:8080/dev/health

# 2. Is the API URL correct in config?
# Check config/web_service.yaml:
#   api:
#     base_url: "http://localhost:8080"  # Must match API port

# 3. Check circuit breaker state (if API was down)
# Circuit breaker may be OPEN - wait 30 seconds and retry
```

### Error: "Circuit breaker is OPEN"

The circuit breaker opens after 5 consecutive failures to protect the system.

```powershell
# 1. Wait 30 seconds (recovery timeout)

# 2. Fix the underlying API issue
curl http://localhost:8080/dev/health

# 3. Make a test request (triggers half-open state)
curl http://localhost:8082/health
```

### Error: "Redis connection refused"

Redis is optional. The system will use in-memory fallback.

```powershell
# Option 1: Start Redis
docker run --rm -p 6379:6379 redis:alpine

# Option 2: Ignore (system will use in-memory fallback)
# Check logs for: "Redis unavailable, using in-memory fallback"

# Option 3: Check redis config
# config/redis.yaml:
#   redis:
#     host: "localhost"
#     port: 6379
```

### Error: "YAML parsing error"

```powershell
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config/api_service.yaml'))"

# Common issues:
# - Tabs instead of spaces (use 2 spaces)
# - Missing quotes around values with special chars
# - Incorrect indentation
```

### Error: "InMemoryFallback active"

This is a warning, not an error. It means Redis is unavailable.

```
# Impact: Rate limiting works per-instance (not shared)
# Fix: Start Redis for shared rate limiting

docker run --rm -p 6379:6379 redis:alpine
```

### How to Diagnose Service Communication

```powershell
# 1. Check all services are running
curl http://localhost:8080/dev/health   # API
curl http://localhost:8082/health        # Web

# 2. Check API is accessible from web service config
cat config\web_service.yaml | Select-String "base_url"

# 3. Test API directly
$token = (Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" `
  -Method POST -ContentType "application/json" `
  -Body '{"client_id":"pi-internal-web-service","client_secret":"YOUR_WEB_CLIENT_SECRET_HERE"}').access_token

Invoke-RestMethod -Uri "http://localhost:8080/dev/v1/redact" `
  -Method POST -Headers @{Authorization="Bearer $token"} `
  -ContentType "application/json" `
  -Body '{"text":"test@email.com"}'
```

---

## Debug Mode

### Enable Debug Logging

```powershell
# Environment variable
$env:LOG_LEVEL = "DEBUG"

# Or in config.yaml
general:
  log_level: "DEBUG"
```

### View Debug Output

```powershell
# CLI
python -m pi_remover -i data.csv -c "Column" 2>&1 | Out-File debug.log

# Docker
docker logs pi-gateway-dev 2>&1 | Out-File debug.log
```

### Enable Debug Endpoints (DEV only)

```powershell
$env:ENABLE_DEBUG_ENDPOINTS = "true"
```

---

## Health Checks

> **Note:** As of v2.8.0, health endpoints require JWT authentication.

### API Health

```powershell
# Get token first
$token = (Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" `
  -Method POST -ContentType "application/json" `
  -Body '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}').access_token

# DEV (with auth)
curl -H "Authorization: Bearer $token" http://localhost:8080/dev/health

# PROD (with auth)
curl -H "Authorization: Bearer $token" http://localhost:9080/prod/health
```

### Expected Response

```json
{
  "status": "healthy",
  "version": "2.12.0",
  "mode": "full",
  "ner_available": true,
  "uptime_seconds": 3600,
  "requests_processed": 1000,
  "avg_latency_ms": 25.5,
  "errors": 0
}
```

### Docker Health

```powershell
docker inspect pi-gateway-dev --format='{{.State.Health.Status}}'
```

### Check All Services

```powershell
# Quick health check script
$services = @(
    @{Name="API DEV"; URL="http://localhost:8080/dev/health"},
    @{Name="API PROD"; URL="http://localhost:9080/prod/health"},
    @{Name="Web DEV"; URL="http://localhost:8082/health"},
    @{Name="Web PROD"; URL="http://localhost:9082/health"}
)

foreach ($svc in $services) {
    try {
        $r = Invoke-WebRequest -Uri $svc.URL -TimeoutSec 5 -UseBasicParsing
        Write-Host "✓ $($svc.Name): OK" -ForegroundColor Green
    } catch {
        Write-Host "✗ $($svc.Name): FAILED" -ForegroundColor Red
    }
}
```

---

# Reference

## All Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| **General** |||
| `ENVIRONMENT` | `development` | `development` or `production` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ENABLE_NER` | `true` | Enable spaCy NER |
| `ENABLE_METRICS` | `true` | Enable metrics tracking |
| `ENABLE_DEBUG_ENDPOINTS` | `true` (DEV) | Enable debug endpoints |
| **Authentication** |||
| `JWT_SECRET_KEY` | Auto-generated | JWT signing key |
| `JWT_EXPIRY_MINUTES` | `30` | Token expiry time |
| `AUTH_CLIENTS` | `pi-dev-client:...` | Comma-separated client credentials |
| `AUTH_CLIENTS_FILE` | `clients.json` | Path to clients file |
| **Rate Limiting** |||
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window size |
| `RATE_LIMIT_BURST` | `20` | Burst allowance |
| **Limits** |||
| `MAX_TEXT_LENGTH` | `100000` | Max chars per request |
| `MAX_BATCH_SIZE` | `100` | Max texts per batch |
| `MAX_FILE_SIZE` | `500MB` | Max upload size |
| **CORS** |||
| `CORS_ORIGINS` | `*` | Allowed origins |
| **Audit** |||
| `AUDIT_LOGGING_ENABLED` | `true` | Enable audit logs |
| `AUDIT_TIMEZONE` | `Asia/Kolkata` | Timezone for logs |
| **Server** |||
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8080` | Server port |

---

## All CLI Options

### Main CLI (`python -m pi_remover`)

```
python -m pi_remover [OPTIONS]

Required:
  -i, --input FILE        Input file (CSV, Excel, JSON, TXT)

Processing:
  -c, --column NAME       Column(s) to process (can repeat)
  -o, --output DIR        Output directory (default: output/)
  --fast                  Disable NER for faster processing (~10x speed)
  --model MODEL           spaCy model when NER enabled:
                            en_core_web_sm  (fastest, lower accuracy)
                            en_core_web_md  (balanced)
                            en_core_web_lg  (default, recommended)
                            en_core_web_trf (highest accuracy, slowest)
  --encoding ENC          File encoding (utf-8, latin-1, cp1252)

Output:
  --audit                 Generate audit report
  --report-format FMT     Report format: json, csv, html
  --dry-run               Preview without saving

Configuration:
  --config FILE           Custom config file path

Logging:
  -v, --verbose           Verbose output
  -q, --quiet             Suppress output
  --log-level LEVEL       DEBUG, INFO, WARNING, ERROR

Help:
  -h, --help              Show help
  --version               Show version
```

### Standalone CLI (pi_remover_standalone.py)

```
python pi_remover_standalone.py [OPTIONS]

Input/Output:
  -i, --input FILE        Input file path (CSV, Excel, JSON, TXT)
  -o, --output FILE       Output file path (default: input_cleaned.ext)
  -c, --columns COLS      Column(s) to process (space-separated)

Processing Mode:
  --fast                  Fast mode - regex only (DEFAULT for standalone)
  --full                  Full mode - NER + regex (requires spaCy)
  --model MODEL           spaCy model to use with --full:
                            en_core_web_sm  (smallest, fastest)
                            en_core_web_md  (medium)
                            en_core_web_lg  (default, recommended)
                            en_core_web_trf (highest accuracy, slowest)

Other Options:
  --interactive           Interactive mode with prompts
  --quiet                 Suppress progress bars
  -h, --help              Show help message
```

### Model Comparison (v2.7.1)

| Model | Size | Speed | Accuracy | Best For |
|-------|------|-------|----------|----------|
| `en_core_web_sm` | 12 MB | Fastest | Lower | Quick scans, resource-limited |
| `en_core_web_md` | 40 MB | Fast | Good | General use, smaller deployments |
| `en_core_web_lg` | 560 MB | Medium | High | **Recommended default** |
| `en_core_web_trf` | 438 MB | Slowest | Highest | Maximum accuracy needed |

---

## All API Endpoints

> **Version 2.17.0** - Some endpoints are disabled by default. See [How to Manage API Endpoints](#how-to-manage-api-endpoints) to enable them.

### Endpoint Feature Flags

| Environment Variable | Default | Endpoints Controlled |
|---------------------|---------|---------------------|
| `ENABLE_BATCH_ENDPOINT` | `false` | `/v1/redact/batch` |
| `ENABLE_HEALTH_ENDPOINT` | `false` | `/health` |
| `ENABLE_DOCS_ENDPOINT` | `false` | `/docs`, `/redoc` |
| `ENABLE_MONITORING_ENDPOINTS` | `false` | `/livez`, `/readyz`, `/metrics` |

### DEV Environment (http://localhost:8080)

| Method | Endpoint | Auth | Status | Description |
|--------|----------|:----:|:------:|-------------|
| GET | `/` | ✅ | ✅ Always | API info & endpoints |
| GET | `/docs` | ❌ | ⚙️ Optional | Swagger UI |
| GET | `/redoc` | ❌ | ⚙️ Optional | ReDoc documentation |
| POST | `/dev/auth/token` | ❌ | ✅ Always | Get JWT token |
| POST | `/dev/v1/redact` | ✅ | ✅ Always | Redact single text |
| POST | `/dev/v1/redact/batch` | ✅ | ⚙️ Optional | Redact multiple texts |
| GET | `/dev/health` | ✅ | ⚙️ Optional | Health check & metrics |
| GET | `/dev/v1/pi-types` | ✅ | ✅ Always | List PI types |
| GET | `/dev/v1/models` | ✅ | ✅ Always | List available spaCy models |
| GET | `/livez` | ❌ | ⚙️ Optional | Kubernetes liveness probe |
| GET | `/readyz` | ❌ | ⚙️ Optional | Kubernetes readiness probe |
| GET | `/metrics` | ❌ | ⚙️ Optional | Prometheus metrics |

### PROD Environment (http://localhost:9080)

| Method | Endpoint | Auth | Status | Description |
|--------|----------|:----:|:------:|-------------|
| GET | `/` | ✅ | ✅ Always | API info & endpoints |
| POST | `/prod/auth/token` | ❌ | ✅ Always | Get JWT token |
| POST | `/prod/v1/redact` | ✅ | ✅ Always | Redact single text |
| POST | `/prod/v1/redact/batch` | ✅ | ⚙️ Optional | Redact multiple texts |
| GET | `/prod/health` | ✅ | ⚙️ Optional | Health check & metrics |
| GET | `/prod/v1/pi-types` | ✅ | ✅ Always | List PI types |
| GET | `/prod/v1/models` | ✅ | ✅ Always | List available spaCy models |

**Legend:** ✅ = Auth Required, ❌ = No Auth | ✅ Always = Enabled, ⚙️ Optional = Disabled by default

### Request/Response Examples

**Get Token:**
```json
// Request
POST /dev/auth/token
{
  "client_id": "pi-dev-client",
  "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"
}

// Response
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Redact Text:**
```json
// Request
POST /dev/v1/redact
Authorization: Bearer <token>
{
  "text": "Contact john@example.com",
  "options": {
    "fast_mode": false,
    "return_stats": true
  }
}

// Response
{
  "redacted_text": "Contact [EMAIL]",
  "stats": {
    "emails": 1,
    "names": 0,
    "phones": 0
  },
  "processing_time_ms": 25.5
}
```

---

## How to Manage API Endpoints

> **Version 2.17.0** - API endpoints can now be enabled/disabled via environment variables or by modifying code.

This section explains how to **enable, disable, add, and remove** API endpoints in the PI Remover API service.

### Endpoint Feature Flags

The API service uses **environment variable feature flags** to control which endpoints are enabled. This allows you to customize the API surface without modifying code.

#### Available Feature Flags

| Environment Variable | Default | Controls |
|---------------------|---------|----------|
| `ENABLE_BATCH_ENDPOINT` | `false` | `/v1/redact/batch` - Batch redaction |
| `ENABLE_HEALTH_ENDPOINT` | `false` | `/health` - Health check with metrics |
| `ENABLE_DOCS_ENDPOINT` | `false` | `/docs`, `/redoc` - Swagger UI & ReDoc |
| `ENABLE_MONITORING_ENDPOINTS` | `false` | `/livez`, `/readyz`, `/metrics` - K8s probes & Prometheus |

#### Currently Enabled Endpoints (Default)

With default settings, only these endpoints are active:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/token` | Get JWT authentication token |
| POST | `/v1/redact` | Redact PI from single text |
| GET | `/` | API info and endpoints |
| GET | `/v1/pi-types` | List supported PI types |
| GET | `/v1/models` | List available spaCy models |

### How to Enable Endpoints

#### Method 1: Environment Variables (Recommended)

Set environment variables before starting the API service:

**Windows (PowerShell):**
```powershell
# Enable all optional endpoints
$env:ENABLE_BATCH_ENDPOINT = "true"
$env:ENABLE_HEALTH_ENDPOINT = "true"
$env:ENABLE_DOCS_ENDPOINT = "true"
$env:ENABLE_MONITORING_ENDPOINTS = "true"

# Start the API service
cd api_service
uvicorn app:app --port 8080
```

**Windows (Command Prompt):**
```cmd
set ENABLE_BATCH_ENDPOINT=true
set ENABLE_HEALTH_ENDPOINT=true
set ENABLE_DOCS_ENDPOINT=true
set ENABLE_MONITORING_ENDPOINTS=true
cd api_service
uvicorn app:app --port 8080
```

**Linux/macOS:**
```bash
# Enable all optional endpoints
export ENABLE_BATCH_ENDPOINT=true
export ENABLE_HEALTH_ENDPOINT=true
export ENABLE_DOCS_ENDPOINT=true
export ENABLE_MONITORING_ENDPOINTS=true

# Start the API service
cd api_service
uvicorn app:app --port 8080
```

**One-liner (Linux/macOS):**
```bash
ENABLE_BATCH_ENDPOINT=true ENABLE_HEALTH_ENDPOINT=true cd api_service && uvicorn app:app --port 8080
```

#### Method 2: Docker Environment Variables

In `docker-compose.yml` or `Dockerfile`:

```yaml
# docker-compose.yml
services:
  api-service:
    build: ./api_service
    ports:
      - "8080:8080"
    environment:
      - ENABLE_BATCH_ENDPOINT=true
      - ENABLE_HEALTH_ENDPOINT=true
      - ENABLE_DOCS_ENDPOINT=true
      - ENABLE_MONITORING_ENDPOINTS=true
```

Or in a `.env` file:
```env
ENABLE_BATCH_ENDPOINT=true
ENABLE_HEALTH_ENDPOINT=true
ENABLE_DOCS_ENDPOINT=true
ENABLE_MONITORING_ENDPOINTS=true
```

#### Method 3: Modify Default Values in Code

To permanently change defaults, edit `api_service/app.py`:

```python
# Find this section (around line 80):
# =============================================================================
# ENDPOINT FEATURE FLAGS
# =============================================================================
ENABLE_BATCH_ENDPOINT = os.environ.get("ENABLE_BATCH_ENDPOINT", "false").lower() == "true"
ENABLE_HEALTH_ENDPOINT = os.environ.get("ENABLE_HEALTH_ENDPOINT", "false").lower() == "true"
ENABLE_DOCS_ENDPOINT = os.environ.get("ENABLE_DOCS_ENDPOINT", "false").lower() == "true"
ENABLE_MONITORING_ENDPOINTS = os.environ.get("ENABLE_MONITORING_ENDPOINTS", "false").lower() == "true"

# Change "false" to "true" to enable by default:
ENABLE_BATCH_ENDPOINT = os.environ.get("ENABLE_BATCH_ENDPOINT", "true").lower() == "true"
```

### How to Disable Endpoints

#### Disable via Environment Variables

Simply set the flag to `false` or don't set it (default is disabled):

```powershell
# Explicitly disable (Windows PowerShell)
$env:ENABLE_BATCH_ENDPOINT = "false"
$env:ENABLE_HEALTH_ENDPOINT = "false"

# Or remove the variable entirely
Remove-Item Env:ENABLE_BATCH_ENDPOINT
```

```bash
# Explicitly disable (Linux/macOS)
export ENABLE_BATCH_ENDPOINT=false

# Or unset the variable
unset ENABLE_BATCH_ENDPOINT
```

### How to Add a New API Endpoint

To add a completely new endpoint to the API:

#### Step 1: Define Request/Response Models

In `api_service/app.py`, add Pydantic models for your endpoint:

```python
# Add after existing model definitions (around line 500)

class MyNewRequest(BaseModel):
    """Request model for my new endpoint."""
    input_data: str = Field(..., description="Input data to process")
    option: bool = Field(default=True, description="Optional flag")

class MyNewResponse(BaseModel):
    """Response model for my new endpoint."""
    result: str = Field(description="Processed result")
    processing_time_ms: float = Field(description="Processing time in milliseconds")
```

#### Step 2: Create the Endpoint Function

Add your endpoint with the `@app.` decorator:

```python
# Add after existing endpoints

@app.post(f"{API_PREFIX}/v1/my-new-endpoint", response_model=MyNewResponse, responses={
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
}, tags=["Custom"])
async def my_new_endpoint(
    request: Request,
    body: MyNewRequest,
    auth_info: Dict[str, Any] = Depends(verify_bearer_token)  # Requires JWT auth
):
    """
    My new custom endpoint.
    
    Describe what this endpoint does here.
    Requires Bearer token authentication.
    """
    import time
    start_time = time.perf_counter()
    
    try:
        # Your processing logic here
        result = f"Processed: {body.input_data}"
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        return MyNewResponse(
            result=result,
            processing_time_ms=round(processing_time, 3)
        )
    except Exception as e:
        logger.error(f"Error in my_new_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Processing failed")
```

#### Step 3: Make It Optional with Feature Flag (Recommended)

Wrap your endpoint with a feature flag for easy enable/disable:

```python
# Add feature flag at the top with other flags
ENABLE_MY_NEW_ENDPOINT = os.environ.get("ENABLE_MY_NEW_ENDPOINT", "true").lower() == "true"

# Wrap the endpoint definition
if ENABLE_MY_NEW_ENDPOINT:
    @app.post(f"{API_PREFIX}/v1/my-new-endpoint", ...)
    async def my_new_endpoint(...):
        ...
```

### How to Remove an API Endpoint

#### Option 1: Disable via Feature Flag (Recommended - Reversible)

Set the corresponding environment variable to `false`:

```powershell
$env:ENABLE_BATCH_ENDPOINT = "false"
```

#### Option 2: Comment Out the Code (Reversible)

In `api_service/app.py`, comment out the endpoint:

```python
# Temporarily disabled - uncomment to re-enable
# @app.post(f"{API_PREFIX}/v1/redact/batch", ...)
# async def redact_batch(...):
#     ...
```

#### Option 3: Delete the Code (Permanent)

Remove the entire endpoint function and its models from `api_service/app.py`.

**Warning:** This is permanent. Consider keeping a backup or using version control.

### Endpoint Configuration Quick Reference

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ENDPOINT MANAGEMENT QUICK REFERENCE                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FILE TO EDIT: api_service/app.py                                           │
│                                                                              │
│  ENABLE/DISABLE:                                                             │
│  ───────────────                                                             │
│  • Set environment variable: ENABLE_<ENDPOINT>_ENDPOINT=true|false          │
│  • Or modify default in code: os.environ.get("...", "true"|"false")         │
│                                                                              │
│  ADD NEW ENDPOINT:                                                           │
│  ─────────────────                                                           │
│  1. Define Pydantic request/response models                                  │
│  2. Add @app.post() or @app.get() decorated function                        │
│  3. (Optional) Wrap with feature flag for easy control                       │
│                                                                              │
│  REMOVE ENDPOINT:                                                            │
│  ────────────────                                                            │
│  • Disable: Set ENABLE_<X>_ENDPOINT=false                                   │
│  • Comment: # @app.post(...) / # async def ...                              │
│  • Delete: Remove function and models from app.py                            │
│                                                                              │
│  CURRENT FEATURE FLAGS:                                                      │
│  ──────────────────────                                                      │
│  ENABLE_BATCH_ENDPOINT        → /v1/redact/batch                            │
│  ENABLE_HEALTH_ENDPOINT       → /health                                      │
│  ENABLE_DOCS_ENDPOINT         → /docs, /redoc                               │
│  ENABLE_MONITORING_ENDPOINTS  → /livez, /readyz, /metrics                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Supported PI Types

| Category | Type | Token | Example |
|----------|------|-------|---------|
| **Personal** ||||
| | Name | `[NAME]` | John Smith, राजेश कुमार |
| | Email | `[EMAIL]` | john@example.com |
| | Phone | `[PHONE]` | +91 9876543210, 1-800-555-1234 |
| | Employee ID | `[EMP_ID]` | EMP123456, E12345 |
| **Government IDs** ||||
| | Aadhaar | `[AADHAAR]` | 1234 5678 9012 |
| | PAN | `[PAN]` | ABCDE1234F |
| | Passport | `[PASSPORT]` | J1234567, A12345678 |
| **Financial** ||||
| | Credit Card | `[CC]` | 4111-1111-1111-1111 |
| | UPI ID | `[UPI]` | user@upi, user@paytm |
| **Infrastructure** ||||
| | Asset ID | `[ASSET_ID]` | 01HW2159845, 01SW1001759 |
| | IP Address | `[IP]` | 192.168.1.100, 10.0.0.1 |
| | Hostname | `[HOSTNAME]` | server-01.domain.com |
| | URL | `[URL]` | https://internal.example.com |
| | VDI/VM | `[ASSET_ID]` | 01VD0036314, 01VS0000117 |
| **Security** ||||
| | Password | `[PASSWORD]` | password: xyz123 |
| | API Key | `[API_KEY]` | sk-xxx, api_key_xxx |
| | Token | `[TOKEN]` | Bearer eyJ... |
| **Context** ||||
| | Signature Block | `[SIGNATURE_BLOCK]` | Regards, John... |
| | Windows Path | `[PATH]` | C:\Users\John\... |

---

## Quick Reference Card

```
╔═══════════════════════════════════════════════════════════════════╗
║                    PI REMOVER QUICK REFERENCE v2.7.1               ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  CLI COMMANDS                                                      ║
║  ──────────────────────────────────────────────────────────────   ║
║  Basic:      python -m pi_remover -i file.csv -c "Column"      ║
║  Fast:       python -m pi_remover -i file.csv -c "Col" --fast  ║
║  Model:      python -m pi_remover -i f.csv -c "C" --model lg   ║
║  Audit:      python -m pi_remover -i file.csv -c "Col" --audit ║
║  Module:     python -m pi_remover -i file.csv -c "Col" --fast     ║
║                                                                    ║
║  STANDALONE (single-file version)                                  ║
║  ──────────────────────────────────────────────────────────────   ║
║  Fast:       python pi_remover_standalone.py -i f.csv --fast      ║
║  Full NER:   python pi_remover_standalone.py -i f.csv --full      ║
║  Model:      python pi_remover_standalone.py --full --model trf   ║
║  Interactive:python pi_remover_standalone.py --interactive        ║
║                                                                    ║
║  SPACY MODELS (use with --model)                                   ║
║  ──────────────────────────────────────────────────────────────   ║
║  sm = en_core_web_sm  (12MB,  fastest,  lower accuracy)           ║
║  md = en_core_web_md  (40MB,  fast,     good accuracy)            ║
║  lg = en_core_web_lg  (560MB, medium,   high accuracy) [DEFAULT]  ║
║  trf= en_core_web_trf (438MB, slowest,  highest accuracy)         ║
║                                                                    ║
║  DEPLOYMENT                                                        ║
║  ──────────────────────────────────────────────────────────────   ║
║  DEV:        .\scripts\deploy-dev.ps1                             ║
║  PROD:       .\scripts\deploy-prod.ps1                            ║
║  Promote:    .\scripts\promote-to-prod.ps1                        ║
║                                                                    ║
║  ENDPOINTS (with /dev or /prod prefix)                            ║
║  ──────────────────────────────────────────────────────────────   ║
║  DEV Auth:   POST http://localhost:8080/dev/auth/token            ║
║  DEV Redact: POST http://localhost:8080/dev/v1/redact             ║
║  DEV Health: GET  http://localhost:8080/dev/health                ║
║  PROD Auth:  POST http://localhost:9080/prod/auth/token           ║
║  PROD Redact:POST http://localhost:9080/prod/v1/redact            ║
║  PROD Health:GET  http://localhost:9080/prod/health               ║
║                                                                    ║
║  API MODEL SELECTION (v2.7.1)                                      ║
║  ──────────────────────────────────────────────────────────────   ║
║  Fast mode:  {"text": "...", "enable_ner": false}                 ║
║  Custom:     {"text": "...", "spacy_model": "en_core_web_trf"}    ║
║                                                                    ║
║  DEV CREDENTIALS                                                   ║
║  ──────────────────────────────────────────────────────────────   ║
║  Client ID:     pi-dev-client                                        ║
║  Client Secret: YOUR_DEV_CLIENT_SECRET_HERE                 ║
║                                                                    ║
║  PORTS                                                             ║
║  ──────────────────────────────────────────────────────────────   ║
║  DEV API:   8080     PROD API:   9080                             ║
║  DEV Web:   8082     PROD Web:   9082                             ║
║                                                                    ║
║  FAST MODE (10x faster, no NER)                                   ║
║  ──────────────────────────────────────────────────────────────   ║
║  CLI:        --fast                                               ║
║  Standalone: --fast (default) or --full for NER                   ║
║  API:        {"enable_ner": false}                                ║
║  Docker:     -e ENABLE_NER=false                                  ║
║  Web UI:     Check "Fast Mode" checkbox                           ║
║                                                                    ║
║  DOCKER                                                            ║
║  ──────────────────────────────────────────────────────────────   ║
║  Build:      docker build -t pi-gateway -f api_service/Dockerfile .║
║  Run:        docker run -p 8080:8080 pi-gateway                   ║
║  Run Fast:   docker run -p 8080:8080 -e ENABLE_NER=false pi-gateway║
║  Logs:       docker logs -f pi-gateway-dev                        ║
║  Stop:       docker-compose -f docker/docker-compose.dev.yml down ║
║                                                                    ║
║  TESTS                                                             ║
║  ──────────────────────────────────────────────────────────────   ║
║  All:        python -m pytest tests/ -v                           ║
║  Core:       python -m pytest tests/test_remover.py -v            ║
║  Coverage:   python -m pytest tests/ --cov=src/pi_remover         ║
║                                                                    ║
║  TROUBLESHOOTING                                                   ║
║  ──────────────────────────────────────────────────────────────   ║
║  No spaCy:   python -m spacy download en_core_web_lg              ║
║  Memory:     docker run --memory=4g ...                           ║
║  Debug:      $env:LOG_LEVEL = "DEBUG"                             ║
║  Health:     curl http://localhost:8080/dev/health                ║
║                                                                    ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

## Files Quick Reference

| File | Purpose | When to Edit |
|------|---------|--------------|
| `config.yaml` | Detection settings, PI types, exclusions | Change what gets detected |
| `docker/.env.dev` | DEV environment variables | Change DEV settings |
| `docker/.env.prod` | PROD secrets & settings | Configure production |
| `docker/docker-compose.dev.yml` | DEV Docker config | Change DEV ports/resources |
| `docker/docker-compose.prod.yml` | PROD Docker config | Change PROD ports/resources |
| `api_service/app.py` | API Gateway code | Add API features |
| `web_service/app.py` | Web UI code (hybrid mode) | Add UI features |
| `src/pi_remover/patterns.py` | Regex patterns | Add detection patterns |
| `src/pi_remover/remover.py` | Detection methods | Add `_redact_*()` methods |
| `src/pi_remover/config.py` | Configuration | Add config flags |
| `src/pi_remover/dictionaries.py` | Name dictionaries | Add names/companies |
| `src/pi_remover/core.py` | Facade (re-exports) | Backward compatibility |
| `requirements.txt` | Python dependencies | Add packages |
| `pyproject.toml` | Package config | Change package metadata |

---

*Last Updated: December 2025*
*Version: 2.12.0*

---

# Management & Business FAQ

This section answers common questions that management, stakeholders, and decision-makers typically ask about PI Remover.

---

## What is PI Remover and why do we need it?

**PI Remover** is an enterprise-grade tool that automatically detects and redacts Personal Information (PI) from text data before it's shared, analyzed, or processed.

### Why We Need It

| Risk | Without PI Remover | With PI Remover |
|------|-------------------|-----------------|
| **Data Breach** | PI exposed in logs, exports, tickets | PI automatically redacted |
| **Compliance Violation** | GDPR/HIPAA fines up to €20M or 4% revenue | Compliant data handling |
| **LLM Data Leakage** | PI sent to external AI models (ChatGPT, Claude) | Clean data to LLMs |
| **Manual Effort** | Hours of manual redaction | Seconds of automatic processing |
| **Human Error** | Inconsistent, missed redactions | Consistent, comprehensive detection |

### Business Value

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BUSINESS VALUE PROPOSITION                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  COMPLIANCE          Risk mitigation for GDPR, HIPAA, PCI-DSS, CCPA         │
│  EFFICIENCY          Process 600K+ records in minutes vs weeks manually      │
│  AI ENABLEMENT       Safely use LLMs without PI exposure                     │
│  COST REDUCTION      Avoid breach costs ($4.45M average) and fines           │
│  SCALABILITY         Handle growing data volumes automatically               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What types of data can PI Remover detect?

PI Remover detects **35+ types of Personal Information** across multiple categories:

### Detection Categories

| Category | PI Types | Examples |
|----------|----------|----------|
| **Personal Identity** | Names, Email, Phone | John Doe, john@company.com, +91-9876543210 |
| **Employee Data** | Employee IDs, Service Accounts | 1234567, sa.rpauser, NT71853 |
| **Government IDs** | Aadhaar, PAN, Passport, SSN | 1234-5678-9012, ABCDE1234F |
| **Financial** | Credit Cards, Bank Accounts, UPI | 4111-1111-1111-1111, user@upi |
| **IT Infrastructure** | IPs, MACs, Hostnames, Asset IDs | 192.168.1.1, 19HW12345678 |
| **ITSM/Tickets** | ServiceNow, JIRA, RFC, CR | INC00012345, RFC # 25224330 |
| **Workplace** | Seat/Desk, Location, Badge | A1F-102, GLAH/7/ODC5/WSN/42 |
| **Security** | Passwords, API Keys, Tokens | password=xxx, Bearer eyJ... |
| **Cloud** | Azure/AWS/GCP IDs | Subscription GUIDs, ARNs |

### Detection Methods

1. **Regex Patterns** - 100+ compiled patterns for structured data
2. **NER (AI-based)** - spaCy Named Entity Recognition for names
3. **Dictionary Matching** - 10,000+ common names database
4. **Contextual Rules** - "From:", "Caller:", "Assigned to:" triggers

---

## How accurate is the detection?

### Accuracy Metrics

| Metric | Value | Meaning |
|--------|-------|---------|
| **Precision** | ~95% | 95% of what we redact is actually PI |
| **Recall** | ~92% | We catch 92% of all PI in the data |
| **F1 Score** | ~93% | Balanced accuracy measure |
| **False Positive Rate** | ~5% | 5% of redactions are incorrect |
| **False Negative Rate** | ~8% | 8% of PI may be missed |

### Accuracy by PI Type

| PI Type | Accuracy | Notes |
|---------|----------|-------|
| Emails | 99%+ | Highly structured, easy to detect |
| Phone Numbers | 98%+ | Multiple formats supported |
| Employee IDs | 97%+ | Organization-specific patterns |
| Credit Cards | 99%+ | Luhn validation applied |
| IP Addresses | 99%+ | Standard format |
| Names | 85-92% | Most challenging due to context |
| Tickets (INC/RFC) | 98%+ | Well-defined patterns |

### Factors Affecting Accuracy

- **Data Quality**: Clean, structured text = higher accuracy
- **Mode Selection**: Full NER mode > Fast mode for names
- **Custom Patterns**: Organization-specific patterns improve accuracy
- **Blocklists**: Tuned blocklists reduce false positives

---

## What happens if PI is missed?

### Risk Assessment

If PI is missed (false negative):

| Scenario | Risk Level | Mitigation |
|----------|------------|------------|
| PI in internal reports | Low | Limited exposure |
| PI sent to LLM | Medium | External AI provider access |
| PI in exported data | High | Potential breach |
| PI in public-facing output | Critical | Regulatory exposure |

### How We Minimize Missed PI

1. **Multi-Layer Detection**: Regex + NER + Dictionary + Context rules
2. **Conservative Matching**: When uncertain, we prefer to redact
3. **Custom Patterns**: Add organization-specific PI formats
4. **Regular Updates**: Patterns updated based on production analysis
5. **Manual Review Option**: Flag uncertain cases for human review

### Continuous Improvement Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONTINUOUS IMPROVEMENT CYCLE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. ANALYZE                    2. IDENTIFY                                  │
│   Production data              Missed PI patterns                            │
│        │                             │                                       │
│        ▼                             ▼                                       │
│   ┌─────────┐                 ┌─────────────┐                                │
│   │ Sample  │────────────────▶│ New Pattern │                                │
│   │ Output  │                 │ Development │                                │
│   └─────────┘                 └──────┬──────┘                                │
│        ▲                             │                                       │
│        │                             ▼                                       │
│   4. DEPLOY                   3. TEST                                        │
│   Version update              Validate accuracy                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What happens if non-PI is incorrectly redacted?

### Impact Assessment

False positives (non-PI incorrectly redacted):

| Impact | Example | Severity |
|--------|---------|----------|
| **Minor** | "dr drill" → "[NAME]" | Low - context recoverable |
| **Moderate** | Technical term redacted | Medium - may confuse readers |
| **High** | Critical data redacted | High - information loss |

### How We Minimize False Positives

1. **Extensive Blocklists**: 200+ words explicitly excluded
2. **Context-Aware Patterns**: Check surrounding text before redacting
3. **Capitalization Rules**: Names require proper capitalization
4. **Version Updates**: v2.8.3 fixed common false positives

### v2.8.3 False Positive Fixes

| Before (False Positive) | After (v2.8.3) | Fix Applied |
|------------------------|----------------|-------------|
| "dr drill" → "[NAME]" | "dr drill" (unchanged) | Capital letter requirement |
| "ms teams" → "[NAME]" | "ms teams" (unchanged) | Product name blocklist |
| "call urgently" → "[NAME]" | "call urgently" (unchanged) | Adverb blocklist |
| "Blue Screen" → "[NAME]" | "Blue Screen" (unchanged) | Technical term blocklist |

### Handling False Positives

1. **Report**: Document the false positive with example text
2. **Analyze**: Determine which pattern caused it
3. **Fix**: Add to blocklist or modify pattern
4. **Test**: Verify fix doesn't break real detections
5. **Deploy**: Update version and document in KEBD

---

## Can we use this with LLMs like ChatGPT/Claude?

**Yes!** This is one of the primary use cases. PI Remover acts as a **gateway** before data reaches external LLMs.

### LLM Gateway Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LLM GATEWAY ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Your Application                                                           │
│         │                                                                    │
│         ▼                                                                    │
│   ┌─────────────────┐                                                        │
│   │  PI Remover API │  ← Redact PI from prompts                             │
│   │  (Port 8080)    │                                                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │ External LLM    │  ChatGPT, Claude, Gemini, etc.                        │
│   │ (Clean Data)    │  ← Receives only redacted data                        │
│   └────────┬────────┘                                                        │
│            │                                                                 │
│            ▼                                                                 │
│   ┌─────────────────┐                                                        │
│   │ Response back   │  LLM response (no PI restored)                        │
│   │ to Application  │                                                        │
│   └─────────────────┘                                                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Integration Example

```python
# Before sending to LLM
import requests

# 1. Get auth token
token = requests.post("http://pi-gateway:8080/dev/auth/token", 
    json={"client_id": "llm-client", "client_secret": "xxx"}).json()["access_token"]

# 2. Redact PI from user prompt
user_prompt = "Fix John's laptop (john@company.com, EMP1234567)"
clean = requests.post("http://pi-gateway:8080/dev/v1/redact",
    headers={"Authorization": f"Bearer {token}"},
    json={"text": user_prompt, "enable_ner": False}).json()

# 3. Send clean prompt to LLM
# clean["redacted_text"] = "Fix [NAME]'s laptop ([EMAIL], [EMP_ID])"
llm_response = call_openai(clean["redacted_text"])
```

### Benefits for LLM Use Cases

- **Compliance**: No PI sent to third-party AI providers
- **Latency**: <50ms added per request (fast mode)
- **Scalability**: Handles high-volume LLM applications
- **Audit Trail**: Log what was redacted before LLM

---

## Is this tool compliant with GDPR/HIPAA/PCI-DSS?

### Compliance Support

| Regulation | How PI Remover Helps |
|------------|---------------------|
| **GDPR** | Data minimization, pseudonymization of personal data |
| **HIPAA** | De-identification of Protected Health Information (PHI) |
| **PCI-DSS** | Masking of cardholder data (credit card numbers) |
| **CCPA** | Redaction of California resident personal information |
| **SOC 2** | Access controls, audit logging, encryption |

### Important Notes

⚠️ **PI Remover is a tool that SUPPORTS compliance, not a compliance certification itself.**

To achieve compliance, you also need:
- Proper data governance policies
- Access controls and authentication
- Secure infrastructure (encryption at rest/transit)
- Audit trails and logging
- Data retention policies
- Incident response procedures

### Compliance-Supporting Features

| Feature | Purpose |
|---------|---------|
| JWT Authentication | Access control |
| Rate Limiting | Abuse prevention |
| Audit Logging | Compliance evidence |
| Structured Logs | SIEM integration |
| No Data Retention | PI never stored |
| Local Processing | Data stays on-premises |

---

## How fast is the processing?

### Performance Benchmarks

| Mode | Speed | Use Case |
|------|-------|----------|
| **Fast Mode** (Regex only) | 4,000-8,000 rows/sec | Real-time, LLM gateway |
| **Full NER Mode** | 200-500 rows/sec | Batch processing, max accuracy |
| **API Latency** | <50ms per request | Real-time applications |
| **Batch Processing** | 600K rows in ~2-5 min | Large file processing |

### Real-World Performance

From production testing (December 2025):

| File | Rows | Mode | Time | Speed |
|------|------|------|------|-------|
| RFC Tickets | 429,448 | Fast | ~55 sec | 7,800 rows/sec |
| Support Tickets | 606,791 | Fast | ~90 sec | 6,742 rows/sec |
| Mixed Data | 5,000 | Fast | 1.03 sec | 4,874 rows/sec |

### Optimizing Performance

1. **Use Fast Mode**: 10-15x faster than Full NER
2. **Batch API Calls**: Use `/v1/redact/batch` endpoint
3. **Smaller spaCy Model**: `en_core_web_sm` faster than `lg`
4. **Parallel Processing**: Multi-worker for large files
5. **Redis Caching**: Faster rate limiting

---

## Can this scale for enterprise use?

**Yes.** The architecture is designed for enterprise-scale deployments.

### Scalability Features

| Component | Scaling Method |
|-----------|---------------|
| **API Service** | Horizontal scaling (multiple instances) |
| **Web Service** | Horizontal scaling with load balancer |
| **Rate Limiting** | Redis for distributed rate limiting |
| **Processing** | Multi-worker, parallel processing |
| **Storage** | Stateless - no database required |

### Enterprise Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE DEPLOYMENT ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                          Load Balancer (L7)                                  │
│                               │                                              │
│            ┌──────────────────┼──────────────────┐                          │
│            │                  │                  │                          │
│            ▼                  ▼                  ▼                          │
│     ┌──────────┐       ┌──────────┐       ┌──────────┐                      │
│     │ API Svc  │       │ API Svc  │       │ API Svc  │  ← Auto-scaling     │
│     │ Node 1   │       │ Node 2   │       │ Node N   │                      │
│     └────┬─────┘       └────┬─────┘       └────┬─────┘                      │
│          │                  │                  │                            │
│          └──────────────────┼──────────────────┘                            │
│                             │                                                │
│                             ▼                                                │
│                       ┌──────────┐                                           │
│                       │  Redis   │  ← Shared rate limiting                  │
│                       │ Cluster  │                                           │
│                       └──────────┘                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Capacity Planning

| Users | Requests/min | Recommended Setup |
|-------|--------------|-------------------|
| 1-50 | <1,000 | Single instance |
| 50-500 | 1,000-10,000 | 2-3 instances + Redis |
| 500-5000 | 10,000-100,000 | 5+ instances + Redis cluster |
| 5000+ | 100,000+ | Kubernetes auto-scaling |

---

## What if we need to detect new PI types?

### Adding New Patterns

New PI types can be added through:

1. **Configuration** (simple patterns):
   - Edit `config.yaml` for basic patterns

2. **Code Changes** (complex patterns):
   - Add regex to `PIPatterns` class
   - Create detection method
   - Add tests

### Turnaround Time

| Change Type | Effort | Time |
|-------------|--------|------|
| Add to blocklist | 5 min | Same day |
| New simple pattern | 30 min | Same day |
| Complex pattern with context | 2-4 hours | 1-2 days |
| New PI category | 1-2 days | 1 week |

### Request Process

1. **Identify**: Document the PI type with examples
2. **Analyze**: Determine pattern format and variations
3. **Develop**: Create and test the pattern
4. **Review**: Code review and testing
5. **Deploy**: Update version and documentation

See **[HOWTO → How to Add Custom Patterns](#how-to-add-custom-patterns)** for detailed instructions.

---

## How do we know the tool is working correctly?

### Monitoring & Validation

| Method | Purpose | Frequency |
|--------|---------|-----------|
| **Health Endpoint** | Service availability | Real-time |
| **Audit Logs** | Request/response tracking | Every request |
| **Sample Validation** | Manual review of output | Weekly/Monthly |
| **Regression Tests** | Automated accuracy tests | Every deployment |
| **Metrics Dashboard** | Processing volumes, latency | Real-time |

### Health Check

```bash
# API Health
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/dev/health

# Response
{
  "status": "healthy",
  "version": "2.12.0",
  "mode": "production",
  "ner_available": true,
  "uptime_seconds": 86400
}
```

### Validation Process

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          VALIDATION PROCESS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   1. INPUT SAMPLE                 2. PROCESS                                 │
│   Known PI data                   Run through PI Remover                     │
│        │                                │                                    │
│        ▼                                ▼                                    │
│   ┌─────────────┐              ┌─────────────────┐                           │
│   │ 100 rows    │─────────────▶│ Redacted Output │                           │
│   │ with known  │              │ + Details       │                           │
│   │ PI values   │              └────────┬────────┘                           │
│   └─────────────┘                       │                                    │
│                                         ▼                                    │
│                               3. COMPARE                                     │
│                               ┌─────────────────┐                            │
│                               │ Expected vs     │                            │
│                               │ Actual Results  │                            │
│                               └────────┬────────┘                            │
│                                        │                                     │
│                               4. REPORT                                      │
│                               ┌─────────────────┐                            │
│                               │ Accuracy Report │                            │
│                               │ False +/- Count │                            │
│                               └─────────────────┘                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What are the infrastructure requirements?

### Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | 2 cores | 4+ cores |
| **RAM** | 4 GB | 8+ GB |
| **Disk** | 2 GB | 10 GB (for models) |
| **Python** | 3.11+ | 3.11+ |
| **Network** | HTTP/HTTPS | HTTPS with TLS |

### spaCy Model Memory

| Model | Memory | Use Case |
|-------|--------|----------|
| `en_core_web_sm` | ~50 MB | Development, testing |
| `en_core_web_md` | ~100 MB | Light production |
| `en_core_web_lg` | ~600 MB | **Production (default)** |
| `en_core_web_trf` | ~500 MB | Maximum accuracy |

### Docker Resource Limits

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Optional Components

| Component | Purpose | Required? |
|-----------|---------|-----------|
| **Redis** | Distributed rate limiting | Optional (has fallback) |
| **ELK/Splunk** | Log aggregation | Optional |
| **Prometheus** | Metrics collection | Optional |
| **Load Balancer** | Multi-instance | For scaling |

---

## What is the total cost of ownership?

### Cost Components

| Component | Type | Estimated Cost |
|-----------|------|----------------|
| **Infrastructure** | Compute (2-4 vCPU, 8GB RAM) | $50-200/month |
| **Redis** (optional) | Managed Redis | $25-100/month |
| **Development** | Initial setup | 40-80 hours |
| **Maintenance** | Ongoing updates | 4-8 hours/month |
| **Training** | User training | 2-4 hours |

### Cost Comparison

| Approach | Annual Cost | Pros | Cons |
|----------|-------------|------|------|
| **PI Remover (Self-hosted)** | $1,000-3,000 | Full control, no data leaves org | Maintenance required |
| **Commercial SaaS** | $10,000-50,000 | Managed service | Data sent to vendor |
| **Manual Redaction** | $100,000+ | Human judgment | Slow, inconsistent, expensive |

### ROI Calculation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ROI CALCULATION                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   COSTS                           SAVINGS                                    │
│   ──────                          ───────                                    │
│   Infrastructure:    $2,400/yr    Manual work avoided:    $50,000/yr        │
│   Maintenance:       $5,000/yr    Breach prevention:      Priceless         │
│   Initial setup:     $5,000       Compliance fines:       Up to $20M        │
│   ───────────────────             ─────────────────────                      │
│   TOTAL:            $12,400       MINIMUM SAVINGS:        $50,000/yr        │
│                                                                              │
│   ROI = (Savings - Cost) / Cost × 100                                       │
│   ROI = ($50,000 - $12,400) / $12,400 × 100 = 303%                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How is the tool secured?

### Security Layers

| Layer | Control | Description |
|-------|---------|-------------|
| 1 | **Authentication** | JWT Bearer tokens (30-min expiry) |
| 2 | **Authorization** | Client-based access control |
| 3 | **Rate Limiting** | Abuse prevention (Redis-backed) |
| 4 | **Input Validation** | Size limits, type checking |
| 5 | **File Security** | Extension, MIME, magic byte checks |
| 6 | **Audit Logging** | Every request logged |
| 7 | **No Data Storage** | PI never persisted |
| 8 | **Container Security** | Non-root, minimal image |

### Authentication Flow

```
Client → POST /auth/token (credentials) → JWT Token
Client → POST /v1/redact (Bearer Token + Data) → Redacted Data
```

### Security Configuration

```yaml
# config/clients.yaml
clients:
  my-app:
    secret: "strong-random-secret"
    rate_limit: 1000
    environment: "production"

jwt:
  secret_key: "your-256-bit-secret"
  algorithm: "HS256"
  expiry_minutes: 30
```

---

## Can we audit who used the tool?

**Yes.** Comprehensive audit logging is built-in.

### Audit Log Contents

| Field | Description |
|-------|-------------|
| `timestamp` | When the request occurred |
| `client_id` | Who made the request |
| `action` | What operation (redact, batch, health) |
| `request_id` | Unique request identifier |
| `correlation_id` | Cross-service tracking |
| `input_length` | Size of input data |
| `redactions_count` | Number of PI items redacted |
| `processing_time_ms` | How long it took |
| `status` | Success or error |

### Sample Audit Log

```json
{
  "timestamp": "2025-12-14T10:30:45.123+05:30",
  "level": "INFO",
  "client_id": "pi-dev-client",
  "action": "redact",
  "request_id": "req-abc123",
  "correlation_id": "corr-xyz789",
  "input_length": 1500,
  "redactions_count": 12,
  "pi_types": ["EMAIL", "PHONE", "NAME", "EMP_ID"],
  "processing_time_ms": 45,
  "status": "success"
}
```

### Log Integration

- **ELK Stack**: Elasticsearch, Logstash, Kibana
- **Splunk**: Direct JSON ingestion
- **CloudWatch**: AWS log groups
- **Stackdriver**: GCP logging

---

## What happens during an outage?

### Hybrid Mode (v2.9.0)

The Web Service has **automatic fallback**:

```
Request → Try API Service → [Available?]
                                │
                    ┌───────────┴───────────┐
                   Yes                      No
                    │                        │
                    ▼                        ▼
              Use API Response        Use Local PIRemover
              (Centralized)           (Automatic Fallback)
```

### Outage Scenarios

| Scenario | Impact | Mitigation |
|----------|--------|------------|
| API Service down | None for Web users | Automatic local fallback |
| Redis down | Slight delay | In-memory rate limiting |
| spaCy model unavailable | Fast mode only | Regex-only detection |
| Complete outage | Service unavailable | Health checks, alerting |

### Circuit Breaker

```yaml
# config/web_service.yaml
circuit_breaker:
  failure_threshold: 5      # Open after 5 failures
  recovery_timeout: 30      # Try again after 30 seconds
  half_open_requests: 3     # Test requests in half-open
```

---

## How do we maintain this tool?

### Maintenance Tasks

| Task | Frequency | Effort |
|------|-----------|--------|
| Dependency updates | Monthly | 1-2 hours |
| spaCy model updates | Quarterly | 1 hour |
| Pattern tuning | As needed | 2-4 hours |
| False positive fixes | As reported | 30 min - 2 hours |
| Security patches | As released | 1-4 hours |
| Documentation updates | With changes | 30 min |

### Update Process

```powershell
# 1. Update dependencies
pip install --upgrade -r requirements.txt

# 2. Update spaCy model
python -m spacy download en_core_web_lg

# 3. Run tests
python -m pytest tests/ -v

# 4. Deploy
.\scripts\deploy-prod.ps1
```

### Monitoring Checklist

- [ ] Health endpoint responding
- [ ] No error spikes in logs
- [ ] Processing times normal
- [ ] No unusual false positive reports
- [ ] Disk space adequate
- [ ] Memory usage stable

---

## Can this be customized for our organization?

**Yes.** Multiple customization options:

### Customization Levels

| Level | What | How |
|-------|------|-----|
| **Configuration** | PI types, tokens, exclusions | Edit `config.yaml` |
| **Patterns** | Organization-specific IDs | Add to `PIPatterns` class |
| **Blocklists** | Words to never redact | Add to blocklist sets |
| **Dictionaries** | Custom name lists | Update `data/names.txt` |
| **Branding** | Web UI appearance | Modify templates |
| **Integration** | API extensions | Extend `app.py` |

### Common Customizations

1. **Organization-specific patterns**:
   - Employee ID format (e.g., `EMP-######`)
   - Asset ID format (e.g., `ASSET-####-####`)
   - Internal ticket systems

2. **Industry-specific PI**:
   - Healthcare: MRN, Provider NPI
   - Finance: Account numbers, SWIFT codes
   - Government: Case numbers, Badge IDs

3. **Regional adaptations**:
   - Phone formats (country-specific)
   - Government IDs (country-specific)
   - Name patterns (cultural variations)

### Getting Help

- **Documentation**: `docs/` folder
- **KEBD**: Known issues and fixes
- **HOWTO**: Step-by-step guides
- **CHANGELOG**: Version history

---

*End of Management & Business FAQ*
