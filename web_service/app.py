"""
PI Remover Web UI - Hybrid Microservices Architecture.

This service provides a web interface for PI redaction with automatic fallback.

Architecture:
    Browser → Web Service (8082) → API Service (8080) [primary]
                                 → Local PIRemover [fallback]
    
Features:
    - File upload with drag-and-drop
    - Real-time text redaction
    - Support for CSV, Excel, JSON, TXT, DOCX, PDF files
    - Background processing for large files
    - Service-to-service authentication
    - **Automatic fallback to local processing if API unavailable**

Run:
    python app.py --config config/web_service.yaml
    python app.py --port 8082

Version: 2.12.0 (Hybrid Mode)
"""

import os
import sys
import uuid
import shutil
import tempfile
import time
import logging
import secrets
import asyncio
import argparse
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable

import httpx
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, BackgroundTasks, status
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator

# Add parent directory to path for shared imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import pandas as pd

# Import shared modules (optional in standalone mode)
ConfigLoader: Optional[type] = None
get_config: Optional[Callable[..., Any]] = None
load_clients_config: Optional[Callable[..., Dict[str, Any]]] = None
setup_structured_logging: Optional[Callable[..., Any]] = None
get_correlation_id: Optional[Callable[[], Optional[str]]] = None
set_correlation_id: Optional[Callable[[str], Any]] = None
RequestLoggingMiddleware: Optional[type] = None

try:
    from shared.config_loader import (
        ConfigLoader as _ConfigLoader,
        get_config as _get_config,
        load_clients_config as _load_clients_config,
    )
    from shared.logging_config import (
        setup_structured_logging as _setup_structured_logging,
        get_correlation_id as _get_correlation_id,
        set_correlation_id as _set_correlation_id,
        RequestLoggingMiddleware as _RequestLoggingMiddleware,
    )

    ConfigLoader = _ConfigLoader
    get_config = _get_config
    load_clients_config = _load_clients_config
    setup_structured_logging = _setup_structured_logging
    get_correlation_id = _get_correlation_id
    set_correlation_id = _set_correlation_id
    RequestLoggingMiddleware = _RequestLoggingMiddleware
except ImportError:
    # Standalone/dev fallback (no shared package on import path)
    pass

# Import API client
from api_client import (
    PIRemoverAPIClient,
    create_api_client,
    APIClientError,
    AuthenticationError,
    ServiceUnavailableError,
    CircuitOpenError
)

# Import local PIRemover for fallback mode
from pi_remover import PIRemover, PIRemoverConfig
LOCAL_REMOVER_AVAILABLE = True

# Import security components (for file validation, audit logging)
try:
    from pi_remover.security import (
        SecurityConfig,
        InputValidator,
        FileSecurityValidator,
        AuditLogger,
        setup_security,
        create_secure_error_handler,
        get_client_ip
    )
    from pi_remover.core import __version__
except ImportError:
    from security import (
        SecurityConfig,
        InputValidator,
        FileSecurityValidator,
        AuditLogger,
        setup_security,
        create_secure_error_handler,
        get_client_ip
    )
    __version__ = "2.12.0"

# Configuration (from YAML config files)
def load_configuration() -> Dict[str, Any]:
    """Load configuration from YAML files, environment variables, or command-line arguments.
    
    Priority order (highest to lowest):
    1. Command-line arguments
    2. Environment variables
    3. YAML config files
    4. Default values
    """
    parser = argparse.ArgumentParser(description='PI Remover Web Service')
    parser.add_argument('--config', type=str, help='Path to config file')
    parser.add_argument('--port', type=int, help='Service port')
    parser.add_argument('--host', type=str, help='Service host')
    parser.add_argument('--api-url', type=str, help='API service URL')
    parser.add_argument('--environment', type=str, choices=['development', 'production'])
    parser.add_argument('--standalone', action='store_true', help='Run in standalone mode (no API)')
    
    args, _ = parser.parse_known_args()
    
    # Try to load from config file
    config = get_config('web_service', args.config) if get_config else None
    
    # Environment variable helpers
    def get_env_bool(key: str, default: bool) -> bool:
        """Get boolean from environment variable."""
        val = os.environ.get(key, '').lower()
        if val in ('true', '1', 'yes', 'on'):
            return True
        if val in ('false', '0', 'no', 'off'):
            return False
        return default
    
    # Build configuration dictionary with defaults
    # Priority: CLI args > Environment vars > Config file > Defaults
    conf = {
        'service': {
            'name': config.get('service.name', 'pi-remover-web') if config else 'pi-remover-web',
            'host': args.host or os.environ.get('HOST', '0.0.0.0') or (config.get('service.host', '0.0.0.0') if config else '0.0.0.0'),
            'port': args.port or int(os.environ.get('PORT', 8080)) or (config.get('service.port', 8082) if config else 8082),
            'environment': args.environment or os.environ.get('ENVIRONMENT', 'development') or (config.get('service.environment', 'development') if config else 'development'),
        },
        'logging': {
            'level': os.environ.get('LOG_LEVEL') or (config.get('logging.level', 'INFO') if config else 'INFO'),
            'json_format': config.get('logging.json_format', False) if config else False,
            'file': config.get('logging.file') if config else None,
        },
        'api_client': {
            # API_URL is the primary way to configure in Docker
            'base_url': args.api_url or os.environ.get('API_URL') or (config.get('api_client.base_url', 'http://localhost:8080') if config else 'http://localhost:8080'),
            # WEB_CLIENT_ID/SECRET for service-to-service auth
            'client_id': os.environ.get('WEB_CLIENT_ID') or (config.get('api_client.client_id', 'pi-internal-web-service') if config else 'pi-internal-web-service'),
            'client_secret': os.environ.get('WEB_CLIENT_SECRET'),  # Optional: loaded from env or clients.yaml
            'timeout_seconds': config.get('api_client.timeout_seconds', 30) if config else 30,
            'max_retries': config.get('api_client.max_retries', 3) if config else 3,
        },
        'upload': {
            'max_file_size': int(os.environ.get('MAX_FILE_SIZE', 0)) or (config.get('upload.max_file_size', 500 * 1024 * 1024) if config else 500 * 1024 * 1024),
            'upload_dir': os.environ.get('UPLOAD_DIR') or (config.get('upload.upload_dir') if config else None),
        },
        'security': {
            'cors_origins': config.get('security.cors_origins', ['*']) if config else ['*'],
        },
        'health': {
            'check_api_service': config.get('health.check_api_service', True) if config else True,
        },
        # Hybrid mode configuration (environment variables override config file)
        'hybrid': {
            'enabled': get_env_bool('HYBRID_ENABLED', not args.standalone),  # Enable hybrid mode unless --standalone
            'prefer_api': get_env_bool('PREFER_API', config.get('hybrid.prefer_api', True) if config else True),  # Try API first
            'fallback_to_local': get_env_bool('FALLBACK_TO_LOCAL', config.get('hybrid.fallback_to_local', True) if config else True),  # Fallback to local if API fails
            'standalone_mode': args.standalone or get_env_bool('STANDALONE_MODE', False),  # Force standalone mode (no API calls)
        }
    }
    
    return conf

