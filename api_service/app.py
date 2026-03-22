"""
PI Remover API - REST endpoint for text redaction.

Main endpoints:
- POST /dev/v1/redact - redact single text
- POST /dev/v1/redact/batch - redact multiple texts
- POST /dev/auth/token - get auth token

Run: uvicorn app:app --host 0.0.0.0 --port 8080
"""

import os
import sys
import time
import uuid
import secrets
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# Add parent directory to path to import pi_remover package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

# Import from consolidated pi_remover package
from pi_remover import (
    PIRemover,
    PIRemoverConfig,
    SecurityConfig,
)
from pi_remover.core import (
    Redaction,
    RedactionResult,
    __version__
)
from pi_remover.security import (
    verify_bearer_token,
    generate_auth_token,
    revoke_token,
    AuthRequest,
    TokenResponse,
    InputValidator,
    AuditLogger,
    setup_security,
    create_secure_error_handler,
    get_client_ip,
)

# Prometheus metrics (optional - graceful fallback if not installed)
try:
    from prometheus_metrics import (
        metrics as prom_metrics,
        create_metrics_endpoint,
        PROMETHEUS_AVAILABLE,
    )
except ImportError:
    prom_metrics = None
    PROMETHEUS_AVAILABLE = False
    create_metrics_endpoint = None
    logging.getLogger(__name__).info("prometheus_metrics module not available")

# --- Config ---

# Environment variables
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
MAX_TEXT_LENGTH = SecurityConfig.MAX_TEXT_LENGTH
MAX_BATCH_SIZE = SecurityConfig.MAX_BATCH_SIZE
ENABLE_METRICS = os.environ.get("ENABLE_METRICS", "true").lower() == "true"
# NER is ON by default - set to "false" to disable for faster processing
ENABLE_NER = os.environ.get("ENABLE_NER", "true").lower() == "true"
# Security settings (auth is always enabled - cannot be disabled)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

# API Prefix based on environment (e.g., /dev/v1/redact or /prod/v1/redact)
API_PREFIX = "/dev" if ENVIRONMENT == "development" else "/prod"

# Optional endpoint toggles - disabled by default for security
# See docs/HOWTO.md for usage
ENABLE_BATCH_ENDPOINT = os.environ.get("ENABLE_BATCH_ENDPOINT", "false").lower() == "true"
ENABLE_HEALTH_ENDPOINT = os.environ.get("ENABLE_HEALTH_ENDPOINT", "false").lower() == "true"
ENABLE_DOCS_ENDPOINT = os.environ.get("ENABLE_DOCS_ENDPOINT", "false").lower() == "true"
ENABLE_MONITORING_ENDPOINTS = os.environ.get("ENABLE_MONITORING_ENDPOINTS", "false").lower() == "true"

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("pi-gateway")

# --- OpenAPI Security Scheme ---

from fastapi.openapi.utils import get_openapi

API_DESCRIPTION = """
## PI Remover API

Secure API for removing Personal Information (PI) from text before sending to LLMs.

### Authentication

All endpoints except `/auth/token` require Bearer token authentication.

**Steps:**
1. `POST /auth/token` with your credentials to get a token
2. Click **Authorize** (top right) and enter the token
3. Test the endpoints
"""

# --- App ---

from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="PI Remover API",
    description=API_DESCRIPTION,
    version=__version__,
    docs_url=None,  # Disable default docs, we'll add custom route
    redoc_url=None  # Disable default redoc, we'll add custom route
)


# Custom Swagger UI HTML template
SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PI Remover API - Swagger UI</title>
    <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png">
    <style>
        body { margin: 0; padding: 0; }
        .swagger-ui .topbar { display: none; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: "/openapi.json",
                dom_id: "#swagger-ui",
                layout: "BaseLayout",
                deepLinking: true,
                showExtensions: true,
                showCommonExtensions: true,
                persistAuthorization: true,
                displayRequestDuration: true,
                filter: true,
                tryItOutEnabled: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ]
            });
            window.ui = ui;
        };
    </script>
