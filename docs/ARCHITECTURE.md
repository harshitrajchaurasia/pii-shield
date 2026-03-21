# PI Remover - Hybrid Microservices Architecture

> Enterprise-grade architecture for Personal Information redaction services.
> 
> **Architecture Version:** 2.13.2 | **PIRemover Core:** v2.13.2 | **Last Updated:** December 2025

## Table of Contents

- [Overview](#overview)
- [Architecture Diagram](#architecture-diagram)
- [Hybrid Mode](#hybrid-mode)
- [Service Components](#service-components)
- [Redaction Priority Layer Architecture](#redaction-priority-layer-architecture)
- [PI Type Dependency Graph](#pi-type-dependency-graph)
- [Communication Flow](#communication-flow)
- [Resilience Patterns](#resilience-patterns)
- [Configuration Files](#configuration-files)
- [Docker Deployment](#docker-deployment)
- [Health Checks](#health-checks)
- [Logging](#logging)
- [Security](#security)
- [Scaling](#scaling)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Service Startup Options](#service-startup-options)
- [Quick Reference](#quick-reference)

---

## Overview

The PI Remover system uses a **Hybrid Microservices Architecture** with automatic local fallback. This design provides:

- **High Availability**: Automatic fallback to local processing if API is unavailable
- **Separation of Concerns**: API logic separate from web UI
- **Independent Scaling**: Scale each service based on demand
- **Service Isolation**: Failures are contained within service boundaries
- **Technology Flexibility**: Each service can evolve independently
- **Enterprise Integration**: Centralized logging, shared rate limiting

## Architecture Diagram

```
                                    ┌─────────────────────────────────────────┐
                                    │           Load Balancer (L7)            │
                                    │         (nginx / Cloud LB)              │
                                    └────────────────────┬────────────────────┘
                                                         │
                         ┌───────────────────────────────┼───────────────────────────────┐
                         │                               │                               │
                         ▼                               ▼                               ▼
              ┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
              │    Web Service 1    │       │    Web Service 2    │       │    Web Service N    │
              │    (Port 8082)      │       │    (Port 8082)      │       │    (Port 8082)      │
              │  ┌───────────────┐  │       │  ┌───────────────┐  │       │  ┌───────────────┐  │
              │  │  API Client   │  │       │  │  API Client   │  │       │  │  API Client   │  │
              │  │  + Circuit    │  │       │  │  + Circuit    │  │       │  │  + Circuit    │  │
              │  │    Breaker    │  │       │  │    Breaker    │  │       │  │    Breaker    │  │
              │  └───────────────┘  │       │  └───────────────┘  │       │  └───────────────┘  │
              │  ┌───────────────┐  │       │  ┌───────────────┐  │       │  ┌───────────────┐  │
              │  │Local PIRemover│◄─┼───────│──│   FALLBACK    │──┼───────│─▶│Local PIRemover│  │
              │  │  (Fallback)   │  │       │  │               │  │       │  │  (Fallback)   │  │
              │  └───────────────┘  │       │  └───────────────┘  │       │  └───────────────┘  │
              └──────────┬──────────┘       └──────────┬──────────┘       └──────────┬──────────┘
                         │                             │                             │
                         │              HTTP (JWT Auth) - Primary Path               │
                         │                             │                             │
                         └─────────────────────────────┼─────────────────────────────┘
                                                       │
                                         ┌─────────────▼─────────────┐
                                         │   Internal Network        │
                                         │   (pi-internal)           │
                                         └─────────────┬─────────────┘
                                                       │
              ┌────────────────────────────────────────┼────────────────────────────────────────┐
              │                                        │                                        │
              ▼                                        ▼                                        ▼
   ┌─────────────────────┐              ┌─────────────────────┐              ┌─────────────────────┐
   │   API Service 1     │              │   API Service 2     │              │   API Service N     │
   │   (Port 8080)       │              │   (Port 8080)       │              │   (Port 8080)       │
   │  ┌───────────────┐  │              │  ┌───────────────┐  │              │  ┌───────────────┐  │
   │  │  PI Remover   │  │              │  │  PI Remover   │  │              │  │  PI Remover   │  │
   │  │    Core       │  │              │  │    Core       │  │              │  │    Core       │  │
   │  └───────────────┘  │              │  └───────────────┘  │              │  └───────────────┘  │
   │  ┌───────────────┐  │              │  ┌───────────────┐  │              │  ┌───────────────┐  │
   │  │    spaCy      │  │              │  │    spaCy      │  │              │  │    spaCy      │  │
   │  │   NER Model   │  │              │  │   NER Model   │  │              │  │   NER Model   │  │
   │  └───────────────┘  │              │  └───────────────┘  │              │  └───────────────┘  │
   └──────────┬──────────┘              └──────────┬──────────┘              └──────────┬──────────┘
              │                                    │                                    │
              └────────────────────────────────────┼────────────────────────────────────┘
                                                   │
                                      ┌────────────▼────────────┐
                                      │        Redis            │
                                      │   (Rate Limiting)       │
                                      │   (Session Cache)       │
                                      └─────────────────────────┘
                                                   │
                                      ┌────────────▼────────────┐
                                      │   ELK / Splunk          │
                                      │   (Centralized Logs)    │
                                      └─────────────────────────┘
```

---

## Hybrid Mode

The Web Service implements **hybrid mode** with automatic fallback to local processing.

### How It Works

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          HYBRID MODE FLOW                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Request arrives                                                        │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────┐                                        │
│   │  Is --standalone flag set?  │                                        │
│   └─────────────────────────────┘                                        │
│        │                                                                 │
│   ┌────┴────┐                                                            │
│  Yes       No                                                            │
│   │         │                                                            │
│   │         ▼                                                            │
│   │   ┌─────────────────────┐                                            │
│   │   │  Try API Service    │                                            │
│   │   │  (HTTP + JWT)       │                                            │
│   │   └──────────┬──────────┘                                            │
│   │              │                                                       │
│   │        ┌─────┴─────┐                                                 │
│   │        │ API OK?   │                                                 │
│   │        └─────┬─────┘                                                 │
│   │         ┌────┴────┐                                                  │
│   │        Yes       No (timeout/error)                                  │
│   │         │         │                                                  │
│   │         ▼         ▼                                                  │
│   │   ┌───────────┐  ┌────────────────────────┐                          │
│   │   │ Use API   │  │ Use Local PIRemover    │                          │
│   │   │ Response  │  │ (automatic fallback)   │                          │
│   │   └───────────┘  └────────────────────────┘                          │
│   │                           ▲                                          │
│   │                           │                                          │
│   └───────────────────────────┘                                          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Startup Modes

| Mode | File | Command | Behavior |
|------|------|---------|----------|
| **Hybrid** | `app.py` | `uvicorn app:app` | API first, local fallback |
| **Standalone** | `app.py` | `python app.py --standalone` | Always local |

### Benefits

| Scenario | API Running | API Down |
|----------|:-----------:|:--------:|
| **User Experience** | Fast, centralized | No interruption |
| **Logging** | Centralized (ELK) | Local logs only |
| **Rate Limiting** | Redis-based | In-memory |

---

## Service Components

### 1. Web Service (Port 8082)

**Purpose**: User-facing web interface and file upload handling.

**Responsibilities**:
- Serve HTML interface
- Handle file uploads (CSV, TXT, JSON)
- Coordinate with API service for redaction (hybrid mode)
- Local PIRemover fallback when API unavailable
- Session management

**Key Components**:
| Component | Description |
|-----------|-------------|
| `app.py` | FastAPI application (hybrid mode) |
| `api_client.py` | HTTP client for API service |
| `templates/` | HTML templates |
| `static/` | CSS, JS, images |

**Configuration**: `config/web_service.yaml`

### 2. API Service (Port 8080)

**Purpose**: Core PI redaction logic and authentication.

**Responsibilities**:
- JWT token generation and validation
- Text redaction (single and batch)
- NER processing with spaCy
- Rate limiting enforcement

**Key Components**:
| Component | Description |
|-----------|-------------|
| `app.py` | FastAPI application |
| `src/pi_remover/` | Modular PIRemover library (v2.12.0) |
| `security.py` | Authentication logic |

**Configuration**: `config/api_service.yaml`

### 3. PIRemover Core Library (v2.12.0 Modular Architecture)

The PI Remover core has been refactored from a monolithic `core.py` into 9 focused modules:

```
src/pi_remover/
├── __init__.py        # Package exports
├── core.py            # Facade module (re-exports for backward compatibility)
├── config.py          # PIRemoverConfig dataclass, YAML loading
├── patterns.py        # PIPatterns class (125+ regex patterns)
├── dictionaries.py    # Indian names, company names, internal systems
├── data_classes.py    # Redaction, RedactionResult, RedactionStats
├── utils.py           # Logging, multiprocessing, DataCleaner
├── ner.py             # SpacyNER, SpacyModelManager singleton
├── remover.py         # Main PIRemover class
├── sanitizer.py       # Input sanitization (SQL/XSS injection)
├── security.py        # API security helpers
├── model_manager.py   # Thread-safe spaCy model management
└── processors/
    └── __init__.py    # CSV, JSON, TXT, DataFrame processors
```

| Module | Lines | Purpose | Key Exports |
|--------|-------|---------|-------------|
| `config.py` | 274 | Configuration management | `PIRemoverConfig`, `load_config_from_yaml` |
| `patterns.py` | 656 | **125+ PI regex patterns** | `PIPatterns` class |
| `dictionaries.py` | 162 | Name dictionaries | `INDIAN_FIRST_NAMES`, `INDIAN_LAST_NAMES` |
| `data_classes.py` | 282 | Result structures | `Redaction`, `RedactionResult`, `RedactionStats` |
| `utils.py` | ~200 | Utilities | `DataCleaner`, `get_cpu_count` |
| `ner.py` | 195 | NER integration | `SpacyNER`, `SpacyModelManager` |
| `remover.py` | 1,047 | Main redaction logic | `PIRemover` class |
| `model_manager.py` | 351 | Thread-safe spaCy loading | `SpacyModelManager` singleton |
| `security.py` | 1,176 | API security | JWT auth, rate limiting helpers |
| `sanitizer.py` | 499 | Input sanitization | SQL/XSS/command injection detection |
| `processors/` | ~300 | File processing | `process_csv`, `process_dataframe` |

### 4. Shared Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `config_loader.py` | `shared/` | YAML configuration loading |
| `logging_config.py` | `shared/` | Structured JSON logging |
| `redis_client.py` | `shared/` | Redis connection with fallback |

---

## Redaction Priority Layer Architecture

> **v2.13.2**: The redaction engine processes PI types in a carefully designed priority order to ensure accurate detection and prevent conflicts.

### Design Principles

1. **Risk Level**: Highest-risk data (credentials) processed first for immediate protection
2. **Compound Structures**: URLs/emails before their components to prevent double-detection
3. **Specificity**: High-specificity patterns before generic ones to avoid false positives
4. **Context Dependency**: Name detection last (requires intact surrounding text for accuracy)

### 19-Layer Priority Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    REDACTION PRIORITY LAYERS (v2.13.2)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   LAYER 0: CRITICAL SECRETS ─────────────────────────────────── HIGHEST    │
│   ├── PASSWORD          Credentials (password:, pwd=, pass:)                │
│   ├── LICENSE_KEY       Software license keys (XXXXX-XXXXX-XXXXX)           │
│   ├── API_KEY           API keys and tokens                                 │
│   └── SESSION_TOKEN     Session/auth tokens                                 │
│                                                                             │
│   LAYER 1: COMPOUND STRUCTURES ─────────────────────────────────────────    │
│   └── URL               Contains multiple PI types (email, hostname, etc.)  │
│                                                                             │
│   LAYER 2: EMAILS ──────────────────────────────────────────────────────    │
│   ├── EMAIL             Standard email addresses                            │
│   ├── EMP_ID@DOMAIN     UPN numeric (1234567@tcs.com → [EMP_ID]@[DOMAIN])   │
│   └── PREFIX.EMP_ID@    UPN prefixed (ad.1234567@tcs.com)                   │
│                                                                             │
│   LAYER 3: GOVERNMENT IDs ──────────────────────────────────────────────    │
│   ├── AADHAAR           Indian Aadhaar (XXXX-XXXX-XXXX)                     │
│   ├── PAN               Indian PAN (ABCDE1234F)                             │
│   └── IFSC              Bank IFSC codes (ABCD0123456)                       │
│                                                                             │
│   LAYER 4: PHONE NUMBERS ───────────────────────────────────────────────    │
│   ├── PHONE_INTL        International formats (+1, +91, +44, etc.)          │
│   ├── PHONE_BR          Brazilian format ((XX) XXXXX-XXXX)                  │
│   ├── PHONE_MY          Malaysian format (+60)                              │
│   └── PHONE_MX          Mexican format (+52)                                │
│                                                                             │
│   LAYER 5: EMPLOYEE IDs (Tiered Context-Aware) ─────────────────────────    │
│   ├── EMP_ID_LABELED    Explicit labels (Emp ID: 1234567)                   │
│   ├── EMP_ID_PREFIXED   Prefixed formats (ad.1234567)                       │
│   ├── EMP_ID_LDAP       LDAP DN (CN=1234567)                                │
│   └── EMP_ID_CONTEXT    4-7 digit with context scoring                     │
│                                                                             │
│   LAYER 6: ASSET IDENTIFIERS ───────────────────────────────────────────    │
│   ├── ASSET_ID          TCS format (19HWCL12345678)                         │
│   ├── RFID              EPC/barcode tags (24-char hex)                      │
│   └── SERIAL            Serial numbers (S/N: XXXXXX)                        │
│                                                                             │
│   LAYER 7: NETWORK IDENTIFIERS ─────────────────────────────────────────    │
│   ├── IPV4              IPv4 addresses                                      │
│   ├── IPV6              IPv6 addresses                                      │
│   └── MAC               MAC addresses (XX:XX:XX:XX:XX:XX)                   │
│                                                                             │
│   LAYER 8: HOSTNAMES ───────────────────────────────────────────────────    │
│   ├── HOSTNAME          Standard format (XX00XXX12345678)                   │
│   ├── HOSTNAME_DB       Database servers (INHYDB03)                         │
│   └── HOSTNAME_GENERIC  Generic servers (PRODDB01, USEASTPRI1)              │
│                                                                             │
│   LAYER 9: IT/ITSM IDENTIFIERS ─────────────────────────────────────────    │
│   ├── JIRA_TICKET       JIRA format (PROJ-12345)                            │
│   ├── RFC               Change requests (RFC#25224330)                      │
│   ├── CR_NUMBER         Change request numbers                              │
│   ├── SECURITY_INCIDENT Security incidents (ES12345678)                     │
│   └── TICKET_NUM        Generic ticket numbers                              │
│                                                                             │
│   LAYER 10: PAYMENT & FINANCIAL ────────────────────────────────────────    │
│   ├── UPI               UPI IDs (xxx@upi, xxx@paytm)                        │
│   └── ARIBA_PR          Procurement (PR435494)                              │
│                                                                             │
│   LAYER 11: SERVICE ACCOUNTS & MISC ────────────────────────────────────    │
│   ├── SERVICE_ACCOUNT   sa.xxxxx, svc.xxxxx, NT71853                        │
│   ├── LOCATION          Location/wing IDs (TCB4/ODC1/WSN/100)               │
│   ├── SEAT              Seat IDs (A1F-102)                                  │
│   ├── WIN_PATH          C:\Users\username                                   │
│   └── INTERNAL_DOMAIN   India.tcs.com, SOAM, NOAM, etc.                     │
│                                                                             │
│   LAYERS 12-14: NER NAME DETECTION ─────────────────────────────────────    │
│   └── NAME (NER)        spaCy PERSON entities with blocklist filtering     │
│                                                                             │
│   LAYER 15: PATTERN-BASED NAMES ────────────────────────────────────────    │
│   ├── NAME_WITH_TITLE   Mr. John Smith, Dr. Jane Doe                        │
│   └── NAME_LABELED      Name: John Smith, Contact: Jane                     │
│                                                                             │
│   LAYER 16: CONTEXTUAL NAMES ───────────────────────────────────────────    │
│   ├── NAME_FROM_BY      From John, By Jane, CC: John                        │
│   ├── NAME_GREETING     Hi John, Dear Jane                                  │
│   └── NAME_CALLER       Caller: John, Raised by: Jane                       │
│                                                                             │
│   LAYERS 17-18: DICTIONARY NAMES ───────────────────────────── LOWEST ──    │
│   └── NAME (Dict)       Dictionary-based with prefix stripping              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Order Matters

| Priority Decision | Reason |
|-------------------|--------|
| Credentials before Email | Password in email context must be redacted first |
| URL before components | `https://user@host.com` - URL contains email, should be one token |
| Email before Emp ID | `1234567@tcs.com` - UPN handling extracts emp ID from email |
| Emp ID before Hostname | Some hostnames contain employee IDs (avoid double-detection) |
| Names LAST | Context-dependent - needs intact text for accurate NER |

---

## PI Type Dependency Graph

> This graph shows which PI types can contain or overlap with other types.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PI TYPE DEPENDENCY GRAPH                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              ┌──────────┐                                   │
│                              │   URL    │                                   │
│                              └────┬─────┘                                   │
│                     ┌─────────────┼─────────────┐                           │
│                     │             │             │                           │
│                     ▼             ▼             ▼                           │
│              ┌──────────┐  ┌──────────┐  ┌──────────┐                       │
│              │  EMAIL   │  │ HOSTNAME │  │    IP    │                       │
│              └────┬─────┘  └────┬─────┘  └──────────┘                       │
│                   │             │                                           │
│                   ▼             ▼                                           │
│              ┌──────────┐  ┌──────────┐                                     │
│              │  EMP_ID  │  │  EMP_ID  │  (hostnames may embed emp IDs)      │
│              │  (UPN)   │  │ (in host)│                                     │
│              └──────────┘  └──────────┘                                     │
│                                                                             │
│   ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│              ┌──────────┐       ┌──────────┐                                │
│              │ PASSWORD │ ───▶  │  EMAIL   │  (password for email)          │
│              └──────────┘       └──────────┘                                │
│                                                                             │
│   ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│              ┌──────────┐       ┌──────────┐                                │
│              │  NAME    │ ───▶  │  EMP_ID  │  (name followed by emp ID)     │
│              └──────────┘       └──────────┘                                │
│                   │                                                         │
│                   ▼                                                         │
│              ┌──────────┐                                                   │
│              │  EMAIL   │  (name part of email local)                       │
│              └──────────┘                                                   │
│                                                                             │
│   ─────────────────────────────────────────────────────────────────────     │
│                                                                             │
│   DETECTION ORDER IMPLICATIONS:                                             │
│                                                                             │
│   1. URL detected first → components inside not double-detected             │
│   2. Email detected → UPN emp ID extracted, domain preserved                │
│   3. Hostname detected → embedded emp ID not re-detected                    │
│   4. Explicit patterns → before context-based detection                     │
│   5. Names detected last → uses intact context for accuracy                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Overlap Resolution Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      OVERLAP RESOLUTION (v2.13.2)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Input: "Contact john.doe@tcs.com (1234567) for asset 19HWCL12345"         │
│                                                                             │
│   STEP 1: Collect all matches by priority layer                             │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │ Layer 2: EMAIL    → "john.doe@tcs.com"     [pos 8-24]            │      │
│   │ Layer 5: EMP_ID   → "1234567"              [pos 26-33]           │      │
│   │ Layer 6: ASSET_ID → "19HWCL12345"          [pos 45-56]           │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│   STEP 2: Remove overlapping positions (earlier layer wins)                 │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │ No overlaps in this example - all positions distinct             │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
│   STEP 3: Apply redactions from end to start (preserve positions)           │
│   ┌──────────────────────────────────────────────────────────────────┐      │
│   │ Result: "Contact [EMAIL] ([EMP_ID]) for asset [ASSET_ID]"        │      │
│   └──────────────────────────────────────────────────────────────────┘      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Communication Flow

### 1. Text Redaction Request

```
User Request → Web Service → API Client → API Service → Response
      │              │             │            │           │
      │              │             │            ▼           │
      │              │             │     ┌─────────────┐    │
      │              │             │     │  Validate   │    │
      │              │             │     │    JWT      │    │
      │              │             │     └─────────────┘    │
      │              │             │            │           │
      │              │             │            ▼           │
      │              │             │     ┌─────────────┐    │
      │              │             │     │   Check     │    │
      │              │             │     │ Rate Limit  │    │
      │              │             │     └─────────────┘    │
      │              │             │            │           │
      │              │             │            ▼           │
      │              │             │     ┌─────────────┐    │
      │              │             │     │  PIRemover  │    │
      │              │             │     │  Process    │    │
      │              │             │     └─────────────┘    │
      │              │             │            │           │
      └──────────────┴─────────────┴────────────┴───────────┘
```

### 2. Authentication Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Web Service │     │  API Service │     │    Redis     │
│  (Startup)   │     │              │     │              │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │  POST /auth/token  │                    │
       │  (client_id,       │                    │
       │   client_secret)   │                    │
       │───────────────────>│                    │
       │                    │                    │
       │                    │  Validate Client   │
       │                    │  (clients.yaml)    │
       │                    │                    │
       │                    │  Check Rate Limit  │
       │                    │───────────────────>│
       │                    │                    │
       │                    │<───────────────────│
       │                    │                    │
       │   JWT Token        │                    │
       │   (30 min exp)     │                    │
       │<───────────────────│                    │
       │                    │                    │
       │  [Token Cached]    │                    │
       │                    │                    │
       │  POST /v1/redact   │                    │
       │  (Bearer token)    │                    │
       │───────────────────>│                    │
       │                    │                    │
```

## Resilience Patterns

### Circuit Breaker

The web service API client implements a circuit breaker pattern to handle API service failures:

```
                    ┌─────────────┐
                    │   CLOSED    │ ◄── Normal operation
                    │ (Requests   │
                    │  pass)      │
                    └──────┬──────┘
                           │
                     5 failures
                           │
                           ▼
                    ┌─────────────┐
                    │    OPEN     │ ◄── Fail fast
                    │ (Requests   │
                    │  rejected)  │
                    └──────┬──────┘
                           │
                     30 seconds
                           │
                           ▼
                    ┌─────────────┐
                    │ HALF-OPEN   │ ◄── Test requests
                    │ (Limited    │
                    │  requests)  │
                    └──────┬──────┘
                           │
          ┌────────────────┴────────────────┐
          │                                 │
     Success                           Failure
          │                                 │
          ▼                                 ▼
    ┌─────────────┐                  ┌─────────────┐
    │   CLOSED    │                  │    OPEN     │
    └─────────────┘                  └─────────────┘
```

**Configuration** (`config/web_service.yaml`):
```yaml
circuit_breaker:
  failure_threshold: 5     # Failures before opening
  recovery_timeout: 30     # Seconds before half-open
  half_open_requests: 3    # Test requests in half-open
```

### Retry Logic

```yaml
retry:
  max_retries: 3
  base_delay: 1.0      # seconds
  max_delay: 30.0      # seconds
  exponential_base: 2  # delay = base * (2^attempt)
```

### API Status Caching (v2.9.1)

The web service implements intelligent API status caching to avoid repeated timeout cascades when the API is unavailable:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    API Status Cache Flow                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐      30-sec       ┌──────────────────────┐       │
│   │  Background  │ ──────────────►   │   APIStatusCache     │       │
│   │ Health Check │    updates        │ ──────────────────── │       │
│   └──────────────┘                   │ is_available: bool   │       │
│         │                            │ last_check: datetime │       │
│         │                            │ response_time_ms: int│       │
│    3-sec timeout                     │ consecutive_failures │       │
│         │                            └──────────┬───────────┘       │
│         ▼                                       │                   │
│   ┌──────────────┐                              │ should_try_api()  │
│   │  API Health  │                              │ (instant check)   │
│   │  /api/health │                              │                   │
│   └──────────────┘                              ▼                   │
│                                    ┌────────────────────────┐       │
│                                    │  Hybrid Redact Request │       │
│                                    │ ────────────────────── │       │
│                                    │ 1. Check cache first   │       │
│                                    │ 2. If unavailable →    │       │
│                                    │    local fallback (0ms)│       │
│                                    │ 3. If available →      │       │
│                                    │    try API → fallback  │       │
│                                    └────────────────────────┘       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Cache Configuration** (constants in `app.py`):
```python
HEALTH_CHECK_INTERVAL = 30  # seconds between background checks
CACHE_TTL_SECONDS = 30      # cache validity period
MAX_CONSECUTIVE_FAILURES = 3 # failures before marking unavailable
```

**Performance Impact**:
| Scenario | Without Caching | With Caching |
|----------|:---------------:|:------------:|
| API available | ~200ms | ~200ms |
| API down (1st request after cache) | 17.6s (4 retries) | 17.6s |
| API down (subsequent requests) | 17.6s (4 retries) | **0ms** |
| API flaky | 4-17s | **3s max** |

**Frontend Status Indicator**:
- Poll `/api/status` endpoint every 60 seconds
- Visual badge: 🟢 API Online | 🔴 Local Mode | 🟡 Checking...

## Configuration Files

All configuration uses YAML files (no environment variables per design):

| File | Purpose |
|------|---------|
| `config/api_service.yaml` | API service settings |
| `config/web_service.yaml` | Web service settings |
| `config/clients.yaml` | Client credentials (secrets!) |
| `config/redis.yaml` | Redis connection settings |
| `config/logging.yaml` | Logging configuration |

### Loading Configuration

```python
from shared.config_loader import ConfigLoader

# From file
config = ConfigLoader.from_yaml("config/api_service.yaml")

# With CLI arguments
import argparse
parser = argparse.ArgumentParser()
config = ConfigLoader.from_args(parser.parse_args())
```

## Docker Deployment

### Development

```powershell
# Using deployment script (recommended)
.\scripts\deploy-dev.ps1 -ConfigPath "config"

# Manual
docker-compose -f docker/docker-compose.base.yml \
               -f docker/docker-compose.dev.yml \
               up --build
```

### Production

```powershell
# Using deployment script
.\scripts\deploy-prod.ps1 -ConfigPath "config" -Replicas 3

# Manual
docker-compose -f docker/docker-compose.base.yml \
               -f docker/docker-compose.prod.yml \
               up -d --scale api-service=3 --scale web-service=2
```

### Docker Networks

| Network | Purpose |
|---------|---------|
| `pi-internal` | Internal service-to-service communication |
| `pi-public` | External access (load balancer) |

## Health Checks

### API Service
```http
GET /dev/health
Authorization: Bearer <token>
```

Response:
```json
{
  "status": "healthy",
  "version": "2.12.0",
  "spacy_model": "en_core_web_lg",
  "timestamp": "2025-01-15T12:00:00Z"
}
```

### Web Service
```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "version": "2.12.0",
  "api_service": {
    "url": "http://api-service:8080",
    "healthy": true,
    "status": "connected"
  },
  "circuit_breaker": {
    "state": "closed",
    "failures": 0
  }
}
```

## Logging

All logs are structured JSON for ELK/Splunk integration:

```json
{
  "timestamp": "2025-01-15T12:00:00.000Z",
  "level": "INFO",
  "service": "web-service",
  "correlation_id": "abc-123-def",
  "message": "Request processed",
  "duration_ms": 45.2,
  "path": "/api/redact-text",
  "method": "POST"
}
```

### Correlation ID

Requests are tracked across services using `X-Correlation-ID` header:

```
User Request
    │
    ▼ X-Correlation-ID: abc-123
┌─────────────┐
│ Web Service │ ──── Logs with abc-123
└──────┬──────┘
       │
       ▼ X-Correlation-ID: abc-123
┌─────────────┐
│ API Service │ ──── Logs with abc-123
└─────────────┘
```

## Security

### Authentication

1. **Client Credentials**: Stored in `config/clients.yaml`
2. **JWT Tokens**: 30-minute expiration, HS256 algorithm
3. **Internal Client**: `pi-internal-web-service` for service-to-service auth

### Network Security

1. **Internal Network**: Services communicate over `pi-internal` network
2. **No External Access**: API service not exposed externally in production
3. **TLS**: Enable in production via reverse proxy

### Secrets Management

⚠️ **Important**: `config/clients.yaml` contains secrets!

```gitignore
# Add to .gitignore
config/clients.yaml
```

Use volume mounts or secret management in production:
- Kubernetes Secrets
- Docker Secrets
- HashiCorp Vault
- AWS Secrets Manager

## Scaling

### Horizontal Scaling

```yaml
# docker-compose.prod.yml
services:
  api-service:
    deploy:
      replicas: 3
      
  web-service:
    deploy:
      replicas: 2
```

### Load Balancing

Configure nginx or cloud load balancer for:
- Round-robin distribution
- Health check endpoints
- Sticky sessions (if needed)

## Monitoring

### Key Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Request latency | Logs | > 5000ms |
| Error rate | Logs | > 1% |
| Circuit breaker state | Health check | OPEN |
| Redis availability | Health check | Unavailable |
| Rate limit hits | Redis | > 100/min |

### Health Check Monitoring

```bash
# Check both services
curl http://localhost:8082/health
```

## Troubleshooting

### Web Service Can't Connect to API

1. Check network: `docker network inspect pi-internal`
2. Verify API health: `curl http://localhost:8080/docs`
3. Check circuit breaker state in health endpoint
4. Review logs: `docker logs web-service`

### Rate Limiting Issues

1. Check Redis connection
2. Verify client rate limits in `clients.yaml`
3. Use internal client for higher limits

### Authentication Failures

1. Verify client credentials in `clients.yaml`
2. Check token expiration (30 min default)
3. Ensure JWT secret matches between services

## Migration from Monolith

If migrating from the standalone version:

1. Deploy API service first
2. Configure API client in web service
3. Update Docker Compose files
4. Test with integration tests
5. Deploy web service
6. Validate with end-to-end tests

---

## Service Startup Options

### Complete Startup Reference

| Mode | Command | API Required | Port | Use Case |
|------|---------|:------------:|:----:|----------|
| **CLI** | `python -m pi_remover -i data.csv` | ❌ | - | Batch file processing |
| **Web Hybrid** | `cd web_service && uvicorn app:app` | Optional | 8082 | Production (recommended) |
| **Web Force Local** | `cd web_service && python app.py --standalone` | ❌ | 8082 | Offline environments |
| **API Only** | `cd api_service && uvicorn app:app` | - | 8080 | Programmatic access |
| **Full Stack Script** | `.\scripts\run_comprehensive_tests.ps1` | ✅ | 8080, 8082 | Development |
| **Docker DEV** | `docker-compose -f docker/docker-compose.dev.yml up` | ✅ | 8080, 8082 | Dev testing |
| **Docker PROD** | `docker-compose -f docker/docker-compose.prod.yml up` | ✅ | 8080, 8082 | Production |

### Recommended for Each Environment

| Environment | Recommended Mode | Why |
|-------------|------------------|-----|
| **Development** | Web Hybrid (manual) | Fast iteration, easy debugging |
| **Testing** | Full Stack Script | Comprehensive test coverage |
| **Production** | Docker PROD | Container orchestration, scaling |
| **Offline/Air-gapped** | Web Standalone | No API dependency |

---

## Quick Reference

| Service | Port | Config File | Health Endpoint |
|---------|------|-------------|-----------------|
| API Service | 8080 | `config/api_service.yaml` | `GET /dev/health` (auth) |
| Web Service | 8082 | `config/web_service.yaml` | `GET /health` |
| Redis | 6379 | `config/redis.yaml` | `PING` |

**Commands**:
```bash
# Start dev (hybrid mode)
cd web_service && uvicorn app:app --reload --port 8082

# Start dev (full stack)
.\scripts\deploy-dev.ps1

# View logs
docker-compose logs -f

# Run integration tests
pytest tests/test_service_integration.py -v
```
