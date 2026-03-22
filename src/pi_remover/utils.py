"""
PI Remover Utilities Module.

Contains utility functions and classes:
- Logging setup
- Platform detection (OS, container, cloud)
- Resource management (CPU count, memory)
- Multiprocessing configuration
- DataCleaner for text preprocessing

Usage:
    from pi_remover.utils import (
        setup_logging,
        get_cpu_count,
        get_memory_percent,
        get_available_memory_gb,
        configure_multiprocessing,
        DataCleaner,
    )
"""

import logging
import multiprocessing as mp
import os
import platform
import re
import sys
import unicodedata
from typing import Dict, List, Optional

import pandas as pd


# Constants
DEFAULT_CPU_COUNT = 4
DEFAULT_MEMORY_GB = 4.0
DEFAULT_MEMORY_PERCENT = 50.0

# Module-level logger
logger = logging.getLogger("pi_remover")


# Platform Detection
try:
    PLATFORM_OS = platform.system().lower()  # windows, linux, darwin
except Exception:
    PLATFORM_OS = "unknown"

IS_WINDOWS = PLATFORM_OS == "windows"
IS_LINUX = PLATFORM_OS == "linux"
IS_MACOS = PLATFORM_OS == "darwin"
IS_UNKNOWN_OS = PLATFORM_OS not in ("windows", "linux", "darwin")

# Container/Cloud detection (safe - catches any exceptions)
try:
    IS_CONTAINER = (
        os.path.exists("/.dockerenv") or 
        os.environ.get("KUBERNETES_SERVICE_HOST") is not None or
        os.environ.get("K_SERVICE") is not None  # Cloud Run
    )
except Exception:
    IS_CONTAINER = False

try:
    IS_CLOUD = (
        os.environ.get("GOOGLE_CLOUD_PROJECT") is not None or
        os.environ.get("AWS_REGION") is not None or
        os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT") is not None
    )
except Exception:
    IS_CLOUD = False


# Optional Imports
# Try to import psutil for resource monitoring (optional)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


