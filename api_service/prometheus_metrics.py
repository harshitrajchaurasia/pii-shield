"""
Prometheus Metrics Module for PI Remover API Service.

Provides comprehensive metrics for monitoring PI removal operations:
- Request counts and latencies
- Redaction statistics by PI type
- Model loading status
- Error tracking
- Resource utilization

Usage:
    from prometheus_metrics import metrics, metrics_endpoint
    
    # Record a request
    with metrics.request_timer("redact"):
        result = process_request()
    
    # Record redactions
    metrics.record_redactions({"email": 5, "phone": 3})
    
    # Expose /metrics endpoint
    app.get("/metrics")(metrics_endpoint)
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Check if prometheus_client is available
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        CollectorRegistry,
        generate_latest,
        CONTENT_TYPE_LATEST,
        REGISTRY,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed. Metrics will be no-ops.")


# ============================================================================
# Fallback implementations when prometheus_client is not available
# ============================================================================

class NoOpMetric:
    """No-operation metric for when prometheus_client is not installed."""
    def labels(self, *args, **kwargs):
        return self
    def inc(self, *args, **kwargs):
        pass
    def dec(self, *args, **kwargs):
        pass
    def set(self, *args, **kwargs):
        pass
    def observe(self, *args, **kwargs):
        pass
    def info(self, *args, **kwargs):
        pass
    def time(self):
        return self._timer_context()
    
    @contextmanager
    def _timer_context(self):
        yield


# ============================================================================
# Prometheus Metrics Definitions
# ============================================================================

if PROMETHEUS_AVAILABLE:
    # Request metrics
    REQUEST_COUNT = Counter(
        'pi_remover_requests_total',
        'Total number of PI removal requests',
        ['endpoint', 'status', 'mode']
    )
    
    REQUEST_LATENCY = Histogram(
        'pi_remover_request_duration_seconds',
        'Request latency in seconds',
        ['endpoint'],
        buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
    )
    
    # Redaction metrics
    REDACTIONS_TOTAL = Counter(
        'pi_remover_redactions_total',
        'Total number of PI items redacted',
        ['pi_type']
    )
    
    TEXT_PROCESSED_BYTES = Counter(
        'pi_remover_text_processed_bytes_total',
        'Total bytes of text processed',
        ['endpoint']
    )
    
    BATCH_SIZE = Histogram(
        'pi_remover_batch_size',
        'Batch sizes for batch processing requests',
        buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000)
    )
    
    # Model metrics
    MODEL_LOADED = Gauge(
        'pi_remover_model_loaded',
        'Whether a spaCy model is loaded (1=loaded, 0=not loaded)',
        ['model_name']
    )
    
    MODEL_LOAD_TIME = Gauge(
        'pi_remover_model_load_seconds',
        'Time taken to load spaCy model',
        ['model_name']
    )
    
    # Error metrics
    ERRORS_TOTAL = Counter(
        'pi_remover_errors_total',
        'Total number of errors',
        ['endpoint', 'error_type']
    )
    
    # Connection metrics
    ACTIVE_REQUESTS = Gauge(
        'pi_remover_active_requests',
        'Number of requests currently being processed',
        ['endpoint']
    )
    
    # Application info
    APP_INFO = Info(
        'pi_remover',
        'PI Remover application information'
    )
    
else:
    # Fallback no-op metrics
    REQUEST_COUNT = NoOpMetric()
    REQUEST_LATENCY = NoOpMetric()
    REDACTIONS_TOTAL = NoOpMetric()
    TEXT_PROCESSED_BYTES = NoOpMetric()
    BATCH_SIZE = NoOpMetric()
    MODEL_LOADED = NoOpMetric()
    MODEL_LOAD_TIME = NoOpMetric()
    ERRORS_TOTAL = NoOpMetric()
    ACTIVE_REQUESTS = NoOpMetric()
    APP_INFO = NoOpMetric()


# ============================================================================
# Metrics Manager Class
# ============================================================================

class PrometheusMetrics:
    """
    Centralized metrics manager for PI Remover.
    
    Provides a clean interface for recording metrics throughout the application.
    Falls back to no-ops if prometheus_client is not installed.
    """
    
    def __init__(self):
        self.enabled = PROMETHEUS_AVAILABLE
        self._start_time = time.time()
        
        if self.enabled:
            # Set application info
            APP_INFO.info({
                'version': self._get_version(),
                'python_version': self._get_python_version(),
            })
    
    def _get_version(self) -> str:
        """Get application version from pyproject.toml."""
        try:
            import tomllib
            with open('pyproject.toml', 'rb') as f:
                return tomllib.load(f).get('project', {}).get('version', 'unknown')
        except Exception:
            return 'unknown'
    
    def _get_python_version(self) -> str:
        """Get Python version."""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    @property
    def uptime_seconds(self) -> float:
        """Get application uptime in seconds."""
        return time.time() - self._start_time
    
    # -------------------------------------------------------------------------
    # Request Metrics
    # -------------------------------------------------------------------------
    
    def record_request(
        self,
        endpoint: str,
        status: str = "success",
        mode: str = "full",
        duration_seconds: Optional[float] = None
    ):
        """Record a completed request."""
        REQUEST_COUNT.labels(endpoint=endpoint, status=status, mode=mode).inc()
        if duration_seconds is not None:
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration_seconds)
    
    @contextmanager
    def request_timer(self, endpoint: str):
        """
        Context manager for timing requests.
        
        Usage:
            with metrics.request_timer("redact"):
                result = process_request()
        """
        ACTIVE_REQUESTS.labels(endpoint=endpoint).inc()
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
            ACTIVE_REQUESTS.labels(endpoint=endpoint).dec()
    
    def track_request(self, endpoint: str):
        """
        Decorator for tracking request metrics.
        
        Usage:
            @metrics.track_request("redact")
            async def redact_endpoint(...):
                ...
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                with self.request_timer(endpoint):
                    try:
                        result = await func(*args, **kwargs)
                        self.record_request(endpoint, status="success")
                        return result
                    except Exception as e:
                        self.record_request(endpoint, status="error")
                        self.record_error(endpoint, type(e).__name__)
                        raise
            return wrapper
        return decorator
    
    # -------------------------------------------------------------------------
    # Redaction Metrics
    # -------------------------------------------------------------------------
    
    def record_redactions(self, redaction_counts: Dict[str, int]):
        """
        Record redaction counts by PI type.
        
        Args:
            redaction_counts: Dict mapping PI type to count, e.g. {"email": 5, "phone": 3}
        """
        for pi_type, count in redaction_counts.items():
            REDACTIONS_TOTAL.labels(pi_type=pi_type.lower()).inc(count)
    
    def record_text_processed(self, endpoint: str, byte_count: int):
        """Record bytes of text processed."""
        TEXT_PROCESSED_BYTES.labels(endpoint=endpoint).inc(byte_count)
    
    def record_batch_size(self, size: int):
        """Record batch size for batch operations."""
        BATCH_SIZE.observe(size)
    
    # -------------------------------------------------------------------------
    # Model Metrics
    # -------------------------------------------------------------------------
    
    def record_model_loaded(self, model_name: str, load_time_seconds: float):
        """Record that a model was loaded."""
        MODEL_LOADED.labels(model_name=model_name).set(1)
        MODEL_LOAD_TIME.labels(model_name=model_name).set(load_time_seconds)
    
    def record_model_unloaded(self, model_name: str):
        """Record that a model was unloaded."""
        MODEL_LOADED.labels(model_name=model_name).set(0)
    
    # -------------------------------------------------------------------------
    # Error Metrics
    # -------------------------------------------------------------------------
    
    def record_error(self, endpoint: str, error_type: str = "unknown"):
        """Record an error occurrence."""
        ERRORS_TOTAL.labels(endpoint=endpoint, error_type=error_type).inc()
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def get_metrics_output(self) -> bytes:
        """Generate Prometheus metrics output."""
        if not self.enabled:
            return b"# Prometheus metrics not available (prometheus_client not installed)\n"
        return generate_latest(REGISTRY)
    
    def get_content_type(self) -> str:
        """Get the content type for metrics output."""
        if not self.enabled:
            return "text/plain; charset=utf-8"
        return CONTENT_TYPE_LATEST


