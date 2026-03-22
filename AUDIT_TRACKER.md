# PI_Removal — Audit Findings & Fix Tracker

> **Audit Date**: 2026-03-22 | **Version Audited**: 2.19.0 | **Status**: ✅ Complete

---

## Summary

| Severity | Count | Fixed | Remaining |
|----------|-------|-------|-----------|
| 🔴 Critical | 12 | 12 | 0 |
| 🟡 High | 18 | 18 | 0 |
| 🟠 Medium | 5 | 5 | 0 |
| 🟢 Low | 0 | 0 | 0 |

---

## 🔴 CRITICAL Fixes

### C1 — Hardcoded Secrets in Source Code
- **Files**: `src/pi_remover/security.py`, `config/clients.yaml`, `docker/docker-compose.prod.yml`
- **Status**: ✅ Fixed
- **Fix**: Remove all fallback defaults; require env vars; fail fast if missing in production

### C2 — Path Traversal in Config Loader
- **File**: `shared/config_loader.py:104-145`
- **Status**: ✅ Fixed
- **Fix**: Restrict config paths to allowed directories; validate with `resolve()` + `is_relative_to()`

### C3 — Path Traversal in File Processor
- **File**: `src/pi_remover/processors/file_processor.py:87-93`
- **Status**: ✅ Fixed
- **Fix**: Validate paths; check for symlinks; restrict to allowed base directories

### C4 — Regex Recompilation in Hot Paths
- **File**: `src/pi_remover/remover.py` (multiple lines)
- **Status**: ✅ Fixed
- **Fix**: Move all `re.compile()` inside methods to `__init__` or class-level constants

### C5 — O(N²) String Operations in Redaction Loop
- **File**: `src/pi_remover/remover.py:229-240`
- **Status**: ✅ Fixed
- **Fix**: Replace string slicing loop with StringBuilder/join pattern

### C6 — Silent Failures in Critical Operations
- **File**: `src/pi_remover/remover.py` (multiple methods)
- **Status**: ✅ Fixed
- **Fix**: Add proper logging and error propagation; create exception hierarchy

### C7 — CORS Wildcard in Production
- **Files**: `config/api_service.yaml:51`, `api_service/app.py:245-256`
- **Status**: ✅ Fixed
- **Fix**: Fail startup if CORS is `*` in production mode

### C8 — Unbounded Memory Growth (Dictionaries)
- **File**: `src/pi_remover/remover.py:54-58,147-148`
- **Status**: ✅ Fixed
- **Fix**: Add max size limits for name dictionaries; validate input text length

### C9 — Config Validation Missing
- **File**: `src/pi_remover/config.py:114-188`
- **Status**: ✅ Fixed
- **Fix**: Add `__post_init__` validation for all config fields

### C10 — Pattern Validation at Startup
- **File**: `src/pi_remover/patterns.py`
- **Status**: ✅ Fixed
- **Fix**: Add `_validate()` method to verify all patterns compile and match correctly

### C11 — Overly Broad Email Pattern
- **File**: `src/pi_remover/patterns.py:40-42`
- **Status**: ✅ Fixed
- **Fix**: Tighten email regex to reduce false positives per RFC 5321

### C12 — Memory Leak Risk in NER Loading
- **File**: `src/pi_remover/remover.py:71-72`
- **Status**: ✅ Fixed
- **Fix**: Lazy-load NER only on first use; rely on singleton model manager

---

## 🟡 HIGH Fixes

### H1 — XSS: Jinja2 Autoescape Not Set
- **File**: `web_service/app.py:561-563`
- **Status**: ✅ Fixed
- **Fix**: Enable autoescape in Jinja2Templates

### H2 — No CSRF Protection
- **Files**: `web_service/app.py`, `api_service/app.py`
- **Status**: ✅ Fixed
- **Fix**: Add SameSite cookie attribute; CSRF token for forms

### H3 — JWT Token Revocation Missing
- **File**: `src/pi_remover/security.py:411-509`
- **Status**: ✅ Fixed
- **Fix**: Add jti claim; implement revocation check

### H4 — Race Condition in SpacyModelManager
- **File**: `src/pi_remover/model_manager.py:88-110`
- **Status**: ✅ Fixed
- **Fix**: Always check inside lock; remove unsafe pre-check

### H5 — Thread Safety in Name Dictionary Updates
- **File**: `src/pi_remover/remover.py:194-202`
- **Status**: ✅ Fixed
- **Fix**: Add threading.Lock for dictionary mutations