# Load configuration
APP_CONFIG = load_configuration()

# Configuration shortcuts
LOG_LEVEL = APP_CONFIG['logging']['level']
UPLOAD_DIR = APP_CONFIG['upload']['upload_dir'] or tempfile.gettempdir()
MAX_FILE_SIZE = APP_CONFIG['upload']['max_file_size']
ALLOWED_EXTENSIONS = SecurityConfig.ALLOWED_EXTENSIONS
ENVIRONMENT = APP_CONFIG['service']['environment']
JOB_TTL_SECONDS = 600  # Auto-delete uploaded files after 10 minutes

# ThreadPoolExecutor for CPU-bound PIRemover work (prevents blocking the event loop)
_executor = ThreadPoolExecutor(max_workers=4)

# Cached PIRemover instances (avoids reloading spaCy on every call)
_cached_removers: Dict[bool, Any] = {}


def _get_remover(fast_mode: bool):
    """Get or create a cached PIRemover instance."""
    if fast_mode not in _cached_removers:
        config = PIRemoverConfig(
            enable_ner=not fast_mode,
            use_typed_tokens=True
        )
        _cached_removers[fast_mode] = PIRemover(config)
    return _cached_removers[fast_mode]

# Configure logging
setup_structured_logging(
    service_name='web_service',
    log_level=LOG_LEVEL,
    json_format=APP_CONFIG['logging']['json_format'],
    log_file=APP_CONFIG['logging']['file']
) if setup_structured_logging else None

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("pi-web-service")

# FastAPI App
app = FastAPI(
    title="PII Shield - LLM Safety Middleware",
    description="Strip personal information from prompts before they reach your LLM",
    version=__version__,
    docs_url="/api/docs" if ENVIRONMENT == "development" else None,
    redoc_url="/api/redoc" if ENVIRONMENT == "development" else None
)

# API Client Singleton
# Global API client instance
_api_client: Optional[PIRemoverAPIClient] = None
_api_client_lock = asyncio.Lock()