# ============================================================================
# Singleton Instance
# ============================================================================

# Global metrics instance
metrics = PrometheusMetrics()


# ============================================================================
# FastAPI Integration
# ============================================================================

def create_metrics_endpoint():
    """
    Create a FastAPI endpoint function for /metrics.
    
    Usage:
        from prometheus_metrics import create_metrics_endpoint
        
        app.get("/metrics")(create_metrics_endpoint())
    """
    from fastapi import Response
    
    async def metrics_endpoint():
        """
        Prometheus metrics endpoint.
        
        Returns metrics in Prometheus text format for scraping.
        This endpoint should NOT require authentication for Prometheus to scrape.
        """
        return Response(
            content=metrics.get_metrics_output(),
            media_type=metrics.get_content_type()
        )
    
    return metrics_endpoint


def create_metrics_middleware():
    """
    Create a Starlette middleware for automatic request tracking.
    
    Usage:
        from prometheus_metrics import create_metrics_middleware
        
        app.add_middleware(create_metrics_middleware())
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    
    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Skip metrics endpoint to avoid recursion
            if request.url.path == "/metrics":
                return await call_next(request)
            
            endpoint = request.url.path
            start_time = time.time()
            
            ACTIVE_REQUESTS.labels(endpoint=endpoint).inc()
            
            try:
                response = await call_next(request)
                status = "success" if response.status_code < 400 else "error"
                REQUEST_COUNT.labels(
                    endpoint=endpoint,
                    status=status,
                    mode="unknown"  # Would need to be set by handler
                ).inc()
                return response
            except Exception as e:
                REQUEST_COUNT.labels(endpoint=endpoint, status="error", mode="unknown").inc()
                ERRORS_TOTAL.labels(endpoint=endpoint, error_type=type(e).__name__).inc()
                raise
            finally:
                duration = time.time() - start_time
                REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
                ACTIVE_REQUESTS.labels(endpoint=endpoint).dec()
    
    return PrometheusMiddleware


# ============================================================================
# Export
# ============================================================================

__all__ = [
    'metrics',
    'PrometheusMetrics',
    'create_metrics_endpoint',
    'create_metrics_middleware',
    'PROMETHEUS_AVAILABLE',
]
