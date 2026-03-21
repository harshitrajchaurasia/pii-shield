# PI Remover Security Documentation

> **Version 2.12.0** | Last Updated: December 16, 2025

Complete security reference for the PI Remover project. This document covers all security measures, validation logic, and file-type-specific protections implemented across the codebase.

---

## Table of Contents

1. [Security Architecture Overview](#1-security-architecture-overview)
2. [Authentication System](#2-authentication-system)
3. [Rate Limiting](#3-rate-limiting)
4. [Input Validation](#4-input-validation)
5. [File Security - Complete Reference](#5-file-security---complete-reference)
6. [Data Leakage Prevention](#6-data-leakage-prevention)
7. [Security Headers](#7-security-headers)
8. [Middleware Stack](#8-middleware-stack)
9. [Audit Logging](#9-audit-logging)
10. [Container Security](#10-container-security)
11. [Configuration Reference](#11-configuration-reference)
12. [Security Code Locations](#12-security-code-locations)

---

## 1. Security Architecture Overview

The PI Remover implements **defense-in-depth** with 7 security layers:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SECURITY LAYERS                                  │
├──────────────┬──────────────────────────────────────────────────────────┤
│ Layer 1      │ NETWORK                                                   │
│              │ • TLS/HTTPS encryption                                   │
│              │ • IP allowlist/blocklist                                 │
│              │ • Firewall rules                                         │
├──────────────┼──────────────────────────────────────────────────────────┤
│ Layer 2      │ RATE LIMITING                                            │
│              │ • Token bucket algorithm                                 │
│              │ • Per-IP and per-client tracking                         │
│              │ • Burst allowance                                        │
├──────────────┼──────────────────────────────────────────────────────────┤
│ Layer 3      │ AUTHENTICATION                                           │
│              │ • JWT Bearer tokens (HMAC-SHA256)                        │
│              │ • 30-minute expiry                                       │
│              │ • Client credentials flow                                │
├──────────────┼──────────────────────────────────────────────────────────┤
│ Layer 4      │ INPUT VALIDATION                                         │
│              │ • Size limits (100KB text, 500MB file)                   │
│              │ • Null byte detection                                    │
│              │ • Pattern sanitization                                   │
├──────────────┼──────────────────────────────────────────────────────────┤
│ Layer 5      │ FILE SECURITY                                            │
│              │ • Extension whitelist                                    │
│              │ • MIME type verification                                 │
│              │ • Magic byte validation                                  │
│              │ • Content scanning (macros, JavaScript, scripts)         │
│              │ • Zip bomb detection                                     │
├──────────────┼──────────────────────────────────────────────────────────┤
│ Layer 6      │ AUDIT LOGGING                                            │
│              │ • All operations logged                                  │
│              │ • PI never logged (sanitized)                            │
│              │ • 90-day retention                                       │
├──────────────┼──────────────────────────────────────────────────────────┤
│ Layer 7      │ CONTAINER                                                │
│              │ • Non-root user                                          │
│              │ • Read-only filesystem                                   │
│              │ • Dropped capabilities                                   │
│              │ • Resource limits                                        │
└──────────────┴──────────────────────────────────────────────────────────┘
```

### Source Files

| File | Purpose |
|------|---------|
| `src/pi_remover/security.py` | Core security module (1190 lines) |
| `src/pi_remover/core.py` | File processing with security validation |
| `api_service/app.py` | API authentication enforcement |
| `web_service/app.py` | File upload handling |

---

## 2. Authentication System

### JWT Bearer Token Flow

Authentication uses OAuth 2.0 Client Credentials flow with JWT tokens.

```
Step 1: Obtain Token
─────────────────────────────────────────────────────────────
Client                                              Server
  │                                                    │
  │  POST /auth/token                                  │
  │  {"client_id": "...", "client_secret": "..."}      │
  │ ─────────────────────────────────────────────────► │
  │                                                    │
  │  {"access_token": "eyJ...", "expires_in": 1800}    │
  │ ◄───────────────────────────────────────────────── │


Step 2: Authenticated Request
─────────────────────────────────────────────────────────────
Client                                              Server
  │                                                    │
  │  POST /v1/redact                                   │
  │  Authorization: Bearer eyJ...                      │
  │  {"text": "john@example.com"}                      │
  │ ─────────────────────────────────────────────────► │
  │                                                    │
  │  {"redacted_text": "[EMAIL]"}                      │
  │ ◄───────────────────────────────────────────────── │
```

### Token Structure

JWT tokens use HS256 (HMAC-SHA256) signing:

```python
# Header
{
    "alg": "HS256",
    "typ": "JWT"
}

# Payload
{
    "client_id": "prod-client",
    "client_name": "production",
    "iat": 1702540800,          # issued at (Unix timestamp)
    "exp": 1702542600,          # expires (30 min later)
    "jti": "a1b2c3d4e5f6..."    # unique token ID (prevents replay)
}

# Signature
HMAC-SHA256(base64(header) + "." + base64(payload), secret_key)
```

### Token Verification Logic

Located in `security.py`, function `verify_bearer_token()`:

```python
# 1. Check if Authorization header present
if not credentials:
    raise HTTPException(401, "Authentication required")

# 2. Decode and verify signature
payload = decode_jwt_token(credentials.credentials)
if not payload:
    raise HTTPException(401, "Invalid or malformed token")

# 3. Check expiry
if time.time() > payload.get("exp", 0):
    raise HTTPException(401, "Token has expired")

# 4. Return client info with rate limit
return {
    "client_id": payload["client_id"],
    "rate_limit": client_data.get("rate_limit", 100)
}
```

### Constant-Time Comparison

Secret comparison uses `hmac.compare_digest()` to prevent timing attacks:

```python
# In generate_auth_token()
if not hmac.compare_digest(client_data["secret"], client_secret):
    return None  # Invalid credentials
```

### Security Properties

| Property | Implementation |
|----------|----------------|
| Signature Algorithm | HMAC-SHA256 |
| Token Expiry | 30 minutes (configurable) |
| Unique Token ID | `secrets.token_hex(16)` per token |
| Secret Storage | Environment variables or secrets file |
| Timing Attack Prevention | `hmac.compare_digest()` |

### API Endpoints Authentication Requirements

**All endpoints require JWT Bearer token authentication** except for the token endpoint itself.

| Method | Endpoint | Auth Required | Purpose |
|--------|----------|:-------------:|---------|
| POST | `/auth/token` | ❌ No | Obtain JWT access token |
| POST | `/v1/redact` | ✅ Yes | Redact PI from single text |
| POST | `/v1/redact/batch` | ✅ Yes | Redact PI from multiple texts |
| GET | `/health` | ✅ Yes | Service health check and metrics |
| GET | `/v1/pi-types` | ✅ Yes | List supported PI types |
| GET | `/v1/models` | ✅ Yes | List available spaCy NER models |
| GET | `/` | ✅ Yes | API info and endpoint listing |

#### Environment-Specific Base URLs

| Environment | Base URL | Description |
|-------------|----------|-------------|
| **DEV** | `http://localhost:8080/dev` | Development (relaxed rate limits) |
| **PROD** | `http://localhost:9080/prod` | Production (strict rate limits) |

#### Unauthenticated Access Response

Requests without valid JWT receive 401 Unauthorized:

```json
{
    "error": "missing_token",
    "message": "Authorization header missing or invalid",
    "request_id": "abc123..."
}
```

---

## 3. Rate Limiting

### Token Bucket Algorithm

The rate limiter uses a token bucket algorithm that allows bursts while enforcing long-term limits.

```
Token Bucket Visualization
──────────────────────────────────────────────────────────────
                     ┌─────────────────────┐
                     │   Token Bucket      │
  Tokens refill      │                     │
  over time          │  ████████░░░░░░░░░  │  Tokens consumed
  (100/minute)       │  ^^^^^^^            │  per request
     ───────────────►│  80 tokens          │◄──────────────
                     │  remaining          │
                     │                     │
                     └─────────────────────┘
                              │
                              ▼
                    Request allowed if tokens > 0
```

### Implementation Logic

Located in `security.py`, class `RateLimiter`:

```python
class RateLimiter:
    def check_rate_limit(self, identifier: str, cost: int = 1):
        # 1. Hash identifier for privacy
        key = hashlib.sha256(identifier.encode()).hexdigest()[:16]
        
        # 2. Refill tokens based on elapsed time
        elapsed = now - bucket["last_update"]
        refill_rate = max_tokens / WINDOW_SECONDS
        bucket["tokens"] = min(max_tokens + BURST, bucket["tokens"] + elapsed * refill_rate)
        
        # 3. Check if request allowed
        if bucket["tokens"] >= cost:
            bucket["tokens"] -= cost
            return True, {"remaining": int(bucket["tokens"])}
        else:
            return False, {"remaining": 0, "reset": seconds_until_reset}
```

### Configuration

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100        # tokens per window
RATE_LIMIT_WINDOW_SECONDS=60   # window duration
RATE_LIMIT_BURST=20            # extra burst allowance
```

### Response Headers

Every response includes rate limit status:

```
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 45
```

### 429 Response When Exceeded

```json
{
    "error": "rate_limit_exceeded",
    "message": "Too many requests. Please slow down.",
    "retry_after": 45
}
```

---

## 4. Input Validation

### Text Validation

Class `InputValidator` in `security.py`:

```python
@classmethod
def validate_text_for_processing(cls, text: str) -> Tuple[bool, Optional[str]]:
    # 1. Check not empty
    if not text:
        return False, "Text cannot be empty"
    
    # 2. Check length limit
    if len(text) > MAX_TEXT_LENGTH:  # 100,000 chars
        return False, f"Text exceeds maximum length"
    
    # 3. Check for null bytes (indicates binary data)
    if '\x00' in text:
        return False, "Text contains invalid null bytes"
    
    return True, None
```

### Filename Validation

```python
@classmethod
def validate_filename(cls, filename: str) -> Tuple[bool, Optional[str]]:
    # 1. Not empty
    if not filename:
        return False, "Filename cannot be empty"
    
    # 2. Prevent path traversal
    if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
        return False, "Invalid filename: path traversal detected"
    
    # 3. Only safe characters (alphanumeric, dash, dot, underscore, space)
    safe_pattern = re.compile(r'^[\w\-. ]+$')
    if not safe_pattern.match(filename):
        return False, "Filename contains invalid characters"
    
    # 4. Extension whitelist
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type not allowed"
    
    return True, None
```

### Dangerous Pattern Detection

Patterns checked in input text and file content:

```python
DANGEROUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',  # XSS script tags
    r'javascript:',                  # javascript: URIs
    r'on\w+\s*=',                    # Event handlers (onclick, onerror, etc.)
    r'\{\{.*?\}\}',                  # Template injection (Jinja, Angular)
    r'\$\{.*?\}',                    # Template literals (JS)
    r'<!--.*?-->',                   # HTML comments
]
```

### Size Limits

| Parameter | Default | Environment Variable |
|-----------|---------|---------------------|
| Max text length | 100,000 chars | `MAX_TEXT_LENGTH` |
| Max batch size | 100 texts | `MAX_BATCH_SIZE` |
| Max request size | 10 MB | `MAX_REQUEST_SIZE` |
| Max file size | 500 MB | `MAX_FILE_SIZE` |

---

## 5. File Security - Complete Reference

This section documents all file type validations, the security checks performed, and the implementation logic.

### Allowed File Types

```python
ALLOWED_EXTENSIONS = {
    # Data files
    '.csv', '.xlsx', '.xls', '.json', '.txt',
    
    # Office documents
    '.docx', '.doc', '.pptx', '.ppt',
    
    # PDF
    '.pdf',
    
    # Other document formats
    '.rtf', '.odt', '.ods', '.odp',
    
    # Markup/Web
    '.xml', '.html', '.htm',
    
    # Text-based
    '.md', '.log',
}
```

### MIME Type Whitelist

```python
ALLOWED_MIME_TYPES = {
    # Text
    'text/csv', 'text/plain', 'text/html', 'text/xml', 
    'text/markdown', 'text/rtf',
    
    # JSON/XML
    'application/json', 'application/xml',
    
    # Excel
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    
    # Word
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    
    # PowerPoint
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    
    # PDF
    'application/pdf',
    
    # OpenDocument
    'application/vnd.oasis.opendocument.text',
    'application/vnd.oasis.opendocument.spreadsheet',
    'application/vnd.oasis.opendocument.presentation',
}
```

### File Validation Pipeline

Every file goes through this 8-step validation:

```
┌────────────────────────────────────────────────────────────────────┐
│                    FILE VALIDATION PIPELINE                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Step 1: SIZE CHECK                                                 │
│  ────────────────                                                   │
│  • Max: 500MB (configurable)                                       │
│  • Reject empty files                                              │
│                                                                     │
│  Step 2: FILENAME VALIDATION                                        │
│  ──────────────────────────                                         │
│  • No path traversal (.., /, \)                                    │
│  • Only safe characters [a-zA-Z0-9_.-]                             │
│  • Valid extension                                                 │
│                                                                     │
│  Step 3: EXTENSION CHECK                                            │
│  ────────────────────────                                           │
│  • Must be in ALLOWED_EXTENSIONS                                   │
│                                                                     │
│  Step 4: MIME TYPE VERIFICATION                                     │
│  ─────────────────────────────                                      │
│  • Extension and MIME must match                                   │
│  • Prevents disguised malware                                      │
│                                                                     │
│  Step 5: MAGIC BYTE VERIFICATION                                    │
│  ───────────────────────────────                                    │
│  • Binary files verified by file signature                         │
│  • Prevents extension spoofing                                     │
│                                                                     │
│  Step 6: SCRIPT DETECTION (text files)                              │
│  ─────────────────────────────────────                              │
│  • Scans for <script>, javascript:, DDE, etc.                      │
│  • Blocks XSS, formula injection                                   │
│                                                                     │
│  Step 7: MACRO DETECTION (Office files)                             │
│  ──────────────────────────────────────                             │
│  • Scans for vbaProject.bin, ActiveX                               │
│  • Blocks macro-enabled documents                                  │
│  • Zip bomb detection (compression ratio)                          │
│                                                                     │
│  Step 8: PDF SAFETY CHECK                                           │
│  ────────────────────────                                           │
│  • Scans for /JavaScript, /Launch, /OpenAction                     │
│  • Blocks malicious PDFs                                           │
│                                                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

### Magic Byte Signatures

Used to verify file content matches the claimed extension:

```python
MAGIC_BYTES = {
    # ZIP-based formats (Office Open XML, OpenDocument)
    b'PK\x03\x04': ['.xlsx', '.docx', '.pptx', '.odt', '.ods', '.odp', '.zip'],
    
    # OLE Compound Document (Legacy Office)
    b'\xd0\xcf\x11\xe0': ['.xls', '.doc', '.ppt'],
    
    # PDF
    b'%PDF': ['.pdf'],
    
    # JSON
    b'{': ['.json'],  # JSON object
    b'[': ['.json'],  # JSON array
    
    # RTF
    b'{\\rtf': ['.rtf'],
    
    # HTML
    b'<!DOCTYPE': ['.html', '.htm'],
    b'<html': ['.html', '.htm'],
    
    # XML
    b'<?xml': ['.xml', '.html'],
}
```

### Verification Logic

```python
# In validate_file(), Step 5
if ext in ['.xlsx', '.xls', '.docx', '.doc', '.pptx', '.ppt', '.pdf']:
    with open(file_path, 'rb') as f:
        magic = f.read(8)  # Read first 8 bytes
        
        # Find expected magic bytes for this extension
        valid_magics = [mb for mb, exts in MAGIC_BYTES.items() if ext in exts]
        
        # Check if any magic byte matches
        matched = any(magic.startswith(m) for m in valid_magics)
        
        if not matched:
            security_logger.warning(f"Magic byte mismatch: {original_filename}")
            return False, "File content does not match extension"
```

---

### File Type Specific Security Checks

#### CSV, TXT, JSON, MD, LOG Files

**Checks:** Script injection, DDE attacks, formula injection

```python
# Text file scanning
suspicious_patterns = [
    r'<script',                    # XSS script tags
    r'javascript:',                # JavaScript URIs
    r'=cmd\|',                     # DDE attack vector
    r'=HYPERLINK\s*\(',            # Excel formula injection
    r'@SUM\(',                     # Formula injection
    r'=DDE\s*\(',                  # Dynamic Data Exchange attack
    r'on\w+\s*=\s*["\']',          # HTML event handlers
    r'<\s*iframe',                 # iframes (content injection)
    r'<\s*object',                 # embedded objects
    r'<\s*embed',                  # embedded content
    r'data:\s*text/html',          # data URIs with HTML
]

# Scan first 10KB
content_sample = f.read(10240)
for pattern in suspicious_patterns:
    if re.search(pattern, content_sample, re.IGNORECASE):
        if QUARANTINE_SUSPICIOUS_FILES:
            return False, "File contains potentially malicious content"
```

---

#### HTML, HTM, XML Files

**Checks:** All text file checks plus additional web-specific patterns

| Pattern | Attack Type | Example |
|---------|-------------|---------|
| `<script>` | XSS | `<script>alert('xss')</script>` |
| `javascript:` | XSS | `href="javascript:evil()"` |
| `onclick=` | XSS | `<div onclick="evil()">` |
| `onerror=` | XSS | `<img onerror="evil()">` |
| `<iframe>` | Content Injection | `<iframe src="evil.com">` |
| `<object>` | Embedded Objects | `<object data="malware.swf">` |
| `<embed>` | Embedded Content | `<embed src="malware">` |
| `data:text/html` | Data URI XSS | `href="data:text/html,<script>..."` |

---

#### XLSX, DOCX, PPTX Files (Office Open XML)

**Checks:** Macros, ActiveX, embedded objects, zip bombs

```python
def _check_office_macros(cls, file_path: str, ext: str):
    """Check Office XML files for dangerous content."""
    
    dangerous_parts = [
        'vbaProject.bin',      # VBA macro code
        'vbaData.xml',         # VBA metadata
        'activeX',             # ActiveX controls (can execute code)
        'embeddings',          # Embedded OLE objects
    ]
    
    with zipfile.ZipFile(file_path, 'r') as zf:
        file_list = zf.namelist()
        
        # Check for dangerous components
        for part in dangerous_parts:
            for f in file_list:
                if part.lower() in f.lower():
                    if QUARANTINE_SUSPICIOUS_FILES:
                        return False, f"File contains {part} which may be unsafe"
        
        # Check for zip bomb (unusually high compression ratio)
        for info in zf.infolist():
            # Check uncompressed size
            if info.file_size > 100 * 1024 * 1024:  # 100MB uncompressed
                return False, "File contains suspiciously large embedded content"
            
            # Check compression ratio
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > 100:  # 100:1 ratio is suspicious
                    return False, "Suspicious compression ratio (potential zip bomb)"
    
    return True, None
```

**What These Components Do:**

| Component | Risk | Description |
|-----------|------|-------------|
| `vbaProject.bin` | **HIGH** | Contains VBA macro code that can execute arbitrary commands, download malware, encrypt files |
| `vbaData.xml` | Medium | VBA project metadata, indicates presence of macros |
| `activeX/` | **HIGH** | ActiveX controls can execute native code, often used in exploits |
| `embeddings/` | Medium | Embedded OLE objects can contain executables or link to external resources |

---

#### XLS, DOC, PPT Files (Legacy Office - OLE Compound)

**Checks:** Magic byte verification (OLE signature: `\xd0\xcf\x11\xe0`)

Legacy Office files are binary formats that are harder to scan safely. The primary protection is:

1. Magic byte verification (ensures file is actually OLE format)
2. MIME type matching
3. Processing happens in isolated environment

---

#### PDF Files

**Checks:** JavaScript, launch actions, auto-open actions, embedded files

```python
def _check_pdf_safety(cls, file_path: str):
    """Check PDF for potentially dangerous content."""
    
    dangerous_patterns = [
        b'/JavaScript',    # JavaScript code in PDF
        b'/JS ',           # JavaScript short form
        b'/Launch',        # Launch external application
        b'/OpenAction',    # Auto-execute on open
        b'/AA ',           # Additional Actions (triggers)
        b'/EmbeddedFile',  # Hidden embedded files
        b'/GoToR',         # Remote go-to (external links)
        b'/GoToE',         # Embedded go-to (embedded documents)
    ]
    
    with open(file_path, 'rb') as f:
        content = f.read(100000)  # First 100KB
        
        for pattern in dangerous_patterns:
            if pattern in content:
                security_logger.warning(f"PDF contains: {pattern.decode()}")
                if QUARANTINE_SUSPICIOUS_FILES:
                    return False, f"PDF contains {pattern.decode()} which may be unsafe"
    
    return True, None
```

**What These PDF Features Do:**

| Feature | Risk | Description |
|---------|------|-------------|
| `/JavaScript` | **HIGH** | Execute JavaScript code when PDF opens - can exploit vulnerabilities |
| `/JS` | **HIGH** | Short form of JavaScript |
| `/Launch` | **CRITICAL** | Launch external programs - can run malware directly |
| `/OpenAction` | **HIGH** | Actions that execute automatically when PDF opens |
| `/AA` | High | Additional actions triggered by events (page open, close, etc.) |
| `/EmbeddedFile` | Medium | Hidden files inside PDF - can contain malware |
| `/GoToR` | Medium | Links to remote PDFs - can redirect to malicious content |
| `/GoToE` | Medium | Links to embedded documents |

**Additional PDF Check in core.py:**

When processing PDFs, an additional inline check runs:

```python
# In _process_pdf()
pdf_str = pdf_bytes.decode('latin-1', errors='ignore')

dangerous_patterns = ['/JavaScript', '/JS ', '/Launch', '/OpenAction', 
                      '/AA ', '/URI ', '/GoToR', '/EmbeddedFile']

for pattern in dangerous_patterns:
    if pattern in pdf_str:
        logger.warning(f"PDF contains potentially dangerous content: {pattern}")
        if QUARANTINE_SUSPICIOUS_FILES:
            logger.error(f"Rejecting PDF with {pattern}")
            return  # Abort processing
```

---

#### RTF Files

**Checks:** Magic byte verification (`{\rtf`)

RTF files can contain embedded objects and OLE links. Currently protected by:

1. Magic byte verification
2. Treated as text and scanned for script patterns

---

#### ODT, ODS, ODP Files (OpenDocument)

**Checks:** Same as Office Open XML (ZIP-based)

OpenDocument files are ZIP archives containing XML. Protected by:

1. Magic byte verification (`PK\x03\x04`)
2. ZIP structure validation
3. Macro component scanning (same as DOCX/XLSX/PPTX)

---

### File Validation Entry Points

**For File Uploads (Web/API):**
```python
# In FileSecurityValidator.validate_file()
# Called by web_service and api_service before processing

is_valid, error = FileSecurityValidator.validate_file(
    file_path=temp_path,
    original_filename=uploaded_filename,
    file_size=file_size
)

if not is_valid:
    raise HTTPException(400, error)
```

**For CLI/Programmatic Use:**
```python
# In core.py, process_file()
# Validates file before processing

def process_file(input_path, output_path, columns, config=None, 
                 skip_security_check=False):
    
    if not skip_security_check:
        is_valid, error = validate_file_security(input_path)
        if not is_valid:
            logger.error(f"Security check failed: {error}")
            raise ValueError(f"File rejected: {error}")
    
    # Continue with processing...
```

**Quick Validation Function:**
```python
# Convenience function for scripts
from pi_remover.security import validate_file_security

is_safe, error = validate_file_security("/path/to/file.xlsx")
if not is_safe:
    print(f"File rejected: {error}")
```

---

### Security Configuration

```bash
# Enable/disable suspicious file quarantine
QUARANTINE_SUSPICIOUS_FILES=true   # Default: true

# Maximum file size (bytes)
MAX_FILE_SIZE=524288000            # Default: 500MB

# Custom allowed extensions (not recommended to expand)
# Modify ALLOWED_EXTENSIONS in security.py if needed
```

---

## 6. Data Leakage Prevention

### PI Never Logged

The most critical security feature: **Personal Information is NEVER written to logs.**

```python
@classmethod
def sanitize_for_logging(cls, text: str, max_preview: int = 100) -> str:
    """Prepare text for logging WITHOUT exposing PI."""
    
    if not text:
        return "[empty]"
    
    length = len(text)
    preview = text[:max_preview]
    
    # Mask PI patterns before logging
    preview = re.sub(r'\b[\w.+-]+@[\w.-]+\.\w+\b', '[EMAIL]', preview)
    preview = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE]', preview)
    preview = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]', preview)
    
    if len(text) > max_preview:
        preview += "..."
    
    return f"[{length} chars] {preview}"
```

**Example:**

```
Input:  "Contact john.doe@company.com at 555-123-4567"
Logged: "[45 chars] Contact [EMAIL] at [PHONE]..."
```

### Audit Log Sanitization

```python
# In AuditLogger.log_request()
if details:
    safe_details = {}
    for key, value in details.items():
        if key in ("text", "content", "input", "output"):
            # Only log length, never actual content
            safe_details[f"{key}_length"] = len(str(value)) if value else 0
        else:
            safe_details[key] = value
    log_entry["details"] = safe_details
```

### Error Response Sanitization

Production error responses never include:
- Stack traces
- Internal file paths
- Database connection strings
- Original input text
- Client secrets or tokens

```python
async def generic_exception_handler(request: Request, exc: Exception):
    # Log full error internally
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    
    # Return generic message to client
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred.",
            "request_id": secrets.token_hex(8)
        }
    )
```

---

## 7. Security Headers

All responses include these headers:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Enable XSS filter |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS |
| `Content-Security-Policy` | (see below) | Prevent code injection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | Disable browser features |
| `Cache-Control` | `no-store, no-cache, must-revalidate` | Prevent caching sensitive data |
| `Pragma` | `no-cache` | HTTP/1.0 cache prevention |

**Content Security Policy:**
```
default-src 'self'; 
script-src 'self' 'unsafe-inline'; 
style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; 
font-src 'self' https://fonts.gstatic.com; 
img-src 'self' data:;
```

---

## 8. Middleware Stack

Request processing order (first to last):

```
┌─────────────────────────────────────────────────────────────┐
│                    Request Processing                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. SecurityHeadersMiddleware                                │
│     └─ Adds security headers to all responses               │
│                                                              │
│  2. RequestSizeLimitMiddleware                               │
│     └─ Rejects requests > 10MB                              │
│                                                              │
│  3. RateLimitMiddleware                                      │
│     └─ Token bucket rate limiting                           │
│     └─ Returns 429 if exceeded                              │
│                                                              │
│  4. IPFilterMiddleware (if configured)                       │
│     └─ Block/allow based on IP lists                        │
│                                                              │
│  5. Authentication (in endpoint)                             │
│     └─ verify_bearer_token() dependency                     │
│                                                              │
│  6. Input Validation                                         │
│     └─ Pydantic models + custom validation                  │
│                                                              │
│  7. Business Logic                                           │
│     └─ PI removal processing                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### IP Filtering

```python
class IPFilterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        client_ip = get_client_ip(request)
        
        # Check blocklist
        if client_ip in SecurityConfig.IP_BLOCKLIST:
            return JSONResponse(status_code=403, content={"error": "forbidden"})
        
        # Check allowlist (if configured)
        if SecurityConfig.IP_ALLOWLIST:
            if client_ip not in SecurityConfig.IP_ALLOWLIST:
                return JSONResponse(status_code=403, content={"error": "forbidden"})
        
        return await call_next(request)
```

### Client IP Detection

Handles reverse proxies correctly:

```python
def get_client_ip(request: Request) -> str:
    # 1. Check X-Forwarded-For (reverse proxy)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # 2. Check X-Real-IP (nginx)
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # 3. Direct connection
    return request.client.host if request.client else "unknown"
```

---

## 9. Audit Logging

### What Gets Logged

| Event | Fields |
|-------|--------|
| API Request | timestamp, action, client_id, path, method, text_length |
| Token Request | timestamp, client_id, success/failure |
| File Upload | job_id, operation, filename, success |
| File Download | job_id, filename |
| Rate Limit Hit | timestamp, client_ip, path |
| Auth Failure | timestamp, client_ip, path, reason |
| Security Event | event_type, client_ip, details |

### Log Entry Format

```json
{
    "timestamp": "2024-12-14 15:30:00 IST",
    "action": "redact_single",
    "client_id": "prod-client",
    "client_name": "production",
    "path": "/v1/redact",
    "method": "POST",
    "details": {
        "text_length": 500,
        "include_details": false
    },
    "redactions": {
        "EMAIL": 2,
        "PHONE": 1,
        "NAME": 3
    },
    "total_redactions": 6
}
```

### Configuration

```bash
AUDIT_LOGGING_ENABLED=true
AUDIT_LOG_FILE=logs/audit.log
AUDIT_RETENTION_DAYS=90
AUDIT_TIMEZONE=Asia/Kolkata   # Timestamps in IST
```

---

## 10. Container Security

### Dockerfile Security Measures

```dockerfile
# 1. Non-root user
RUN useradd -m -u 1000 -s /usr/sbin/nologin appuser
USER appuser

# 2. Minimal base image
FROM python:3.11-slim

# 3. No shell access
RUN rm /bin/sh /bin/bash || true
```

### Docker Compose Security

```yaml
services:
  pi-gateway:
    security_opt:
      - no-new-privileges:true    # Prevent privilege escalation
    cap_drop:
      - ALL                        # Drop all capabilities
    read_only: true                # Read-only filesystem
    tmpfs:
      - /tmp                       # Writable /tmp in RAM
    deploy:
      resources:
        limits:
          cpus: '2'                # CPU limit
          memory: 4G               # Memory limit
```

### Security Checklist

- [x] Run as non-root user
- [x] Drop all capabilities
- [x] No new privileges
- [x] Read-only filesystem (where possible)
- [x] Resource limits
- [x] Minimal base image
- [x] No shell access

---

## 11. Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| **Authentication** |||
| `JWT_SECRET_KEY` | (dev key) | HMAC-SHA256 signing key |
| `JWT_EXPIRY_MINUTES` | `30` | Token lifetime |
| `AUTH_CLIENTS` | | Comma-separated client credentials |
| `AUTH_CLIENTS_FILE` | `clients.json` | Path to clients file |
| **Rate Limiting** |||
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_REQUESTS` | `100` | Requests per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Window duration |
| `RATE_LIMIT_BURST` | `20` | Burst allowance |
| **Size Limits** |||
| `MAX_TEXT_LENGTH` | `100000` | Max text chars |
| `MAX_BATCH_SIZE` | `100` | Max texts per batch |
| `MAX_REQUEST_SIZE` | `10485760` | Max request bytes (10MB) |
| `MAX_FILE_SIZE` | `524288000` | Max file bytes (500MB) |
| **File Security** |||
| `QUARANTINE_SUSPICIOUS` | `true` | Block suspicious files |
| **Audit** |||
| `AUDIT_LOGGING_ENABLED` | `true` | Enable audit logs |
| `AUDIT_LOG_FILE` | `logs/audit.log` | Audit log path |
| `AUDIT_RETENTION_DAYS` | `90` | Log retention |
| `AUDIT_TIMEZONE` | `Asia/Kolkata` | Timestamp timezone |
| **Network** |||
| `CORS_ORIGINS` | `*` | Allowed CORS origins |
| `IP_BLOCKLIST` | | Blocked IPs |
| `IP_ALLOWLIST` | | Allowed IPs (if set, only these) |

---

## 12. Security Code Locations

Quick reference for security implementation in the codebase:

| Feature | File | Location |
|---------|------|----------|
| JWT Authentication | `security.py` | Lines 345-530 |
| Token Verification | `security.py` | `verify_bearer_token()` |
| Rate Limiter | `security.py` | Class `RateLimiter` |
| Input Validation | `security.py` | Class `InputValidator` |
| File Validation | `security.py` | Class `FileSecurityValidator` |
| Magic Bytes | `security.py` | `MAGIC_BYTES` dict |
| Office Macro Check | `security.py` | `_check_office_macros()` |
| PDF Safety Check | `security.py` | `_check_pdf_safety()` |
| Security Headers | `security.py` | Class `SecurityHeadersMiddleware` |
| Audit Logging | `security.py` | Class `AuditLogger` |
| File Processing Gate | `core.py` | `process_file()` |
| PDF Inline Check | `core.py` | `_process_pdf()` |

---

## Appendix: Generating Secure Keys

```bash
# Generate JWT secret (256-bit)
openssl rand -hex 32

# Generate client secret (256-bit)
openssl rand -hex 32

# Generate client ID
openssl rand -hex 8

# Example output:
# JWT: a7f3e2d1c0b9a8f7e6d5c4b3a2918273646576879a8b9c0d1e2f3a4b5c6d7e8f
# Secret: 9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e8f7
# Client ID: a1b2c3d4e5f6a7b8
```

---

*This document is maintained alongside the codebase. For questions, see the main README or open an issue.*