# API Status Cache (for fast routing decisions)
@dataclass
class APIStatusCache:
    """
    Cached API availability status for instant routing decisions.
    
    Instead of waiting 17+ seconds for retry timeouts, we check this cache
    and route immediately to local fallback if API is known to be down.
    """
    is_available: bool = False
    last_check: float = 0.0
    last_check_time: str = ""
    response_time_ms: float = 0.0
    error_message: str = ""
    consecutive_failures: int = 0
    check_in_progress: bool = False
    
    # Configuration
    CACHE_TTL_SECONDS: float = 30.0  # How long to trust cached status
    HEALTH_CHECK_INTERVAL: float = 30.0  # Background check interval
    HEALTH_CHECK_TIMEOUT: float = 3.0  # Fast timeout for health checks
    MAX_CONSECUTIVE_FAILURES: int = 3  # Mark unavailable after N failures
    
    def is_stale(self) -> bool:
        """Check if cached status is stale and needs refresh."""
        if self.last_check == 0:
            return True
        return (time.time() - self.last_check) > self.CACHE_TTL_SECONDS
    
    def should_try_api(self) -> bool:
        """
        Determine if we should attempt API call based on cached status.
        
        Returns True if:
        - API is known to be available, OR
        - Cache is stale (we should recheck)
        """
        if self.is_stale():
            return True  # Cache stale, let the request determine status
        return self.is_available
    
    def mark_available(self, response_time_ms: float = 0.0) -> None:
        """Mark API as available after successful health check."""
        self.is_available = True
        self.last_check = time.time()
        self.last_check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.response_time_ms = response_time_ms
        self.error_message = ""
        self.consecutive_failures = 0
        logger.info(f"API status: AVAILABLE (response: {response_time_ms:.1f}ms)")
    
    def mark_unavailable(self, error: str = "") -> None:
        """Mark API as unavailable after failed health check."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self.is_available = False
            self.error_message = error
            logger.warning(f"API status: UNAVAILABLE after {self.consecutive_failures} failures - {error}")
        else:
            logger.warning(f"API health check failed ({self.consecutive_failures}/{self.MAX_CONSECUTIVE_FAILURES}): {error}")
        self.last_check = time.time()
        self.last_check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.response_time_ms = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            'api_available': self.is_available,
            'last_check': self.last_check_time,
            'response_time_ms': round(self.response_time_ms, 1),
            'error_message': self.error_message if not self.is_available else None,
            'cache_stale': self.is_stale(),
            'consecutive_failures': self.consecutive_failures,
            'local_fallback_available': LOCAL_REMOVER_AVAILABLE,
            'mode': 'hybrid' if not APP_CONFIG.get('hybrid', {}).get('standalone_mode', False) else 'standalone'
        }


# Global API status cache instance
_api_status = APIStatusCache()
_api_status_lock = asyncio.Lock()
_background_task: Optional[asyncio.Task] = None


async def check_api_health(timeout: float = 3.0) -> Tuple[bool, float, str]:
    """
    Quick health check of the API service.
    
    Uses authenticated client. If client is not initialized, returns unavailable
    rather than making unauthenticated calls (which cause 401 warnings).
    
    Args:
        timeout: Maximum time to wait for response
        
    Returns:
        Tuple of (is_available, response_time_ms, error_message)
    """
    global _api_status, _api_client
    
    # If no authenticated client available, report unavailable
    # This avoids 401 warnings from unauthenticated health checks
    if _api_client is None:
        return False, 0.0, "API client not initialized"
    
    try:
        start_time = time.perf_counter()
        
        # Use authenticated health check
        result = await _api_client.health_check()
        response_time = (time.perf_counter() - start_time) * 1000
        return True, response_time, ""
        
    except httpx.ConnectError as e:
        return False, 0.0, f"Connection refused"
    except httpx.TimeoutException as e:
        return False, 0.0, f"Timeout after {timeout}s"
    except Exception as e:
        return False, 0.0, str(e)


async def update_api_status() -> Dict[str, Any]:
    """
    Update the cached API status.
    
    Returns:
        Current status dictionary
    """
    global _api_status
    
    async with _api_status_lock:
        if _api_status.check_in_progress:
            return _api_status.to_dict()
        _api_status.check_in_progress = True
    
    try:
        is_available, response_time, error = await check_api_health(
            timeout=_api_status.HEALTH_CHECK_TIMEOUT
        )
        
        async with _api_status_lock:
            if is_available:
                _api_status.mark_available(response_time)
            else:
                _api_status.mark_unavailable(error)
            _api_status.check_in_progress = False
            
        return _api_status.to_dict()
        
    except Exception as e:
        async with _api_status_lock:
            _api_status.mark_unavailable(str(e))
            _api_status.check_in_progress = False
        return _api_status.to_dict()


async def background_health_check():
    """
    Background task that periodically checks API health.
    
    Runs every HEALTH_CHECK_INTERVAL seconds to keep the cache fresh.
    """
    global _api_status
    
    logger.info("Starting background API health check task")
    
    while True:
        try:
            await asyncio.sleep(_api_status.HEALTH_CHECK_INTERVAL)
            
            # Skip if in standalone mode
            if APP_CONFIG.get('hybrid', {}).get('standalone_mode', False):
                continue
            
            await update_api_status()
            
        except asyncio.CancelledError:
            logger.info("Background health check task cancelled")
            break
        except Exception as e:
            logger.error(f"Background health check error: {e}")
            await asyncio.sleep(5)  # Wait before retry


async def background_job_cleanup():
    """Background task that auto-deletes expired job files (zero data retention)."""
    logger.info("Starting background job cleanup task (TTL=%ds)", JOB_TTL_SECONDS)

    while True:
        try:
            await asyncio.sleep(60)  # Check every 60 seconds

            now = datetime.now()
            expired_jobs = []

            for job_id, job in list(jobs.items()):
                created_str = job.get("created_at")
                if not created_str:
                    continue
                try:
                    created_at = datetime.fromisoformat(created_str)
                    if (now - created_at).total_seconds() > JOB_TTL_SECONDS:
                        expired_jobs.append(job_id)
                except (ValueError, TypeError):
                    continue

            for job_id in expired_jobs:
                job = jobs.pop(job_id, None)
                if job and job.get("input_file"):
                    input_dir = Path(job["input_file"]).parent
                    if input_dir.exists():
                        shutil.rmtree(input_dir, ignore_errors=True)
                        logger.info("Auto-cleaned expired job %s", job_id[:8])

        except asyncio.CancelledError:
            logger.info("Background job cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Background job cleanup error: {e}")


_cleanup_task = None


async def get_api_client() -> PIRemoverAPIClient:
    """Get or create the API client singleton."""
    global _api_client
    
    async with _api_client_lock:
        if _api_client is None:
            client_id = APP_CONFIG['api_client']['client_id']
            
            # Priority for client secret:
            # 1. Environment variable (WEB_CLIENT_SECRET) - passed via APP_CONFIG
            # 2. clients.yaml config file
            # 3. Fallback hardcoded value (for development only)
            client_secret = APP_CONFIG['api_client'].get('client_secret')
            
            if not client_secret:
                # Try loading from clients.yaml
                clients = load_clients_config() if load_clients_config else {}
                client_data = clients.get(client_id, {})
                client_secret = client_data.get('secret', '')
            
            if not client_secret:
                if ENVIRONMENT == "production":
                    raise RuntimeError(
                        "FATAL: WEB_CLIENT_SECRET not configured. "
                        "Set WEB_CLIENT_SECRET environment variable for production."
                    )
                # Final fallback (development only)
                client_secret = "YOUR_WEB_CLIENT_SECRET_HERE"
                logger.warning(
                    f"Client secret not found in env/config for {client_id}, "
                    "using dev fallback - NOT SAFE FOR PRODUCTION"
                )
            
            _api_client = PIRemoverAPIClient(
                base_url=APP_CONFIG['api_client']['base_url'],
                client_id=client_id,
                client_secret=client_secret
            )
            
            # Detect API prefix
            try:
                await _api_client.detect_api_prefix()
            except Exception as e:
                logger.warning(f"Could not detect API prefix: {e}")
            
            logger.info(
                f"API client initialized: {APP_CONFIG['api_client']['base_url']} "
                f"(client: {client_id})"
            )
        
        return _api_client


# Security Setup
# Configure security middleware (rate limiting and security headers)
setup_security(
    app,
    enable_rate_limit=True
)

# CORS - more restrictive for web service
app.add_middleware(
    CORSMiddleware,
    allow_origins=APP_CONFIG['security']['cors_origins'],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Accept", "X-Correlation-ID"],
)

# Add request logging middleware
if RequestLoggingMiddleware:
    app.add_middleware(RequestLoggingMiddleware, service_name='web_service')

# Add secure error handler
app.add_exception_handler(Exception, create_secure_error_handler())

# Static files and templates
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Job Storage (in-memory - use Redis for production horizontal scaling)
jobs: Dict[str, Dict[str, Any]] = {}

# Models
class TextRedactRequest(BaseModel):
    text: str
    fast_mode: bool = False  # NER ON by default
    
    @validator('text')
    def validate_text(cls, v):
        """Validate text input."""
        is_valid, error = InputValidator.validate_text_for_processing(v)
        if not is_valid:
            raise ValueError(error)
        return v


class TextRedactResponse(BaseModel):
    redacted_text: str
    processing_time_ms: float
    redaction_count: int
    api_service_used: bool = True


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    message: str
    input_file: Optional[str] = None
    output_file: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# Helper Functions
def get_file_columns(file_path: str) -> List[str]:
    """Get column names from structured files (CSV, Excel, JSON)."""
    ext = Path(file_path).suffix.lower()
    
    # Document types don't have columns
    if ext in {'.txt', '.md', '.log', '.docx', '.doc', '.pptx', '.ppt', 
               '.pdf', '.html', '.htm', '.xml', '.rtf'}:
        return []
    
    try:
        if ext == '.csv':
            df = pd.read_csv(file_path, nrows=0)
            return list(df.columns)
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, nrows=0)
            return list(df.columns)
        elif ext == '.json':
            df = pd.read_json(file_path, lines=True, nrows=1)
            return list(df.columns) if not df.empty else []
        else:
            return []
    except Exception as e:
        logger.error(f"Error getting columns: {e}")
        return []


async def redact_text_via_api(text: str, fast_mode: bool = False) -> Dict[str, Any]:
    """
    Redact text by calling the API service.
    
    Args:
        text: Text to redact
        fast_mode: Use fast mode (NER disabled)
        
    Returns:
        API response dictionary
    """
    client = await get_api_client()
    return await client.redact_text(
        text=text,
        fast_mode=fast_mode,
        include_details=True
    )


def redact_text_locally(text: str, fast_mode: bool = False) -> Dict[str, Any]:
    """
    Redact text using local PIRemover (fallback mode).
    
    Args:
        text: Text to redact
        fast_mode: Use fast mode (NER disabled)
        
    Returns:
        Dict with redacted_text, redactions, processing_time_ms
    """
    if not LOCAL_REMOVER_AVAILABLE or PIRemover is None:
        raise RuntimeError("Local PIRemover not available")
    
    start_time = time.perf_counter()
    
    remover = _get_remover(fast_mode)
    result = remover.redact_with_details(text)

    processing_time = (time.perf_counter() - start_time) * 1000

    # Build response similar to API format
    redactions = []
    if hasattr(result, 'redactions') and result.redactions:
        for r in result.redactions:
            redactions.append({
                'original': r.original if hasattr(r, 'original') else '',
                'replacement': r.replacement if hasattr(r, 'replacement') else '',
                'type': r.pi_type if hasattr(r, 'pi_type') else 'UNKNOWN',
                'confidence': r.confidence if hasattr(r, 'confidence') else 1.0,
            })

    return {
        'redacted_text': result.redacted_text,
        'redactions': redactions,
        'processing_time_ms': round(processing_time, 3),
        'mode': 'fast' if fast_mode else 'full',
        'used_fallback': True,  # Indicates local processing
    }


async def redact_text_hybrid(text: str, fast_mode: bool = False) -> Dict[str, Any]:
    """
    Hybrid redaction: Try API first, fallback to local if unavailable.
    
    OPTIMIZED: Uses cached API status for instant routing decisions.
    If API is known to be down, immediately uses local fallback (0ms delay).
    
    Args:
        text: Text to redact
        fast_mode: Use fast mode (NER disabled)
        
    Returns:
        Dict with redacted_text, redactions, processing_time_ms, and source
    """
    global _api_status
    hybrid_config = APP_CONFIG.get('hybrid', {})
    
    loop = asyncio.get_event_loop()

    # If standalone mode, always use local
    if hybrid_config.get('standalone_mode', False):
        logger.debug("Standalone mode: using local PIRemover")
        result = await loop.run_in_executor(_executor, redact_text_locally, text, fast_mode)
        result['source'] = 'local'
        return result

    # OPTIMIZATION: Check cached API status for instant routing
    # If API is known to be unavailable, skip directly to local fallback
    if not _api_status.should_try_api():
        if hybrid_config.get('fallback_to_local', True) and LOCAL_REMOVER_AVAILABLE:
            logger.debug("API unavailable (cached), using local PIRemover immediately")
            result = await loop.run_in_executor(_executor, redact_text_locally, text, fast_mode)
            result['source'] = 'local_fallback'
            result['routing_reason'] = 'api_unavailable_cached'
            return result
    
    # Try API first if preferred and status indicates it might be available
    if hybrid_config.get('prefer_api', True):
        try:
            result = await redact_text_via_api(text, fast_mode)
            result['source'] = 'api'
            result['used_fallback'] = False
            # Update cache on success
            _api_status.mark_available()
            return result
        except (APIClientError, AuthenticationError, ServiceUnavailableError, CircuitOpenError) as e:
            logger.warning(f"API service unavailable ({type(e).__name__}), falling back to local: {e}")
            # Update cache on failure
            _api_status.mark_unavailable(str(e))
        except Exception as e:
            logger.warning(f"API call failed ({type(e).__name__}), falling back to local: {e}")
            _api_status.mark_unavailable(str(e))
    
    # Fallback to local if enabled
    if hybrid_config.get('fallback_to_local', True) and LOCAL_REMOVER_AVAILABLE:
        logger.info("Using local PIRemover as fallback")
        result = await loop.run_in_executor(_executor, redact_text_locally, text, fast_mode)
        result['source'] = 'local_fallback'
        return result

    # No fallback available - raise error
    raise ServiceUnavailableError("API service unavailable and local fallback disabled")


def redact_batch_locally(texts: List[str], fast_mode: bool = False) -> List[str]:
    """
    Redact multiple texts using local PIRemover (fallback mode).
    
    Args:
        texts: List of texts to redact
        fast_mode: Use fast mode (NER disabled)
        
    Returns:
        List of redacted texts
    """
    if not LOCAL_REMOVER_AVAILABLE or PIRemover is None:
        raise RuntimeError("Local PIRemover not available")
    
    remover = _get_remover(fast_mode)

    results = []
    for text in texts:
        result = remover.redact_with_details(text)
        results.append(result.redacted_text)
    
    return results


async def redact_batch_hybrid(texts: List[str], fast_mode: bool = False) -> List[str]:
    """
    Hybrid batch redaction: Try API first, fallback to local if unavailable.
    
    OPTIMIZED: Uses cached API status for instant routing decisions.
    If API is known to be down, immediately uses local fallback (0ms delay).
    
    Args:
        texts: List of texts to redact
        fast_mode: Use fast mode (NER disabled)
        
    Returns:
        List of redacted texts
    """
    global _api_status
    hybrid_config = APP_CONFIG.get('hybrid', {})
    loop = asyncio.get_event_loop()

    # If standalone mode, always use local
    if hybrid_config.get('standalone_mode', False):
        logger.debug("Standalone mode: using local PIRemover for batch")
        return await loop.run_in_executor(_executor, redact_batch_locally, texts, fast_mode)

    # OPTIMIZATION: Check cached API status for instant routing
    # If API is known to be unavailable, skip directly to local fallback
    if not _api_status.should_try_api():
        if hybrid_config.get('fallback_to_local', True) and LOCAL_REMOVER_AVAILABLE:
            logger.debug("API unavailable (cached), using local PIRemover for batch immediately")
            return await loop.run_in_executor(_executor, redact_batch_locally, texts, fast_mode)
    
    # Try API first if preferred and status indicates it might be available
    if hybrid_config.get('prefer_api', True):
        try:
            result = await redact_batch_via_api(texts, fast_mode)
            # Update cache on success
            _api_status.mark_available()
            return result
        except (APIClientError, AuthenticationError, ServiceUnavailableError, CircuitOpenError) as e:
            logger.warning(f"API service unavailable for batch ({type(e).__name__}), falling back to local: {e}")
            # Update cache on failure
            _api_status.mark_unavailable(str(e))
        except Exception as e:
            logger.warning(f"API batch call failed ({type(e).__name__}), falling back to local: {e}")
            _api_status.mark_unavailable(str(e))
    
    # Fallback to local if enabled
    if hybrid_config.get('fallback_to_local', True) and LOCAL_REMOVER_AVAILABLE:
        logger.info("Using local PIRemover as fallback for batch")
        return await loop.run_in_executor(_executor, redact_batch_locally, texts, fast_mode)

    # No fallback available - raise error
    raise ServiceUnavailableError("API service unavailable and local fallback disabled")


async def redact_batch_via_api(texts: List[str], fast_mode: bool = False) -> List[str]:
    """
    Redact multiple texts by calling the API service.
    
    Args:
        texts: List of texts to redact
        fast_mode: Use fast mode (NER disabled)
        
    Returns:
        List of redacted texts
    """
    client = await get_api_client()
    
    # Batch in chunks of 100 (API limit)
    batch_size = 100
    all_results = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = await client.redact_batch(
            texts=batch,
            fast_mode=fast_mode,
            include_details=False
        )
        
        # Extract redacted texts from response
        for result in response.get('results', []):
            all_results.append(result.get('redacted_text', ''))
    
    return all_results


# Endpoints - Frontend
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main HTML page."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "version": __version__
    })


# Endpoints - Text Redaction (Hybrid Mode: API with Local Fallback)
@app.post("/api/redact-text", response_model=TextRedactResponse)
async def redact_text(request: Request, body: TextRedactRequest):
    """
    Redact PI from text input.
    
    Uses hybrid mode:
    - Tries API service first (if available)
    - Falls back to local PIRemover if API fails
    """
    correlation_id = secrets.token_hex(8)
    if set_correlation_id:
        set_correlation_id(correlation_id)
    
    try:
        start_time = time.perf_counter()
        
        # Use hybrid redaction (API first, fallback to local)
        result = await redact_text_hybrid(body.text, body.fast_mode)
        
        processing_time = (time.perf_counter() - start_time) * 1000
        
        # Count redactions
        redaction_count = len(result.get('redactions', []))
        
        # Determine source
        source = result.get('source', 'unknown')
        used_api = source == 'api'
        used_fallback = source in ('local', 'local_fallback')
        
        # Audit log
        AuditLogger.log_request(
            request,
            {"client_id": "web_user", "client_name": "Web UI User"},
            "redact_text",
            {
                "text_length": len(body.text),
                "fast_mode": body.fast_mode,
                "processing_time_ms": result.get('processing_time_ms'),
                "redaction_count": redaction_count,
                "source": source,
                "used_fallback": used_fallback
            }
        )

        return TextRedactResponse(
            redacted_text=result.get('redacted_text', ''),
            processing_time_ms=round(processing_time, 3),
            redaction_count=redaction_count,
            api_service_used=used_api
        )

    except ServiceUnavailableError as e:
        # This only happens if both API and local fallback fail
        logger.error(f"All redaction methods failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Redaction service unavailable. Please try again later."
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error redacting text: {e}")
        raise HTTPException(
            status_code=500, 
            detail="An error occurred while processing. Please try again."
        )


# Endpoints - File Upload and Processing
@app.post("/api/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Upload a file and get its columns (for CSV/Excel).
    Returns a job_id for further processing.
    """
    # 1. Validate filename
    is_valid, error = InputValidator.validate_filename(file.filename)
    if not is_valid:
        AuditLogger.log_security_event("invalid_filename", request, details=error)
        raise HTTPException(status_code=400, detail=error)

    filename = file.filename
    if filename is None:
        AuditLogger.log_security_event("invalid_filename", request, details="Missing filename")
        raise HTTPException(status_code=400, detail="Missing filename")
    
    # 2. Check file extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        AuditLogger.log_security_event(
            "invalid_file_type", 
            request, 
            details=f"Extension: {ext}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 3. Generate secure job ID and create isolated directory
    job_id = secrets.token_hex(16)
    upload_dir = Path(UPLOAD_DIR) / "pi_remover" / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 4. Use safe filename
    safe_filename = FileSecurityValidator.generate_safe_filename(file.filename, job_id[:8])
    file_path = upload_dir / safe_filename

    # 5. Save file with size limit check
    try:
        file_size = 0
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    buffer.close()
                    file_path.unlink(missing_ok=True)
                    shutil.rmtree(upload_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB"
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to save file")

    # 6. Validate file
    is_valid, error = FileSecurityValidator.validate_file(
        str(file_path), 
        file.filename, 
        file_size
    )
    if not is_valid:
        AuditLogger.log_file_operation(job_id, "upload_rejected", file.filename, False, error)
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=error)

    # 7. Get columns if applicable
    columns = get_file_columns(str(file_path))

    # 8. Store job info
    jobs[job_id] = {
        "job_id": job_id,
        "status": "uploaded",
        "progress": 0,
        "message": "File uploaded successfully",
        "input_file": str(file_path),
        "original_filename": file.filename,
        "output_file": None,
        "columns": columns,
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "client_ip": get_client_ip(request)
    }

    # 9. Audit log
    AuditLogger.log_file_operation(job_id, "upload", file.filename, True)

    return {
        "job_id": job_id,
        "filename": file.filename,
        "columns": columns,
        "file_type": ext,
        "file_size": file_size,
        "message": "File uploaded successfully"
    }