</body>
</html>
"""


# Custom docs endpoint with proper Swagger UI
# Controlled by ENABLE_DOCS_ENDPOINT feature flag (default: disabled)
if ENABLE_DOCS_ENDPOINT:
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """Serve Swagger UI with proper configuration."""
        if ENVIRONMENT != "development":
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        return HTMLResponse(content=SWAGGER_UI_HTML, media_type="text/html")


if ENABLE_DOCS_ENDPOINT:
    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_html():
        """Serve ReDoc with proper configuration."""
        if ENVIRONMENT != "development":
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{app.title} - ReDoc"
        )


def custom_openapi():
    """Custom OpenAPI schema with Bearer token security scheme."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token obtained from /auth/token endpoint"
        }
    }
    
    # Apply security to all paths except /auth/token
    for path, path_item in openapi_schema["paths"].items():
        # Skip auth endpoint
        if "/auth/token" in path:
            continue
        for method in path_item:
            if method in ["get", "post", "put", "delete", "patch"]:
                # Add security requirement
                openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Pylance/type checkers treat FastAPI.openapi as a method; use setattr to avoid
# method-assignment errors while preserving runtime behavior.
setattr(app, "openapi", custom_openapi)

# --- Security ---

# Rate limiting, headers, size limits
setup_security(
    app, 
    enable_rate_limit=SecurityConfig.RATE_LIMIT_ENABLED
)

# CORS middleware - restrict in production
allowed_origins = SecurityConfig.CORS_ORIGINS
if ENVIRONMENT == "production" and "*" in allowed_origins:
    logger.error(
        "CORS is set to allow all origins in production! "
        "Falling back to restrictive default. Set CORS_ORIGINS env var."
    )
    allowed_origins = []  # Block all cross-origin requests until explicitly configured

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=SecurityConfig.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST"],  # Restrict to only needed methods
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Correlation-ID"],
)

# Request logging middleware with correlation IDs
try:
    from shared.logging_config import RequestLoggingMiddleware
    app.add_middleware(RequestLoggingMiddleware, service_name='pi-gateway-api')
    logger.info("Request logging middleware enabled with correlation IDs")
except ImportError:
    logger.debug("shared.logging_config not available, request logging middleware disabled")

# Add secure error handler
app.add_exception_handler(Exception, create_secure_error_handler())

# --- Metrics ---

class Metrics:
    def __init__(self):
        self.start_time = time.time()
        self.requests_processed = 0
        self.total_processing_time_ms = 0.0
        self.errors = 0

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def avg_latency_ms(self) -> float:
        if self.requests_processed == 0:
            return 0.0
        return float(round(self.total_processing_time_ms / self.requests_processed, 2))

    def record_request(self, processing_time_ms: float):
        self.requests_processed += 1
        self.total_processing_time_ms += processing_time_ms

    def record_error(self):
        self.errors += 1

metrics = Metrics()

# --- spaCy Models ---

# Allowed spaCy models whitelist
ALLOWED_SPACY_MODELS = ["en_core_web_sm", "en_core_web_md", "en_core_web_lg", "en_core_web_trf"]
DEFAULT_SPACY_MODEL = "en_core_web_lg"

# Model availability cache (checked at startup)
_available_models: Dict[str, bool] = {}

# PIRemover instance cache (lazy loaded per model)
_remover_cache: Dict[str, 'PIRemover'] = {}
_cache_lock = None  # Will be set if threading is needed

def check_available_models() -> Dict[str, bool]:
    """Check which spaCy models are installed on the system."""
    global _available_models
    if _available_models:
        return _available_models
    
    import importlib.util
    for model in ALLOWED_SPACY_MODELS:
        # Check if model package is installed
        model_pkg = model.replace("-", "_")
        spec = importlib.util.find_spec(model_pkg)
        _available_models[model] = spec is not None
        if spec is not None:
            logger.info(f"spaCy model available: {model}")
        else:
            logger.debug(f"spaCy model not installed: {model}")
    
    return _available_models

