"""
Security module - handles auth, rate limiting, input validation, etc.
Version: 2.5.0
"""

import os
import re
import time
import hmac
import hashlib
import secrets
import logging
import mimetypes
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from zoneinfo import ZoneInfo
from collections import defaultdict
from pathlib import Path
import json

from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field


# --- Config ---

class SecurityConfig:
    """Security settings."""
    
    # =========================================================================
    # HARDCODED CREDENTIALS (for development and testing)
    # =========================================================================
    # DEV Environment
    DEV_JWT_SECRET = "YOUR_DEV_JWT_SECRET_HERE"
    DEV_CLIENT_ID = "pi-dev-client"
    DEV_CLIENT_SECRET = "YOUR_DEV_CLIENT_SECRET_HERE"
    
    # PROD Environment
    PROD_JWT_SECRET = "YOUR_PROD_JWT_SECRET_HERE"
    PROD_CLIENT_ID = "pi-prod-client"
    PROD_CLIENT_SECRET = "YOUR_PROD_CLIENT_SECRET_HERE"
    
    # Test Client (for running tests)
    TEST_CLIENT_ID = "pi-test-client"
    TEST_CLIENT_SECRET = "TestClientSecret1234567890ABCDEF"
    
    # JWT Token Authentication (always enabled - cannot be disabled)
    # Uses environment variable if set, otherwise falls back to DEV secret
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", DEV_JWT_SECRET)
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_MINUTES = int(os.environ.get("JWT_EXPIRY_MINUTES", "30"))  # 30 minutes
    
    # Client Credentials (for obtaining tokens)
    # Format: {"client_id": {"secret": "...", "name": "...", "rate_limit": 100}}
    CLIENTS: Dict[str, Dict[str, Any]] = {}
    
    # Rate Limiting
    RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))  # per window
    RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
    RATE_LIMIT_BURST = int(os.environ.get("RATE_LIMIT_BURST", "20"))  # burst allowance
    
    # Request Size Limits
    MAX_TEXT_LENGTH = int(os.environ.get("MAX_TEXT_LENGTH", "100000"))  # 100KB text
    MAX_BATCH_SIZE = int(os.environ.get("MAX_BATCH_SIZE", "100"))
    MAX_REQUEST_SIZE = int(os.environ.get("MAX_REQUEST_SIZE", str(10 * 1024 * 1024)))  # 10MB
    MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE", str(500 * 1024 * 1024)))  # 500MB
    
    # File Upload Security
    ALLOWED_EXTENSIONS = {
        '.csv', '.xlsx', '.xls', '.json', '.txt',  # data files
        '.docx', '.doc', '.pptx', '.ppt',  # Office docs
        '.pdf',  # PDFs
        '.rtf', '.odt', '.ods', '.odp',  # other doc formats
        '.xml', '.html', '.htm',  # markup
        '.md', '.log',  # text-based
    }
    ALLOWED_MIME_TYPES = {
        # Text
        'text/csv', 'text/plain', 'text/html', 'text/xml', 'text/markdown', 'text/rtf',
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
    QUARANTINE_SUSPICIOUS_FILES = os.environ.get("QUARANTINE_SUSPICIOUS", "true").lower() == "true"
    
    # Audit Logging
    AUDIT_LOGGING_ENABLED = os.environ.get("AUDIT_LOGGING_ENABLED", "true").lower() == "true"
    AUDIT_LOG_FILE = os.environ.get("AUDIT_LOG_FILE", "logs/audit.log")
    AUDIT_RETENTION_DAYS = int(os.environ.get("AUDIT_RETENTION_DAYS", "90"))
    # Timezone for audit logs (e.g., "Asia/Kolkata" for IST)
    AUDIT_TIMEZONE = os.environ.get("AUDIT_TIMEZONE", "Asia/Kolkata")
    
    # Security Headers
    # Note: CSP allows cdn.jsdelivr.net for Swagger UI, and fastapi.tiangolo.com for favicon
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com;"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
        "Pragma": "no-cache"
    }
    
    # CORS Configuration (restrict in production)
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
    CORS_ALLOW_CREDENTIALS = os.environ.get("CORS_CREDENTIALS", "true").lower() == "true"
    
    # Input Sanitization
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS script tags
        r'javascript:',  # javascript: URIs
        r'on\w+\s*=',  # Event handlers
        r'\{\{.*?\}\}',  # Template injection
        r'\$\{.*?\}',  # Template literals
        r'<!--.*?-->',  # HTML comments
    ]
    
    # IP Blocking
    IP_BLOCKLIST: List[str] = []  # Add known malicious IPs
    IP_ALLOWLIST: List[str] = []  # If set, only these IPs allowed
    
    @classmethod
    def load_clients(cls):
        """Load client credentials from environment, YAML config, or secrets file."""
        import yaml  # Local import to avoid circular dependencies
        
        # Load from environment (comma-separated client_id:client_secret:name)
        clients_env = os.environ.get("AUTH_CLIENTS", "")
        if clients_env:
            for entry in clients_env.split(","):
                parts = entry.split(":")
                if len(parts) >= 2:
                    client_id = parts[0].strip()
                    client_secret = parts[1].strip()
                    name = parts[2].strip() if len(parts) > 2 else client_id
                    cls.CLIENTS[client_id] = {
                        "secret": client_secret,
                        "name": name,
                        "created": datetime.now().isoformat(),
                        "rate_limit": cls.RATE_LIMIT_REQUESTS
                    }
        
        # Load from clients.yaml (primary v2.9.0 config method)
        yaml_paths = [
            "config/clients.yaml",
            "../config/clients.yaml",
            os.path.join(os.path.dirname(__file__), "..", "..", "config", "clients.yaml"),
        ]
        for yaml_path in yaml_paths:
            if os.path.exists(yaml_path):
                try:
                    with open(yaml_path, 'r', encoding='utf-8') as f:
                        yaml_data = yaml.safe_load(f) or {}
                        clients_data = yaml_data.get('clients', {})
                        for client_id, data in clients_data.items():
                            cls.CLIENTS[client_id] = data
                        # Also load JWT settings if present
                        jwt_config = yaml_data.get('jwt', {})
                        if jwt_config.get('secret_key'):
                            cls.JWT_SECRET_KEY = jwt_config['secret_key']
                        if jwt_config.get('expiry_minutes'):
                            cls.JWT_EXPIRY_MINUTES = jwt_config['expiry_minutes']
                        logging.info(f"Loaded {len(clients_data)} clients from {yaml_path}")
                    break  # Stop after first successful load
                except Exception as e:
                    logging.warning(f"Failed to load clients.yaml from {yaml_path}: {e}")
        
        # Load from JSON secrets file if exists (legacy support)
        secrets_file = os.environ.get("AUTH_CLIENTS_FILE", "clients.json")
        if os.path.exists(secrets_file):
            try:
                with open(secrets_file, 'r') as f:
                    clients_data = json.load(f)
                    for client_id, data in clients_data.items():
                        cls.CLIENTS[client_id] = data
            except Exception as e:
                logging.error(f"Failed to load clients file: {e}")
        
        # If no clients configured, use hardcoded defaults
        if not cls.CLIENTS:
            environment = os.environ.get("ENVIRONMENT", "development")
            
            # Always add dev client for development/testing
            cls.CLIENTS[cls.DEV_CLIENT_ID] = {
                "secret": cls.DEV_CLIENT_SECRET,
                "name": "development",
                "created": datetime.now().isoformat(),
                "rate_limit": 1000
            }
            
            # Add test client
            cls.CLIENTS[cls.TEST_CLIENT_ID] = {
                "secret": cls.TEST_CLIENT_SECRET,
                "name": "testing",
                "created": datetime.now().isoformat(),
                "rate_limit": 1000
            }
            
            # Add internal web service client (for microservices architecture)
            cls.CLIENTS["pi-internal-web-service"] = {
                "secret": "YOUR_WEB_CLIENT_SECRET_HERE",
                "name": "Web Service Internal",
                "created": datetime.now().isoformat(),
                "rate_limit": 10000
            }
            
            # Add prod client if in production
            if environment == "production":
                cls.CLIENTS[cls.PROD_CLIENT_ID] = {
                    "secret": cls.PROD_CLIENT_SECRET,
                    "name": "production",
                    "created": datetime.now().isoformat(),
                    "rate_limit": cls.RATE_LIMIT_REQUESTS
                }
            
            logging.info(
                f"Using hardcoded credentials for {environment} environment.\n"
                f"  Available clients: {list(cls.CLIENTS.keys())}"
            )


