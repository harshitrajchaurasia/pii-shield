"""
Centralized Structured Logging for PI Remover Services.

Provides ELK/Splunk-compatible JSON logging with:
- Correlation IDs for request tracing across services
- Structured JSON format for log aggregation
- Automatic PI masking in logs
- Service identification

Usage:
    from shared.logging_config import setup_structured_logging, get_correlation_id
    
    # Setup at service startup
    setup_structured_logging(service_name='api_service')
    
    # In request handlers
    logger.info("Processing request", extra={
        'correlation_id': get_correlation_id(),
        'user_id': 'user123',
        'action': 'redact_text'
    })

Version: 2.9.0
"""

import os
import sys
import json
import logging
import re
import time
import contextvars
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path

# Context variable for request correlation ID
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)


def get_correlation_id() -> Optional[str]:
    """Get the current request's correlation ID."""
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> contextvars.Token:
    """Set the correlation ID for the current request context."""
    return _correlation_id.set(correlation_id)


class PIRedactingFilter(logging.Filter):
    """
    Logging filter that masks potential PI in log messages.
    
    Prevents accidental PI leakage in logs by masking:
    - Email addresses
    - Phone numbers
    - Credit card numbers
    - SSN patterns
    """
    
    # Patterns to mask
    PATTERNS = [
        (re.compile(r'\b[\w.+-]+@[\w.-]+\.\w+\b'), '[EMAIL]'),
        (re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE]'),
        (re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'), '[CARD]'),
        (re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'), '[SSN]'),
        (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'), '[IP]'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Mask PI patterns in the log message."""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        
        # Also mask in args if present
        if hasattr(record, 'args') and record.args:
            masked_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    masked = arg
                    for pattern, replacement in self.PATTERNS:
                        masked = pattern.sub(replacement, masked)
                    masked_args.append(masked)
                else:
                    masked_args.append(arg)
            record.args = tuple(masked_args)
        
        return True


class StructuredJSONFormatter(logging.Formatter):
    """
    JSON log formatter for ELK/Splunk integration.
    
    Output format:
    {
        "timestamp": "2025-12-14T10:30:00.000Z",
        "level": "INFO",
        "service": "api_service",
        "logger": "pi-gateway",
        "correlation_id": "abc-123-def",
        "message": "Processing request",
        "extra": { ... }
    }
    """
    
    def __init__(self, service_name: str = 'pi-remover'):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base log structure
        log_data: Dict[str, Any] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'service': self.service_name,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add correlation ID if available
        correlation_id = get_correlation_id()
        if correlation_id:
            log_data['correlation_id'] = correlation_id
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields (skip internal logging fields)
        skip_fields = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'pathname', 'process', 'processName', 'relativeCreated',
            'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
            'taskName', 'message'
        }
        
        extra = {}
        for key, value in record.__dict__.items():
            if key not in skip_fields and not key.startswith('_'):
                try:
                    # Ensure value is JSON serializable
                    json.dumps(value)
                    extra[key] = value
                except (TypeError, ValueError):
                    extra[key] = str(value)
        
        if extra:
            log_data['extra'] = extra
        
        # Add source location for errors
        if record.levelno >= logging.ERROR:
            log_data['source'] = {
                'file': record.filename,
                'line': record.lineno,
                'function': record.funcName
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class StandardFormatter(logging.Formatter):
    """Standard human-readable formatter for console output."""
    
    def __init__(self, service_name: str = 'pi-remover'):
        self.service_name = service_name
        super().__init__(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def format(self, record: logging.LogRecord) -> str:
        """Add correlation ID to standard format if available."""
        correlation_id = get_correlation_id()
        if correlation_id:
            record.msg = f"[{correlation_id[:8]}] {record.msg}"
        return super().format(record)


def setup_structured_logging(
    service_name: str = 'pi-remover',
    log_level: str = 'INFO',
    json_format: bool = True,
    log_file: Optional[str] = None,
    console_output: bool = True
) -> None:
    """
    Configure structured logging for a service.
    
    Args:
        service_name: Name of the service (e.g., 'api_service', 'web_service')
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        json_format: Use JSON format (True for production, False for development)
        log_file: Optional path to log file
        console_output: Whether to output to console
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Add PI redacting filter
    pi_filter = PIRedactingFilter()
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.addFilter(pi_filter)
        
        if json_format:
            console_handler.setFormatter(StructuredJSONFormatter(service_name))
        else:
            console_handler.setFormatter(StandardFormatter(service_name))
        
        root_logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(pi_filter)
        
        # Always use JSON format for file logs (for log aggregation)
        file_handler.setFormatter(StructuredJSONFormatter(service_name))
        
        root_logger.addHandler(file_handler)
    
    # Log startup
    logging.info(f"Logging configured for {service_name}", extra={
        'log_level': log_level,
        'json_format': json_format,
        'log_file': log_file
    })


class RequestLoggingMiddleware:
    """
    FastAPI middleware for request logging with correlation IDs.
    
    Usage:
        from shared.logging_config import RequestLoggingMiddleware
        app.add_middleware(RequestLoggingMiddleware, service_name='api_service')
    """
    
    def __init__(self, app, service_name: str = 'pi-remover'):
        self.app = app
        self.service_name = service_name
        self.logger = logging.getLogger(f'{service_name}.request')
    
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        
        import secrets
        
        # Generate or extract correlation ID
        correlation_id = None
        for header_name, header_value in scope.get('headers', []):
            if header_name.lower() == b'x-correlation-id':
                correlation_id = header_value.decode('utf-8')
                break
        
        if not correlation_id:
            correlation_id = secrets.token_hex(8)
        
        # Set correlation ID in context
        token = set_correlation_id(correlation_id)
        
        # Track timing
        start_time = time.perf_counter()
        
        # Store response status
        response_status = [200]  # Default, will be updated
        
        async def send_wrapper(message):
            if message['type'] == 'http.response.start':
                response_status[0] = message['status']
                # Add correlation ID header to response
                headers = list(message.get('headers', []))
                headers.append((b'x-correlation-id', correlation_id.encode('utf-8')))
                message['headers'] = headers
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Log request completion
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            path = scope.get('path', '/')
            method = scope.get('method', 'GET')
            
            # Don't log health checks at INFO level
            log_level = logging.DEBUG if '/health' in path else logging.INFO
            
            self.logger.log(log_level, f"{method} {path}", extra={
                'method': method,
                'path': path,
                'status_code': response_status[0],
                'duration_ms': round(duration_ms, 2),
                'correlation_id': correlation_id
            })
            
            # Reset correlation ID
            _correlation_id.set(None)