def get_remover_for_model(model_name: str, enable_ner: bool = True) -> tuple:
    """
    Get or create a PIRemover instance for the specified model.
    Returns (remover, actual_model_used, fallback_occurred)
    """
    global _remover_cache
    
    # If NER disabled, use a single fast-mode remover
    if not enable_ner:
        cache_key = "__fast_mode__"
        if cache_key not in _remover_cache:
            fast_config = PIRemoverConfig(
                enable_ner=False,
                enable_regex=True,
                enable_dictionaries=True,
                enable_context_rules=True,
                enable_data_cleaning=True,
                use_typed_tokens=True,
            )
            _remover_cache[cache_key] = PIRemover(fast_config)
            logger.info("Created fast-mode PIRemover (NER disabled)")
        return _remover_cache[cache_key], None, False
    
    # Validate model name
    actual_model = model_name
    fallback = False
    
    if model_name not in ALLOWED_SPACY_MODELS:
        logger.warning(f"Invalid model '{model_name}', falling back to {DEFAULT_SPACY_MODEL}")
        actual_model = DEFAULT_SPACY_MODEL
        fallback = True
    elif not _available_models.get(model_name, False):
        logger.warning(f"Model '{model_name}' not installed, falling back to {DEFAULT_SPACY_MODEL}")
        actual_model = DEFAULT_SPACY_MODEL
        fallback = True
        
        # If default is also not available, try to find any available model
        if not _available_models.get(DEFAULT_SPACY_MODEL, False):
            for model in ALLOWED_SPACY_MODELS:
                if _available_models.get(model, False):
                    actual_model = model
                    logger.warning(f"Default model not available, using {actual_model}")
                    break
            else:
                # No models available, disable NER
                logger.error("No spaCy models available, disabling NER")
                return get_remover_for_model(model_name, enable_ner=False)
    
    # Check cache
    cache_key = f"ner_{actual_model}"
    if cache_key not in _remover_cache:
        ner_config = PIRemoverConfig(
            enable_ner=True,
            enable_regex=True,
            enable_dictionaries=True,
            enable_context_rules=True,
            enable_data_cleaning=True,
            use_typed_tokens=True,
            spacy_model=actual_model,  # Pass model to config
        )
        _remover_cache[cache_key] = PIRemover(ner_config)
        logger.info(f"Created PIRemover with spaCy model: {actual_model}")
    
    return _remover_cache[cache_key], actual_model, fallback

# --- Default remover ---

# NER on by default, use ENABLE_NER=false for speed
config = PIRemoverConfig(
    enable_ner=ENABLE_NER,      # NER ON by default, toggle via env var
    enable_regex=True,
    enable_dictionaries=True,
    enable_context_rules=True,
    enable_data_cleaning=True,
    use_typed_tokens=True,
)

# Initialize default PIRemover at startup (will be cached)
remover = PIRemover(config)
mode_str = "FULL (NER enabled)" if ENABLE_NER else "FAST (NER disabled)"
logger.info(f"PI Remover initialized in {mode_str} mode (v{__version__})")

# --- Request/Response Models ---

class RedactConfig(BaseModel):
    """Redaction options."""
    redact_emails: bool = True
    redact_phones: bool = True
    redact_names: bool = True
    redact_emp_ids: bool = True
    redact_asset_ids: bool = True
    redact_ip_addresses: bool = True
    redact_urls: bool = True
    redact_credentials: bool = True
    use_typed_tokens: bool = True


class RedactRequest(BaseModel):
    """Request body for single text redaction."""
    text: str = Field(..., description="Text to redact", max_length=MAX_TEXT_LENGTH)
    config: Optional[RedactConfig] = Field(default=None, description="Override default config")
    include_details: bool = Field(default=False, description="Include detailed redaction info")
    request_id: Optional[str] = Field(default=None, description="Client-provided request ID", max_length=64)
    enable_ner: bool = Field(default=True, description="Enable NER for name detection (set False for fast mode)")
    spacy_model: Optional[str] = Field(
        default=None, 
        description=f"spaCy model to use. Allowed: {ALLOWED_SPACY_MODELS}. Default: {DEFAULT_SPACY_MODEL}"
    )
    
    @validator('text')
    def validate_text(cls, v):
        """Validate text input."""
        is_valid, error = InputValidator.validate_text_for_processing(v)
        if not is_valid:
            raise ValueError(error)
        return v
    
    @validator('request_id')
    def validate_request_id(cls, v):
        """Validate request ID is alphanumeric."""
        if v and not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError("request_id must be alphanumeric with hyphens/underscores only")
        return v
    
    @validator('spacy_model')
    def validate_spacy_model(cls, v):
        """Validate spaCy model name (warning only, will fallback)."""
        # We allow any value here - validation and fallback happens at runtime
        return v