@app.post("/api/process/{job_id}")
async def process_uploaded_file(
    job_id: str,
    background_tasks: BackgroundTasks,
    columns: List[str] = Form(default=[]),
    fast_mode: bool = Form(default=False)
):
    """
    Process an uploaded file with the specified columns.
    Processing happens in background using API service for redaction.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] not in ["uploaded", "failed"]:
        raise HTTPException(status_code=400, detail=f"Job is already {job['status']}")

    input_file = job["input_file"]
    if not input_file or not Path(input_file).exists():
        raise HTTPException(status_code=404, detail="Input file not found")

    # Update job status
    job["status"] = "processing"
    job["progress"] = 0
    job["message"] = "Processing started"

    # Start background processing
    background_tasks.add_task(
        process_file_background,
        job_id,
        input_file,
        columns,
        fast_mode
    )

    return {"job_id": job_id, "status": "processing", "message": "Processing started"}


async def process_file_background(
    job_id: str,
    input_file: str,
    columns: List[str],
    fast_mode: bool
):
    """
    Background task to process a file using API service for redaction.
    
    This reads the file, sends text to API for redaction, and writes output.
    """
    job = jobs.get(job_id)
    if not job:
        return

    job["started_at"] = datetime.now().isoformat()

    try:
        input_path = Path(input_file)
        output_file = input_path.parent / f"{input_path.stem}_cleaned{input_path.suffix}"
        ext = input_path.suffix.lower()

        job["progress"] = 10
        job["message"] = "Loading file..."

        # Process based on file type
        if ext == '.csv':
            await process_csv_file(input_path, output_file, columns, fast_mode, job)
        elif ext in ['.xlsx', '.xls']:
            await process_excel_file(input_path, output_file, columns, fast_mode, job)
        elif ext == '.json':
            await process_json_file(input_path, output_file, columns, fast_mode, job)
        elif ext == '.txt':
            await process_text_file(input_path, output_file, fast_mode, job)
        else:
            # For other files, process as text
            await process_text_file(input_path, output_file, fast_mode, job)

        job["status"] = "completed"
        job["progress"] = 100
        job["message"] = "Processing completed"
        job["output_file"] = str(output_file)
        job["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        logger.error(f"Error processing file for job {job_id}: {e}")
        job["status"] = "failed"
        job["message"] = f"Processing failed: {str(e)}"
        job["error_details"] = traceback.format_exc()
        job["failed_at"] = datetime.now().isoformat()


async def process_csv_file(input_path: Path, output_path: Path, columns: List[str], fast_mode: bool, job: dict):
    """Process CSV file using API service."""
    try:
        df = pd.read_csv(input_path)
    except Exception as e:
        logger.error(f"Failed to read CSV file: {e}")
        raise ValueError(f"Failed to read CSV file: {e}")
    
    total_rows = len(df)
    
    # Determine columns to process
    cols_to_process = columns if columns else list(df.columns)
    # Filter to only existing columns
    cols_to_process = [col for col in cols_to_process if col in df.columns]
    
    if not cols_to_process:
        raise ValueError(f"No valid columns found to process. Available: {list(df.columns)}")
    
    job["progress"] = 20
    job["message"] = f"Processing {len(cols_to_process)} column(s), {total_rows} rows..."
    
    # Calculate progress per column
    progress_per_col = 65 // len(cols_to_process)  # Leave room for file save (20-85%)
    
    for col_idx, col in enumerate(cols_to_process):
        job["message"] = f"Redacting column '{col}' ({col_idx + 1}/{len(cols_to_process)})..."
        
        # Get all text values
        texts = df[col].fillna('').astype(str).tolist()
        
        # Redact via hybrid (API with local fallback)
        redacted = await redact_batch_hybrid(texts, fast_mode)
        
        # Create new _cleaned column instead of replacing original
        cleaned_col_name = f"{col}_cleaned"
        df[cleaned_col_name] = redacted
        
        # Update progress
        job["progress"] = min(85, 20 + (col_idx + 1) * progress_per_col)
    
    # Save output
    job["message"] = "Saving file..."
    try:
        df.to_csv(output_path, index=False, encoding='utf-8')
    except Exception as e:
        logger.error(f"Failed to save CSV file: {e}")
        raise ValueError(f"Failed to save CSV file: {e}")
    
    job["progress"] = 95


async def process_excel_file(input_path: Path, output_path: Path, columns: List[str], fast_mode: bool, job: dict):
    """Process Excel file using API service."""
    try:
        # Read Excel file - try openpyxl first (for .xlsx), fall back to xlrd (for .xls)
        try:
            df = pd.read_excel(input_path, engine='openpyxl')
        except Exception:
            df = pd.read_excel(input_path)
    except Exception as e:
        logger.error(f"Failed to read Excel file: {e}")
        raise ValueError(f"Failed to read Excel file: {e}")
    
    total_rows = len(df)
    
    # Determine columns to process
    cols_to_process = columns if columns else list(df.columns)
    # Filter to only existing columns
    cols_to_process = [col for col in cols_to_process if col in df.columns]
    
    if not cols_to_process:
        raise ValueError(f"No valid columns found to process. Available: {list(df.columns)}")
    
    job["progress"] = 20
    job["message"] = f"Processing {len(cols_to_process)} column(s), {total_rows} rows..."
    
    # Calculate progress per column
    progress_per_col = 65 // len(cols_to_process)  # Leave room for file save (20-85%)
    
    for col_idx, col in enumerate(cols_to_process):
        job["message"] = f"Redacting column '{col}' ({col_idx + 1}/{len(cols_to_process)})..."
        
        # Get all text values
        texts = df[col].fillna('').astype(str).tolist()
        
        # Redact via hybrid (API with local fallback) with progress callback
        logger.info(f"Processing {len(texts)} rows in column '{col}'...")
        redacted = await redact_batch_hybrid(texts, fast_mode)
        
        # Create new _cleaned column instead of replacing original
        cleaned_col_name = f"{col}_cleaned"
        df[cleaned_col_name] = redacted
        
        # Update progress
        job["progress"] = min(85, 20 + (col_idx + 1) * progress_per_col)
        logger.info(f"Column '{col}' processed, progress: {job['progress']}%")
    
    # Save output with explicit engine to prevent corruption
    job["message"] = "Saving Excel file..."
    try:
        # Use openpyxl engine for .xlsx files to ensure proper formatting
        df.to_excel(output_path, index=False, engine='openpyxl')
        logger.info(f"Excel file saved successfully: {output_path}")
    except Exception as e:
        logger.error(f"Failed to save Excel file: {e}")
        raise ValueError(f"Failed to save Excel file: {e}")
    
    job["progress"] = 95


async def process_json_file(input_path: Path, output_path: Path, columns: List[str], fast_mode: bool, job: dict):
    """Process JSON file using API service."""
    import json
    
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    job["progress"] = 20
    
    # Handle both list and dict JSON
    if isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, dict):
                for key in (columns if columns else item.keys()):
                    if key in item and isinstance(item[key], str):
                        result = await redact_text_hybrid(item[key], fast_mode)
                        item[key] = result.get('redacted_text', item[key])
            job["progress"] = min(90, 20 + int(70 * i / len(data)))
    elif isinstance(data, dict):
        for key in (columns if columns else data.keys()):
            if key in data and isinstance(data[key], str):
                result = await redact_text_hybrid(data[key], fast_mode)
                data[key] = result.get('redacted_text', data[key])
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    job["progress"] = 95


async def process_text_file(input_path: Path, output_path: Path, fast_mode: bool, job: dict):
    """Process text file using API service."""
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    job["progress"] = 30
    job["message"] = "Redacting content..."
    
    # Redact via hybrid (API with local fallback)
    result = await redact_text_hybrid(content, fast_mode)
    
    job["progress"] = 80
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result.get('redacted_text', content))
    
    job["progress"] = 95


@app.get("/api/status/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status of a processing job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    return JobStatus(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        input_file=Path(job["input_file"]).name if job["input_file"] else None,
        output_file=Path(job["output_file"]).name if job.get("output_file") else None,
        created_at=job["created_at"],
        completed_at=job.get("completed_at")
    )


@app.get("/api/download/{job_id}")
async def download_result(request: Request, job_id: str):
    """Download the processed file."""
    if not job_id.replace('-', '').isalnum() or len(job_id) > 64:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="File not ready for download")

    output_file = job.get("output_file")
    if not output_file or not Path(output_file).exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    AuditLogger.log_file_operation(
        job_id, 
        "download", 
        Path(output_file).name, 
        True
    )

    original_name = job.get("original_filename", Path(output_file).name)
    download_name = f"cleaned_{Path(original_name).stem}{Path(output_file).suffix}"

    return FileResponse(
        output_file,
        media_type="application/octet-stream",
        filename=download_name
    )


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its files."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]

    try:
        if job.get("input_file"):
            input_dir = Path(job["input_file"]).parent
            if input_dir.exists():
                shutil.rmtree(input_dir)
    except Exception as e:
        logger.error(f"Error deleting files for job {job_id}: {e}")

    del jobs[job_id]

    return {"message": "Job deleted successfully"}


# Endpoints - Health
@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Checks both web service and API service health.
    """
    api_healthy = False
    api_status = "unknown"
    
    if APP_CONFIG['health']['check_api_service']:
        try:
            client = await get_api_client()
            if client.is_healthy():
                api_result = await client.health_check()
                api_healthy = api_result.get('status') == 'healthy'
                api_status = 'healthy' if api_healthy else 'unhealthy'
            else:
                api_status = f"circuit_{client.get_circuit_state()}"
        except Exception as e:
            api_status = f"error: {str(e)[:50]}"
    
    return {
        "status": "healthy" if api_healthy else "degraded",
        "version": __version__,
        "service": "web_service",
        "architecture": "microservices",
        "active_jobs": len(jobs),
        "api_service": {
            "url": APP_CONFIG['api_client']['base_url'],
            "status": api_status,
            "healthy": api_healthy
        }
    }


