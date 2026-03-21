"""
PI Remover Processors Package.

Contains file processor modules for different file formats:
- CSV (with multiprocessing support)
- Excel (.xlsx, .xls)
- JSON
- Text (.txt, .md, .log)
- Word (.docx)
- PowerPoint (.pptx)
- PDF
- HTML/XML

Usage:
    from pi_remover.processors import (
        process_file,
        process_csv,
        process_dataframe,
    )
"""

from pi_remover.processors.file_processor import (
    process_file,
    process_csv,
    process_dataframe,
    ValidationError,
    validate_file,
    validate_columns,
    validate_config,
)


__all__ = [
    'process_file',
    'process_csv',
    'process_dataframe',
    'ValidationError',
    'validate_file',
    'validate_columns',
    'validate_config',
]