class RedactResponse(BaseModel):
    """Response for single text redaction."""
    redacted_text: str
    request_id: str
    processing_time_ms: float
    redactions: Optional[List[Dict[str, Any]]] = None
    mode: str = Field(description="Processing mode: 'full' (NER enabled) or 'fast' (NER disabled)")
    spacy_model: Optional[str] = Field(default=None, description="spaCy model used for NER (null if fast mode)")
    used_fallback: bool = Field(default=False, description="True if requested model was unavailable and fallback was used")


class BatchRedactRequest(BaseModel):
    """Request body for batch redaction."""
    texts: List[str] = Field(..., description="List of texts to redact", max_length=MAX_BATCH_SIZE)
    config: Optional[RedactConfig] = Field(default=None, description="Override default config")
    include_details: bool = Field(default=False, description="Include detailed redaction info")
    enable_ner: bool = Field(default=True, description="Enable NER for name detection (set False for fast mode)")
    spacy_model: Optional[str] = Field(
        default=None, 
        description=f"spaCy model to use. Allowed: {ALLOWED_SPACY_MODELS}. Default: {DEFAULT_SPACY_MODEL}"
    )
    
    @validator('texts')
    def validate_texts(cls, v):
        """Validate all texts in batch."""
        for i, text in enumerate(v):
            is_valid, error = InputValidator.validate_text_for_processing(text)
            if not is_valid:
                raise ValueError(f"Text at index {i}: {error}")
        return v


class BatchResult(BaseModel):
    """Single result in batch response."""
    redacted_text: str
    index: int
    redactions: Optional[List[Dict[str, Any]]] = None


class BatchRedactResponse(BaseModel):
    """Response for batch redaction."""
    results: List[BatchResult]
    request_id: str
    total_count: int
    processing_time_ms: float
    mode: str = Field(description="Processing mode: 'full' (NER enabled) or 'fast' (NER disabled)")
    spacy_model: Optional[str] = Field(default=None, description="spaCy model used for NER (null if fast mode)")
    used_fallback: bool = Field(default=False, description="True if requested model was unavailable and fallback was used")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    mode: str
    ner_available: bool
    available_models: List[str] = Field(description="List of installed spaCy models")
    default_model: str = Field(description="Default spaCy model used")
    uptime_seconds: int
    requests_processed: int
    avg_latency_ms: float
    errors: int


class PITypeInfo(BaseModel):
    """PI type information."""
    type: str
    token: str
    description: str


class PITypesResponse(BaseModel):
    """List of supported PI types."""
    pi_types: List[PITypeInfo]


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    message: str
    request_id: str


class ModelInfo(BaseModel):
    """spaCy model information."""
    name: str = Field(description="Model name (e.g., en_core_web_lg)")
    installed: bool = Field(description="Whether the model is installed")
    is_default: bool = Field(description="Whether this is the default model")
    description: str = Field(description="Model description")


class ModelsResponse(BaseModel):
    """List of available spaCy models."""
    models: List[ModelInfo] = Field(description="List of all supported spaCy models")
    installed_count: int = Field(description="Number of installed models")
    default_model: str = Field(description="Default model used when not specified")
    ner_enabled: bool = Field(description="Whether NER is enabled in current config")


# --- Auth Endpoints ---

# H7: Simple in-memory rate limiter for auth endpoint
_auth_attempts: Dict[str, list] = {}
_AUTH_RATE_LIMIT = 10  # max requests per window
_AUTH_RATE_WINDOW = 60  # seconds


def _check_auth_rate_limit(client_ip: str) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    import time
    now = time.time()
    if client_ip not in _auth_attempts:
        _auth_attempts[client_ip] = []
    # Clean old entries
    _auth_attempts[client_ip] = [
        t for t in _auth_attempts[client_ip] if now - t < _AUTH_RATE_WINDOW
    ]
    if len(_auth_attempts[client_ip]) >= _AUTH_RATE_LIMIT:
        return False
    _auth_attempts[client_ip].append(now)
    return True


