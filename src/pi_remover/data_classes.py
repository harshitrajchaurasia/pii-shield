"""
PI Remover Data Classes Module.

Contains data classes for PI detection and redaction:
- Redaction: Single redaction info
- RedactionResult: Result of redaction operation
- RedactionStats: Statistics for a redaction run

Usage:
    from pi_remover.data_classes import (
        Redaction,
        RedactionResult,
        RedactionStats,
    )
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Redaction:
    """
    Single redaction info.
    
    Attributes:
        original: Original text that was redacted
        replacement: Replacement token (e.g., "[EMAIL]")
        pi_type: Type of PI (EMAIL, PHONE, NAME, etc.)
        start: Start position in original text
        end: End position in original text
        confidence: Confidence score (0.0 - 1.0)
        detection_method: How it was detected (regex, ner, dictionary, context)
    """
    original: str           # Original text that was redacted
    replacement: str        # Replacement token (e.g., "[EMAIL]")
    pi_type: str           # Type of PI (EMAIL, PHONE, NAME, etc.)
    start: int             # Start position in original text
    end: int               # End position in original text
    confidence: float      # Confidence score (0.0 - 1.0)
    detection_method: str  # How it was detected (regex, ner, dictionary, context)


@dataclass
class RedactionResult:
    """
    Result of redaction operation with detailed information.
    
    Attributes:
        redacted_text: Final redacted text
        redactions: List of all redactions made
        processing_time_ms: Processing time in milliseconds
        original_length: Length of original text
        redacted_count: Number of redactions made
    """
    redacted_text: str                    # Final redacted text
    redactions: List[Redaction]           # List of all redactions made
    processing_time_ms: float             # Processing time in milliseconds
    original_length: int = 0              # Length of original text
    redacted_count: int = 0               # Number of redactions made

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'redacted_text': self.redacted_text,
            'redactions': [
                {
                    'original': r.original,
                    'replacement': r.replacement,
                    'type': r.pi_type,
                    'start': r.start,
                    'end': r.end,
                    'confidence': r.confidence,
                    'method': r.detection_method
                }
                for r in self.redactions
            ],
            'processing_time_ms': self.processing_time_ms,
            'original_length': self.original_length,
            'redacted_count': self.redacted_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedactionResult":
        """Create RedactionResult from dictionary."""
        redactions = [
            Redaction(
                original=r.get('original', ''),
                replacement=r.get('replacement', ''),
                pi_type=r.get('type', ''),
                start=r.get('start', 0),
                end=r.get('end', 0),
                confidence=r.get('confidence', 0.0),
                detection_method=r.get('method', '')
            )
            for r in data.get('redactions', [])
        ]
        return cls(
            redacted_text=data.get('redacted_text', ''),
            redactions=redactions,
            processing_time_ms=data.get('processing_time_ms', 0.0),
            original_length=data.get('original_length', 0),
            redacted_count=data.get('redacted_count', 0)
        )


@dataclass
class RedactionStats:
    """
    Stats for a redaction run.
    
    Used for audit reports and processing metrics.
    
    Attributes:
        input_file: Path to input file
        output_file: Path to output file
        total_rows: Total number of rows processed
        columns_processed: List of column names processed
        processing_time_seconds: Total processing time
        redaction_counts: Dictionary of redaction counts by type
        error_count: Number of errors encountered
        timestamp: ISO timestamp of processing
    """
    input_file: str
    output_file: str
    total_rows: int
    columns_processed: List[str]
    processing_time_seconds: float
    redaction_counts: Dict[str, int]  # {"EMAIL": 123, "PHONE": 456, ...}
    error_count: int
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'input_file': self.input_file,
            'output_file': self.output_file,
            'total_rows': self.total_rows,
            'columns_processed': self.columns_processed,
            'processing_time_seconds': self.processing_time_seconds,
            'redaction_counts': self.redaction_counts,
            'error_count': self.error_count,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RedactionStats":
        """Create RedactionStats from dictionary."""
        return cls(
            input_file=data.get('input_file', ''),
            output_file=data.get('output_file', ''),
            total_rows=data.get('total_rows', 0),
            columns_processed=data.get('columns_processed', []),
            processing_time_seconds=data.get('processing_time_seconds', 0.0),
            redaction_counts=data.get('redaction_counts', {}),
            error_count=data.get('error_count', 0),
            timestamp=data.get('timestamp', '')
        )

    @property
    def total_redactions(self) -> int:
        """Get total number of redactions across all types."""
        return sum(self.redaction_counts.values())

    @property
    def rows_per_second(self) -> float:
        """Calculate processing speed."""
        if self.processing_time_seconds > 0:
            return self.total_rows / self.processing_time_seconds
        return 0.0

    @property
    def most_common_type(self) -> str:
        """Get the most common redaction type."""
        if self.redaction_counts:
            return max(self.redaction_counts.items(), key=lambda x: x[1])[0]
        return ""


# ============================================================================
# Utility Functions
# ============================================================================

def count_redactions(text: str) -> Dict[str, int]:
    """Count redaction tokens in a text."""
    import re
    counts: Dict[str, int] = {}
    pattern = re.compile(r'\[([A-Z_]+)\]')
    for match in pattern.finditer(str(text)):
        token = match.group(1)
        counts[token] = counts.get(token, 0) + 1
    return counts


def generate_audit_report(
    input_file: str,
    output_file: str,
    stats: RedactionStats,
    report_path: str,
    format: str = "json"
) -> str:
    """Generate an audit report for a redaction run.
    
    Args:
        input_file: Path to input file
        output_file: Path to output file
        stats: RedactionStats object
        report_path: Where to save the report
        format: "json" or "html"
        
    Returns:
        Path to generated report
    """
    import json
    from pathlib import Path
    from datetime import datetime
    
    report_data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "pi_remover_version": "2.12.0",
            "input_file": str(input_file),
            "output_file": str(output_file),
        },
        "processing": {
            "total_rows": stats.total_rows,
            "columns_processed": stats.columns_processed,
            "processing_time_seconds": round(stats.processing_time_seconds, 2),
            "rows_per_second": round(stats.total_rows / max(stats.processing_time_seconds, 0.001), 0),
            "error_count": stats.error_count,
        },
        "redactions": stats.redaction_counts,
        "summary": {
            "total_redactions": sum(stats.redaction_counts.values()),
            "redaction_types": len(stats.redaction_counts),
            "most_common": max(stats.redaction_counts.items(), key=lambda x: x[1])[0] if stats.redaction_counts else None,
        }
    }
    
    if format == "json":
        report_file = Path(report_path).with_suffix('.json')
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
        return str(report_file)
    
    elif format == "html":
        report_file = Path(report_path).with_suffix('.html')
        html = _generate_html_report(report_data)
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html)
        return str(report_file)
    
    return ""


def _generate_html_report(data: Dict[str, Any]) -> str:
    """Generate HTML audit report."""
    redactions_rows = "\n".join([
        f"<tr><td>{k}</td><td>{v:,}</td></tr>"
        for k, v in sorted(data['redactions'].items(), key=lambda x: -x[1])
    ])
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>PI Remover Audit Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; max-width: 600px; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #e7f3fe; padding: 20px; margin: 20px 0; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>PI Remover Audit Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Generated:</strong> {data['metadata']['generated_at']}</p>
        <p><strong>Input File:</strong> {data['metadata']['input_file']}</p>
        <p><strong>Output File:</strong> {data['metadata']['output_file']}</p>
        <p><strong>Total Rows:</strong> {data['processing']['total_rows']:,}</p>
        <p><strong>Processing Time:</strong> {data['processing']['processing_time_seconds']:.2f}s</p>
        <p><strong>Total Redactions:</strong> {data['summary']['total_redactions']:,}</p>
    </div>
    <h2>Redactions by Type</h2>
    <table>
        <tr><th>Type</th><th>Count</th></tr>
        {redactions_rows}
    </table>
</body>
</html>"""
    return html


# ============================================================================
# Export
# ============================================================================

__all__ = [
    'Redaction',
    'RedactionResult',
    'RedactionStats',
    'count_redactions',
    'generate_audit_report',
]
