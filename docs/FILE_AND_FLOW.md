# FILE_AND_FLOW.md

## PI Remover v2.13.2 - Complete System Documentation

This document provides an in-depth explanation of how the PI Remover system works, covering both the Web UI and API flows, along with a detailed breakdown of the folder structure and file responsibilities.

> **v2.13.2 Update:** This version introduces a **19-Layer Priority Architecture** for optimal redaction ordering, **UPN email handling** for employee ID extraction, and **tiered context-aware detection** for 4-7 digit employee IDs.
>
> **PIRemover Core:** v2.13.2 (as of 2025-12-16)

---

# Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Changes v2.9.0](#architecture-changes-v290)
3. [Service Startup Options](#service-startup-options)
4. [Tech Stack & Libraries](#tech-stack--libraries)
5. [Complete Flow: Web UI](#complete-flow-web-ui)
6. [Complete Flow: API](#complete-flow-api)
7. [Folder Structure](#folder-structure)
8. [File Responsibilities](#file-responsibilities)
9. [Configuration System](#configuration-system)
10. [Quick Reference](#quick-reference)

---

# System Overview

## v2.9.0 Hybrid Microservices Architecture (Current)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 PI REMOVER HYBRID MICROSERVICES ARCHITECTURE                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Users/Browsers              LLM Gateways              CLI/Standalone        │
│        │                          │                          │              │
│        ▼                          │                          │              │
│  ┌─────────────────┐              │                          │              │
│  │   WEB SERVICE   │              │                          │              │
│  │   (Port 8082)   │              │                          │              │
│  │                 │              │                          │              │
│  │ ┌─────────────┐ │              │                          │              │
│  │ │ API Client  │ │              │                          │              │
│  │ │ + Circuit   │──── HTTP + JWT ──────────┐                │              │
│  │ │   Breaker   │ │              │         │                │              │
│  │ └─────────────┘ │              │         │                │              │
│  │                 │              │         │                │              │
│  │ ┌─────────────┐ │              │         │                │              │
│  │ │   LOCAL     │ │◄─ Fallback ──┘         │                │              │
│  │ │  PIREMOVER  │ │              │         │                │              │
│  │ └─────────────┘ │              │         │                │              │
│  └─────────────────┘              │         │                │              │
│                                   │         ▼                ▼              │
│                                   │  ┌─────────────────────────────┐        │
│                                   └─▶│      API SERVICE            │        │
│                                      │      (Port 8080)            │        │
│                                      │                             │        │
│                                      │  ┌─────────────────────┐    │        │
│                                      │  │    PI REMOVER CORE  │    │        │
│                                      │  │  (src/pi_remover/)  │    │        │
│                                      │  │                     │    │        │
│                                      │  │  • Regex Patterns   │    │        │
│                                      │  │  • NER (spaCy)      │    │        │
│                                      │  │  • Name Dictionaries│    │        │
│                                      │  │  • Context Rules    │    │        │
│                                      │  └─────────────────────┘    │        │
│                                      └──────────────┬──────────────┘        │
│                                                     │                        │
│                                                     ▼                        │
│                                      ┌─────────────────────────────┐        │
│                                      │         REDIS               │        │
│                                      │    (Rate Limiting)          │        │
│                                      │    (Optional)               │        │
│                                      └─────────────────────────────┘        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                        CONFIGURATION                                     ││
│  │  config/api_service.yaml    config/web_service.yaml    config/redis.yaml││
│  │  config/clients.yaml        config/logging.yaml                          ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     SHARED INFRASTRUCTURE                                ││
│  │  shared/config_loader.py    shared/logging_config.py   shared/redis.py  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Ways to Use PI Remover

| Method | Use Case | Port | Authentication | Architecture |
|--------|----------|------|----------------|--------------|
| **Web UI (Hybrid)** | Interactive with API + fallback | 8082 | None (for users) | Calls API, fallback to local |
| **Web UI (Standalone)** | Interactive local processing | 8082 | None (for users) | Local PIRemover only |
| **API** | Programmatic access, LLM gateway | 8080 | JWT Bearer Token | Direct access |
| **CLI** | Batch file processing | N/A | None | Self-contained |

---

# Architecture Changes v2.9.0

## Before vs After

### Before (v2.8.x - Monolith)

```
┌─────────────────┐        ┌─────────────────┐
│   Web Service   │        │   API Service   │
│   (Port 8082)   │        │   (Port 8080)   │
│                 │        │                 │
│ ┌─────────────┐ │        │ ┌─────────────┐ │
│ │ PIRemover   │ │        │ │ PIRemover   │ │   ← Duplicate!
│ │ (spaCy NER) │ │        │ │ (spaCy NER) │ │
│ └─────────────┘ │        │ └─────────────┘ │
│                 │        │                 │
│ Independent     │        │ Independent     │
└─────────────────┘        └─────────────────┘
```

**Problems:**
- Duplicate spaCy models (~600MB each)
- Duplicate code maintenance
- No shared rate limiting
- No centralized logging

### After (v2.9.0 - Hybrid Microservices)

```
┌─────────────────┐              ┌─────────────────┐     ┌─────────┐
│   Web Service   │── HTTP+JWT ─▶│   API Service   │────▶│  Redis  │
│   (Port 8082)   │              │   (Port 8080)   │     │         │
│                 │              │                 │     └─────────┘
│ ┌─────────────┐ │              │ ┌─────────────┐ │
│ │ API Client  │ │              │ │ PIRemover   │ │   ← Primary instance
│ │ + Circuit   │ │              │ │ (spaCy NER) │ │
│ │   Breaker   │ │              │ └─────────────┘ │
│ └─────────────┘ │              │                 │
│                 │              │  Rate Limiting  │
│ ┌─────────────┐ │              │  Auth/Security  │
│ │   Local     │ │              └─────────────────┘
│ │  PIRemover  │ │ ◄── Automatic fallback if API unavailable
│ │ (Fallback)  │ │
│ └─────────────┘ │
└─────────────────┘

        │                                │
        └────────────────┬───────────────┘
                         ▼
              config/*.yaml (shared)
              shared/*.py (common code)
```

**Benefits:**
- Primary PIRemover instance in API service
- Automatic local fallback in Web service
- Zero downtime - users unaffected by API outages
- Shared Redis for rate limiting across instances
- Circuit breaker handles API outages gracefully
- Centralized JSON logging for ELK/Splunk
- YAML configuration (no environment variables)

---

# Service Startup Options

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

## Hybrid Mode Flow

```
Request → Web Service → Try API → [Available?] → Yes → Use API Response
                                       ↓
                                      No
                                       ↓
                           Use Local PIRemover (automatic)
```

## New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **API Client** | `web_service/api_client.py` | HTTP client for web→API calls |
| **Circuit Breaker** | `web_service/api_client.py` | Resilience pattern |
| **Local Fallback** | `web_service/app.py` | Hybrid redaction functions |
| **Config Loader** | `shared/config_loader.py` | YAML configuration |
| **Logging Config** | `shared/logging_config.py` | Structured JSON logging |
| **Redis Client** | `shared/redis_client.py` | Rate limiting + cache |

---

# Tech Stack & Libraries

This section provides a comprehensive breakdown of what each library does and which component uses it.

## Version Summary

| Component | Version | Description |
|-----------|---------|-------------|
| **Architecture** | v2.13.2 | Modular Hybrid Microservices + 19-Layer Priority |
| **PIRemover Core** | v2.13.2 | PI detection and redaction engine (9 modules) |
| **PIRemover Standalone** | v2.13.2 | Single-file PI remover (fully synced) |
| **Python** | 3.11+ | Runtime requirement |
| **FastAPI** | 0.104+ | Web framework |
| **spaCy** | 3.7+ | NER engine |
| **pytest** | - | 61 tests pass |

> **See Also**: [ARCHITECTURE.md - Redaction Priority Layer Architecture](ARCHITECTURE.md#redaction-priority-layer-architecture) for detailed priority ordering and dependency graph.

## Complete Tech Stack Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TECHNOLOGY STACK (v2.13.2)                           │
│                         PIRemover Core: v2.13.2 (19-Layer Priority)          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  RUNTIME                                                                     │
│  └── Python 3.11+ (required for zoneinfo, improved typing)                 │
│                                                                              │
│  WEB FRAMEWORK                                                               │
│  └── FastAPI 0.104+ (async-first, automatic OpenAPI docs)                  │
│      └── Uvicorn (ASGI server with hot reload)                             │
│      └── Pydantic 2.0+ (request/response validation)                       │
│                                                                              │
│  HTTP CLIENT                                                                 │
│  └── httpx 0.25+ (async HTTP client for Web→API calls)                    │
│                                                                              │
│  DATA PROCESSING                                                             │
│  └── pandas 2.0+ (DataFrame operations for CSV/Excel)                      │
│  └── openpyxl 3.1+ (Excel .xlsx read/write)                                │
│  └── xlrd 2.0+ (Legacy Excel .xls read)                                    │
│  └── PyArrow (Parquet/columnar data support)                               │
│                                                                              │
│  NLP / NER                                                                   │
│  └── spaCy 3.7+ (Named Entity Recognition)                                 │
│      └── en_core_web_lg (English language model, ~600MB)                   │
│                                                                              │
│  CONFIGURATION                                                               │
│  └── PyYAML 6.0+ (YAML config file parsing)                                │
│                                                                              │
│  CACHING/RATE LIMITING                                                      │
│  └── redis 5.0+ (optional, with in-memory fallback)                        │
│                                                                              │
│  SECURITY (Custom Implementation - No External JWT Library)                 │
│  └── hmac + hashlib (HMAC-SHA256 for JWT signatures)                       │
│  └── base64 (JWT encoding/decoding)                                        │
│  └── secrets (Secure token generation)                                     │
│  └── zoneinfo (Timezone-aware audit logging)                               │
│                                                                              │
│  WEB UI                                                                      │
│  └── Jinja2 3.1+ (HTML templating)                                         │
│  └── python-multipart (File upload handling)                               │
│                                                                              │
│  UTILITIES                                                                   │
│  └── tqdm (Progress bars for batch processing)                             │
│  └── re (Standard library regex for pattern detection)                     │
│  └── multiprocessing (Parallel file processing)                            │
│                                                                              │
│  CONTAINERIZATION                                                            │
│  └── Docker (python:3.11-slim base image)                                  │
│  └── Docker Compose (multi-container orchestration)                        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Library-by-Library Breakdown

### Core Framework Libraries

| Library | Version | What It Does | Used By |
|---------|---------|--------------|---------|
| **FastAPI** | ≥0.104.0 | High-performance async web framework. Provides routing, dependency injection, automatic request validation, and OpenAPI documentation generation | `api_service/app.py`, `web_service/app.py` |
| **Uvicorn** | ≥0.24.0 (with standard extras) | ASGI server that runs FastAPI. Provides hot reload in development and production-ready serving | Both services via command line |
| **Pydantic** | ≥2.0.0 | Data validation using Python type hints. Validates API request/response bodies, enforces field constraints, generates JSON schemas | `api_service/app.py`, `web_service/app.py`, `security.py` |
| **Starlette** | (via FastAPI) | Low-level ASGI toolkit. Provides middleware base class, static files, CORS middleware | `security.py` (BaseHTTPMiddleware) |

### Data Processing Libraries

| Library | Version | What It Does | Used By |
|---------|---------|--------------|---------|
| **pandas** | ≥2.0.0 | DataFrame operations for reading, processing, and writing tabular data. Handles CSV column selection, batch processing, and data export | `src/pi_remover/processors/`, `web_service/app.py` |
| **openpyxl** | ≥3.1.0 | Read/write Excel 2010+ files (.xlsx). Used when users upload or download Excel files | `src/pi_remover/processors/` (via pandas engine) |
| **xlrd** | ≥2.0.0 | Read legacy Excel files (.xls). Fallback for older Excel format support | `src/pi_remover/processors/` (via pandas engine) |
| **PyArrow** | (optional) | High-performance columnar data. Enables Parquet file support and faster DataFrame operations | `requirements.txt` (optional) |

### NLP & Pattern Detection

| Library | Version | What It Does | Used By |
|---------|---------|--------------|---------|
| **spaCy** | ≥3.7.0 | Industrial-strength NLP library. Provides Named Entity Recognition (NER) for detecting PERSON, ORG, GPE, LOC entities | `src/pi_remover/ner.py` (SpacyNER class) |
| **en_core_web_lg** | (spaCy model) | Large English language model (~600MB). Trained on web text, provides high-accuracy NER. Downloaded separately | Loaded by SpacyNER.load() |
| **re** | (stdlib) | Regular expression engine. Powers **125+ compiled patterns** for emails, phones, IDs, IT/ITSM, cloud, security, etc. | `src/pi_remover/patterns.py` (PIPatterns class) |

### Security Libraries (Custom JWT Implementation)

> **Important:** This project uses a **custom JWT implementation** instead of libraries like PyJWT or python-jose. This is intentional for:
> - Reduced dependencies
> - Full control over token structure
> - No external library vulnerabilities

| Library | Version | What It Does | Used By |
|---------|---------|--------------|---------|
| **hmac** | (stdlib) | Hash-based Message Authentication Code. Creates HMAC-SHA256 signatures for JWT tokens | `security.py` (create_jwt_token, decode_jwt_token) |
| **hashlib** | (stdlib) | Secure hash algorithms. Provides SHA256 for JWT signatures and rate limit key hashing | `security.py` |
| **base64** | (stdlib) | Base64 encoding/decoding. Encodes JWT header, payload, and signature in URL-safe base64 | `security.py` (create_jwt_token, decode_jwt_token) |
| **secrets** | (stdlib) | Cryptographically secure random generation. Generates token IDs (jti), job IDs, session keys | `security.py`, `api_service/app.py` |
| **zoneinfo** | (stdlib, Python 3.9+) | IANA timezone database. Provides timezone-aware timestamps for audit logs (default: Asia/Kolkata) | `security.py` (get_audit_timestamp) |

### Web UI Libraries

| Library | Version | What It Does | Used By |
|---------|---------|--------------|---------|
| **Jinja2** | ≥3.1.0 | Template engine for HTML. Renders dynamic web pages with Python variables and logic | `web_service/app.py` (templates) |
| **python-multipart** | ≥0.0.6 | Parses multipart form data. Required for file uploads in FastAPI | `web_service/app.py` (file upload) |

### Configuration & Utilities

| Library | Version | What It Does | Used By |
|---------|---------|--------------|---------|
| **PyYAML** | ≥6.0 | YAML parser. Loads `config.yaml` for PI removal settings | `src/pi_remover/config.py` (load_config_from_yaml) |
| **tqdm** | ≥4.66.0 | Progress bar library. Shows processing progress for large files/batches | `src/pi_remover/utils.py` (file processing) |
| **multiprocessing** | (stdlib) | Parallel processing. Distributes work across CPU cores for large files | `src/pi_remover/utils.py` (PIRemoverConfig.num_workers) |
| **dataclasses** | (stdlib) | Decorator for data classes. Used for PIRemoverConfig, Redaction, RedactionResult | `src/pi_remover/config.py`, `src/pi_remover/data_classes.py` |
| **typing** | (stdlib) | Type hints support. Provides Optional, List, Dict, Any, Tuple for type annotations | All Python files |

---

## Component-Specific Dependencies

### API Service (`api_service/requirements.txt`)

```
fastapi>=0.104.0      # Web framework
uvicorn[standard]     # ASGI server with extras (websockets, watchfiles)
pydantic>=2.0.0       # Request/response validation
pandas>=2.0.0         # Data processing
tqdm>=4.66.0          # Progress bars (for batch processing)
```

> **Note:** spaCy is **NOT** included in API service requirements to keep the Docker image small (~100MB vs ~500MB). The API uses regex-only mode by default, with NER available if spaCy is installed separately.

### Web Service (`web_service/requirements.txt`)

```
fastapi>=0.104.0      # Web framework
uvicorn[standard]     # ASGI server
jinja2>=3.1.0         # HTML templates
python-multipart      # File upload handling
pydantic>=2.0.0       # Validation
pandas>=2.0.0         # Data processing
tqdm>=4.66.0          # Progress bars
openpyxl>=3.1.0       # Excel file support
```

### Root Package (`requirements.txt`)

```
pandas>=2.0.0         # DataFrame operations
tqdm>=4.66.0          # Progress bars
spacy>=3.5.0          # NER engine
openpyxl>=3.1.0       # Excel .xlsx support
xlrd>=2.0.0           # Legacy Excel .xls
pyyaml>=6.0           # Config file parsing
pyarrow               # Parquet/columnar data (optional)

# Post-install: python -m spacy download en_core_web_lg
```

---

## How Each Library Is Used (Code Examples)

### FastAPI + Pydantic (Request Validation)
```python
# api_service/app.py
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, validator

class RedactRequest(BaseModel):
    text: str = Field(..., max_length=100000)  # Pydantic enforces 100KB limit
    include_details: bool = False
    
    @validator('text')
    def validate_text(cls, v):
        # Custom validation logic
        if not v.strip():
            raise ValueError("Text cannot be empty")
        return v

@app.post("/dev/v1/redact")
async def redact_text(body: RedactRequest):  # Pydantic validates automatically
    ...
```

### Custom JWT (No PyJWT Library)
```python
# security.py - Custom HMAC-SHA256 JWT implementation

import hmac
import hashlib
import base64
import json

def create_jwt_token(payload: Dict[str, Any]) -> str:
    """Create JWT using stdlib only - no PyJWT needed."""
    
    # 1. Create header
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(
        json.dumps(header).encode()
    ).rstrip(b'=').decode()
    
    # 2. Create payload
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).rstrip(b'=').decode()
    
    # 3. Create signature using HMAC-SHA256
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b'=').decode()
    
    # 4. Combine into JWT
    return f"{header_b64}.{payload_b64}.{signature_b64}"
```

### spaCy NER (Name Detection)
```python
# src/pi_remover/ner.py

import spacy

class SpacyNER:
    def __init__(self, model_name: str = "en_core_web_lg"):
        self.nlp = None
        
    def load(self):
        # Load ~600MB English model
        self.nlp = spacy.load("en_core_web_lg")
        # Disable unused components for speed
        self.nlp.disable_pipes(["parser", "lemmatizer"])
        
    def extract_entities(self, text: str):
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG", "GPE", "LOC"}:
                yield (ent.text, ent.label_, ent.start_char, ent.end_char)
```

### pandas (Data Processing)
```python
# src/pi_remover/processors/csv_processor.py

import pandas as pd

def process_file(input_path: str, columns: List[str]) -> pd.DataFrame:
    # Auto-detect file format and load
    if input_path.endswith('.csv'):
        df = pd.read_csv(input_path)
    elif input_path.endswith('.xlsx'):
        df = pd.read_excel(input_path, engine='openpyxl')
    elif input_path.endswith('.xls'):
        df = pd.read_excel(input_path, engine='xlrd')
    
    # Process specified columns
    for col in columns:
        df[col] = df[col].apply(lambda x: remover.redact(str(x)) if pd.notna(x) else x)
    
    return df
```

### Token Bucket Rate Limiting
```python
# security.py - Custom rate limiter (no external library)

class RateLimiter:
    """Token bucket algorithm for rate limiting."""
    
    def __init__(self):
        self._buckets = defaultdict(lambda: {
            "tokens": 100,  # max requests
            "last_update": time.time()
        })
    
    def check_rate_limit(self, identifier: str) -> bool:
        bucket = self._buckets[identifier]
        
        # Refill tokens based on time elapsed
        elapsed = time.time() - bucket["last_update"]
        refill_rate = 100 / 60  # 100 requests per 60 seconds
        bucket["tokens"] = min(100, bucket["tokens"] + elapsed * refill_rate)
        bucket["last_update"] = time.time()
        
        # Check if request allowed
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True
        return False
```

---

## Why Certain Libraries Were Chosen

| Decision | Reasoning |
|----------|-----------|
| **FastAPI over Flask** | Async-first, automatic OpenAPI docs, Pydantic integration, better performance |
| **Custom JWT over PyJWT** | Fewer dependencies, full control, no supply chain risk |
| **spaCy over NLTK** | Better NER accuracy, production-ready, faster inference |
| **pandas over pure Python** | Industry standard for tabular data, excellent Excel support |
| **Jinja2 over React/Vue** | Server-side rendering, simpler deployment, no JS build step |
| **Docker over VMs** | Consistent environments, faster deployments, better resource usage |

---

## Library Size Impact

| Library | Disk Size | Memory Impact | Notes |
|---------|-----------|---------------|-------|
| spaCy + en_core_web_lg | ~600MB | ~500MB RAM | Optional - only for FULL mode |
| pandas | ~50MB | Variable | Required for file processing |
| FastAPI + Uvicorn | ~5MB | ~30MB RAM | Core framework |
| openpyxl + xlrd | ~10MB | ~20MB RAM | Excel support |

> **Docker Image Sizes:**
> - API Service (without spaCy): ~100MB
> - API Service (with spaCy): ~700MB
> - Web Service: ~150MB

---

# Complete Flow: Web UI

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WEB UI FLOW                                          │
└─────────────────────────────────────────────────────────────────────────────┘

User Opens Browser
        │
        ▼
┌───────────────────┐
│ GET /             │ ◄─── Request to web_service/app.py
│ (Port 8082)       │
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────────────────────────────────┐
│ web_service/templates/index.html                              │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │  PI Remover - Enterprise Data Protection                  │ │
│ │  ┌──────────────────┐  ┌───────────────────────────────┐  │ │
│ │  │ FILE UPLOAD TAB  │  │ TEXT INPUT TAB                │  │ │
│ │  │                  │  │                               │  │ │
│ │  │ [Choose File]    │  │ Enter text here...            │  │ │
│ │  │                  │  │                               │  │ │
│ │  │ Select Columns:  │  │ ☐ Fast Mode (NER disabled)    │  │ │
│ │  │ ☐ Description    │  │                               │  │ │
│ │  │ ☐ Solution       │  │ [REDACT TEXT]                 │  │ │
│ │  │                  │  │                               │  │ │
│ │  │ [PROCESS FILE]   │  │ Output:                       │  │ │
│ │  └──────────────────┘  │ Contact [EMAIL] at [PHONE]    │  │ │
│ │                        └───────────────────────────────┘  │ │
│ └───────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

## Detailed Steps: Text Redaction

### Step 1: User Enters Text
```
User types in the text area:
"Contact John Smith at john@company.com or call +91 98765 43210"
```

### Step 2: Click "Redact Text" Button
```javascript
// Frontend JavaScript (in index.html)
async function redactText() {
    const response = await fetch('/api/redact-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text: inputText,
            fast_mode: isFastMode
        })
    });
}
```

### Step 3: Request Hits Web Service
```
POST /api/redact-text
Host: localhost:8082
Content-Type: application/json

{
    "text": "Contact John Smith at john@company.com or call +91 98765 43210",
    "fast_mode": false
}
```

### Step 4: Web Service Processes Request
```python
# web_service/app.py - Line 224-265

@app.post("/api/redact-text", response_model=TextRedactResponse)
async def redact_text(request: Request, body: TextRedactRequest):
    # 1. Validate input
    is_valid, error = InputValidator.validate_text_for_processing(body.text)
    
    # 2. Create PIRemover with config
    config = PIRemoverConfig(
        enable_ner=not body.fast_mode,  # NER ON if not fast mode
        use_typed_tokens=True
    )
    remover = PIRemover(config)
    
    # 3. Process text
    result = remover.redact_with_details(body.text)
    
    # 4. Audit log
    AuditLogger.log_request(request, {...}, "redact_text", {...})
    
    # 5. Return response
    return TextRedactResponse(
        redacted_text=result.redacted_text,
        processing_time_ms=processing_time,
        redaction_count=result.redacted_count
    )
```

### Step 5: Core PI Remover Executes
```python
# src/pi_remover/remover.py - PIRemover.redact() method

def redact(self, text: str) -> str:
    # Layer 1: Data Cleaning
    text = DataCleaner.clean(text)
    
    # Layer 2: Regex Patterns (from patterns.py)
    all_positions = []
    all_positions.extend(self._redact_emails(text))      # EMAIL pattern
    all_positions.extend(self._redact_phones(text))       # PHONE patterns
    all_positions.extend(self._redact_emp_ids(text))      # EMP_ID patterns
    # ... more patterns ...
    
    # Layer 3: NER (if enabled, from ner.py)
    if self.config.enable_ner:
        entities = self.ner.extract_entities(text)
        for ent in entities:
            if ent.label_ == "PERSON":
                all_positions.append(...)
    
    # Layer 4: Dictionary-based Names (from dictionaries.py)
    for match in name_pattern.finditer(text):
        if match in self._all_names:
            all_positions.append(...)
    
    # Layer 5: Apply redactions
    result = self._redact_by_positions(text, all_positions)
    
    return result
```

### Step 6: Response Returned to Browser
```json
{
    "redacted_text": "Contact [NAME] at [EMAIL] or call [PHONE]",
    "processing_time_ms": 12.345,
    "redaction_count": 3
}
```

### Step 7: UI Updates
```
┌─────────────────────────────────────────────┐
│ Output:                                      │
│ Contact [NAME] at [EMAIL] or call [PHONE]   │
│                                              │
│ ✓ 3 items redacted in 12.35ms               │
└─────────────────────────────────────────────┘
```

---

## Detailed Steps: File Upload & Processing

### Step 1: User Uploads File
```
User clicks "Choose File" and selects: data.csv
```

### Step 2: File Upload Request
```
POST /api/upload
Content-Type: multipart/form-data

file: data.csv (binary)
```

### Step 3: Upload Endpoint Processes
```python
# web_service/app.py - Line 292-387

@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile):
    # 1. Validate filename (path traversal check)
    is_valid, error = InputValidator.validate_filename(file.filename)
    
    # 2. Check file extension
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:  # {.csv, .xlsx, .xls, .json, .txt}
        raise HTTPException(400, "File type not supported")
    
    # 3. Generate secure job ID
    job_id = secrets.token_hex(16)  # e.g., "a1b2c3d4e5f6..."
    
    # 4. Create isolated directory
    upload_dir = Path(UPLOAD_DIR) / "pi_remover" / job_id
    upload_dir.mkdir(parents=True)
    
    # 5. Save file with size limit check
    file_size = 0
    with open(file_path, "wb") as buffer:
        while chunk := await file.read(8192):
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE:  # 500MB
                raise HTTPException(413, "File too large")
            buffer.write(chunk)
    
    # 6. Validate file (MIME type, magic bytes)
    is_valid, error = FileSecurityValidator.validate_file(...)
    
    # 7. Get columns from file
    columns = get_file_columns(str(file_path))
    
    # 8. Store job in memory
    jobs[job_id] = {
        "job_id": job_id,
        "status": "uploaded",
        "input_file": str(file_path),
        "columns": columns,
        ...
    }
    
    # 9. Return job info
    return {
        "job_id": "a1b2c3d4e5f6...",
        "filename": "data.csv",
        "columns": ["Description", "Solution", "Notes"]
    }
```

### Step 4: UI Shows Column Selection
```
┌─────────────────────────────────────────────┐
│ File: data.csv                              │
│                                              │
│ Select columns to process:                  │
│ ☑ Description                               │
│ ☑ Solution                                  │
│ ☐ Notes                                      │
│                                              │
│ ☐ Fast Mode (faster, less accurate)         │
│                                              │
│ [PROCESS FILE]                              │
└─────────────────────────────────────────────┘
```

### Step 5: User Clicks "Process File"
```
POST /api/process/{job_id}
Content-Type: application/x-www-form-urlencoded

columns=Description&columns=Solution&fast_mode=false
```

### Step 6: Background Processing Starts
```python
# web_service/app.py - Line 389-428

@app.post("/api/process/{job_id}")
async def process_uploaded_file(job_id, background_tasks, columns, fast_mode):
    # 1. Verify job exists
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    # 2. Update status
    job["status"] = "processing"
    
    # 3. Start background task
    background_tasks.add_task(
        process_file_background,
        job_id, input_file, columns, fast_mode
    )
    
    return {"job_id": job_id, "status": "processing"}


async def process_file_background(job_id, input_file, columns, fast_mode):
    # 1. Configure remover
    config = PIRemoverConfig(enable_ner=not fast_mode)
    
    # 2. Process file (uses src/pi_remover/processors/)
    process_file(
        input_path,
        output_path,   # data_cleaned.csv
        columns,
        config
    )
    
    # 3. Update job status
    job["status"] = "completed"
    job["output_file"] = str(output_path)
```

### Step 7: File Processing (Processors)
```python
# src/pi_remover/processors/csv_processor.py

def process_file(input_path, output_path, columns, config):
    # 1. Load file
    if ext == '.csv':
        df = pd.read_csv(input_path)
    elif ext in {'.xlsx', '.xls'}:
        df = pd.read_excel(input_path)
    
    # 2. Process each column
    remover = PIRemover(config)
    for col in columns:
        new_col = f"{col}_cleaned"
        df[new_col] = df[col].apply(
            lambda x: remover.redact(str(x)) if pd.notna(x) else x
        )
    
    # 3. Save output
    df.to_csv(output_path, index=False)
```

### Step 8: UI Polls for Status
```javascript
// Poll every 2 seconds
const interval = setInterval(async () => {
    const response = await fetch(`/api/status/${jobId}`);
    const status = await response.json();
    
    updateProgressBar(status.progress);
    
    if (status.status === 'completed') {
        clearInterval(interval);
        showDownloadButton();
    }
}, 2000);
```

### Step 9: Download Processed File
```
GET /api/download/{job_id}

Response: data_cleaned.csv (file download)
```

---

# Complete Flow: API

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           API FLOW                                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   LLM Client    │ (e.g., Python script calling Claude/GPT)
└────────┬────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ STEP 1: Obtain JWT Token                                                    │
│                                                                             │
│ POST /dev/auth/token                                                        │
│ {                                                                           │
│     "client_id": "pi-dev-client",                                          │
│     "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"         │
│ }                                                                           │
│                                                                             │
│ Response:                                                                   │
│ {                                                                           │
│     "access_token": "eyJhbGciOiJIUzI1NiIs...",                             │
│     "token_type": "bearer",                                                 │
│     "expires_in": 1800                                                      │
│ }                                                                           │
└────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ STEP 2: Call Redaction Endpoint                                             │
│                                                                             │
│ POST /dev/v1/redact                                                         │
│ Authorization: Bearer eyJhbGciOiJIUzI1NiIs...                              │
│ {                                                                           │
│     "text": "Contact john@company.com for help",                           │
│     "include_details": true                                                 │
│ }                                                                           │
│                                                                             │
│ Response:                                                                   │
│ {                                                                           │
│     "redacted_text": "Contact [EMAIL] for help",                           │
│     "request_id": "abc123",                                                 │
│     "processing_time_ms": 5.2,                                              │
│     "redactions": [                                                         │
│         {"original": "john@company.com", "type": "EMAIL", ...}             │
│     ]                                                                       │
│ }                                                                           │
└────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│ STEP 3: Send Clean Data to LLM                                              │
│                                                                             │
│ POST https://api.anthropic.com/v1/messages                                  │
│ {                                                                           │
│     "model": "claude-3",                                                    │
│     "messages": [{"role": "user", "content": "Contact [EMAIL] for help"}]  │
│ }                                                                           │
│                                                                             │
│ ✓ No PI leaked to LLM!                                                      │
└────────────────────────────────────────────────────────────────────────────┘
```

## Detailed Steps: API Authentication

### Step 1: Client Sends Credentials
```
POST /dev/auth/token
Host: localhost:8080
Content-Type: application/json

{
    "client_id": "pi-dev-client",
    "client_secret": "YOUR_DEV_CLIENT_SECRET_HERE"
}
```

### Step 2: API Validates Credentials
```python
# api_service/app.py - Token endpoint

@app.post(f"{API_PREFIX}/auth/token")
async def obtain_token(request: Request, body: AuthRequest):
    # 1. Audit log (without secret)
    AuditLogger.log_request(request, {...}, "token_request", {...})
    
    # 2. Generate token
    token_response = generate_auth_token(body.client_id, body.client_secret)
    
    if not token_response:
        raise HTTPException(401, "Invalid client credentials")
    
    return token_response
```

### Step 3: Security Module Validates & Generates JWT
```python
# security.py - generate_auth_token()

def generate_auth_token(client_id: str, client_secret: str) -> Optional[TokenResponse]:
    # 1. Look up client
    if client_id not in SecurityConfig.CLIENTS:
        return None
    
    client = SecurityConfig.CLIENTS[client_id]
    
    # 2. Verify secret (constant-time comparison)
    if not secrets.compare_digest(client["secret"], client_secret):
        return None
    
    # 3. Create JWT payload
    now = datetime.now(timezone.utc)
    payload = {
        "sub": client_id,
        "iat": now,
        "exp": now + timedelta(minutes=30),
        "jti": secrets.token_hex(16)
    }
    
    # 4. Encode JWT
    token = jwt.encode(payload, SecurityConfig.JWT_SECRET_KEY, algorithm="HS256")
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=1800
    )
```

### Step 4: Client Receives Token
```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwaS1kZXYtY2xpZW50IiwiaWF0IjoxNzAyNDUxMjAwLCJleHAiOjE3MDI0NTMwMDAsImp0aSI6ImFiYzEyMyJ9.xxx",
    "token_type": "bearer",
    "expires_in": 1800
}
```

## Detailed Steps: API Redaction

### Step 1: Client Sends Authenticated Request
```
POST /dev/v1/redact
Host: localhost:8080
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
    "text": "Contact john.smith@company.com or call +91 98765 43210",
    "include_details": true
}
```

### Step 2: Security Middleware Validates Token
```python
# security.py - verify_bearer_token()

async def verify_bearer_token(credentials: HTTPAuthorizationCredentials):
    token = credentials.credentials
    
    try:
        # 1. Decode and verify JWT
        payload = jwt.decode(
            token,
            SecurityConfig.JWT_SECRET_KEY,
            algorithms=["HS256"]
        )
        
        # 2. Check expiration
        exp = payload.get("exp")
        if datetime.fromtimestamp(exp, timezone.utc) < datetime.now(timezone.utc):
            raise HTTPException(401, "Token expired")
        
        # 3. Return auth info
        return {
            "client_id": payload["sub"],
            "authenticated": True
        }
        
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
```

### Step 3: Rate Limiter Checks
```python
# security.py - RateLimiter middleware

class RateLimiter:
    def check_rate_limit(self, client_id: str, client_ip: str):
        key = f"{client_id}:{client_ip}"
        
        # Check requests in window
        if self.requests[key] >= SecurityConfig.RATE_LIMIT_REQUESTS:
            raise HTTPException(429, "Rate limit exceeded")
        
        # Increment counter
        self.requests[key] += 1
```

### Step 4: Request Validation
```python
# api_service/app.py - Pydantic model

class RedactRequest(BaseModel):
    text: str = Field(..., max_length=100000)  # 100KB limit
    
    @validator('text')
    def validate_text(cls, v):
        is_valid, error = InputValidator.validate_text_for_processing(v)
        if not is_valid:
            raise ValueError(error)
        return v
```

### Step 5: Redaction Endpoint Processes
```python
# api_service/app.py - Line 382-450

@app.post(f"{API_PREFIX}/v1/redact")
async def redact_text(
    request: Request,
    body: RedactRequest,
    auth_info: Dict = Depends(verify_bearer_token)  # Token verified here
):
    request_id = body.request_id or str(uuid.uuid4())
    
    # Process with details
    result = remover.redact_with_details(body.text)
    
    # Audit log with PI types
    redaction_counts = {}
    for r in result.redactions:
        redaction_counts[r.pi_type] = redaction_counts.get(r.pi_type, 0) + 1
    
    AuditLogger.log_request(
        request, auth_info, "redact_single",
        {"text_length": len(body.text)},
        redactions=redaction_counts
    )
    
    # Record metrics
    metrics.record_request(result.processing_time_ms)
    
    return RedactResponse(
        redacted_text=result.redacted_text,
        request_id=request_id,
        processing_time_ms=result.processing_time_ms,
        redactions=[...]
    )
```

### Step 6: Response Returned
```json
{
    "redacted_text": "Contact [EMAIL] or call [PHONE]",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "processing_time_ms": 8.234,
    "redactions": [
        {
            "original": "john.smith@company.com",
            "replacement": "[EMAIL]",
            "type": "EMAIL",
            "start": 8,
            "end": 30,
            "confidence": 1.0,
            "method": "regex"
        },
        {
            "original": "+91 98765 43210",
            "replacement": "[PHONE]",
            "type": "PHONE",
            "start": 39,
            "end": 54,
            "confidence": 1.0,
            "method": "regex"
        }
    ]
}
```

---

# Folder Structure

## Root Directory (v2.12.0)

```
PI_Removal/
│
├── api_service/              # REST API Gateway (main processing)
├── config/                   # YAML configuration files
├── docker/                   # Docker configurations
├── docs/                     # Documentation
├── scripts/                  # Deployment & test scripts
├── shared/                   # Common infrastructure
├── src/                      # Main source code (modular v2.12.0)
├── tests/                    # Test files (61 tests pass)
├── web_service/              # Web UI service (calls API)
├── others/                   # Non-essential/archived files
│
├── config.yaml               # PI Removal patterns configuration
├── pyproject.toml            # Python project config
├── README.md                 # Project readme
├── requirements.txt          # Python dependencies
├── CHANGELOG.md              # Version history
└── SECURITY.md               # Security documentation
```

## Detailed Structure

```
PI_Removal/
│
├── api_service/                    # ══════ REST API SERVICE ══════
│   ├── app.py                      # Main FastAPI application
│   ├── Dockerfile                  # Container definition
│   ├── docker-compose.yml          # Local compose file
│   ├── requirements.txt            # API-specific dependencies
│   └── README.md                   # API documentation
│
├── config/                         # ══════ YAML CONFIGURATION ══════
│   ├── api_service.yaml            # API service settings (host, port, CORS)
│   ├── web_service.yaml            # Web service settings + API URL
│   ├── clients.yaml                # JWT client credentials & rate limits
│   ├── redis.yaml                  # Redis connection settings
│   └── logging.yaml                # Structured logging configuration
│
├── docker/                         # ══════ DOCKER CONFIGS ══════
│   ├── docker-compose.base.yml     # Base configuration
│   ├── docker-compose.dev.yml      # DEV environment (ports 8080, 8082)
│   └── docker-compose.prod.yml     # PROD environment (ports 9080, 9082)
│
├── docs/                           # ══════ DOCUMENTATION ══════
│   ├── ARCHITECTURE.md             # System architecture (modular microservices)
│   ├── API_REFERENCE.md            # Complete API reference
│   ├── DEPLOYMENT.md               # Deployment guide
│   ├── SECURITY.md                 # Security documentation
│   ├── TROUBLESHOOTING.md          # Troubleshooting guide
│   ├── CHAT_SERVICE.md             # Chat integration guide
│   ├── DEVOPS_STRATEGY.md          # DevOps deployment strategy
│   ├── GOOGLE_CLOUD.md             # GCP deployment guide
│   └── MEMORY.md                   # Project memory/context
│
├── scripts/                        # ══════ DEPLOYMENT & TEST SCRIPTS ══════
│   ├── run_comprehensive_tests.ps1 # Full test runner (Windows)
│   ├── run_comprehensive_tests.sh  # Full test runner (Linux)
│   ├── test_components.py          # Component tests (no services needed)
│   ├── deploy-dev.ps1/.sh          # Deploy to DEV
│   ├── deploy-prod.ps1/.sh         # Deploy to PROD
│   └── promote-to-prod.ps1/.sh     # Promote DEV to PROD
│
├── shared/                         # ══════ SHARED INFRASTRUCTURE ══════
│   ├── __init__.py                 # Package exports
│   ├── config_loader.py            # Load YAML configs (no env vars!)
│   ├── logging_config.py           # Structured JSON logging
│   └── redis_client.py             # Redis + InMemoryFallback
│
├── src/                            # ══════ MAIN SOURCE CODE ══════
│   └── pi_remover/                 # 🔄 Modular architecture (v2.12.0)
│       ├── __init__.py             # Package exports
│       ├── __main__.py             # CLI entry point
│       ├── core.py                 # Facade module (re-exports for backward compat)
│       ├── config.py               # PIRemoverConfig, YAML loading
│       ├── patterns.py             # PIPatterns (125+ regex patterns)
│       ├── dictionaries.py         # Name dictionaries
│       ├── data_classes.py         # Redaction, RedactionResult
│       ├── utils.py                # Logging, multiprocessing
│       ├── ner.py                  # SpacyNER, SpacyModelManager
│       ├── remover.py              # Main PIRemover class
│       ├── sanitizer.py            # Input sanitization
│       ├── security.py             # Security module
│       ├── model_manager.py        # Thread-safe spaCy model management
│       └── processors/             # File processors
│           └── __init__.py         # CSV, JSON, TXT, DataFrame
│
├── tests/                          # ══════ TEST FILES ══════
│   ├── __init__.py                 # Test package
│   ├── test_api.py                 # API endpoint tests
│   ├── test_comprehensive_pi.py    # Comprehensive PI tests
│   ├── test_edge_cases.py          # Edge case tests
│   ├── test_service_integration.py # Microservices integration tests
│   └── test_remover.py             # Core remover tests
│
├── web_service/                    # ══════ WEB UI SERVICE ══════
│   ├── app.py                      # Hybrid mode (API + local fallback)
│   ├── api_client.py               # HTTP client with circuit breaker
│   ├── Dockerfile                  # Container definition
│   ├── docker-compose.yml          # Local compose file
│   ├── requirements.txt            # Web-specific dependencies (+ httpx)
│   ├── static/                     # Static assets (CSS, JS)
│   └── templates/
│       └── index.html              # Main UI template
│
├── others/                         # ══════ NON-ESSENTIAL FILES ══════
│   ├── standalone/
│   │   ├── pi_remover_standalone.py  # Single-file for ad-hoc use
│   │   └── README.md                  # Standalone usage guide
│   ├── examples/                    # Sample data files
│   ├── misc/                        # Miscellaneous files
│   ├── logs/                        # Log files
│   ├── output/                      # Output files
│   └── CREDENTIALS.txt              # Credentials reference
│
├── config.yaml                      # PI removal patterns configuration
├── pyproject.toml                   # Python project configuration
├── README.md                        # Project readme
├── requirements.txt                 # Root dependencies
├── security.py                      # Root security module
├── HOWTO.md                         # Complete how-to guide
└── FILE_AND_FLOW.MD                 # This file
```

---

# File Responsibilities

## Core Files (v2.12.0 Modular Architecture)

The PI removal engine was refactored from a single monolithic `core.py` into modular files:

### `src/pi_remover/` Directory Structure

| File | Lines | Purpose |
|------|-------|---------|
| `patterns.py` | 656 | `PIPatterns` class - **125+ compiled regex patterns** |
| `remover.py` | 1047 | `PIRemover` class - main redaction logic, `_redact_*()` methods |
| `config.py` | 274 | `PIRemoverConfig` dataclass - all configuration options |
| `dictionaries.py` | 162 | Name lists (Indian names, companies, internal systems) |
| `data_classes.py` | 282 | `Redaction`, `RedactionResult`, `RedactionStats` classes |
| `ner.py` | 195 | `SpacyNER` class - spaCy NER wrapper |
| `sanitizer.py` | 499 | `DataCleaner` - text preprocessing (Unicode, HTML) |
| `utils.py` | varies | Utilities, multiprocessing support |
| `core.py` | 240 | **Facade module** - re-exports for backward compatibility |
| `__init__.py` | 81 | Package exports |

### Key Classes & Methods

```python
# All imports work via facade pattern:
from src.pi_remover import PIRemover, PIRemoverConfig

class PIRemover:  # In remover.py
    def redact(text) -> str                    # Simple redaction
    def redact_with_details(text) -> RedactionResult  # Detailed redaction
    def redact_batch(texts) -> List[str]       # Batch processing
    def health_check() -> Dict                  # Health status

class PIPatterns:  # In patterns.py
    EMAIL = re.compile(...)
    PHONE_INDIAN = re.compile(...)
    # 125+ patterns for emails, phones, IDs, IT/ITSM, cloud, security, etc.
```

### Where to Make Changes

| Task | File to Edit |
|------|-------------|
| Add new regex pattern | `src/pi_remover/patterns.py` |
| Add detection method | `src/pi_remover/remover.py` |
| Add blocklist words | `src/pi_remover/remover.py` |
| Add config option | `src/pi_remover/config.py` |
| Add name dictionary | `src/pi_remover/dictionaries.py` |

---

### `src/pi_remover/security.py` (1176 lines)
**Purpose:** Centralized security controls for all services

**Key Components:**
| Component | Lines | Description |
|-----------|-------|-------------|
| `SecurityConfig` | 45-200 | All security configuration |
| `generate_auth_token()` | 300-350 | JWT token generation |
| `verify_bearer_token()` | 350-420 | Token validation dependency |
| `RateLimiter` | 500-600 | Rate limiting middleware |
| `InputValidator` | 700-800 | Input validation utilities |
| `FileSecurityValidator` | 800-900 | File upload security |
| `AuditLogger` | 900-1000 | Audit logging |
| `setup_security()` | 1000-1073 | Middleware setup function |

**Credentials (v2.9.0 - moved to YAML):**
Now configured in `config/clients.yaml` instead of hardcoded.

---

## Shared Infrastructure

### `shared/config_loader.py`
**Purpose:** Load all YAML configuration files

**Key Functions:**
```python
def load_config(config_name: str) -> dict:
    """Load a YAML config file from config/ directory."""
    # Example: load_config("api_service") → loads config/api_service.yaml
    
def get_config(config_name: str) -> dict:
    """Get config with caching (loaded once, reused)."""
```

**Usage Example:**
```python
from shared.config_loader import get_config

# Load API service configuration
api_config = get_config("api_service")
host = api_config["server"]["host"]  # "0.0.0.0"
port = api_config["server"]["port"]  # 8080
```

---

### `shared/logging_config.py`
**Purpose:** Structured JSON logging for ELK/Splunk

**Key Functions:**
```python
def setup_logging(service_name: str) -> logging.Logger:
    """Configure JSON logging with correlation IDs."""
```

**Log Format:**
```json
{
  "timestamp": "2025-01-15T10:30:45.123Z",
  "level": "INFO",
  "service": "api_service",
  "correlation_id": "abc123",
  "message": "Request processed",
  "extra": {"processing_time_ms": 12.5}
}
```

---

### `shared/redis_client.py`
**Purpose:** Redis connection with graceful fallback

**Key Classes:**
```python
class RedisClient:
    """Redis connection with automatic reconnection."""
    
class InMemoryFallback:
    """In-memory rate limiting when Redis is unavailable."""
    async def check_rate_limit(client_id: str, limit: int, window: int) -> bool
    async def increment(key: str, window: int) -> int
```

**Fallback Behavior:**
```
1. Try Redis connection
2. If Redis unavailable → Use InMemoryFallback
3. Log warning: "Redis unavailable, using in-memory fallback"
4. Rate limiting continues to work (per-instance)
```

---

## Configuration Files

### `config/api_service.yaml`
**Purpose:** API service settings

```yaml
server:
  host: "0.0.0.0"
  port: 8080
  environment: "development"

pi_remover:
  enable_ner: false  # NER disabled by default (faster)
  use_typed_tokens: true
  default_token: "[REDACTED]"

cors:
  allowed_origins:
    - "http://localhost:8082"
    - "http://localhost:3000"

security:
  jwt_algorithm: "HS256"
  token_expiry_minutes: 30
```

---

### `config/web_service.yaml`
**Purpose:** Web service + API connection settings

```yaml
server:
  host: "0.0.0.0"
  port: 8082
  environment: "development"

api:
  base_url: "http://localhost:8080"  # ← API service URL
  timeout_seconds: 30
  
circuit_breaker:
  failure_threshold: 5     # Open after 5 failures
  recovery_timeout: 30     # Try again after 30 seconds
  half_open_requests: 3    # Allow 3 test requests
```

---

### `config/clients.yaml`
**Purpose:** JWT client credentials and rate limits

```yaml
clients:
  pi-dev-client:
    secret: "YOUR_DEV_CLIENT_SECRET_HERE"
    rate_limit: 1000     # requests per minute
    environment: "development"
    
  # pi-prod-client:  # Uncomment and configure for production
  #   secret: "<generate-unique-secret>"
  #   rate_limit: 10000
  #   environment: "production"
    
  pi-internal-web-service:  # ← Web service uses this!
    secret: "YOUR_WEB_CLIENT_SECRET_HERE"
    rate_limit: 10000
    environment: "internal"

jwt:
  secret_key: "YOUR_DEV_JWT_SECRET_HERE"
  algorithm: "HS256"
  expiry_minutes: 30
```

---

### `config/redis.yaml`
**Purpose:** Redis connection settings

```yaml
redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null  # Set for production
  
  pool:
    max_connections: 10
    
  timeouts:
    connect: 5
    read: 5
```

---

### `config/logging.yaml`
**Purpose:** Logging configuration

```yaml
logging:
  level: "INFO"
  format: "json"  # or "text" for development
  
  handlers:
    - type: "console"
    - type: "file"
      path: "logs/app.log"
      
  elk:
    enabled: false
    host: "localhost"
    port: 5044
```

---

## Web Service API Client

### `web_service/api_client.py`
**Purpose:** HTTP client with circuit breaker for calling API service

**Key Classes:**
```python
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Open after 5 failures
    recovery_timeout: int = 30      # Seconds before retry
    half_open_requests: int = 3     # Test requests in half-open

class CircuitBreaker:
    """Prevents cascading failures when API is down."""
    
class PIRemoverAPIClient:
    """HTTP client for Web → API communication."""
    
    async def redact_text(text: str, include_details: bool = False) -> dict
    async def health_check() -> dict
```

**Circuit Breaker States:**
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

---

### `web_service/app.py`
**Purpose:** Web service with hybrid mode (API + local fallback)

**Key Features:**
```python
# Hybrid mode - API first, local fallback
api_client = PIRemoverAPIClient(config)
result = await api_client.redact_text(text)  # Tries API first
# If API unavailable, automatic fallback to local PIRemover
```

**Startup Modes:**
| Mode | Command | Behavior |
|------|---------|----------|
| Hybrid | `uvicorn app:app` | API first, local fallback |
| Standalone | `python app.py --standalone` | Always uses local PIRemover |

---

## Service Files

### `api_service/app.py`
**Purpose:** REST API Gateway for programmatic access

**Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/dev/auth/token` | POST | Obtain JWT token |
| `/dev/v1/redact` | POST | Single text redaction |
| `/dev/v1/redact/batch` | POST | Batch text redaction |
| `/dev/health` | GET | Health check |
| `/dev/v1/pi-types` | GET | List PI types |
| `/` | GET | Root info |

**Key Components:**
```python
# Global PI Remover instance (initialized once at startup)
remover = PIRemover(config)

# Metrics tracking
metrics = Metrics()

# Environment-based prefix
API_PREFIX = "/dev" if ENVIRONMENT == "development" else "/prod"
```

---

### `web_service/app.py` (standalone mode)
**Purpose:** Web UI for interactive file/text processing (self-contained)

**Endpoints:**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve HTML UI |
| `/api/redact-text` | POST | Redact text input |
| `/api/upload` | POST | Upload file |
| `/api/process/{job_id}` | POST | Start processing |
| `/api/status/{job_id}` | GET | Get job status |
| `/api/download/{job_id}` | GET | Download result |
| `/api/job/{job_id}` | DELETE | Delete job |
| `/health` | GET | Health check |

---

### `web_service/templates/index.html`
**Purpose:** Complete web UI with modern design

**Sections:**
| Section | Lines | Description |
|---------|-------|-------------|
| CSS Styles | 1-400 | Dark/light theme, responsive design |
| Header | 400-450 | Logo, theme toggle |
| Tab Navigation | 450-500 | File Upload / Text Input tabs |
| File Upload UI | 500-650 | Drag-drop, column selection |
| Text Input UI | 650-750 | Text area, fast mode toggle |
| Results Display | 750-850 | Output display, download button |
| JavaScript | 850-1411 | All interactivity logic |
  names: true
  emails: true
  phones: true
  # ... etc

tokens:
  default: "[REDACTED]"
  use_typed: true

performance:
  multiprocessing: true
  batch_size: 5000
```

---

# Configuration System

## How Configuration Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONFIGURATION LOADING                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. Application starts                                                       │
│  2. shared/config_loader.py finds config/ directory                        │
│  3. Loads required YAML files                                                │
│  4. Caches configuration (load once, use many)                              │
│  5. No environment variables needed!                                         │
│                                                                              │
│  config/                                                                     │
│  ├── api_service.yaml ──────▶ API host, port, CORS                         │
│  ├── web_service.yaml ──────▶ Web host, port, API URL                      │
│  ├── clients.yaml ──────────▶ JWT secrets, rate limits                     │
│  ├── redis.yaml ────────────▶ Redis connection                             │
│  └── logging.yaml ──────────▶ Log format, level                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## How to Change Configuration

### Change API Port
```yaml
# config/api_service.yaml
server:
  port: 9000  # Changed from 8080
```

### Change Rate Limits
```yaml
# config/clients.yaml
clients:
  pi-dev-client:
    rate_limit: 2000  # Changed from 1000
```

### Change Circuit Breaker Settings
```yaml
# config/web_service.yaml
circuit_breaker:
  failure_threshold: 10   # More tolerant (was 5)
  recovery_timeout: 60    # Wait longer (was 30)
```

### Add New Client
```yaml
# config/clients.yaml
clients:
  # ... existing clients ...
  
  my-new-client:
    secret: "generate-a-secure-secret-here"
    rate_limit: 500
    environment: "development"
```

### Enable Redis Password
```yaml
# config/redis.yaml
redis:
  password: "your-secure-password"
```

---

# Quick Reference

## Architecture Summary (v2.12.0)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  USER ─────▶ WEB SERVICE (8082) ────HTTP+JWT────▶ API SERVICE (8080)       │
│                     │                                    │                   │
│              ┌──────┴──────┐                     ┌───────┴───────┐          │
│              │ api_client  │                     │  PIRemover    │          │
│              │ + circuit   │                     │  (modular)    │          │
│              │   breaker   │                     │  + security   │          │
│              └─────────────┘                     └───────────────┘          │
│                                                         │                    │
│                                                         ▼                    │
│                                                      REDIS                   │
│                                                   (optional)                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## API Endpoints Summary

| Environment | Base URL | Port |
|-------------|----------|------|
| DEV | `http://localhost:8080/dev` | 8080 |
| PROD | `http://localhost:9080/prod` | 9080 |

### Authentication
```bash
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}'
```

### Redaction
```bash
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text":"john@email.com","include_details":true}'
```

## Web UI URLs

| Environment | URL | Port |
|-------------|-----|------|
| DEV | `http://localhost:8082` | 8082 |
| PROD | `http://localhost:9082` | 9082 |

## Docker Commands

```bash
# Start DEV
docker-compose -f docker/docker-compose.dev.yml up -d

# Start PROD  
docker-compose -f docker/docker-compose.prod.yml up -d

# View logs
docker-compose -f docker/docker-compose.dev.yml logs -f
```

## Manual Service Startup (v2.12.0)

```powershell
# Terminal 1: Redis (optional)
docker run --rm -p 6379:6379 redis:alpine

# Terminal 2: API Service
cd api_service
uvicorn app:app --reload --port 8080

# Terminal 3: Web Service (hybrid mode)
cd web_service
uvicorn app:app --reload --port 8082
```

## Test Commands (v2.12.0)

```powershell
# Run comprehensive tests (starts all services)
.\scripts\run_comprehensive_tests.ps1

# Run component tests only (no services needed)
python scripts\test_components.py

# Run with services already running
python scripts\test_components.py --with-services
```

## Standalone Usage

```bash
cd others/standalone
python pi_remover_standalone.py -i data.csv -c "Description" "Solution"
```

---

## Data Flow Summary

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        PI REMOVAL PIPELINE                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  INPUT TEXT                                                               │
│     │                                                                     │
│     ▼                                                                     │
│  ┌─────────────────┐                                                     │
│  │ 1. DATA CLEANER │ → Normalize Unicode, decode HTML, fix whitespace   │
│  └────────┬────────┘                                                     │
│           │                                                               │
│           ▼                                                               │
│  ┌─────────────────┐                                                     │
│  │ 2. REGEX ENGINE │ → 30+ patterns for email, phone, IP, IDs, etc.    │
│  └────────┬────────┘                                                     │
│           │                                                               │
│           ▼                                                               │
│  ┌─────────────────┐                                                     │
│  │ 3. NER ENGINE   │ → spaCy model detects PERSON, ORG, GPE, LOC       │
│  └────────┬────────┘   (optional, disabled in FAST mode)                │
│           │                                                               │
│           ▼                                                               │
│  ┌─────────────────┐                                                     │
│  │ 4. DICTIONARIES │ → 500+ Indian names, surnames, companies           │
│  └────────┬────────┘                                                     │
│           │                                                               │
│           ▼                                                               │
│  ┌─────────────────┐                                                     │
│  │ 5. MERGE & APPLY│ → Remove overlaps, apply redactions               │
│  └────────┬────────┘                                                     │
│           │                                                               │
│           ▼                                                               │
│  OUTPUT TEXT: "Contact [NAME] at [EMAIL] or [PHONE]"                    │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Key Changes Summary

| Version | Key Change |
|---------|------------|
| v2.8.x → v2.9.0 | Monolith → Microservices architecture |
| v2.9.0 → v2.12.0 | Monolithic `core.py` → Modular architecture (9 files) |

### v2.12.0 Modular Architecture

| Old (v2.8.x) | New (v2.12.0) | Purpose |
|--------------|---------------|---------|
| `core.py` (2500+ lines) | `patterns.py` | 125+ regex patterns |
| | `remover.py` | PIRemover class, `_redact_*()` methods |
| | `config.py` | PIRemoverConfig dataclass |
| | `dictionaries.py` | Name dictionaries |
| | `ner.py` | SpacyNER class |
| | `data_classes.py` | Redaction, RedactionResult |
| | `core.py` (facade) | Re-exports for backward compatibility |

---

*Document Version: 4.0*  
*Last Updated: December 2025*  
*v2.12.0: Modular architecture, hybrid mode consolidation (app.py)*