@app.post(f"{API_PREFIX}/auth/token", response_model=TokenResponse, responses={
    401: {"model": ErrorResponse},
    429: {"model": ErrorResponse}
}, tags=["Authentication"])
async def obtain_token(request: Request, body: AuthRequest):
    """
    Obtain a Bearer token for API authentication.
    
    Provide client_id and client_secret to receive a JWT token.
    Token expires in 30 minutes (configurable via JWT_EXPIRY_MINUTES).
    
    Use the token in subsequent requests:
    ```
    Authorization: Bearer <token>
    ```
    """
    # Rate limit check for auth endpoint (H7)
    client_ip = request.client.host if request.client else "unknown"
    if not _check_auth_rate_limit(client_ip):
        AuditLogger.log_security_event(
            "auth_rate_limited",
            request,
            details=f"Auth rate limit exceeded for IP: {client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many authentication attempts. Try again in {_AUTH_RATE_WINDOW} seconds."
        )
    
    # Audit log (without secret)
    AuditLogger.log_request(
        request,
        {"client_id": body.client_id, "authenticated": False},
        "token_request",
        {"client_id": body.client_id}
    )
    
    # Generate token
    token_response = generate_auth_token(body.client_id, body.client_secret)
    
    if not token_response:
        AuditLogger.log_security_event(
            "token_auth_failed",
            request,
            details=f"Invalid credentials for client: {body.client_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    logger.info(f"Token issued for client: {body.client_id}")
    return token_response


# H3: Token revocation endpoint
@app.post(f"{API_PREFIX}/auth/revoke", responses={
    200: {"description": "Token revoked successfully"},
    401: {"model": ErrorResponse}
}, tags=["Authentication"])
async def revoke_auth_token(
    request: Request,
    auth_info: Dict[str, Any] = Depends(verify_bearer_token)
):
    """Revoke the current Bearer token so it cannot be reused."""
    jti = auth_info.get("token_jti")
    exp = auth_info.get("token_exp", 0)
    if jti:
        revoke_token(jti, exp)
        AuditLogger.log_security_event(
            "token_revoked",
            request,
            details=f"Token revoked for client: {auth_info.get('client_id')}"
        )
    return {"message": "Token revoked successfully"}


# --- Redaction Endpoints ---

@app.post(f"{API_PREFIX}/v1/redact", response_model=RedactResponse, responses={
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    413: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
}, tags=["Redaction"])
async def redact_text(
    request: Request,
    body: RedactRequest,
    auth_info: Dict[str, Any] = Depends(verify_bearer_token)
):
    """
    Redact PI from a single text string.

    This is the primary endpoint for LLM gateway use - call this before
    sending any user data to an LLM to ensure no PI is leaked.
    
    **Model Selection:**
    - `enable_ner`: Set to `false` for fast mode (10x faster, no NER)
    - `spacy_model`: Choose model - "en_core_web_sm", "en_core_web_md", "en_core_web_lg" (default), "en_core_web_trf"
    
    Requires Bearer token authentication (Authorization header).
    """
    request_id = body.request_id or str(uuid.uuid4())

    try:
        # Get the appropriate remover based on model selection
        requested_model = body.spacy_model or DEFAULT_SPACY_MODEL
        active_remover, model_used, fallback = get_remover_for_model(
            requested_model, 
            enable_ner=body.enable_ner
        )
        mode = "full" if body.enable_ner else "fast"
        
        # Process
        if body.include_details:
            result = active_remover.redact_with_details(body.text)

            # Count redactions by type for audit log
            redaction_counts: Dict[str, int] = {}
            for r in result.redactions:
                pi_type = r.pi_type
                redaction_counts[pi_type] = redaction_counts.get(pi_type, 0) + 1
            
            # Audit log with PI types and counts
            AuditLogger.log_request(request, auth_info, "redact_single", {
                "text_length": len(body.text),
                "include_details": body.include_details,
                "request_id": request_id,
                "model_requested": requested_model if body.enable_ner else None,
                "model_used": model_used,
                "mode": mode
            }, redactions=redaction_counts if redaction_counts else None)

            # Record metrics
            if ENABLE_METRICS:
                metrics.record_request(result.processing_time_ms)

            return RedactResponse(
                redacted_text=result.redacted_text,
                request_id=request_id,
                processing_time_ms=result.processing_time_ms,
                redactions=[
                    {
                        "original": r.original,
                        "replacement": r.replacement,
                        "type": r.pi_type,
                        "start": r.start,
                        "end": r.end,
                        "confidence": r.confidence,
                        "method": r.detection_method
                    }
                    for r in result.redactions
                ],
                mode=mode,
                spacy_model=model_used,
                used_fallback=fallback
            )
        else:
            start_time = time.perf_counter()
            redacted = active_remover.redact(body.text)
            processing_time = (time.perf_counter() - start_time) * 1000
            
            # For simple redact, count tokens in output to estimate redactions
            import re as regex_module
            token_pattern = regex_module.compile(r'\[([A-Z_]+)\]')
            tokens = token_pattern.findall(redacted)
            redaction_counts = {}
            for token in tokens:
                redaction_counts[token] = redaction_counts.get(token, 0) + 1
            
            # Audit log with PI types and counts
            AuditLogger.log_request(request, auth_info, "redact_single", {
                "text_length": len(body.text),
                "include_details": body.include_details,
                "request_id": request_id,
                "model_requested": requested_model if body.enable_ner else None,
                "model_used": model_used,
                "mode": mode
            }, redactions=redaction_counts if redaction_counts else None)

            # Record metrics
            if ENABLE_METRICS:
                metrics.record_request(processing_time)

            return RedactResponse(
                redacted_text=redacted,
                request_id=request_id,
                processing_time_ms=round(processing_time, 3),
                mode=mode,
                spacy_model=model_used,
                used_fallback=fallback
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing request {request_id}: {str(e)}")
        if ENABLE_METRICS:
            metrics.record_error()
        # Don't expose internal error details
        raise HTTPException(
            status_code=500, 
            detail="An error occurred while processing. Please try again."
        )


# --- Batch Redaction Endpoint ---
# Controlled by ENABLE_BATCH_ENDPOINT feature flag (default: disabled)
# To enable: set ENABLE_BATCH_ENDPOINT=true environment variable

if ENABLE_BATCH_ENDPOINT:
    @app.post(f"{API_PREFIX}/v1/redact/batch", response_model=BatchRedactResponse, responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse}
    }, tags=["Redaction"])
    async def redact_batch(
        request: Request,
        body: BatchRedactRequest,
        auth_info: Dict[str, Any] = Depends(verify_bearer_token)
    ):
        """
        Redact PI from multiple text strings in a single request.

        More efficient than making multiple single requests when you have
        several texts to process.
        
        **Model Selection:**
        - `enable_ner`: Set to `false` for fast mode (10x faster, no NER)
        - `spacy_model`: Choose model - "en_core_web_sm", "en_core_web_md", "en_core_web_lg" (default), "en_core_web_trf"
        
        Requires Bearer token authentication (Authorization header).
        """
        request_id = str(uuid.uuid4())

        try:
            # Get the appropriate remover based on model selection
            requested_model = body.spacy_model or DEFAULT_SPACY_MODEL
            active_remover, model_used, fallback = get_remover_for_model(
                requested_model, 
                enable_ner=body.enable_ner
            )
            mode = "full" if body.enable_ner else "fast"
            
            # Audit log
            AuditLogger.log_request(request, auth_info, "redact_batch", {
                "batch_size": len(body.texts),
                "total_chars": sum(len(t) for t in body.texts),
                "include_details": body.include_details,
                "model_requested": requested_model if body.enable_ner else None,
                "model_used": model_used,
                "mode": mode
            })

            start_time = time.perf_counter()

            results = []
            if body.include_details:
                for i, text in enumerate(body.texts):
                    result = active_remover.redact_with_details(text)
                    results.append(BatchResult(
                        redacted_text=result.redacted_text,
                        index=i,
                        redactions=[
                            {
                                "original": r.original,
                                "replacement": r.replacement,
                                "type": r.pi_type,
                                "start": r.start,
                                "end": r.end,
                                "confidence": r.confidence,
                                "method": r.detection_method
                            }
                            for r in result.redactions
                        ]
                    ))
            else:
                redacted_texts = active_remover.redact_batch(body.texts)
                for i, redacted in enumerate(redacted_texts):
                    results.append(BatchResult(
                        redacted_text=redacted,
                        index=i
                    ))

            processing_time = (time.perf_counter() - start_time) * 1000

            # Record metrics
            if ENABLE_METRICS:
                metrics.record_request(processing_time)

            return BatchRedactResponse(
                results=results,
                request_id=request_id,
                total_count=len(results),
                processing_time_ms=round(processing_time, 3),
                mode=mode,
                spacy_model=model_used,
                used_fallback=fallback
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing batch request {request_id}: {str(e)}")
            if ENABLE_METRICS:
                metrics.record_error()
            raise HTTPException(
                status_code=500, 
                detail="An error occurred while processing. Please try again."
            )


# --- Health Check Endpoints ---
# Controlled by ENABLE_HEALTH_ENDPOINT and ENABLE_MONITORING_ENDPOINTS flags
# To enable: set environment variables to "true"

# Kubernetes liveness probe - controlled by ENABLE_MONITORING_ENDPOINTS (default: disabled)
if ENABLE_MONITORING_ENDPOINTS:
    @app.get("/livez", tags=["Health & Info"], include_in_schema=False)
    async def liveness_probe():
        """
        Kubernetes liveness probe - no authentication required.
        
        Returns 200 if the service is alive.
        Used by load balancers and orchestrators.
        """
        return {"status": "alive"}


# Kubernetes readiness probe - controlled by ENABLE_MONITORING_ENDPOINTS (default: disabled)
if ENABLE_MONITORING_ENDPOINTS:
    @app.get("/readyz", tags=["Health & Info"], include_in_schema=False)
    async def readiness_probe():
        """
        Kubernetes readiness probe - no authentication required.
        
        Returns 200 if the service is ready to accept requests.
        Checks if models are loaded and service is operational.
        """
        # Check if at least one model is available or fast mode works
        available_models = [m for m, v in _available_models.items() if v] if _available_models else []
        
        if not available_models and config.enable_ner:
            # NER is enabled but no models available - not ready
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "No spaCy models available for NER mode"}
            )
        
        return {"status": "ready", "models_loaded": len(available_models)}


