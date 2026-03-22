"""
PI Remover API Client for Web Service.

This module provides an HTTP client for the web service to communicate
with the API service. It handles:
- JWT authentication with automatic token refresh
- Connection pooling for performance
- Retry logic with exponential backoff
- Circuit breaker pattern for resilience
- Request/response logging with correlation IDs

Usage:
    from api_client import PIRemoverAPIClient
    
    # Initialize client
    client = PIRemoverAPIClient(
        base_url="http://localhost:8080",
        client_id="pi-internal-web-service",
        client_secret="your-secret-here"
    )
    
    # Redact text
    result = await client.redact_text("John's email is john@example.com")
    print(result['redacted_text'])
    
    # Batch redaction
    results = await client.redact_batch(["text1", "text2", "text3"])

Version: 2.9.0
"""

import time
import asyncio
import logging
import secrets
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import httpx

# Add parent directory to path for shared imports
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from shared.logging_config import get_correlation_id, set_correlation_id
    from shared.config_loader import get_config, load_clients_config
except ImportError:
    # Fallback if shared module not available
    def get_correlation_id():
        return None
    def set_correlation_id(cid):
        pass
    def get_config(*args, **kwargs):
        return None
    def load_clients_config(*args, **kwargs):
        return {}

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    enabled: bool = True
    failure_threshold: int = 3      # Failures before opening
    recovery_timeout: float = 10.0  # Seconds before trying again
    half_open_max_calls: int = 3    # Calls allowed in half-open