# Logging
def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """
    Set up logging with safe fallbacks.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logging
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("pi_remover")
    
    # Safe level parsing with fallback
    try:
        log_level = getattr(logging, level.upper(), logging.INFO)
    except Exception:
        log_level = logging.INFO
    logger.setLevel(log_level)
    
    # Clear existing handlers
    try:
        logger.handlers.clear()
    except Exception:
        pass  # Older Python versions might not have clear()
    
    # Create formatter with timestamp
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler (should always work)
    try:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    except Exception:
        pass  # If console fails, continue without it
    
    # File handler (optional, may fail due to permissions)
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # Don't fail startup if log file can't be created
            print(f"Warning: Could not create log file {log_file}: {e}")
    
    return logger


# Resource Management
def get_cpu_count() -> int:
    """
    Get CPU count, container-aware with safe fallbacks.
    
    Priority:
    1. Container cgroup limits (Linux)
    2. psutil (if available)
    3. multiprocessing.cpu_count()
    4. os.cpu_count()
    5. Default fallback (4 CPUs)
    
    Returns:
        Number of available CPUs
    """
    # Check for container CPU limits (Linux cgroups)
    if IS_LINUX:
        try:
            # cgroups v2
            if os.path.exists("/sys/fs/cgroup/cpu.max"):
                with open("/sys/fs/cgroup/cpu.max") as f:
                    parts = f.read().strip().split()
                    if parts[0] != "max":
                        quota = int(parts[0])
                        period = int(parts[1])
                        return max(1, int(quota / period))
            # cgroups v1
            quota_path = "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"
            period_path = "/sys/fs/cgroup/cpu/cpu.cfs_period_us"
            if os.path.exists(quota_path) and os.path.exists(period_path):
                with open(quota_path) as f:
                    quota = int(f.read().strip())
                with open(period_path) as f:
                    period = int(f.read().strip())
                if quota > 0:
                    return max(1, int(quota / period))
        except Exception:
            pass
    
    # Try psutil first (most reliable)
    if PSUTIL_AVAILABLE:
        try:
            return psutil.cpu_count(logical=True) or DEFAULT_CPU_COUNT
        except Exception:
            pass
    
    # Try multiprocessing
    try:
        count = mp.cpu_count()
        if count and count > 0:
            return count
    except (NotImplementedError, Exception):
        pass
    
    # Try os.cpu_count() as backup
    try:
        os_count = os.cpu_count()
        if os_count and os_count > 0:
            count = os_count
            return count
    except Exception:
        pass
    
    # Final fallback
    return DEFAULT_CPU_COUNT


def get_memory_percent() -> float:
    """
    Get memory usage percentage (cross-platform) with safe fallbacks.
    
    Returns:
        Memory usage percentage (0-100), or DEFAULT_MEMORY_PERCENT on failure
    """
    # Try psutil first (most reliable, cross-platform)
    if PSUTIL_AVAILABLE:
        try:
            return psutil.virtual_memory().percent
        except Exception:
            pass
    
    # Linux fallback via /proc/meminfo
    if IS_LINUX:
        try:
            meminfo = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        meminfo[parts[0].rstrip(":")] = int(parts[1])
            total = meminfo.get("MemTotal", 1)
            available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            if total > 0:
                return ((total - available) / total) * 100
        except Exception:
            pass
    
    # Default fallback - assume moderate usage
    return DEFAULT_MEMORY_PERCENT


def get_available_memory_gb() -> float:
    """
    Get available memory in GB with safe fallbacks.
    
    Returns:
        Available (free + cached) memory in gigabytes
    """
    # Try psutil first (most reliable, cross-platform)
    if PSUTIL_AVAILABLE:
        try:
            return psutil.virtual_memory().available / (1024 ** 3)
        except Exception:
            pass
    
    # Linux fallback via /proc/meminfo
    if IS_LINUX:
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        # Value is in KB, convert to GB
                        return int(line.split()[1]) / (1024 ** 2)
        except Exception:
            pass
    
    # Default fallback - conservative estimate
    return DEFAULT_MEMORY_GB


# Multiprocessing
def get_multiprocessing_method() -> str:
    """
    Get the appropriate multiprocessing start method for the current platform.
    
    - Windows: Only supports 'spawn' (new process with fresh Python interpreter)
    - macOS: Default changed to 'spawn' in Python 3.8+ (safer with fork-unsafe libs)
    - Linux: Defaults to 'fork' (faster, shares memory via copy-on-write)
    - Unknown OS: Use 'spawn' as safest default
    
    In containers, we prefer 'spawn' for better isolation and compatibility.
    
    Returns:
        Start method name ('spawn' or 'fork')
    """
    if IS_WINDOWS:
        return "spawn"  # Only option on Windows
    elif IS_MACOS:
        return "spawn"  # Default in Python 3.8+, safer with multiprocessing
    elif IS_CONTAINER:
        return "spawn"  # Safer in containerized environments
    elif IS_LINUX:
        return "fork"   # Linux default - faster due to copy-on-write
    else:
        # Unknown OS - use spawn as safest option
        return "spawn"


def configure_multiprocessing() -> str:
    """
    Configure multiprocessing for the current platform with safe fallbacks.
    
    Must be called in the main module before creating any Process or Pool.
    On Windows, this is especially critical because of the 'spawn' method.
    
    Returns:
        The start method that was configured or is currently active
    """
    logger = logging.getLogger("pi_remover")
    method = get_multiprocessing_method()
    try:
        mp.set_start_method(method, force=False)
        logger.debug(f"Multiprocessing start method configured: {method}")
        return method
    except RuntimeError:
        # Already set - this is normal
        try:
            current = mp.get_start_method()
            logger.debug(f"Multiprocessing start method already set: {current}")
            return current or method
        except Exception:
            return method
    except Exception as e:
        # Unexpected error - log and continue
        logger.warning(f"Could not configure multiprocessing: {e}")
        try:
            return mp.get_start_method() or method
        except Exception:
            return method


# Data Cleaner (v2.18.0)
class DataCleaner:
    """
    Cleans text before redaction (unicode, whitespace, etc).

    Preprocessing steps (v2.18.0):
    - NFKC Unicode normalization (ﬁ→fi, ²→2, Ｊｏｈｎ→John)
    - Strip zero-width/invisible Unicode characters
    - Fix encoding issues (mojibake)
    - Replace Unicode characters (smart quotes, dashes)
    - Decode HTML entities
    - Strip control characters
    - Normalize phone formats
    - Normalize whitespace
    """

    # Unicode replacements for common problematic characters
    UNICODE_REPLACEMENTS = {
        '\u2018': "'",  # Left single quote
        '\u2019': "'",  # Right single quote
        '\u201c': '"',  # Left double quote
        '\u201d': '"',  # Right double quote
        '\u2013': '-',  # En dash
        '\u2014': '-',  # Em dash
        '\u2026': '...',  # Ellipsis
        '\u00a0': ' ',  # Non-breaking space
        '\r\n': '\n',   # Windows newline
        '\r': '\n',     # Old Mac newline
    }

    # Zero-width and invisible Unicode characters (v2.18.0)
    # These can be used to hide/obfuscate PI and evade detection
    ZERO_WIDTH_PATTERN = re.compile(
        r'[\u200b-\u200f'    # Zero-width space, non-joiner, joiner, LTR/RTL marks
        r'\u2028-\u202f'     # Line/paragraph separators, directional formatting
        r'\u205f-\u206f'     # Medium math space, word joiner, function application, invisible operators
        r'\ufeff'            # BOM / Zero-width no-break space
        r'\u00ad'            # Soft hyphen
        r'\u034f'            # Combining grapheme joiner
        r'\u061c'            # Arabic letter mark
        r'\u115f\u1160'      # Hangul fillers
        r'\u17b4\u17b5'      # Khmer vowel inherent
        r'\u180e'            # Mongolian vowel separator
        r'\u2060-\u2064'     # Word joiner, invisible operators
        r'\u2066-\u206f'     # Directional isolates and formatting
        r'\u3164'            # Hangul filler
        r'\uffa0'            # Halfwidth Hangul filler
        r'\ufff0-\ufff8'     # Specials
        r']+'
    )

    # HTML entities
    HTML_ENTITIES = {
        '&nbsp;': ' ',
        '&amp;': '&',
        '&lt;': '<',
        '&gt;': '>',
        '&quot;': '"',
        '&apos;': "'",
        '&#39;': "'",
        '&ndash;': '-',
        '&mdash;': '-',
    }

    @classmethod
    def clean(cls, text: str, options: Optional[Dict[str, bool]] = None) -> str:
        """
        Clean and normalize text for better PI detection.

        Args:
            text: Input text to clean
            options: Dict of cleaning options (all True by default):
                - nfkc_normalize: Apply NFKC Unicode normalization (v2.18.0)
                - strip_zero_width: Remove zero-width/invisible chars (v2.18.0)
                - normalize_unicode: Replace smart quotes, dashes
                - decode_html: Decode HTML entities
                - normalize_whitespace: Collapse multiple spaces
                - normalize_phone_formats: Standardize phone separators
                - strip_control_chars: Remove control characters
                - fix_encoding: Fix common encoding issues

        Returns:
            Cleaned text
        """
        if not isinstance(text, str) or not text:
            return text

        opts = options or {}

        # Default all options to True
        nfkc_normalize = opts.get('nfkc_normalize', True)
        strip_zero_width = opts.get('strip_zero_width', True)
        normalize_unicode = opts.get('normalize_unicode', True)
        decode_html = opts.get('decode_html', True)
        normalize_whitespace = opts.get('normalize_whitespace', True)
        normalize_phone_formats = opts.get('normalize_phone_formats', True)
        strip_control_chars = opts.get('strip_control_chars', True)
        fix_encoding = opts.get('fix_encoding', True)

        result = text

        # 1. NFKC Unicode normalization (v2.18.0)
        # Normalizes: ﬁ→fi, ²→2, ①→1, Ｊｏｈｎ→John, ℡→TEL, etc.
        # Critical for detecting PI written with fullwidth or special Unicode chars
        if nfkc_normalize:
            result = unicodedata.normalize('NFKC', result)

        # 1b. Homoglyph normalization — map Cyrillic/Greek lookalikes to ASCII
        # Prevents bypass like: jоhn@cоmpany.cоm (Cyrillic о instead of Latin o)
        _HOMOGLYPH_MAP = {
            '\u0430': 'a', '\u0435': 'e', '\u043e': 'o', '\u0440': 'p',
            '\u0441': 'c', '\u0443': 'y', '\u0445': 'x', '\u0456': 'i',
            '\u0410': 'A', '\u0412': 'B', '\u0415': 'E', '\u041a': 'K',
            '\u041c': 'M', '\u041d': 'H', '\u041e': 'O', '\u0420': 'P',
            '\u0421': 'C', '\u0422': 'T', '\u0425': 'X',
            '\u03bf': 'o', '\u03b1': 'a', '\u03b5': 'e',  # Greek
        }
        result = result.translate(str.maketrans(_HOMOGLYPH_MAP))  # type: ignore[arg-type]

        # 2. Strip zero-width/invisible characters (v2.18.0)
        # Prevents PI obfuscation like: john​smith@email.com (zero-width space in middle)
        if strip_zero_width:
            result = cls.ZERO_WIDTH_PATTERN.sub('', result)

        # 3. Fix common encoding issues (mojibake)
        if fix_encoding:
            result = cls._fix_encoding(result)

        # 4. Replace Unicode characters (smart quotes, dashes)
        if normalize_unicode:
            for old, new in cls.UNICODE_REPLACEMENTS.items():
                result = result.replace(old, new)

        # 5. Decode HTML entities
        if decode_html:
            for entity, char in cls.HTML_ENTITIES.items():
                result = result.replace(entity, char)
            # Also handle numeric entities
            result = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), result)
            result = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), result)

        # 6. Strip control characters (except newlines and tabs)
        if strip_control_chars:
            result = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', result)

        # 7. Normalize phone number formats (helps regex matching)
        if normalize_phone_formats:
            # Protect IP addresses from phone normalization by temporarily replacing them
            ip_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?::\d{2,5})?\b'
            ip_placeholders: Dict[str, str] = {}

            def protect_ip(m: re.Match) -> str:
                placeholder = f"__IP_PLACEHOLDER_{len(ip_placeholders)}__"
                ip_placeholders[placeholder] = m.group(0)
                return placeholder

            result = re.sub(ip_pattern, protect_ip, result)

            # Now normalize phone formats (dots/spaces between digit groups)
            result = re.sub(r'(\+?\d{1,4})[\s.]+(\d)', r'\1 \2', result)

            # Restore IP addresses
            for placeholder, ip in ip_placeholders.items():
                result = result.replace(placeholder, ip)

        # 8. Normalize whitespace (do this last)
        if normalize_whitespace:
            # Collapse multiple spaces to single space
            result = re.sub(r'[ \t]+', ' ', result)
            # Collapse multiple newlines to max 2
            result = re.sub(r'\n{3,}', '\n\n', result)
            # Strip leading/trailing whitespace per line
            result = '\n'.join(line.strip() for line in result.split('\n'))

        return result.strip()
    
    @classmethod
    def _fix_encoding(cls, text: str) -> str:
        """Fix common encoding issues (mojibake)."""
        # Common UTF-8 mojibake patterns
        replacements = {
            'â€™': "'",
            'â€œ': '"',
            'â€': '"',
            'â€"': '-',
            'Ã©': 'é',
            'Ã¨': 'è',
            'Ã ': 'à',
            'Ã¢': 'â',
            'Ã´': 'ô',
            'Ã§': 'ç',
            'Ã¯': 'ï',
            'Ã¼': 'ü',
            'Ã¶': 'ö',
            'Ã¤': 'ä',
            'Ã±': 'ñ',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    
    @classmethod
    def clean_dataframe(
        cls, 
        df: pd.DataFrame, 
        columns: List[str], 
        options: Optional[Dict[str, bool]] = None
    ) -> pd.DataFrame:
        """
        Clean specified columns in a DataFrame.
        
        Args:
            df: Input DataFrame
            columns: Columns to clean
            options: Cleaning options
            
        Returns:
            DataFrame with cleaned columns
        """
        result = df.copy()
        for col in columns:
            if col in result.columns:
                result[col] = result[col].apply(
                    lambda x: cls.clean(str(x), options) if pd.notna(x) else x
                )
        return result


# Exports
__all__ = [
    # Constants
    'DEFAULT_CPU_COUNT',
    'DEFAULT_MEMORY_GB',
    'DEFAULT_MEMORY_PERCENT',
    # Platform detection
    'PLATFORM_OS',
    'IS_WINDOWS',
    'IS_LINUX',
    'IS_MACOS',
    'IS_UNKNOWN_OS',
    'IS_CONTAINER',
    'IS_CLOUD',
    'PSUTIL_AVAILABLE',
    # Logging
    'setup_logging',
    'logger',
    # Resource management
    'get_cpu_count',
    'get_memory_percent',
    'get_available_memory_gb',
    # Multiprocessing
    'get_multiprocessing_method',
    'configure_multiprocessing',
    # Data cleaning
    'DataCleaner',
]
