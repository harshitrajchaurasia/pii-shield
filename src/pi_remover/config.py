"""
PI Remover Configuration Module.

Contains configuration dataclass and YAML loading functionality.
Extracted from core.py for better modularity.

Usage:
    from pi_remover.config import PIRemoverConfig, load_config_from_yaml
    
    # Use defaults
    config = PIRemoverConfig()
    
    # Fast mode (no NER)
    config = PIRemoverConfig(enable_ner=False)
    
    # Load from YAML
    config = load_config_from_yaml("config.yaml")
"""

import multiprocessing as mp
from dataclasses import dataclass, field
from typing import Set

# Default CPU count fallback when detection fails
DEFAULT_CPU_COUNT = 4


@dataclass
class PIRemoverConfig:
    """Config options for the remover."""
    # Enable/disable detection layers
    enable_ner: bool = True  # spaCy NER for names
    enable_regex: bool = True  # Pattern-based detection
    enable_dictionaries: bool = True  # Custom word lists
    enable_context_rules: bool = True  # Signature blocks, etc.
    enable_data_cleaning: bool = True  # Pre-process text before redaction
    
    # spaCy model selection (v2.7.1)
    # Allowed: en_core_web_sm, en_core_web_md, en_core_web_lg, en_core_web_trf
    spacy_model: str = "en_core_web_lg"

    # What to redact
    redact_names: bool = True
    redact_emails: bool = True
    redact_phones: bool = True
    redact_emp_ids: bool = True
    redact_asset_ids: bool = True
    redact_ip_addresses: bool = True
    redact_urls: bool = True
    redact_hostnames: bool = True
    redact_companies: bool = True
    redact_locations: bool = True
    redact_credentials: bool = True
    
    # IT/ITSM specific redaction options (v2.6)
    redact_ticket_ids: bool = True           # ServiceNow, JIRA tickets
    redact_active_directory: bool = True     # LDAP DN, SAMAccountName, SID
    redact_remote_access_ids: bool = True    # TeamViewer, AnyDesk IDs
    redact_database_strings: bool = True     # Connection strings with creds
    redact_session_tokens: bool = True       # Session IDs, JWT, OAuth tokens
    redact_encryption_keys: bool = True      # BitLocker, recovery keys
    redact_workplace_info: bool = True       # Desk location, badge numbers
    redact_cloud_ids: bool = True            # Azure/AWS/GCP identifiers
    redact_license_keys: bool = True         # Software license keys
    redact_chat_handles: bool = True         # @mentions, Slack/Teams handles
    redact_audit_info: bool = True           # Login events, user actions

    # Replacement token (use consistent marker for each type)
    replacement_token: str = "[REDACTED]"
    use_typed_tokens: bool = True  # [NAME], [EMAIL], etc.
    use_granular_tokens: bool = True  # v2.17.0: [EMP_ID_AD], [PHONE_IN], [TICKET_INC], etc.

    # Performance
    batch_size: int = 1000
    show_progress: bool = True

    # Multiprocessing
    # Safe default: wraps cpu_count with fallback to DEFAULT_CPU_COUNT (4)
    num_workers: int = field(default_factory=lambda: max(1, (mp.cpu_count() or DEFAULT_CPU_COUNT) - 1) if hasattr(mp, 'cpu_count') else DEFAULT_CPU_COUNT - 1)
    use_multiprocessing: bool = True
    
    # Auto-scaling (Level 1 & 2)
    auto_scale_workers: bool = True  # Automatically adjust workers based on file size
    adaptive_scaling: bool = False   # Runtime resource-aware scaling (Level 2)
    multiprocessing_threshold: int = 5000  # Min rows to trigger multiprocessing
    
    # Error handling
    continue_on_error: bool = True
    error_log_file: str = "pi_remover_errors.log"
    include_original_in_log: bool = False
    max_errors: int = 0

    # Data cleaning options
    clean_nfkc_normalize: bool = True  # v2.18.0: NFKC Unicode normalization (ﬁ→fi, ²→2, fullwidth→ASCII)
    clean_normalize_unicode: bool = True
    clean_decode_html: bool = True
    clean_normalize_whitespace: bool = True
    clean_strip_control_chars: bool = True
    clean_strip_zero_width: bool = True  # v2.18.0: Remove all zero-width/invisible Unicode chars

    # Exclusions / Whitelist (items that should NOT be redacted)
    excluded_emails: Set[str] = field(default_factory=set)  # e.g., {"support@example.com"}
    excluded_phones: Set[str] = field(default_factory=set)  # e.g., {"1800"} for prefixes
    excluded_terms: Set[str] = field(default_factory=set)   # e.g., {"ServiceNow", "JIRA"}
    excluded_domains: Set[str] = field(default_factory=set) # e.g., {"example.com"}