@app.get("/ready")
async def readiness_check():
    """Readiness probe - returns 200 only when PIRemover is fully initialized."""
    try:
        remover = _get_remover(fast_mode=True)
        if remover is None:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "PIRemover not initialized"}
            )
        return {"status": "ready", "local_remover": True, "version": __version__}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": str(e)}
        )


@app.get("/api/service-info")
async def service_info():
    """Get information about the service configuration."""
    client = await get_api_client()
    
    return {
        "service": "pi-remover-web",
        "version": __version__,
        "architecture": "microservices",
        "environment": ENVIRONMENT,
        "api_client": {
            "base_url": APP_CONFIG['api_client']['base_url'],
            "circuit_state": client.get_circuit_state(),
            "is_healthy": client.is_healthy()
        }
    }


@app.get("/api/status")
async def get_api_status(refresh: bool = False):
    """
    Get current API service availability status.
    
    This endpoint returns the cached API status for instant routing decisions.
    Used by the frontend to determine whether to show API status indicator
    and to enable immediate fallback when API is known to be down.
    
    Args:
        refresh: Force a fresh health check (default: use cache)
        
    Returns:
        API status including:
        - api_available: Whether API is currently reachable
        - last_check: When status was last checked
        - response_time_ms: API response time (if available)
        - local_fallback_available: Whether local fallback is ready
        - mode: Current operating mode (hybrid/standalone)
    """
    global _api_status
    
    # If standalone mode, always return local-only status
    if APP_CONFIG.get('hybrid', {}).get('standalone_mode', False):
        return {
            'api_available': False,
            'last_check': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'response_time_ms': 0,
            'error_message': 'Standalone mode - API disabled',
            'cache_stale': False,
            'consecutive_failures': 0,
            'local_fallback_available': LOCAL_REMOVER_AVAILABLE,
            'mode': 'standalone'
        }
    
    # Force refresh if requested or cache is stale
    if refresh or _api_status.is_stale():
        await update_api_status()
    
    return _api_status.to_dict()