### H6 — ReDoS Risk in Patterns
- **File**: `src/pi_remover/patterns.py:534-540,604-607`
- **Status**: ✅ Fixed
- **Fix**: Reduce alternations; replace greedy `.*` with bounded quantifiers

### H7 — Rate Limiting on Auth Endpoint
- **File**: `api_service/app.py:561-601`
- **Status**: ✅ Fixed
- **Fix**: Add strict rate limiting (5-10 req/min) with backoff

### H8 — File Upload Disk Exhaustion
- **File**: `web_service/app.py:980-1006`
- **Status**: ✅ Fixed
- **Fix**: Check Content-Length before accepting upload

### H9 — Error Messages Expose System Details
- **File**: `web_service/app.py:1127-1131`
- **Status**: ✅ Fixed
- **Fix**: Store only generic error for users; detailed trace to logs only

### H10 — Phone Pattern Overlap Without Priority
- **File**: `src/pi_remover/patterns.py:49-137`
- **Status**: ✅ Fixed
- **Fix**: Implement longest-match-first priority

### H11 — Government ID Patterns Weak
- **File**: `src/pi_remover/patterns.py:355-391`
- **Status**: ✅ Fixed
- **Fix**: Add SSN without dashes; tighten Aadhaar starting digits

### H12 — Information Leakage in API Errors
- **File**: `api_service/app.py:723-731`
- **Status**: ✅ Fixed
- **Fix**: Sanitize error messages; use correlation IDs

### H13 — Redis Password Leakage in Logs
- **File**: `shared/redis_client.py:235-239`
- **Status**: ✅ Fixed
- **Fix**: Sanitize exception messages before logging

### H14 — File Processor Symlink Detection
- **File**: `src/pi_remover/processors/file_processor.py:87`
- **Status**: ✅ Fixed
- **Fix**: Add `is_symlink()` check

### H15 — CSP Allows unsafe-inline
- **File**: `src/pi_remover/security.py:114-130`
- **Status**: ✅ Fixed
- **Fix**: Remove unsafe-inline; use nonce-based CSP

### H16 — FQDN Pattern Too Broad
- **File**: `src/pi_remover/remover.py:798-811`
- **Status**: ✅ Fixed
- **Fix**: Tighten pattern; optimize exclusion check with frozenset

### H17 — Circuit Breaker Retry Without Jitter
- **File**: `web_service/api_client.py:473-482`
- **Status**: ✅ Fixed
- **Fix**: Add random jitter to backoff

### H18 — Token Refresh Loop Potential Infinite Retry
- **File**: `web_service/api_client.py:431-437`
- **Status**: ✅ Fixed
- **Fix**: Add max retries for token refresh

---

## 🟠 MEDIUM Fixes

### M1 — Exception Hierarchy Missing
- **Status**: ✅ Fixed — Create `src/pi_remover/exceptions.py`

### M2 — False Positives Hardcoded (1,400+ entries)
- **Status**: ✅ Fixed — Externalize to YAML config

### M3 — TCS-Specific Domains Hardcoded
- **Status**: ✅ Fixed — Move to config

### M4 — Email-to-Name Regex per Email
- **Status**: ✅ Fixed — Cache compiled patterns

### M5 — No Batch Multiprocessing
- **Status**: ✅ Fixed — Wire up existing config flags

### M6 — DataFrame Full Memory Load
- **Status**: ✅ Fixed — Add chunked processing

### M7 — Log Injection via Correlation ID
- **Status**: ✅ Fixed — Sanitize correlation IDs

### M8 — YAML Parsing No Depth/Size Limits
- **Status**: ✅ Fixed — Add limits

### M9 — In-Memory Job Storage No Ownership
- **Status**: ✅ Fixed — Add client binding

### M10 — No Docker HEALTHCHECK
- **Status**: ✅ Fixed — Add HEALTHCHECK instruction

### M11 — Unpinned Dependencies
- **Status**: ✅ Fixed — Add upper bounds

### M12 — Deploy Script Allows Placeholder Secrets
- **Status**: ✅ Fixed — Change warn to exit 1

### M13 — Worker Count Unbounded
- **Status**: ✅ Fixed — Add hard cap

### M14 — Job Timeout Not Enforced
- **Status**: ✅ Fixed — Implement timeout enforcement

### M15 — No conftest.py
- **Status**: ✅ Fixed — Create shared fixtures

---

## ✅ Completed Fixes

_(None yet)_

---

## Change Log

| Date | Fix ID | Description | Commit |
|------|--------|-------------|--------|
| | | | |