def load_config_from_yaml(yaml_path: str) -> PIRemoverConfig:
    """Load config from YAML file. Falls back to defaults if anything's missing."""
    try:
        import yaml
    except ImportError:
        print("WARNING: PyYAML not installed. Using default config.")
        print("Install with: pip install pyyaml")
        return PIRemoverConfig()
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Config file not found: {yaml_path}. Using defaults.")
        return PIRemoverConfig()
    except Exception as e:
        print(f"Error reading config: {e}. Using defaults.")
        return PIRemoverConfig()
    
    # Map YAML structure to PIRemoverConfig
    engines = cfg.get('engines', {})
    pi_types = cfg.get('pi_types', {})
    tokens = cfg.get('tokens', {})
    general = cfg.get('general', {})
    error_handling = cfg.get('error_handling', {})
    exclusions = cfg.get('exclusions', {})
    data_cleaning = cfg.get('data_cleaning', {})
    
    num_workers = general.get('num_workers', 0)
    if num_workers == 0:
        num_workers = max(1, (mp.cpu_count() or DEFAULT_CPU_COUNT) - 1)
    
    return PIRemoverConfig(
        enable_ner=engines.get('ner', True),
        enable_regex=engines.get('regex', True),
        enable_dictionaries=engines.get('dictionaries', True),
        enable_context_rules=engines.get('context_rules', True),
        enable_data_cleaning=data_cleaning.get('enabled', True),
        redact_names=pi_types.get('names', True),
        redact_emails=pi_types.get('emails', True),
        redact_phones=pi_types.get('phones', True),
        redact_emp_ids=pi_types.get('employee_ids', True),
        redact_asset_ids=pi_types.get('asset_ids', True),
        redact_ip_addresses=pi_types.get('ip_addresses', True),
        redact_urls=pi_types.get('urls', True),
        redact_hostnames=pi_types.get('hostnames', True),
        redact_companies=pi_types.get('companies', True),
        redact_locations=pi_types.get('locations', True),
        redact_credentials=pi_types.get('credentials', True),
        replacement_token=tokens.get('default', '[REDACTED]'),
        use_typed_tokens=tokens.get('use_typed', True),
        use_granular_tokens=tokens.get('use_granular', True),  # v2.17.0
        batch_size=general.get('batch_size', 5000),
        show_progress=general.get('show_progress', True),
        num_workers=num_workers,
        use_multiprocessing=cfg.get('performance', {}).get('multiprocessing', True),
        continue_on_error=error_handling.get('continue_on_error', True),
        error_log_file=error_handling.get('error_log_file', 'pi_remover_errors.log'),
        include_original_in_log=error_handling.get('include_original_in_log', False),
        max_errors=error_handling.get('max_errors', 0),
        clean_nfkc_normalize=data_cleaning.get('nfkc_normalize', True),
        clean_normalize_unicode=data_cleaning.get('normalize_unicode', True),
        clean_decode_html=data_cleaning.get('decode_html', True),
        clean_normalize_whitespace=data_cleaning.get('normalize_whitespace', True),
        clean_strip_control_chars=data_cleaning.get('strip_control_chars', True),
        clean_strip_zero_width=data_cleaning.get('strip_zero_width', True),
        excluded_emails=set(exclusions.get('emails', [])),
        excluded_phones=set(exclusions.get('phones', [])),
        excluded_terms=set(exclusions.get('terms', [])),
        excluded_domains=set(exclusions.get('domains', [])),
    )


def config_to_dict(config: PIRemoverConfig) -> dict:
    """Convert config to dictionary for serialization or multiprocessing."""
    return {
        'enable_ner': config.enable_ner,
        'enable_regex': config.enable_regex,
        'enable_dictionaries': config.enable_dictionaries,
        'enable_context_rules': config.enable_context_rules,
        'enable_data_cleaning': config.enable_data_cleaning,
        'spacy_model': config.spacy_model,
        'redact_names': config.redact_names,
        'redact_emails': config.redact_emails,
        'redact_phones': config.redact_phones,
        'redact_emp_ids': config.redact_emp_ids,
        'redact_asset_ids': config.redact_asset_ids,
        'redact_ip_addresses': config.redact_ip_addresses,
        'redact_urls': config.redact_urls,
        'redact_hostnames': config.redact_hostnames,
        'redact_companies': config.redact_companies,
        'redact_locations': config.redact_locations,
        'redact_credentials': config.redact_credentials,
        'redact_ticket_ids': config.redact_ticket_ids,
        'redact_active_directory': config.redact_active_directory,
        'redact_remote_access_ids': config.redact_remote_access_ids,
        'redact_database_strings': config.redact_database_strings,
        'redact_session_tokens': config.redact_session_tokens,
        'redact_encryption_keys': config.redact_encryption_keys,
        'redact_workplace_info': config.redact_workplace_info,
        'redact_cloud_ids': config.redact_cloud_ids,
        'redact_license_keys': config.redact_license_keys,
        'redact_chat_handles': config.redact_chat_handles,
        'redact_audit_info': config.redact_audit_info,
        'replacement_token': config.replacement_token,
        'use_typed_tokens': config.use_typed_tokens,
        'use_granular_tokens': config.use_granular_tokens,  # v2.17.0
        'batch_size': config.batch_size,
        'show_progress': config.show_progress,
        'num_workers': config.num_workers,
        'use_multiprocessing': config.use_multiprocessing,
        'auto_scale_workers': config.auto_scale_workers,
        'adaptive_scaling': config.adaptive_scaling,
        'multiprocessing_threshold': config.multiprocessing_threshold,
        'continue_on_error': config.continue_on_error,
        'error_log_file': config.error_log_file,
        'include_original_in_log': config.include_original_in_log,
        'max_errors': config.max_errors,
        'clean_nfkc_normalize': config.clean_nfkc_normalize,
        'clean_normalize_unicode': config.clean_normalize_unicode,
        'clean_decode_html': config.clean_decode_html,
        'clean_normalize_whitespace': config.clean_normalize_whitespace,
        'clean_strip_control_chars': config.clean_strip_control_chars,
        'clean_strip_zero_width': config.clean_strip_zero_width,
        'excluded_emails': list(config.excluded_emails),
        'excluded_phones': list(config.excluded_phones),
        'excluded_terms': list(config.excluded_terms),
        'excluded_domains': list(config.excluded_domains),
    }