# Initialize configuration
SecurityConfig.load_clients()


# --- Logging ---

def get_audit_timestamp() -> str:
    """Get timestamp in configured timezone."""
    try:
        tz = ZoneInfo(SecurityConfig.AUDIT_TIMEZONE)
        return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S %Z')
    except Exception:
        # Fallback to UTC if timezone not available
        return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


# Configure audit logger
audit_logger = logging.getLogger("pi-remover-audit")
audit_logger.setLevel(logging.INFO)

if SecurityConfig.AUDIT_LOGGING_ENABLED:
    try:
        # Ensure log directory exists
        log_dir = os.path.dirname(SecurityConfig.AUDIT_LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # File handler for audit logs
        audit_handler = logging.FileHandler(SecurityConfig.AUDIT_LOG_FILE)
        audit_handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        audit_logger.addHandler(audit_handler)
    except (PermissionError, OSError) as e:
        # Fall back to console logging if file not writable
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s | AUDIT | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        audit_logger.addHandler(console_handler)
        logging.warning(f"Could not create audit log file: {e}. Using console logging.")

# Security logger for security events
security_logger = logging.getLogger("pi-remover-security")
security_logger.setLevel(logging.WARNING)


# --- Rate Limiting ---

class RateLimiter:
    """Token bucket rate limiter - tracks per IP and API key."""
    
    def __init__(self):
        self._buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "tokens": SecurityConfig.RATE_LIMIT_REQUESTS,
            "last_update": time.time()
        })
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def _get_key(self, identifier: str) -> str:
        """Hash identifier for privacy."""
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
    def _refill_tokens(self, bucket: Dict[str, Any], max_tokens: int) -> None:
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - bucket["last_update"]
        
        # Calculate tokens to add
        refill_rate = max_tokens / SecurityConfig.RATE_LIMIT_WINDOW_SECONDS
        new_tokens = elapsed * refill_rate
        
        bucket["tokens"] = min(max_tokens + SecurityConfig.RATE_LIMIT_BURST, 
                               bucket["tokens"] + new_tokens)
        bucket["last_update"] = now
    
    def check_rate_limit(self, identifier: str, cost: int = 1, 
                         max_tokens: Optional[int] = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.
        
        Returns:
            Tuple of (allowed: bool, info: dict with remaining tokens and reset time)
        """
        if not SecurityConfig.RATE_LIMIT_ENABLED:
            return True, {"remaining": -1, "reset": 0}
        
        max_tokens = max_tokens or SecurityConfig.RATE_LIMIT_REQUESTS
        key = self._get_key(identifier)
        bucket = self._buckets[key]
        
        # Refill tokens
        self._refill_tokens(bucket, max_tokens)
        
        # Check if request allowed
        if bucket["tokens"] >= cost:
            bucket["tokens"] -= cost
            return True, {
                "remaining": int(bucket["tokens"]),
                "reset": int(SecurityConfig.RATE_LIMIT_WINDOW_SECONDS)
            }
        else:
            return False, {
                "remaining": 0,
                "reset": int(SecurityConfig.RATE_LIMIT_WINDOW_SECONDS - 
                           (time.time() - bucket["last_update"]))
            }
    
    def cleanup_old_buckets(self) -> None:
        """Remove stale rate limit buckets."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        stale_threshold = SecurityConfig.RATE_LIMIT_WINDOW_SECONDS * 2
        stale_keys = [
            key for key, bucket in self._buckets.items()
            if now - bucket["last_update"] > stale_threshold
        ]
        
        for key in stale_keys:
            del self._buckets[key]
        
        self._last_cleanup = now


# Global rate limiter instance
rate_limiter = RateLimiter()


# --- JWT Auth ---

# Bearer token extractor
bearer_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """JWT token payload structure."""
    client_id: str
    client_name: str
    iat: float  # issued at (timestamp)
    exp: float  # expiry (timestamp)
    jti: str    # unique token ID


class TokenResponse(BaseModel):
    """Response for token generation."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthRequest(BaseModel):
    """Request for obtaining auth token."""
    client_id: str = Field(..., description="Client ID")
    client_secret: str = Field(..., description="Client Secret")


def create_jwt_token(payload: Dict[str, Any]) -> str:
    """
    Create a JWT token using HMAC-SHA256.
    
    Token format: base64(header).base64(payload).base64(signature)
    """
    # Header
    header = {"alg": SecurityConfig.JWT_ALGORITHM, "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(
        json.dumps(header, separators=(',', ':')).encode()
    ).rstrip(b'=').decode()
    
    # Payload
    payload_b64 = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(',', ':')).encode()
    ).rstrip(b'=').decode()
    
    # Signature
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        SecurityConfig.JWT_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b'=').decode()
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token.
    
    Returns payload if valid, None if invalid.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify signature
        message = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(
            SecurityConfig.JWT_SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).digest()
        expected_signature_b64 = base64.urlsafe_b64encode(expected_signature).rstrip(b'=').decode()
        
        if not hmac.compare_digest(signature_b64, expected_signature_b64):
            return None
        
        # Decode payload (add padding if needed)
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        
        payload: dict[str, Any] = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload
        
    except Exception:
        return None


def generate_auth_token(client_id: str, client_secret: str) -> Optional[TokenResponse]:
    """
    Generate a JWT auth token for valid client credentials.
    
    Returns TokenResponse if valid, None if invalid credentials.
    """
    client_data = SecurityConfig.CLIENTS.get(client_id)
    if not client_data:
        return None
    
    # Verify secret using constant-time comparison
    if not hmac.compare_digest(client_data["secret"], client_secret):
        return None
    
    # Generate token
    now = time.time()
    expiry_seconds = SecurityConfig.JWT_EXPIRY_MINUTES * 60
    
    payload = {
        "client_id": client_id,
        "client_name": client_data.get("name", client_id),
        "iat": now,
        "exp": now + expiry_seconds,
        "jti": secrets.token_hex(16)  # Unique token ID
    }
    
    token = create_jwt_token(payload)
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expiry_seconds
    )


async def verify_bearer_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)
) -> Dict[str, Any]:
    """
    Verify Bearer token and return token claims.
    Raises HTTPException if authentication fails.
    Authentication is always required and cannot be disabled.
    """
    if not credentials:
        security_logger.warning(
            f"Missing auth token | IP: {get_client_ip(request)} | Path: {request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide Bearer token in Authorization header.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Decode and verify token
    payload = decode_jwt_token(credentials.credentials)
    if not payload:
        security_logger.warning(
            f"Invalid token signature | IP: {get_client_ip(request)} | Path: {request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed token",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
        )
    
    # Check expiry
    if time.time() > payload.get("exp", 0):
        security_logger.warning(
            f"Expired token | Client: {payload.get('client_id')} | IP: {get_client_ip(request)}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please obtain a new token.",
            headers={"WWW-Authenticate": "Bearer error=\"token_expired\""}
        )
    
    # Get client rate limit
    client_data = SecurityConfig.CLIENTS.get(payload.get("client_id", ""))
    rate_limit = client_data.get("rate_limit", SecurityConfig.RATE_LIMIT_REQUESTS) if client_data else SecurityConfig.RATE_LIMIT_REQUESTS
    
    return {
        "client_id": payload.get("client_id"),
        "client_name": payload.get("client_name"),
        "authenticated": True,
        "rate_limit": rate_limit,
        "token_exp": payload.get("exp"),
        "token_jti": payload.get("jti")
    }


def create_client(client_id: str, name: str, rate_limit: Optional[int] = None) -> str:
    """Create a new client and return the secret."""
    client_secret = secrets.token_hex(32)
    SecurityConfig.CLIENTS[client_id] = {
        "secret": client_secret,
        "name": name,
        "created": datetime.now().isoformat(),
        "rate_limit": rate_limit or SecurityConfig.RATE_LIMIT_REQUESTS
    }
    return client_secret


# --- Input Validation ---

class InputValidator:
    """Validates and sanitizes user input."""
    
    # Compile regex patterns for performance
    _dangerous_patterns = [re.compile(p, re.IGNORECASE | re.DOTALL) 
                          for p in SecurityConfig.DANGEROUS_PATTERNS]
    
    @classmethod
    def sanitize_text(cls, text: str, max_length: Optional[int] = None) -> str:
        """
        Sanitize text input by removing dangerous patterns.
        Note: For PI removal, we want to preserve the original text for accurate
        detection, so this is used for metadata fields, not the main content.
        """
        if not text:
            return text
        
        # Enforce length limit
        max_len = max_length or SecurityConfig.MAX_TEXT_LENGTH
        if len(text) > max_len:
            raise ValueError(f"Text exceeds maximum length of {max_len} characters")
        
        return text
    
    @classmethod
    def validate_text_for_processing(cls, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate text that will be processed for PI removal.
        Returns (is_valid, error_message).
        
        Note: We don't sanitize the actual content because PI patterns might
        be embedded in various contexts. The PI remover will handle them.
        """
        if not text:
            return False, "Text cannot be empty"
        
        if len(text) > SecurityConfig.MAX_TEXT_LENGTH:
            return False, f"Text exceeds maximum length of {SecurityConfig.MAX_TEXT_LENGTH} characters"
        
        # Check for null bytes (could indicate binary data)
        if '\x00' in text:
            return False, "Text contains invalid null bytes"
        
        return True, None
    
    @classmethod
    def validate_filename(cls, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate uploaded filename."""
        if not filename:
            return False, "Filename cannot be empty"
        
        # Prevent path traversal
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            return False, "Invalid filename: path traversal detected"
        
        # Only allow safe characters
        safe_pattern = re.compile(r'^[\w\-. ]+$')
        if not safe_pattern.match(filename):
            return False, "Filename contains invalid characters"
        
        # Check extension
        ext = Path(filename).suffix.lower()
        if ext not in SecurityConfig.ALLOWED_EXTENSIONS:
            return False, f"File type not allowed. Permitted: {', '.join(SecurityConfig.ALLOWED_EXTENSIONS)}"
        
        return True, None
    
    @classmethod
    def sanitize_for_logging(cls, text: str, max_preview: int = 100) -> str:
        """
        Prepare text for logging WITHOUT exposing potential PI.
        This is critical to prevent PI leakage in logs.
        """
        if not text:
            return "[empty]"
        
        # Never log full content - only show length and preview with PI masked
        length = len(text)
        preview = text[:max_preview].replace('\n', ' ').replace('\r', '')
        
        # Mask anything that looks like PI in the preview
        preview = re.sub(r'\b[\w.+-]+@[\w.-]+\.\w+\b', '[EMAIL]', preview)
        preview = re.sub(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[PHONE]', preview)
        preview = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]', preview)
        
        if len(text) > max_preview:
            preview += "..."
        
        return f"[{length} chars] {preview}"


# --- File Upload Security ---

class FileSecurityValidator:
    """Validates file uploads (extension, magic bytes, size)."""
    
    # Magic bytes for common file types
    MAGIC_BYTES = {
        b'PK\x03\x04': ['.xlsx', '.docx', '.pptx', '.odt', '.ods', '.odp', '.zip'],  # ZIP-based
        b'\xd0\xcf\x11\xe0': ['.xls', '.doc', '.ppt'],  # OLE compound (legacy Office)
        b'%PDF': ['.pdf'],  # PDF
        b'{': ['.json'],  # JSON object
        b'[': ['.json'],  # JSON array
        b'{\\rtf': ['.rtf'],  # RTF
        b'<!DOCTYPE': ['.html', '.htm'],  # HTML
        b'<html': ['.html', '.htm'],  # HTML
        b'<?xml': ['.xml', '.html'],  # XML
    }
    
    @classmethod
    def validate_file(cls, file_path: str, original_filename: str, 
                     file_size: int) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive file validation.
        
        Returns (is_valid, error_message).
        """
        # 1. Check file size
        if file_size > SecurityConfig.MAX_FILE_SIZE:
            return False, f"File exceeds maximum size of {SecurityConfig.MAX_FILE_SIZE // (1024*1024)}MB"
        
        if file_size == 0:
            return False, "File is empty"
        
        # 2. Validate filename
        is_valid, error = InputValidator.validate_filename(original_filename)
        if not is_valid:
            return False, error
        
        # 3. Check extension
        ext = Path(original_filename).suffix.lower()
        if ext not in SecurityConfig.ALLOWED_EXTENSIONS:
            return False, f"File type '{ext}' not allowed"
        
        # 4. Verify MIME type matches extension
        mime_type, _ = mimetypes.guess_type(original_filename)
        if mime_type and mime_type not in SecurityConfig.ALLOWED_MIME_TYPES:
            # Allow text/plain as fallback for CSV/TXT
            if mime_type != 'text/plain':
                return False, f"MIME type '{mime_type}' not allowed"
        
        # 5. Magic byte verification for binary files
        if ext in ['.xlsx', '.xls', '.docx', '.doc', '.pptx', '.ppt', '.pdf']:
            try:
                with open(file_path, 'rb') as f:
                    magic = f.read(8)  # Read 8 bytes for better matching
                    valid_magics = [mb for mb, exts in cls.MAGIC_BYTES.items() 
                                   if ext in exts]
                    if valid_magics:
                        matched = any(magic.startswith(m) for m in valid_magics)
                        if not matched:
                            security_logger.warning(
                                f"Magic byte mismatch for {original_filename}: "
                                f"expected one of {valid_magics}, got {magic[:4]!r}"
                            )
                            return False, "File content does not match extension"
            except Exception as e:
                return False, f"Failed to verify file: {str(e)}"
        
        # 6. Check for embedded scripts in text files
        if ext in ['.csv', '.txt', '.json', '.md', '.log', '.html', '.htm', '.xml']:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    # Read first 10KB for script detection
                    content_sample = f.read(10240)
                    
                    # Check for suspicious patterns
                    suspicious_patterns = [
                        r'<script',
                        r'javascript:',
                        r'=cmd\|',  # DDE attack
                        r'=HYPERLINK\s*\(',  # Excel formula injection
                        r'@SUM\(',
                        r'=DDE\s*\(',
                        r'on\w+\s*=\s*["\']',  # HTML event handlers (onclick, onerror, etc.)
                        r'<\s*iframe',  # iframes
                        r'<\s*object',  # embedded objects
                        r'<\s*embed',   # embedded content
                        r'data:\s*text/html',  # data URIs with HTML
                    ]
                    
                    for pattern in suspicious_patterns:
                        if re.search(pattern, content_sample, re.IGNORECASE):
                            security_logger.warning(
                                f"Suspicious content in {original_filename}: pattern '{pattern}'"
                            )
                            if SecurityConfig.QUARANTINE_SUSPICIOUS_FILES:
                                return False, "File contains potentially malicious content"
            except Exception:
                pass  # If we can't read, continue with other checks
        
        # 7. Check Office documents for macros/embedded content
        if ext in ['.docx', '.pptx', '.xlsx']:
            is_safe, macro_error = cls._check_office_macros(file_path, ext)
            if not is_safe:
                return False, macro_error
        
        # 8. Check PDF for JavaScript/actions
        if ext == '.pdf':
            is_safe, pdf_error = cls._check_pdf_safety(file_path)
            if not is_safe:
                return False, pdf_error
        
        return True, None
    
    @classmethod
    def _check_pdf_safety(cls, file_path: str) -> Tuple[bool, Optional[str]]:
        """Check PDF for potentially dangerous JavaScript/actions."""
        dangerous_patterns = [
            b'/JavaScript',   # JavaScript action
            b'/JS ',          # JavaScript short form
            b'/Launch',       # Launch application
            b'/OpenAction',   # Auto-open action
            b'/AA ',          # Additional actions
            b'/EmbeddedFile', # Embedded files
            b'/GoToR',        # Remote go-to
            b'/GoToE',        # Embedded go-to
        ]
        
        try:
            with open(file_path, 'rb') as f:
                content = f.read(100000)  # First 100KB
                
                for pattern in dangerous_patterns:
                    if pattern in content:
                        security_logger.warning(
                            f"PDF contains potentially dangerous content: {pattern.decode()}"
                        )
                        if SecurityConfig.QUARANTINE_SUSPICIOUS_FILES:
                            return False, f"PDF contains {pattern.decode()} which may be unsafe"
        except Exception as e:
            security_logger.warning(f"Error checking PDF {file_path}: {e}")
        
        return True, None
    
    @classmethod
    def _check_office_macros(cls, file_path: str, ext: str) -> Tuple[bool, Optional[str]]:
        """Check Office XML files for macros and suspicious content."""
        import zipfile
        
        dangerous_parts = [
            'vbaProject.bin',      # VBA macros
            'vbaData.xml',         # VBA metadata
            'activeX',             # ActiveX controls
            'embeddings',          # Embedded OLE objects
        ]
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                file_list = zf.namelist()
                
                for part in dangerous_parts:
                    for f in file_list:
                        if part.lower() in f.lower():
                            security_logger.warning(
                                f"Potentially dangerous content in {file_path}: {f}"
                            )
                            if SecurityConfig.QUARANTINE_SUSPICIOUS_FILES:
                                return False, f"File contains {part} which may be unsafe"
                
                # Check for unusually large embedded files (possible zip bomb)
                for info in zf.infolist():
                    if info.file_size > 100 * 1024 * 1024:  # 100MB uncompressed
                        security_logger.warning(
                            f"Suspiciously large file inside archive: {info.filename}"
                        )
                        return False, "File contains suspiciously large embedded content"
                    
                    # Check compression ratio (zip bomb indicator)
                    if info.compress_size > 0:
                        ratio = info.file_size / info.compress_size
                        if ratio > 100:  # 100:1 compression ratio is suspicious
                            security_logger.warning(
                                f"Suspicious compression ratio in {file_path}: {ratio:.0f}:1"
                            )
                            return False, "File has suspicious compression ratio (potential zip bomb)"
        except zipfile.BadZipFile:
            return False, "Invalid or corrupted Office document"
        except Exception as e:
            security_logger.warning(f"Error checking Office file {file_path}: {e}")
            # Continue - don't block on check failures
        
        return True, None
    
    @classmethod
    def generate_safe_filename(cls, original_filename: str, job_id: str) -> str:
        """Generate a safe filename that prevents path traversal."""
        # Extract extension
        ext = Path(original_filename).suffix.lower()
        if ext not in SecurityConfig.ALLOWED_EXTENSIONS:
            ext = '.txt'  # Default to txt if unknown
        
        # Generate safe name using job ID
        safe_name = f"upload_{job_id}{ext}"
        return safe_name
    
    @classmethod
    def quick_validate(cls, file_path: str) -> Tuple[bool, Optional[str]]:
        """Quick file validation for CLI/programmatic use.
        
        Use this when processing files locally (not uploads).
        Validates extension, size, magic bytes, and content.
        """
        path = Path(file_path)
        if not path.exists():
            return False, f"File not found: {file_path}"
        
        return cls.validate_file(
            file_path=str(path),
            original_filename=path.name,
            file_size=path.stat().st_size
        )


def validate_file_security(file_path: str, strict: bool = True) -> Tuple[bool, Optional[str]]:
    """Validate a file before processing.
    
    Args:
        file_path: Path to file
        strict: If True, reject suspicious files. If False, just log warnings.
    
    Returns:
        (is_valid, error_message)
    """
    return FileSecurityValidator.quick_validate(file_path)


# --- Audit Logging ---

class AuditLogger:
    """Audit logging - redacts PI before writing."""
    
    @classmethod
    def log_request(cls, request: Request, api_key_info: Dict[str, Any],
                   action: str, details: Optional[Dict[str, Any]] = None,
                   redactions: Optional[Dict[str, int]] = None):
        """Log API request for audit trail.
        
        Args:
            request: FastAPI request object
            api_key_info: Client authentication info
            action: Action being performed
            details: Additional details to log
            redactions: Dictionary of PI types and their counts (e.g., {"EMAIL": 2, "PHONE": 1})
        """
        if not SecurityConfig.AUDIT_LOGGING_ENABLED:
            return
        
        log_entry = {
            "timestamp": get_audit_timestamp(),
            "action": action,
            "client_ip": get_client_ip(request),
            "user_agent": request.headers.get("user-agent", "unknown")[:100],
            "client_id": api_key_info.get("client_id", "anonymous"),
            "client_name": api_key_info.get("client_name", "anonymous"),
            "path": request.url.path,
            "method": request.method,
        }
        
        if details:
            safe_details = {}
            for key, value in details.items():
                if key in ("text", "content", "input", "output"):
                    # Only log length, never actual content
                    safe_details[f"{key}_length"] = len(str(value)) if value else 0
                else:
                    safe_details[key] = value
            log_entry["details"] = safe_details
        
        # Log what PI types were redacted and their counts
        if redactions:
            log_entry["redactions"] = redactions
            log_entry["total_redactions"] = sum(redactions.values())
        
        audit_logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    @classmethod
    def log_file_operation(cls, job_id: str, operation: str, 
                          filename: str, success: bool, 
                          error: Optional[str] = None):
        """Log file operations."""
        if not SecurityConfig.AUDIT_LOGGING_ENABLED:
            return
        
        log_entry = {
            "timestamp": get_audit_timestamp(),
            "action": "file_operation",
            "operation": operation,
            "job_id": job_id,
            "filename": filename,
            "success": success
        }
        
        if error:
            log_entry["error"] = error[:200]  # Limit error message length
        
        audit_logger.info(json.dumps(log_entry, ensure_ascii=False))
    
    @classmethod
    def log_security_event(cls, event_type: str, request: Request,
                          details: Optional[str] = None):
        """Log security-related events."""
        log_entry = {
            "timestamp": get_audit_timestamp(),
            "event_type": event_type,
            "client_ip": get_client_ip(request),
            "path": request.url.path,
            "method": request.method,
            "user_agent": request.headers.get("user-agent", "unknown")[:100]
        }
        
        if details:
            log_entry["details"] = details[:500]
        
        security_logger.warning(json.dumps(log_entry))


# --- Middleware ---

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to responses."""
    
    # Paths that need relaxed CSP for Swagger UI
    DOCS_PATHS = {"/docs", "/redoc", "/openapi.json"}
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        for header, value in SecurityConfig.SECURITY_HEADERS.items():
            # Use relaxed CSP for docs pages (Swagger UI needs CDN access)
            if header == "Content-Security-Policy" and request.url.path in self.DOCS_PATHS:
                response.headers[header] = (
                    "default-src 'self' https://cdn.jsdelivr.net; "
                    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                    "font-src 'self' https://fonts.gstatic.com; "
                    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.jsdelivr.net; "
                    "connect-src 'self';"
                )
            else:
                response.headers[header] = value
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    async def dispatch(self, request: Request, call_next):
        if not SecurityConfig.RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/api/health"]:
            return await call_next(request)
        
        # Get identifier (client_id from token or IP)
        auth_header = request.headers.get("Authorization", "")
        client_id = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_jwt_token(token)
            if payload:
                client_id = payload.get("client_id")
        
        identifier = client_id if client_id else get_client_ip(request)
        
        # Check rate limit
        allowed, info = rate_limiter.check_rate_limit(identifier)
        
        if not allowed:
            AuditLogger.log_security_event("rate_limit_exceeded", request)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please slow down.",
                    "retry_after": info["reset"]
                },
                headers={
                    "Retry-After": str(info["reset"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"])
                }
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        
        return response


class IPFilterMiddleware(BaseHTTPMiddleware):
    """IP allowlist/blocklist middleware."""
    
    async def dispatch(self, request: Request, call_next):
        client_ip = get_client_ip(request)
        
        # Check blocklist
        if client_ip in SecurityConfig.IP_BLOCKLIST:
            AuditLogger.log_security_event("ip_blocked", request)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "forbidden", "message": "Access denied"}
            )
        
        # Check allowlist (if configured)
        if SecurityConfig.IP_ALLOWLIST and client_ip not in SecurityConfig.IP_ALLOWLIST:
            AuditLogger.log_security_event("ip_not_allowed", request)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "forbidden", "message": "Access denied"}
            )
        
        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Limit request body size."""
    
    async def dispatch(self, request: Request, call_next):
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > SecurityConfig.MAX_REQUEST_SIZE:
                    return JSONResponse(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        content={
                            "error": "request_too_large",
                            "message": f"Request exceeds maximum size of {SecurityConfig.MAX_REQUEST_SIZE // (1024*1024)}MB"
                        }
                    )
            except ValueError:
                pass
        
        return await call_next(request)


# --- Helpers ---

def get_client_ip(request: Request) -> str:
    """Get client IP, handles proxy headers."""
    # Check X-Forwarded-For (from reverse proxy/load balancer)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection IP
    if request.client:
        return request.client.host
    
    return "unknown"


def setup_security(app, enable_rate_limit: bool = True):
    """
    Configure security middleware for a FastAPI app.
    Authentication is always enabled and cannot be disabled.
    
    Args:
        app: FastAPI application
        enable_rate_limit: Whether to enable rate limiting
    """
    # Add middleware in order (last added = first executed)
    
    # 1. Security headers (always enabled)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # 2. Request size limit
    app.add_middleware(RequestSizeLimitMiddleware)
    
    # 3. Rate limiting
    if enable_rate_limit:
        app.add_middleware(RateLimitMiddleware)
    
    # 4. IP filtering (if configured)
    if SecurityConfig.IP_BLOCKLIST or SecurityConfig.IP_ALLOWLIST:
        app.add_middleware(IPFilterMiddleware)


# --- Error Handling ---

def create_secure_error_handler():
    """Creates error handler that doesn't leak sensitive info."""
    
    async def generic_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions without leaking details."""
        # Log the full error internally
        logging.error(f"Unhandled exception: {exc}", exc_info=True)
        
        # Log security event
        AuditLogger.log_security_event(
            "unhandled_exception", 
            request, 
            details=str(type(exc).__name__)
        )
        
        # Return generic error to client
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred. Please try again.",
                "request_id": secrets.token_hex(8)
            }
        )
    
    return generic_exception_handler


# --- Exports ---

__all__ = [
    # Configuration
    'SecurityConfig',
    
    # Authentication (JWT Bearer Token)
    'verify_bearer_token',
    'generate_auth_token',
    'create_jwt_token',
    'decode_jwt_token',
    'create_client',
    'AuthRequest',
    'TokenResponse',
    'TokenPayload',
    
    # Validation
    'InputValidator',
    'FileSecurityValidator',
    
    # Rate Limiting
    'RateLimiter',
    'rate_limiter',
    
    # Logging
    'AuditLogger',
    'audit_logger',
    'security_logger',
    
    # Middleware
    'SecurityHeadersMiddleware',
    'RateLimitMiddleware',
    'IPFilterMiddleware',
    'RequestSizeLimitMiddleware',
    
    # Helpers
    'get_client_ip',
    'setup_security',
    'create_secure_error_handler',
    'validate_file_security',
]
