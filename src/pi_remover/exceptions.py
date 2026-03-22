"""
PI Remover Exception Hierarchy.

Provides structured exception classes for all PI removal operations.
Created as part of the v2.19.1 audit remediation.

Usage:
    from pi_remover.exceptions import (
        PIRemovalError, ConfigurationError, RedactionError,
        ModelLoadError, FileProcessingError, ValidationError,
        PatternError, DictionaryLoadError
    )
    
    try:
        result = remover.redact(text)
    except RedactionError as e:
        logger.error(f"Redaction failed: {e}")
    except PIRemovalError as e:
        logger.error(f"PI removal error: {e}")
"""


class PIRemovalError(Exception):
    """Base exception for all PI removal operations."""
    pass


class ConfigurationError(PIRemovalError):
    """Invalid or missing configuration."""
    pass


class RedactionError(PIRemovalError):
    """Redaction operation failed."""
    pass


class ModelLoadError(PIRemovalError):
    """Failed to load an ML model (e.g., spaCy)."""
    pass


class FileProcessingError(PIRemovalError):
    """File processing failed (encoding, format, I/O)."""
    pass


class ValidationError(PIRemovalError):
    """Input validation failed (text size, format, path)."""
    pass


class PatternError(PIRemovalError):
    """Regex pattern compilation or matching error."""
    pass


class DictionaryLoadError(PIRemovalError):
    """Failed to load name or other dictionaries."""
    pass


class SecurityError(PIRemovalError):
    """Security-related error (auth, sanitization)."""
    pass


__all__ = [
    'PIRemovalError',
    'ConfigurationError',
    'RedactionError',
    'ModelLoadError',
    'FileProcessingError',
    'ValidationError',
    'PatternError',
    'DictionaryLoadError',
    'SecurityError',
]