def config_from_dict(data: dict) -> PIRemoverConfig:
    """Create config from dictionary."""
    return PIRemoverConfig(
        enable_ner=data.get('enable_ner', True),
        enable_regex=data.get('enable_regex', True),
        enable_dictionaries=data.get('enable_dictionaries', True),
        enable_context_rules=data.get('enable_context_rules', True),
        enable_data_cleaning=data.get('enable_data_cleaning', True),
        spacy_model=data.get('spacy_model', 'en_core_web_lg'),
        redact_names=data.get('redact_names', True),
        redact_emails=data.get('redact_emails', True),
        redact_phones=data.get('redact_phones', True),
        redact_emp_ids=data.get('redact_emp_ids', True),
        redact_asset_ids=data.get('redact_asset_ids', True),
        redact_ip_addresses=data.get('redact_ip_addresses', True),
        redact_urls=data.get('redact_urls', True),
        redact_hostnames=data.get('redact_hostnames', True),
        redact_companies=data.get('redact_companies', True),
        redact_locations=data.get('redact_locations', True),
        redact_credentials=data.get('redact_credentials', True),
        redact_ticket_ids=data.get('redact_ticket_ids', True),
        redact_active_directory=data.get('redact_active_directory', True),
        redact_remote_access_ids=data.get('redact_remote_access_ids', True),
        redact_database_strings=data.get('redact_database_strings', True),
        redact_session_tokens=data.get('redact_session_tokens', True),
        redact_encryption_keys=data.get('redact_encryption_keys', True),
        redact_workplace_info=data.get('redact_workplace_info', True),
        redact_cloud_ids=data.get('redact_cloud_ids', True),
        redact_license_keys=data.get('redact_license_keys', True),
        redact_chat_handles=data.get('redact_chat_handles', True),
        redact_audit_info=data.get('redact_audit_info', True),
        replacement_token=data.get('replacement_token', '[REDACTED]'),
        use_typed_tokens=data.get('use_typed_tokens', True),
        use_granular_tokens=data.get('use_granular_tokens', True),  # v2.17.0
        batch_size=data.get('batch_size', 1000),
        show_progress=data.get('show_progress', True),
        num_workers=data.get('num_workers', DEFAULT_CPU_COUNT - 1),
        use_multiprocessing=data.get('use_multiprocessing', True),
        auto_scale_workers=data.get('auto_scale_workers', True),
        adaptive_scaling=data.get('adaptive_scaling', False),
        multiprocessing_threshold=data.get('multiprocessing_threshold', 5000),
        continue_on_error=data.get('continue_on_error', True),
        error_log_file=data.get('error_log_file', 'pi_remover_errors.log'),
        include_original_in_log=data.get('include_original_in_log', False),
        max_errors=data.get('max_errors', 0),
        clean_nfkc_normalize=data.get('clean_nfkc_normalize', True),
        clean_normalize_unicode=data.get('clean_normalize_unicode', True),
        clean_decode_html=data.get('clean_decode_html', True),
        clean_normalize_whitespace=data.get('clean_normalize_whitespace', True),
        clean_strip_control_chars=data.get('clean_strip_control_chars', True),
        clean_strip_zero_width=data.get('clean_strip_zero_width', True),
        excluded_emails=set(data.get('excluded_emails', [])),
        excluded_phones=set(data.get('excluded_phones', [])),
        excluded_terms=set(data.get('excluded_terms', [])),
        excluded_domains=set(data.get('excluded_domains', [])),
    )


# ============================================================================
# Export
# ============================================================================

__all__ = [
    'PIRemoverConfig',
    'load_config_from_yaml',
    'config_to_dict',
    'config_from_dict',
    'DEFAULT_CPU_COUNT',
]
