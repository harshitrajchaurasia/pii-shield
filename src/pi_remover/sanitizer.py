"""
Input Sanitization Module for PI Remover.

Provides comprehensive input sanitization to prevent:
- XSS (Cross-Site Scripting) via HTML/script injection
- SQL injection patterns
- Command injection patterns
- Control character injection
- Unicode normalization attacks

Usage:
    from pi_remover.sanitizer import InputSanitizer
    
    # Sanitize text before processing
    sanitized_text, warnings = InputSanitizer.validate_and_sanitize(text)
    
    # Check for dangerous patterns without modifying
    is_safe, issues = InputSanitizer.detect_dangerous_patterns(text)
"""

import re
import html
import unicodedata
import logging
from typing import Tuple, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class SanitizerConfig:
    """Configuration for input sanitizer."""
    
    # Maximum text length (prevent DoS)
    max_length: int = 10_000_000  # 10MB
    
    # Control character handling
    allow_newlines: bool = True
    allow_tabs: bool = True
    allow_carriage_return: bool = True
    
    # Unicode normalization form (NFC, NFKC, NFD, NFKD, or None)
    unicode_normalization: Optional[str] = "NFKC"
    
    # HTML entity handling
    escape_html: bool = False  # Don't escape by default (PI remover needs raw text)
    
    # Strip null bytes
    strip_null_bytes: bool = True
    
    # Log warnings for detected patterns
    log_warnings: bool = True


# Default configuration
DEFAULT_CONFIG = SanitizerConfig()


# ============================================================================
# Dangerous Pattern Definitions
# ============================================================================

# SQL Injection patterns
SQL_INJECTION_PATTERNS = [
    re.compile(r"(?:--|#|/\*)\s*$", re.IGNORECASE),  # SQL comments at end
    re.compile(r";\s*(?:DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)\s+", re.IGNORECASE),
    re.compile(r"'\s*OR\s+'?\d+'?\s*=\s*'?\d+", re.IGNORECASE),  # ' OR '1'='1
    re.compile(r"'\s*OR\s+'\w+'\s*=\s*'\w+'", re.IGNORECASE),  # ' OR 'a'='a
    re.compile(r"UNION\s+(?:ALL\s+)?SELECT", re.IGNORECASE),
    re.compile(r"(?:EXEC|EXECUTE)\s*\(?\s*(?:xp_|sp_)", re.IGNORECASE),  # SQL Server procedures
]

# Command Injection patterns
COMMAND_INJECTION_PATTERNS = [
    re.compile(r"[;&|]\s*(?:cat|ls|dir|rm|del|wget|curl|bash|sh|cmd|powershell)", re.IGNORECASE),
    re.compile(r"\$\(\s*\w+", re.IGNORECASE),  # $(command)
    re.compile(r"`[^`]+`"),  # `command`
    re.compile(r">\s*/(?:dev/|etc/|tmp/)"),  # Redirect to sensitive paths
    re.compile(r"\|\s*(?:bash|sh|zsh|cmd|powershell)", re.IGNORECASE),
]

# Script Injection patterns (XSS)
SCRIPT_INJECTION_PATTERNS = [
    re.compile(r"<\s*script\b[^>]*>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"on\w+\s*=\s*[\"'][^\"']*[\"']", re.IGNORECASE),  # onclick="..."
    re.compile(r"<\s*iframe\b", re.IGNORECASE),
    re.compile(r"<\s*object\b", re.IGNORECASE),
    re.compile(r"<\s*embed\b", re.IGNORECASE),
    re.compile(r"<\s*svg\b[^>]*\s+on\w+", re.IGNORECASE),  # SVG with event handlers
    re.compile(r"expression\s*\(", re.IGNORECASE),  # CSS expression()
    re.compile(r"vbscript\s*:", re.IGNORECASE),
    re.compile(r"data\s*:\s*text/html", re.IGNORECASE),  # data: URI with HTML
]

# Path Traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    re.compile(r"\.\.[\\/]"),  # ../
    re.compile(r"[\\/]\.\."),  # /..
    re.compile(r"%2e%2e[\\/]", re.IGNORECASE),  # URL encoded ../
    re.compile(r"\.\.%2f", re.IGNORECASE),  # Mixed encoding
]

# Null byte injection
NULL_BYTE_PATTERN = re.compile(r"\x00")

# Control characters (excluding allowed ones)
def get_control_char_pattern(config: SanitizerConfig) -> re.Pattern:
    """Build control character pattern based on config."""
    # Control chars are 0x00-0x1F and 0x7F
    # We may allow \n (0x0A), \r (0x0D), \t (0x09)
    allowed = []
    if config.allow_newlines:
        allowed.append(r"\x0a")
    if config.allow_carriage_return:
        allowed.append(r"\x0d")
    if config.allow_tabs:
        allowed.append(r"\x09")
    
    if allowed:
        allowed_str = "".join(allowed)
        # Match control chars except allowed ones
        return re.compile("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]")
    else:
        return re.compile(r"[\x00-\x1f\x7f]")


# ============================================================================
# Detection Results
# ============================================================================