# Health check endpoint - controlled by ENABLE_HEALTH_ENDPOINT (default: disabled)
if ENABLE_HEALTH_ENDPOINT:
    @app.get(f"{API_PREFIX}/health", response_model=HealthResponse, responses={
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse}
    }, tags=["Health & Info"])
    async def health_check(
        request: Request,
        auth_info: Dict[str, Any] = Depends(verify_bearer_token)
    ):
        """
        Health check endpoint for monitoring and load balancers.
        
        Returns available spaCy models and default model configuration.
        Requires authentication.
        """
        health = remover.health_check()
        
        # Get list of available models
        available = [model for model, is_available in _available_models.items() if is_available]

        return HealthResponse(
            status=health["status"],
            version=health["version"],
            mode=health["mode"],
            ner_available=health["ner_available"],
            available_models=available,
            default_model=DEFAULT_SPACY_MODEL,
            uptime_seconds=metrics.uptime_seconds,
            requests_processed=metrics.requests_processed,
            avg_latency_ms=metrics.avg_latency_ms,
            errors=metrics.errors
        )


@app.get(f"{API_PREFIX}/v1/pi-types", response_model=PITypesResponse, responses={
    401: {"model": ErrorResponse},
    429: {"model": ErrorResponse}
}, tags=["Health & Info"])
async def get_pi_types(
    request: Request,
    auth_info: Dict[str, Any] = Depends(verify_bearer_token)
):
    """
    Get list of supported PI types and their replacement tokens.
    Requires authentication.
    """
    pi_types = remover.get_supported_pi_types()

    return PITypesResponse(
        pi_types=[PITypeInfo(**pt) for pt in pi_types]
    )