# Lifecycle
@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    global _background_task
    
    logger.info(f"PI Remover Web Service starting (v{__version__})")
    logger.info(f"Architecture: Hybrid Microservices (API + Local Fallback)")
    logger.info(f"API Service URL: {APP_CONFIG['api_client']['base_url']}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Local PIRemover available: {LOCAL_REMOVER_AVAILABLE}")
    
    # Check if running in standalone mode
    if APP_CONFIG.get('hybrid', {}).get('standalone_mode', False):
        logger.info("Running in STANDALONE mode - API calls disabled")
        return
    
    # Initialize API client FIRST (before any health checks)
    # This ensures health checks use authenticated calls
    logger.info("Initializing API client...")
    try:
        client = await get_api_client()
        logger.info(f"API client initialized, circuit state: {client.get_circuit_state()}")
    except Exception as e:
        logger.warning(f"Could not initialize API client: {e}")
    
    # Perform initial API health check (now uses authenticated client)
    logger.info("Performing initial API health check...")
    status = await update_api_status()
    if status['api_available']:
        logger.info(f"API service is AVAILABLE (response: {status['response_time_ms']}ms)")
    else:
        logger.warning(f"API service is UNAVAILABLE - will use local fallback")
        if LOCAL_REMOVER_AVAILABLE:
            logger.info("Local PIRemover is ready for fallback")
        else:
            logger.error("Local PIRemover NOT available - service may be degraded")
    
    # Start background health check task
    _background_task = asyncio.create_task(background_health_check())
    logger.info("Background API health check task started")

    # Start background job cleanup task (zero data retention)
    global _cleanup_task
    _cleanup_task = asyncio.create_task(background_job_cleanup())
    logger.info("Background job cleanup task started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global _background_task, _cleanup_task, _api_client

    logger.info("PI Remover Web Service shutting down")

    # Cancel background health check task
    if _background_task:
        _background_task.cancel()
        try:
            await _background_task
        except asyncio.CancelledError:
            pass
        logger.info("Background health check task stopped")

    # Cancel background job cleanup task
    if _cleanup_task:
        _cleanup_task.cancel()
        try:
            await _cleanup_task
        except asyncio.CancelledError:
            pass
        logger.info("Background job cleanup task stopped")

    # Clean up all uploaded files (zero data retention on shutdown)
    for job_id, job in list(jobs.items()):
        try:
            if job.get("input_file"):
                input_dir = Path(job["input_file"]).parent
                if input_dir.exists():
                    shutil.rmtree(input_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Shutdown cleanup error for job {job_id[:8]}: {e}")
    jobs.clear()
    logger.info("All job files cleaned up on shutdown")

    # Close API client
    if _api_client:
        await _api_client.close()
        logger.info("API client closed")


# Main
if __name__ == "__main__":
    import uvicorn
    
    port = APP_CONFIG['service']['port']
    host = APP_CONFIG['service']['host']

    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=(ENVIRONMENT == "development"),
        log_level=LOG_LEVEL.lower()
    )
