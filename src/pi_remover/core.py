"""
PI Remover - Facade module for backward compatibility.

This module re-exports all public APIs from the modular architecture.
All original functionality is preserved - imports continue to work as before.

Architecture refactored in v2.12.0 for maintainability.
Original monolithic code backed up to core_backup.py.

Two modes:
- Full (default): spaCy NER + regex + dictionaries (~1K rows/sec)
- Fast (--fast): regex + dictionaries only (~10x faster)

Works offline once you've downloaded the spaCy model.
"""

__version__ = "2.16.0"

# Re-exports from modular architecture
# Configuration
from .config import (
    PIRemoverConfig,
    load_config_from_yaml,
    config_to_dict,
    config_from_dict,
)

# Patterns
from .patterns import PIPatterns

# Dictionaries
from .dictionaries import (
    INDIAN_FIRST_NAMES,
    INDIAN_LAST_NAMES,
    COMPANY_NAMES,
    INTERNAL_SYSTEMS,
    get_all_names,
    get_first_names_lower,
    get_last_names_lower,
)

# Data classes
from .data_classes import (
    Redaction,
    RedactionResult,
    RedactionStats,
    count_redactions,
    generate_audit_report,
)

# Utilities
from .utils import (
    setup_logging,
    logger,
    get_cpu_count,
    get_memory_percent,
    configure_multiprocessing,
    DataCleaner,
    PSUTIL_AVAILABLE,
)

# NER
from .ner import (
    SpacyNER,
    SpacyModelManager,
    SPACY_AVAILABLE,
)

# Main PIRemover class
from .remover import PIRemover

# File processors
from .processors import (
    process_file,
    process_csv,
    process_dataframe,
    ValidationError,
)

# Backward compatible exports
# Security validation (optional - for file processing)
try:
    from .security import validate_file_security  # noqa: F401
    SECURITY_AVAILABLE = True
except ImportError:
    SECURITY_AVAILABLE = False
    def validate_file_security(path, strict=True):  # type: ignore[misc]
        return True, None

# Resource monitoring for auto-scaling (optional)
import os
import sys
try:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from shared.resource_monitor import (
        ResourceMonitor,
        get_platform_info,
    )
    RESOURCE_MONITOR_AVAILABLE = True
except ImportError:
    RESOURCE_MONITOR_AVAILABLE = False
    ResourceMonitor = None  # type: ignore[assignment,misc]
    get_platform_info = None  # type: ignore[assignment]

# CLI Support
def main():
    """Command-line interface for PI Remover."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="PI Remover - Remove personal information from text files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m pi_remover.core input.csv output.csv
  python -m pi_remover.core input.csv output.csv --fast
  python -m pi_remover.core input.csv output.csv --column "Description"
  python -m pi_remover.core input.xlsx output.xlsx --sheet "Data"
        """
    )
    
    parser.add_argument("input_file", help="Input file path (CSV, Excel, JSON, TXT, DOCX, PDF, HTML)")
    parser.add_argument("output_file", help="Output file path")
    parser.add_argument("--fast", action="store_true", help="Fast mode (no NER, regex only)")
    parser.add_argument("--column", "-c", help="Column to process (CSV/Excel)")
    parser.add_argument("--columns", nargs="+", help="Multiple columns to process")
    parser.add_argument("--sheet", "-s", help="Sheet name (Excel only)")
    parser.add_argument("--workers", "-w", type=int, help="Number of worker processes")
    parser.add_argument("--config", help="YAML config file path")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO")
    parser.add_argument("--version", "-v", action="version", version=f"PI Remover {__version__}")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(level=args.log_level)
    
    # Load config
    if args.config:
        config = load_config_from_yaml(args.config)
    else:
        config = PIRemoverConfig()
    
    # Apply CLI overrides
    if args.fast:
        config.enable_ner = False
    if args.workers:
        config.max_workers = args.workers
    
    # Determine columns
    columns = None
    if args.columns:
        columns = args.columns
    elif args.column:
        columns = [args.column]
    
    # Process file
    try:
        result = process_file(
            args.input_file,
            args.output_file,
            config=config,
            columns=columns,
            sheet_name=args.sheet,
        )
        
        if result:
            print(f"✓ Successfully processed {args.input_file}")
            print(f"  Output saved to: {args.output_file}")
            if hasattr(result, 'stats'):
                print(f"  Rows processed: {result.stats.get('rows', 'N/A')}")
        else:
            print(f"✗ Failed to process {args.input_file}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        print(f"✗ Error: {e}")
        sys.exit(1)


run_cli = main  # Alias used by pyproject.toml entry point and __main__.py

if __name__ == "__main__":
    main()


# Public API
__all__ = [
    # Version
    "__version__",
    
    # Configuration
    "PIRemoverConfig",
    "load_config_from_yaml",
    "config_to_dict",
    "config_from_dict",
    
    # Patterns
    "PIPatterns",
    
    # Dictionaries
    "INDIAN_FIRST_NAMES",
    "INDIAN_LAST_NAMES",
    "COMPANY_NAMES",
    "INTERNAL_SYSTEMS",
    "get_all_names",
    "get_first_names_lower",
    "get_last_names_lower",
    
    # Data classes
    "Redaction",
    "RedactionResult",
    "RedactionStats",
    "count_redactions",
    "generate_audit_report",
    
    # Utilities
    "setup_logging",
    "logger",
    "get_cpu_count",
    "get_memory_percent",
    "configure_multiprocessing",
    "DataCleaner",
    "PSUTIL_AVAILABLE",
    
    # NER
    "SpacyNER",
    "SpacyModelManager",
    "SPACY_AVAILABLE",
    
    # Main class
    "PIRemover",
    
    # File processors
    "process_file",
    "process_csv",
    "process_dataframe",
    "ValidationError",
    
    # Security
    "validate_file_security",
    "SECURITY_AVAILABLE",
    
    # Resource monitoring
    "RESOURCE_MONITOR_AVAILABLE",
    
    # CLI
    "main",
    "run_cli",
]
