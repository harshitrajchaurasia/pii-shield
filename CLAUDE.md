# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PI Remover is an enterprise-grade Personal Information (PI/PII) redaction tool designed for IT support data. It detects and removes 35+ types of sensitive information (names, emails, phones, employee IDs, IPs, hostnames, financial data, government IDs, etc.) to enable safe LLM processing.

**Version**: 2.18.0 | **Python**: 3.11+ | **License**: MIT

## Architecture

Hybrid microservices with three deployment modes:

```
Browser/App
    ↓
Web Service (Port 8082) ─→ API Service (Port 8080) ─→ PI Remover Core + spaCy NER
    │                                                      │
    └─────────→ Local PIRemover (Fallback) ←───────────────┘
```

- **CLI**: Direct Python execution for file processing (`pi-remover` entry point via `core.py:run_cli`)
- **Web Service** (8082): HTML UI with drag-and-drop, auto-fallback to local processing if API unavailable
- **API Gateway** (8080): REST API with JWT auth (always enabled, cannot be disabled), rate limiting

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/pi_remover/remover.py` | Core PIRemover class — redaction engine (~2100 LOC) |
| `src/pi_remover/patterns.py` | 35+ compiled regex patterns organized by category |
| `src/pi_remover/config.py` | PIRemoverConfig dataclass with 40+ boolean flags for granular PI type control |
| `src/pi_remover/core.py` | Facade re-exporting modular API (backward compat from v2.12.0 refactoring) |
| `src/pi_remover/ner.py` | spaCy NER wrapper with lazy loading |
| `src/pi_remover/model_manager.py` | Thread-safe singleton for spaCy model (~500MB) — prevents duplicate loading |
| `src/pi_remover/sanitizer.py` | XSS/SQL injection/command injection prevention, Unicode normalization |
| `src/pi_remover/processors/file_processor.py` | Multi-format file handling (CSV, Excel, JSON, DOCX, PDF, etc.) |
| `src/pi_remover/dictionaries.py` | Indian names, company names, internal systems (expandable via external files) |
| `api_service/app.py` | FastAPI REST API with env-based path prefix (`/dev/v1/` vs `/prod/v1/`) |
| `web_service/app.py` | FastAPI Web UI with background task processing for large files |
| `web_service/api_client.py` | HTTP client with circuit breaker (CLOSED→OPEN→HALF_OPEN), JWT auto-refresh |
| `shared/` | Config loader (YAML, dot notation), structured JSON logging, Redis client, resource monitor, autoscaler, job queue |

### Processing Modes

- **Full mode**: Regex + NER + Dictionaries (~150 rows/sec, highest accuracy)
- **Fast mode** (`--fast`): Regex + Dictionaries only (~1,500 rows/sec, recommended for production)

### Key Architectural Patterns

1. **Facade pattern**: `core.py` re-exports the modular API for backward compatibility (refactored in v2.12.0)
2. **Hybrid fallback**: Web Service automatically falls back to local PIRemover if API unavailable via circuit breaker
3. **Graceful degradation**: Optional dependencies (Redis, psutil, spacy, prometheus) are wrapped in try/except with fallbacks to in-memory or no-op implementations
4. **Singleton model management**: `SpacyModelManager` prevents duplicate ~500MB model loading across PIRemover instances
5. **PI-safe logging**: Log filter redacts PI from log output to prevent log leakage
6. **Cross-platform**: Platform detection (Windows/Linux/macOS) and cloud awareness (GCP/AWS/Azure) in `resource_monitor.py` and `utils.py`

## Common Commands

### Installation
```bash
pip install -e ".[all]"           # Full development install
python -m spacy download en_core_web_lg  # Optional: NER model
```

### CLI Usage
```bash
python -m pi_remover -i input.csv -o output.csv -c "Description"
python -m pi_remover -i input.csv -o output.csv -c "Description" --fast  # 10x faster
python -m pi_remover -i input.csv -o output.csv --columns col1 col2 col3
```

### Running Services
```bash
# Web Service
cd web_service && uvicorn app:app --reload --port 8082

# API Service
cd api_service && uvicorn app:app --reload --port 8080

# Docker (all services)
docker-compose -f docker/docker-compose.dev.yml up -d
```

### Testing
```bash
pytest tests/ -v                          # All tests
pytest tests/test_remover.py -v           # Specific file
pytest tests/test_remover.py::test_email_redaction -v  # Specific test
pytest tests/ --cov=src/pi_remover --cov-report=html   # With coverage
```

Test files: `test_remover.py` (core), `test_comprehensive_pi.py` (scenarios), `test_edge_cases.py`, `test_api.py` (REST endpoints), `test_service_integration.py`. No `conftest.py` — fixtures defined in test files (`remover` = fast mode, `remover_full` = full mode with NER).

### Code Quality
```bash
black src/ tests/ api_service/ web_service/  # Format (line-length=100, target=py311)
ruff check src/ tests/                        # Lint (rules: E, W, F, I, B, C4, UP)
mypy src/pi_remover --ignore-missing-imports  # Type check
```

## Configuration

All configuration is YAML-based in `config/` directory:
- `api_service.yaml`: API settings (port 8080, rate limiting, JWT)
- `web_service.yaml`: Web settings (port 8082, file upload limits)
- `clients.yaml`: API client credentials
- `redis.yaml`: Optional distributed rate limiting
- `config.yaml` (root): Default PI detection settings — general, data_cleaning, NER, detection layers, replacement tokens (50+ options)

Environment separation:
- **DEV**: ports 8080/8082, `docker/docker-compose.dev.yml`
- **PROD**: ports 9080/9082, `docker/docker-compose.prod.yml`

## Deployment

No CI/CD pipeline — deployments handled via shell scripts in `scripts/`:
- `deploy-dev.sh` / `.ps1`: Development deployment
- `deploy-prod.sh` / `.ps1`: Production deployment
- `deploy-gcp.sh`: GCP Cloud Run/Compute Engine
- `promote-to-prod.sh` / `.ps1` / `-gcp.sh`: Staging→production promotion
