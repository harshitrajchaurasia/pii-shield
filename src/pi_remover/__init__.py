"""
PI Remover - strips personal info from text.

Usage:
    from pi_remover import PIRemover, PIRemoverConfig
    
    remover = PIRemover(PIRemoverConfig(enable_ner=False))  # fast mode
    result = remover.redact("Contact john@test.com")
    print(result.redacted_text)  # Contact [EMAIL]

Architecture:
    v2.12.0 - Modular architecture refactoring
    - core.py now acts as facade for backward compatibility
    - Actual implementations in: config.py, patterns.py, dictionaries.py,
      data_classes.py, utils.py, ner.py, remover.py, processors/
"""

__version__ = "2.18.0"
__author__ = "PI Remover Team"

# Import from core module (facade pattern - maintains backward compatibility)
from pi_remover.core import (
    PIRemover,
    PIRemoverConfig,
    Redaction,
    RedactionResult,
    process_file,
    setup_logging,
)

# Import from security module
from pi_remover.security import (
    SecurityConfig,
    verify_bearer_token,
    generate_auth_token,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    InputValidator,
    FileSecurityValidator,
    AuditLogger,
    rate_limiter,
)

# Import from sanitizer module
from pi_remover.sanitizer import (
    InputSanitizer,
    SanitizerConfig,
    sanitize_text,
    is_safe_input,
)

# Import from model manager module
from pi_remover.model_manager import (
    SpacyModelManager,
    get_spacy_model,
    SPACY_AVAILABLE,
)

__all__ = [
    # Version
    "__version__",
    # Core classes
    "PIRemover",
    "PIRemoverConfig",
    "Redaction",
    "RedactionResult",
    # Processing functions
    "process_file",
    "setup_logging",
    # Security module
    "SecurityConfig",
    "verify_bearer_token",
    "generate_auth_token",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
    "InputValidator",
    "FileSecurityValidator",
    "AuditLogger",
    "rate_limiter",
    # Sanitizer module
    "InputSanitizer",
    "SanitizerConfig",
    "sanitize_text",
    "is_safe_input",
    # Model manager
    "SpacyModelManager",
    "get_spacy_model",
    "SPACY_AVAILABLE",
]