@dataclass
class CircuitBreaker:
    """
    Circuit breaker implementation for resilient API calls.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = 0
    last_failure_time: float = 0
    half_open_calls: int = 0
    
    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            # Successfully tested recovery
            self.state = CircuitState.CLOSED
            logger.info("Circuit breaker CLOSED - service recovered")
        self.failure_count = 0
        self.half_open_calls = 0
    
    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker OPEN - recovery failed")
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker OPEN after {self.failure_count} failures"
            )
    
    def can_proceed(self) -> Tuple[bool, Optional[str]]:
        """
        Check if a request can proceed.
        
        Returns:
            Tuple of (can_proceed, error_message)
        """
        if not self.config.enabled:
            return True, None
        
        if self.state == CircuitState.CLOSED:
            return True, None
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("Circuit breaker HALF-OPEN - testing recovery")
                return True, None
            else:
                remaining = self.config.recovery_timeout - elapsed
                return False, f"Circuit open, retry in {remaining:.1f}s"
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls < self.config.half_open_max_calls:
                self.half_open_calls += 1
                return True, None
            else:
                return False, "Circuit half-open, max test calls reached"
        
        return True, None


@dataclass
class APIClientConfig:
    """API client configuration."""
    base_url: str = "http://localhost:8080"
    client_id: str = "pi-internal-web-service"
    client_secret: str = ""
    
    # Timeouts
    timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 5.0
    
    # Retry configuration
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 10.0
    retry_exponential_base: float = 2.0
    
    # Connection pooling
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry_seconds: float = 30.0
    
    # Circuit breaker
    circuit_breaker: CircuitBreakerConfig = field(
        default_factory=CircuitBreakerConfig
    )
    
    @classmethod
    def from_config(cls, config_path: Optional[str] = None) -> 'APIClientConfig':
        """Load configuration from YAML file."""
        config = get_config('web_service', config_path)
        if not config:
            return cls()
        
        api_config = config.get_section('api_client')
        cb_config = api_config.get('circuit_breaker', {})
        
        # Load client secret from clients.yaml
        clients = load_clients_config()
        client_id = api_config.get('client_id', 'pi-internal-web-service')
        client_data = clients.get(client_id, {})
        
        return cls(
            base_url=api_config.get('base_url', 'http://localhost:8080'),
            client_id=client_id,
            client_secret=client_data.get('secret', ''),
            timeout_seconds=api_config.get('timeout_seconds', 30.0),
            connect_timeout_seconds=api_config.get('connect_timeout_seconds', 5.0),
            max_retries=api_config.get('max_retries', 3),
            retry_delay_seconds=api_config.get('retry_delay_seconds', 1.0),
            retry_max_delay_seconds=api_config.get('retry_max_delay_seconds', 10.0),
            retry_exponential_base=api_config.get('retry_exponential_base', 2.0),
            max_connections=api_config.get('max_connections', 100),
            max_keepalive_connections=api_config.get('max_keepalive_connections', 20),
            keepalive_expiry_seconds=api_config.get('keepalive_expiry_seconds', 30.0),
            circuit_breaker=CircuitBreakerConfig(
                enabled=cb_config.get('enabled', True),
                failure_threshold=cb_config.get('failure_threshold', 5),
                recovery_timeout=cb_config.get('recovery_timeout_seconds', 30.0),
                half_open_max_calls=cb_config.get('half_open_max_calls', 3),
            )
        )


class APIClientError(Exception):
    """Base exception for API client errors."""
    pass


class AuthenticationError(APIClientError):
    """Authentication failed."""
    pass


class ServiceUnavailableError(APIClientError):
    """API service is unavailable."""
    pass


class CircuitOpenError(APIClientError):
    """Circuit breaker is open."""
    pass


class PIRemoverAPIClient:
    """
    HTTP client for PI Remover API service.
    
    Features:
    - Automatic JWT token management with refresh
    - Connection pooling
    - Retry with exponential backoff
    - Circuit breaker for resilience
    - Correlation ID propagation
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        config: Optional[APIClientConfig] = None,
        config_path: Optional[str] = None
    ):
        """
        Initialize the API client.
        
        Args:
            base_url: API service base URL (overrides config)
            client_id: Client ID for authentication (overrides config)
            client_secret: Client secret for authentication (overrides config)
            config: Pre-built configuration object
            config_path: Path to config file
        """
        # Load configuration
        if config:
            self.config = config
        else:
            self.config = APIClientConfig.from_config(config_path)
        
        # Override with explicit parameters
        if base_url:
            self.config.base_url = base_url
        if client_id:
            self.config.client_id = client_id
        if client_secret:
            self.config.client_secret = client_secret
        
        # Token cache
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0
        self._token_lock = asyncio.Lock()
        
        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(self.config.circuit_breaker)
        
        # HTTP client (lazy initialized)
        self._client: Optional[httpx.AsyncClient] = None
        
        # Detect API prefix (dev or prod)
        self._api_prefix = "/dev"  # Default to dev, will be detected
        
        logger.info(
            f"API client initialized for {self.config.base_url} "
            f"(client: {self.config.client_id})"
        )
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(
                    self.config.timeout_seconds,
                    connect=self.config.connect_timeout_seconds
                ),
                limits=httpx.Limits(
                    max_connections=self.config.max_connections,
                    max_keepalive_connections=self.config.max_keepalive_connections,
                    keepalive_expiry=self.config.keepalive_expiry_seconds
                )
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> 'PIRemoverAPIClient':
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_token(self) -> str:
        """
        Ensure we have a valid access token.
        
        Returns:
            Valid JWT access token
            
        Raises:
            AuthenticationError: If authentication fails
        """
        async with self._token_lock:
            # Check if current token is still valid (with 60s buffer)
            if self._access_token and time.time() < (self._token_expiry - 60):
                return self._access_token
            
            # Need to get a new token
            logger.debug("Obtaining new access token")
            
            client = await self._get_client()
            
            try:
                response = await client.post(
                    f"{self._api_prefix}/auth/token",
                    json={
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret
                    }
                )
                
                if response.status_code == 401:
                    raise AuthenticationError(
                        f"Authentication failed: {response.json().get('detail', 'Invalid credentials')}"
                    )
                
                response.raise_for_status()
                data = response.json()
                
                self._access_token = data["access_token"]
                self._token_expiry = time.time() + data.get("expires_in", 1800)
                
                logger.info(
                    f"Obtained access token (expires in {data.get('expires_in', 1800)}s)"
                )
                
                return self._access_token
                
            except httpx.RequestError as e:
                raise ServiceUnavailableError(
                    f"Failed to connect to API service: {e}"
                )
    
    async def _request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make an authenticated request with retry and circuit breaker.
        
        Args:
            method: HTTP method
            path: API path (without prefix)
            **kwargs: Additional arguments for httpx
            
        Returns:
            Response JSON data
        """
        # Check circuit breaker
        can_proceed, error = self._circuit_breaker.can_proceed()
        if not can_proceed:
            raise CircuitOpenError(error)
        
        # Add correlation ID header
        headers = kwargs.pop('headers', {})
        correlation_id = get_correlation_id()
        if correlation_id:
            headers['X-Correlation-ID'] = correlation_id
        
        # Get token
        token = await self._ensure_token()
        headers['Authorization'] = f'Bearer {token}'
        
        client = await self._get_client()
        full_path = f"{self._api_prefix}{path}"
        
        last_error = None
        _token_refresh_attempts = 0
        _max_token_refreshes = 2  # Prevent infinite token refresh loops
        
        for attempt in range(self.config.max_retries + 1):
            try:
                response = await client.request(
                    method,
                    full_path,
                    headers=headers,
                    **kwargs
                )
                
                # Handle token expiry
                if response.status_code == 401:
                    _token_refresh_attempts += 1
                    if _token_refresh_attempts > _max_token_refreshes:
                        raise APIClientError("Token refresh failed after max attempts")
                    # Token expired, refresh and retry
                    self._access_token = None
                    token = await self._ensure_token()
                    headers['Authorization'] = f'Bearer {token}'
                    continue
                
                response.raise_for_status()
                
                # Success - record it
                self._circuit_breaker.record_success()
                return response.json()
                
            except httpx.TimeoutException as e:
                last_error = e
                logger.warning(
                    f"Request timeout (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}"
                )
                self._circuit_breaker.record_failure()
                
            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    f"Request error (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}"
                )
                self._circuit_breaker.record_failure()
                
            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    self._circuit_breaker.record_success()  # Not a service failure
                    raise APIClientError(
                        f"API error: {e.response.status_code} - {e.response.text}"
                    )
                
                last_error = e
                logger.warning(
                    f"HTTP error (attempt {attempt + 1}/{self.config.max_retries + 1}): {e}"
                )
                self._circuit_breaker.record_failure()
            
            # Exponential backoff with jitter (H17 fix)
            if attempt < self.config.max_retries:
                delay = min(
                    self.config.retry_delay_seconds * (
                        self.config.retry_exponential_base ** attempt
                    ),
                    self.config.retry_max_delay_seconds
                )
                # Add random jitter (±25%) to prevent thundering herd
                jitter = delay * random.uniform(-0.25, 0.25)
                delay = max(0.1, delay + jitter)
                logger.debug(f"Retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
        
        raise ServiceUnavailableError(
            f"API request failed after {self.config.max_retries + 1} attempts: {last_error}"
        )
    
    # =========================================================================
    # PUBLIC API METHODS
    # =========================================================================
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check API service health.
        
        Returns:
            Health status dictionary
        """
        return await self._request('GET', '/health')
    
    async def get_models(self) -> Dict[str, Any]:
        """
        Get available spaCy NER models.
        
        Returns:
            Dictionary with model information
        """
        return await self._request('GET', '/v1/models')
    
    async def get_pi_types(self) -> Dict[str, Any]:
        """
        Get supported PI types.
        
        Returns:
            Dictionary with PI type information
        """
        return await self._request('GET', '/v1/pi-types')
    
    async def redact_text(
        self,
        text: str,
        fast_mode: bool = False,
        include_details: bool = False,
        spacy_model: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Redact PI from a single text string.
        
        Args:
            text: Text to redact
            fast_mode: Use fast mode (NER disabled)
            include_details: Include detailed redaction info
            spacy_model: Specific spaCy model to use
            request_id: Optional request ID for tracking
            
        Returns:
            Dictionary with redacted text and metadata
        """
        payload = {
            "text": text,
            "enable_ner": not fast_mode,
            "include_details": include_details,
        }
        
        if spacy_model:
            payload["spacy_model"] = spacy_model
        if request_id:
            payload["request_id"] = request_id
        
        return await self._request('POST', '/v1/redact', json=payload)
    
    async def redact_batch(
        self,
        texts: List[str],
        fast_mode: bool = False,
        include_details: bool = False,
        spacy_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Redact PI from multiple text strings.
        
        Args:
            texts: List of texts to redact
            fast_mode: Use fast mode (NER disabled)
            include_details: Include detailed redaction info
            spacy_model: Specific spaCy model to use
            
        Returns:
            Dictionary with results list and metadata
        """
        payload = {
            "texts": texts,
            "enable_ner": not fast_mode,
            "include_details": include_details,
        }
        
        if spacy_model:
            payload["spacy_model"] = spacy_model
        
        return await self._request('POST', '/v1/redact/batch', json=payload)
    
    async def detect_api_prefix(self) -> str:
        """
        Detect the API prefix (/dev or /prod) by checking endpoints.
        
        Returns:
            API prefix string
        """
        client = await self._get_client()
        
        # Try /dev first
        for prefix in ['/dev', '/prod']:
            try:
                # Try to get token (doesn't require existing auth)
                response = await client.post(
                    f"{prefix}/auth/token",
                    json={
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret
                    },
                    timeout=5.0
                )
                if response.status_code in [200, 401]:  # Endpoint exists
                    self._api_prefix = prefix
                    logger.info(f"Detected API prefix: {prefix}")
                    return prefix
            except httpx.RequestError:
                continue
        
        # Default to /dev
        self._api_prefix = '/dev'
        return self._api_prefix
    
    def get_circuit_state(self) -> str:
        """Get current circuit breaker state."""
        return self._circuit_breaker.state.value
    
    def is_healthy(self) -> bool:
        """Check if the client considers the API healthy."""
        return self._circuit_breaker.state != CircuitState.OPEN


# Convenience function for creating client from config
def create_api_client(
    config_path: Optional[str] = None,
    **overrides
) -> PIRemoverAPIClient:
    """
    Create an API client from configuration.
    
    Args:
        config_path: Path to config file
        **overrides: Override specific settings
        
    Returns:
        Configured PIRemoverAPIClient
    """
    config = APIClientConfig.from_config(config_path)
    
    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return PIRemoverAPIClient(config=config)