@app.get(f"{API_PREFIX}/v1/models", response_model=ModelsResponse, responses={
    401: {"model": ErrorResponse},
    429: {"model": ErrorResponse}
}, tags=["Health & Info"])
async def get_available_models(
    request: Request,
    auth_info: Dict[str, Any] = Depends(verify_bearer_token)
):
    """
    Get list of available spaCy NER models.
    
    Returns all supported models with their installation status.
    Use this to check which models can be used in redaction requests.
    Requires authentication.
    """
    # Model descriptions
    model_descriptions = {
        "en_core_web_sm": "Small English model (~12MB) - fastest, lower accuracy",
        "en_core_web_md": "Medium English model (~40MB) - balanced speed/accuracy",
        "en_core_web_lg": "Large English model (~560MB) - best balance, recommended",
        "en_core_web_trf": "Transformer English model (~400MB) - highest accuracy, slowest",
    }
    
    # Build model info list
    models = []
    for model_name in ALLOWED_SPACY_MODELS:
        is_installed = _available_models.get(model_name, False)
        models.append(ModelInfo(
            name=model_name,
            installed=is_installed,
            is_default=(model_name == DEFAULT_SPACY_MODEL),
            description=model_descriptions.get(model_name, "English NER model")
        ))
    
    installed_count = sum(1 for m in models if m.installed)
    
    return ModelsResponse(
        models=models,
        installed_count=installed_count,
        default_model=DEFAULT_SPACY_MODEL,
        ner_enabled=config.enable_ner
    )