@dataclass
class DetectionResult:
    """Result of pattern detection."""
    is_safe: bool
    issues: List[str] = field(default_factory=list)
    categories: Set[str] = field(default_factory=set)
    
    def add_issue(self, category: str, description: str):
        self.is_safe = False
        self.issues.append(description)
        self.categories.add(category)


@dataclass
class SanitizationResult:
    """Result of sanitization operation."""
    text: str
    was_modified: bool
    warnings: List[str] = field(default_factory=list)
    removed_chars: int = 0
    
    def add_warning(self, warning: str):
        self.warnings.append(warning)


# ============================================================================
# Main Sanitizer Class
# ============================================================================

class InputSanitizer:
    """
    Comprehensive input sanitization for text processing.
    
    Provides detection of dangerous patterns and sanitization of input text.
    Thread-safe - all methods are stateless class methods.
    """
    
    # -------------------------------------------------------------------------
    # Detection Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    def detect_sql_injection(cls, text: str) -> List[str]:
        """Detect potential SQL injection patterns."""
        issues = []
        for pattern in SQL_INJECTION_PATTERNS:
            if pattern.search(text):
                issues.append(f"SQL injection pattern detected: {pattern.pattern[:50]}")
        return issues
    
    @classmethod
    def detect_command_injection(cls, text: str) -> List[str]:
        """Detect potential command injection patterns."""
        issues = []
        for pattern in COMMAND_INJECTION_PATTERNS:
            if pattern.search(text):
                issues.append(f"Command injection pattern detected: {pattern.pattern[:50]}")
        return issues
    
    @classmethod
    def detect_script_injection(cls, text: str) -> List[str]:
        """Detect potential XSS/script injection patterns."""
        issues = []
        for pattern in SCRIPT_INJECTION_PATTERNS:
            if pattern.search(text):
                issues.append(f"Script injection pattern detected: {pattern.pattern[:50]}")
        return issues
    
    @classmethod
    def detect_path_traversal(cls, text: str) -> List[str]:
        """Detect potential path traversal patterns."""
        issues = []
        for pattern in PATH_TRAVERSAL_PATTERNS:
            if pattern.search(text):
                issues.append(f"Path traversal pattern detected: {pattern.pattern[:30]}")
        return issues
    
    @classmethod
    def detect_dangerous_patterns(
        cls, 
        text: str, 
        check_sql: bool = True,
        check_command: bool = True,
        check_script: bool = True,
        check_path: bool = True,
    ) -> DetectionResult:
        """
        Comprehensive detection of dangerous patterns in text.
        
        Args:
            text: Text to analyze
            check_sql: Check for SQL injection patterns
            check_command: Check for command injection patterns
            check_script: Check for XSS/script injection patterns
            check_path: Check for path traversal patterns
            
        Returns:
            DetectionResult with safety status and any issues found
        """
        result = DetectionResult(is_safe=True)
        
        if not text:
            return result
        
        if check_sql:
            for issue in cls.detect_sql_injection(text):
                result.add_issue("sql_injection", issue)
        
        if check_command:
            for issue in cls.detect_command_injection(text):
                result.add_issue("command_injection", issue)
        
        if check_script:
            for issue in cls.detect_script_injection(text):
                result.add_issue("script_injection", issue)
        
        if check_path:
            for issue in cls.detect_path_traversal(text):
                result.add_issue("path_traversal", issue)
        
        return result
    
    # -------------------------------------------------------------------------
    # Sanitization Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    def remove_control_chars(
        cls, 
        text: str, 
        config: SanitizerConfig = DEFAULT_CONFIG
    ) -> Tuple[str, int]:
        """
        Remove control characters from text.
        
        Returns:
            Tuple of (sanitized_text, number_of_chars_removed)
        """
        if not text:
            return text, 0
        
        pattern = get_control_char_pattern(config)
        
        # Count occurrences before removal
        matches = pattern.findall(text)
        removed_count = len(matches)
        
        # Remove control characters
        sanitized = pattern.sub("", text)
        
        return sanitized, removed_count
    
    @classmethod
    def remove_null_bytes(cls, text: str) -> Tuple[str, int]:
        """
        Remove null bytes from text.
        
        Returns:
            Tuple of (sanitized_text, number_of_null_bytes_removed)
        """
        if not text:
            return text, 0
        
        count = text.count("\x00")
        sanitized = text.replace("\x00", "")
        
        return sanitized, count
    
    @classmethod
    def normalize_unicode(
        cls, 
        text: str, 
        form: str = "NFKC"
    ) -> str:
        """
        Normalize Unicode text to prevent homograph attacks.
        
        Args:
            text: Text to normalize
            form: Normalization form (NFC, NFKC, NFD, NFKD)
            
        Returns:
            Normalized text
        """
        if not text:
            return text
        
        try:
            return unicodedata.normalize(form, text)
        except Exception as e:
            logger.warning(f"Unicode normalization failed: {e}")
            return text
    
    @classmethod
    def escape_html_entities(cls, text: str) -> str:
        """
        Escape HTML entities to prevent XSS.
        
        Note: Only use this if the text will be rendered as HTML.
        For PI removal processing, raw text should be preserved.
        """
        if not text:
            return text
        
        return html.escape(text, quote=True)
    
    @classmethod
    def sanitize(
        cls, 
        text: str, 
        config: SanitizerConfig = DEFAULT_CONFIG
    ) -> SanitizationResult:
        """
        Sanitize text by applying configured sanitization steps.
        
        Args:
            text: Text to sanitize
            config: Sanitization configuration
            
        Returns:
            SanitizationResult with sanitized text and metadata
        """
        result = SanitizationResult(text=text, was_modified=False)
        
        if not text:
            return result
        
        original_text = text
        total_removed = 0
        
        # 1. Check length
        if len(text) > config.max_length:
            result.add_warning(f"Text truncated from {len(text)} to {config.max_length} chars")
            text = text[:config.max_length]
        
        # 2. Remove null bytes
        if config.strip_null_bytes:
            text, null_count = cls.remove_null_bytes(text)
            if null_count > 0:
                result.add_warning(f"Removed {null_count} null byte(s)")
                total_removed += null_count
        
        # 3. Remove control characters
        text, ctrl_count = cls.remove_control_chars(text, config)
        if ctrl_count > 0:
            result.add_warning(f"Removed {ctrl_count} control character(s)")
            total_removed += ctrl_count
        
        # 4. Unicode normalization
        if config.unicode_normalization:
            normalized = cls.normalize_unicode(text, config.unicode_normalization)
            if normalized != text:
                result.add_warning(f"Text was Unicode normalized ({config.unicode_normalization})")
                text = normalized
        
        # 5. HTML escaping (only if configured - off by default for PI removal)
        if config.escape_html:
            escaped = cls.escape_html_entities(text)
            if escaped != text:
                result.add_warning("HTML entities were escaped")
                text = escaped
        
        result.text = text
        result.was_modified = text != original_text
        result.removed_chars = total_removed
        
        return result
    
    @classmethod
    def validate_and_sanitize(
        cls, 
        text: str, 
        config: SanitizerConfig = DEFAULT_CONFIG,
        detect_patterns: bool = True,
        log_warnings: bool = True,
    ) -> Tuple[str, List[str]]:
        """
        Validate text for dangerous patterns and sanitize.
        
        This is the main entry point for input sanitization.
        
        Args:
            text: Text to validate and sanitize
            config: Sanitization configuration
            detect_patterns: Whether to check for dangerous patterns
            log_warnings: Whether to log warnings
            
        Returns:
            Tuple of (sanitized_text, list_of_warnings)
        """
        warnings = []
        
        if not text:
            return text, warnings
        
        # 1. Detect dangerous patterns (warning only - we don't block)
        if detect_patterns:
            detection = cls.detect_dangerous_patterns(text)
            if not detection.is_safe:
                for issue in detection.issues:
                    warnings.append(f"Warning: {issue}")
                    if log_warnings and config.log_warnings:
                        logger.warning(f"Dangerous pattern in input: {issue}")
        
        # 2. Sanitize
        sanitization = cls.sanitize(text, config)
        warnings.extend(sanitization.warnings)
        
        if log_warnings and config.log_warnings and sanitization.was_modified:
            logger.info(f"Input was sanitized: {len(sanitization.warnings)} modifications")
        
        return sanitization.text, warnings
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    def is_safe(cls, text: str) -> bool:
        """
        Quick check if text is safe (no dangerous patterns).
        
        Returns:
            True if no dangerous patterns detected
        """
        if not text:
            return True
        
        detection = cls.detect_dangerous_patterns(text)
        return detection.is_safe
    
    @classmethod
    def get_text_stats(cls, text: str) -> dict:
        """
        Get statistics about the text for logging/debugging.
        
        Returns:
            Dict with text statistics
        """
        if not text:
            return {"length": 0, "lines": 0, "has_unicode": False}
        
        return {
            "length": len(text),
            "lines": text.count("\n") + 1,
            "has_unicode": any(ord(c) > 127 for c in text),
            "has_control_chars": bool(re.search(r"[\x00-\x1f\x7f]", text)),
            "has_null_bytes": "\x00" in text,
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def sanitize_text(text: str, **kwargs) -> str:
    """
    Convenience function for quick text sanitization.
    
    Args:
        text: Text to sanitize
        **kwargs: Additional arguments passed to validate_and_sanitize
        
    Returns:
        Sanitized text (warnings are logged but not returned)
    """
    sanitized, _ = InputSanitizer.validate_and_sanitize(text, **kwargs)
    return sanitized


def is_safe_input(text: str) -> bool:
    """
    Convenience function for quick safety check.
    
    Args:
        text: Text to check
        
    Returns:
        True if no dangerous patterns detected
    """
    return InputSanitizer.is_safe(text)


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "InputSanitizer",
    "SanitizerConfig",
    "SanitizationResult",
    "DetectionResult",
    "sanitize_text",
    "is_safe_input",
    "DEFAULT_CONFIG",
]
