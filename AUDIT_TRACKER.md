# PI_Removal — Audit Findings & Fix Tracker

> **Audit Date**: 2026-03-22 | **Version Audited**: 2.19.0 | **Status**: 🔧 In Progress

---

## Summary

| Severity | Count | Fixed | Remaining |
|----------|-------|-------|-----------|
| 🔴 Critical | 12 | 0 | 12 |
| 🟡 High | 18 | 0 | 18 |
| 🟠 Medium | 25 | 0 | 25 |
| 🟢 Low | 15 | 0 | 15 |

---

## 🔴 CRITICAL Fixes

### C1 — Hardcoded Secrets in Source Code
- **Files**: `src/pi_remover/security.py`, `config/clients.yaml`, `docker/docker-compose.prod.yml`
- **Status**: ⬜ Pending
- **Fix**: Remove all fallback defaults; require env vars; fail fast if missing in production

### C2 — Path Traversal in Config Loader
- **File**: `shared/config_loader.py:104-145`
- **Status**: ⬜ Pending
- **Fix**: Restrict config paths to allowed directories; validate with `resolve()` + `is_relative_to()`

### C3 — Path Traversal in File Processor
- **File**: `src/pi_remover/processors/file_processor.py:87-93`
- **Status**: ⬜ Pending
- **Fix**: Validate paths; check for symlinks; restrict to allowed base directories

### C4 — Regex Recompilation in Hot Paths
- **File**: `src/pi_remover/remover.py` (multiple lines)
- **Status**: ⬜ Pending
- **Fix**: Move all `re.compile()` inside methods to `__init__` or class-level constants

### C5 — O(N²) String Operations in Redaction Loop
- **File**: `src/pi_remover/remover.py:229-240`
- **Status**: ⬜ Pending
- **Fix**: Replace string slicing loop with StringBuilder/join pattern

### C6 — Silent Failures in Critical Operations
- **File**: `src/pi_remover/remover.py` (multiple methods)
- **Status**: ⬜ Pending
- **Fix**: Add proper logging and error propagation; create exception hierarchy

### C7 — CORS Wildcard in Production
- **Files**: `config/api_service.yaml:51`, `api_service/app.py:245-256`
- **Status**: ⬜ Pending
- **Fix**: Fail startup if CORS is `*` in production mode

### C8 — Unbounded Memory Growth (Dictionaries)
- **File**: `src/pi_remover/remover.py:54-58,147-148`
- **Status**: ⬜ Pending
- **Fix**: Add max size limits for name dictionaries; validate input text length

### C9 — Config Validation Missing
- **File**: `src/pi_remover/config.py:114-188`
- **Status**: ⬜ Pending
- **Fix**: Add `__post_init__` validation for all config fields

### C10 — Pattern Validation at Startup
- **File**: `src/pi_remover/patterns.py`
- **Status**: ⬜ Pending
- **Fix**: Add `_validate()` method to verify all patterns compile and match correctly

### C11 — Overly Broad Email Pattern
- **File**: `src/pi_remover/patterns.py:40-42`
- **Status**: ⬜ Pending
- **Fix**: Tighten email regex to reduce false positives per RFC 5321

### C12 — Memory Leak Risk in NER Loading
- **File**: `src/pi_remover/remover.py:71-72`
- **Status**: ⬜ Pending
- **Fix**: Lazy-load NER only on first use; rely on singleton model manager

---

## 🟡 HIGH Fixes

### H1 — XSS: Jinja2 Autoescape Not Set
- **File**: `web_service/app.py:561-563`
- **Status**: ⬜ Pending
- **Fix**: Enable autoescape in Jinja2Templates

### H2 — No CSRF Protection
- **Files**: `web_service/app.py`, `api_service/app.py`
- **Status**: ⬜ Pending
- **Fix**: Add SameSite cookie attribute; CSRF token for forms

### H3 — JWT Token Revocation Missing
- **File**: `src/pi_remover/security.py:411-509`
- **Status**: ⬜ Pending
- **Fix**: Add jti claim; implement revocation check

### H4 — Race Condition in SpacyModelManager
- **File**: `src/pi_remover/model_manager.py:88-110`
- **Status**: ⬜ Pending
- **Fix**: Always check inside lock; remove unsafe pre-check

### H5 — Thread Safety in Name Dictionary Updates
- **File**: `src/pi_remover/remover.py:194-202`
- **Status**: ⬜ Pending
- **Fix**: Add threading.Lock for dictionary mutations

