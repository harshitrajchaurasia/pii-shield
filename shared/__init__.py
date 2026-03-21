"""
Shared modules for PI Remover Services.

This package contains shared utilities used by both api_service and web_service:
- config_loader: YAML configuration file loading
- redis_client: Redis connection management for distributed rate limiting
- logging_config: Centralized structured logging (ELK/Splunk compatible)

Version: 2.9.0
"""

from .config_loader import ConfigLoader, get_config
from .logging_config import setup_structured_logging, get_correlation_id, set_correlation_id

__all__ = [
    'ConfigLoader',
    'get_config',
    'setup_structured_logging',
    'get_correlation_id',
    'set_correlation_id',
]