@app.get("/", responses={
    401: {"model": ErrorResponse},
    429: {"model": ErrorResponse}
}, tags=["Health & Info"])
async def root(
    request: Request,
    auth_info: Dict[str, Any] = Depends(verify_bearer_token)
):
    """Root endpoint - shows environment and available endpoints. Requires authentication."""
    env_name = "DEV" if ENVIRONMENT == "development" else "PROD"
    return {
        "name": "PI Remover API",
        "version": __version__,
        "environment": env_name,
        "api_prefix": API_PREFIX,
        "endpoints": {
            "auth": f"{API_PREFIX}/auth/token",
            "redact": f"{API_PREFIX}/v1/redact",
            "batch": f"{API_PREFIX}/v1/redact/batch",
            "health": f"{API_PREFIX}/health",
            "pi_types": f"{API_PREFIX}/v1/pi-types",
            "models": f"{API_PREFIX}/v1/models"
        },
        "docs": "/docs"
    }


# --- Error Handlers ---

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Log security-relevant HTTP errors
    if exc.status_code in [401, 403, 429]:
        AuditLogger.log_security_event(
            f"http_error_{exc.status_code}",
            request,
            details=str(exc.detail)[:100]
        )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail,
            "request_id": secrets.token_hex(8)
        }
    )


# Note: General exception handler is set via create_secure_error_handler() above


# --- Prometheus Metrics Endpoint ---
# Controlled by ENABLE_MONITORING_ENDPOINTS (default: disabled)

if ENABLE_MONITORING_ENDPOINTS and PROMETHEUS_AVAILABLE and create_metrics_endpoint:
    from fastapi.responses import Response
    
    @app.get("/metrics", tags=["Monitoring"], include_in_schema=False)
    async def prometheus_metrics():
        """
        Prometheus metrics endpoint for scraping.
        
        No authentication required - standard practice for Prometheus scraping.
        Excluded from OpenAPI schema.
        """
        return Response(
            content=prom_metrics.get_metrics_output(),
            media_type=prom_metrics.get_content_type()
        )


# --- Lifecycle ---

@app.on_event("startup")
async def startup_event():
    logger.info(f"PI Gateway API starting up (v{__version__})")
    logger.info(f"Mode: {'FAST' if not config.enable_ner else 'FULL'}")
    logger.info(f"Max text length: {MAX_TEXT_LENGTH}")
    logger.info(f"Max batch size: {MAX_BATCH_SIZE}")
    
    # Check available spaCy models at startup
    available = check_available_models()
    available_list = [m for m, v in available.items() if v]
    logger.info(f"Default spaCy model: {DEFAULT_SPACY_MODEL}")
    logger.info(f"Available spaCy models: {available_list if available_list else 'None (fast mode only)'}")
    logger.info(f"Allowed models: {ALLOWED_SPACY_MODELS}")
    
    # Record model availability in Prometheus metrics
    if PROMETHEUS_AVAILABLE and prom_metrics:
        for model_name, is_available in available.items():
            if is_available:
                prom_metrics.record_model_loaded(model_name, 0.0)  # Load time unknown at startup
        logger.info("Prometheus metrics enabled at /metrics")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("PI Gateway API shutting down")
    logger.info(f"Total requests processed: {metrics.requests_processed}")
    logger.info(f"Average latency: {metrics.avg_latency_ms}ms")


# --- Main ---

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=False,
        log_level=LOG_LEVEL.lower()
    )