### H6 — ReDoS Risk in Patterns
- **File**: `src/pi_remover/patterns.py:534-540,604-607`
- **Status**: ⬜ Pending
- **Fix**: Reduce alternations; replace greedy `.*` with bounded quantifiers

### H7 — Rate Limiting on Auth Endpoint
- **File**: `api_service/app.py:561-601`
- **Status**: ⬜ Pending
- **Fix**: Add strict rate limiting (5-10 req/min) with backoff

### H8 — File Upload Disk Exhaustion
- **File**: `web_service/app.py:980-1006`
- **Status**: ⬜ Pending
- **Fix**: Check Content-Length before accepting upload

### H9 — Error Messages Expose System Details
- **File**: `web_service/app.py:1127-1131`
- **Status**: ⬜ Pending
- **Fix**: Store only generic error for users; detailed trace to logs only

### H10 — Phone Pattern Overlap Without Priority
- **File**: `src/pi_remover/patterns.py:49-137`
- **Status**: ⬜ Pending
- **Fix**: Implement longest-match-first priority

### H11 — Government ID Patterns Weak
- **File**: `src/pi_remover/patterns.py:355-391`
- **Status**: ⬜ Pending
- **Fix**: Add SSN without dashes; tighten Aadhaar starting digits

### H12 — Information Leakage in API Errors
- **File**: `api_service/app.py:723-731`
- **Status**: ⬜ Pending
- **Fix**: Sanitize error messages; use correlation IDs

### H13 — Redis Password Leakage in Logs
- **File**: `shared/redis_client.py:235-239`
- **Status**: ⬜ Pending
- **Fix**: Sanitize exception messages before logging

### H14 — File Processor Symlink Detection
- **File**: `src/pi_remover/processors/file_processor.py:87`
- **Status**: ⬜ Pending
- **Fix**: Add `is_symlink()` check

### H15 — CSP Allows unsafe-inline
- **File**: `src/pi_remover/security.py:114-130`
- **Status**: ⬜ Pending
- **Fix**: Remove unsafe-inline; use nonce-based CSP

### H16 — FQDN Pattern Too Broad
- **File**: `src/pi_remover/remover.py:798-811`
- **Status**: ⬜ Pending
- **Fix**: Tighten pattern; optimize exclusion check with frozenset

### H17 — Circuit Breaker Retry Without Jitter
- **File**: `web_service/api_client.py:473-482`
- **Status**: ⬜ Pending
- **Fix**: Add random jitter to backoff

### H18 — Token Refresh Loop Potential Infinite Retry
- **File**: `web_service/api_client.py:431-437`
- **Status**: ⬜ Pending
- **Fix**: Add max retries for token refresh

---

## 🟠 MEDIUM Fixes

### M1 — Exception Hierarchy Missing
- **Status**: ⬜ Pending — Create `src/pi_remover/exceptions.py`

### M2 — False Positives Hardcoded (1,400+ entries)
- **Status**: ⬜ Pending — Externalize to YAML config

### M3 — TCS-Specific Domains Hardcoded
- **Status**: ⬜ Pending — Move to config

### M4 — Email-to-Name Regex per Email
- **Status**: ⬜ Pending — Cache compiled patterns

### M5 — No Batch Multiprocessing
- **Status**: ⬜ Pending — Wire up existing config flags

### M6 — DataFrame Full Memory Load
- **Status**: ⬜ Pending — Add chunked processing

### M7 — Log Injection via Correlation ID
- **Status**: ⬜ Pending — Sanitize correlation IDs

### M8 — YAML Parsing No Depth/Size Limits
- **Status**: ⬜ Pending — Add limits

### M9 — In-Memory Job Storage No Ownership
- **Status**: ⬜ Pending — Add client binding

### M10 — No Docker HEALTHCHECK
- **Status**: ⬜ Pending — Add HEALTHCHECK instruction

### M11 — Unpinned Dependencies
- **Status**: ⬜ Pending — Add upper bounds

### M12 — Deploy Script Allows Placeholder Secrets
- **Status**: ⬜ Pending — Change warn to exit 1

### M13 — Worker Count Unbounded
- **Status**: ⬜ Pending — Add hard cap

### M14 — Job Timeout Not Enforced
- **Status**: ⬜ Pending — Implement timeout enforcement

### M15 — No conftest.py
- **Status**: ⬜ Pending — Create shared fixtures

---

## ✅ Completed Fixes

_(None yet)_

---

## Change Log

| Date | Fix ID | Description | Commit |
|------|--------|-------------|--------|
| | | | |
