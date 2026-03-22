"""
PI Remover - Main PIRemover class.

This module contains the core PIRemover class with all redaction methods.
Extracted from core.py as part of v2.12.0 modular architecture refactoring.
"""

import re
import json
import time
import logging
import threading
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any

import pandas as pd

from .config import PIRemoverConfig, MAX_DICTIONARY_SIZE
from .patterns import PIPatterns
from .dictionaries import (
    INDIAN_FIRST_NAMES, INDIAN_LAST_NAMES,
    INTERNATIONAL_FIRST_NAMES,
    COMPANY_NAMES, INTERNAL_SYSTEMS
)
from .data_classes import Redaction, RedactionResult
from .utils import DataCleaner

# Try to import spacy availability flag
try:
    from .ner import SpacyNER, SPACY_AVAILABLE
except ImportError:
    SPACY_AVAILABLE = False
    SpacyNER = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Version
__version__ = "2.19.0"


class PIRemover:
    """Main class - combines NER, regex, and dictionaries."""

    def __init__(self, config: Optional[PIRemoverConfig] = None):
        self.config = config or PIRemoverConfig()
        self.patterns = PIPatterns()
        # Thread safety lock for mutable name dictionaries
        self._name_lock = threading.Lock()
        # Use spacy_model from config (v2.7.1) — lazy loaded on first use (C12 fix)
        if SpacyNER is not None:
            self._ner_class = SpacyNER
        else:
            self._ner_class = None
        self.ner = None  # Lazy-loaded via _get_ner()

        # Precompile name sets for faster lookup (with safe fallback)
        try:
            self._first_names = {n.lower() for n in INDIAN_FIRST_NAMES} | {n.lower() for n in INTERNATIONAL_FIRST_NAMES}
            self._last_names = {n.lower() for n in INDIAN_LAST_NAMES}
            self._all_names = self._first_names | self._last_names
            self._companies = {c.lower() for c in COMPANY_NAMES}
            self._systems = {s.lower() for s in INTERNAL_SYSTEMS}
        except Exception as e:
            logger.warning(f"Failed to load name dictionaries: {e}")
            self._first_names = set()
            self._last_names = set()
            self._all_names = set()
            self._companies = set()
            self._systems = set()
        
        # Load external name dictionaries if available
        self._load_external_names()

        # Precompile regex patterns used in hot paths (C4 fix)
        self._adjacent_name_re = re.compile(r'\[NAME\]\s+([A-Z][a-z]{1,20})\b')
        self._email_fragment_re = re.compile(
            r'\[(?:NAME|EMP_ID)\][._]?([a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        )
        self._prefixed_id_re = re.compile(
            r'(?i)\b(ad|iada|cad|ws|pr|sa|oth|vo|da|di)\.([a-z0-9]{4,}|\d{4,})\b'
        )
        self._email_local_split_re = re.compile(r'[._\-]')

        # Negative context patterns for employee ID detection (avoid recompilation)
        self._emp_negative_patterns = [
            re.compile(r'(?:Rs\.?|INR|USD|\$|#)\s*$', re.IGNORECASE),
            re.compile(r'(?:order|ref|case|ticket|sr|cr|rfc|inc)\s*#?\s*$', re.IGNORECASE),
            re.compile(r'\d{1,2}[/.-]\d{1,2}[/.-]$'),
            re.compile(r'v(?:ersion)?\.?\s*\d*\.?$', re.IGNORECASE),
            re.compile(r'(?:port|error|code)\s*:?\s*$', re.IGNORECASE),
            re.compile(r'(?:room|floor|building|seat|desk)\s*(?:no\.?|#)?\s*$', re.IGNORECASE),
        ]
        # Name dictionary pattern (precompiled)
        self._name_pattern_re = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b')
        self._caps_name_re = re.compile(r'\b([A-Z]{2,}(?:\s+[A-Z]{2,}){1,2})\b')
        self._single_name_re = re.compile(
            r'(?<!\w)([A-Z][a-z]{2,20})(?!\w)'
        )
        # Strong prefix pattern for single-name detection
        _strong_prefixes = {
            'dear', 'hello', 'hi', 'hey', 'mr', 'mrs', 'ms', 'dr', 'prof',
            'contact', 'call', 'email', 'notify', 'attn', 'cc',
        }
        self._single_name_prefix_re = re.compile(
            r'\b(' + '|'.join(re.escape(p) for p in _strong_prefixes) + r')[\s,.]+([A-Z][a-z]+)\b',
            re.IGNORECASE
        )
        self._cn_pattern_re = re.compile(r'CN=([^,]+)', re.IGNORECASE)

        # Initialize NER if enabled (lazy: only loads model on first use)
        if self.config.enable_ner and self._ner_class is not None:
            self.ner = self._ner_class(model_name=self.config.spacy_model)
            self.ner.load()

    # Verhoeff checksum tables for Aadhaar validation
    _verhoeff_d = [
        [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],
        [2,3,4,0,1,7,8,9,5,6],[3,4,0,1,2,8,9,5,6,7],
        [4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
        [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],
        [8,7,6,5,9,3,2,1,0,4],[9,8,7,6,5,4,3,2,1,0],
    ]
    _verhoeff_p = [
        [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],
        [5,8,0,3,7,9,6,1,4,2],[8,9,1,6,0,4,3,5,2,7],
        [9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
        [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
    ]
    _verhoeff_inv = [0,4,3,2,1,5,6,7,8,9]

    @classmethod
    def _verify_aadhaar(cls, digits: str) -> bool:
        """Validate Aadhaar number using Verhoeff checksum algorithm."""
        try:
            c = 0
            for i, digit in enumerate(reversed(digits)):
                c = cls._verhoeff_d[c][cls._verhoeff_p[i % 8][int(digit)]]
            return c == 0
        except (ValueError, IndexError):
            return False

    def _load_external_names(self, names_file: Optional[str] = None) -> int:
        """Load additional names from external dictionary file (v2.5)."""
        default_locations = [
            Path("names.txt"),
            Path("data/names.txt"),
            Path(__file__).parent / "data" / "names.txt",
            Path(__file__).parent.parent.parent / "data" / "names.txt",
        ]
        
        names_path = None
        if names_file:
            names_path = Path(names_file)
        else:
            for loc in default_locations:
                if loc.exists():
                    names_path = loc
                    break
        
        if not names_path or not names_path.exists():
            return 0
        
        loaded_count = 0
        suffix = names_path.suffix.lower()
        
        try:
            if suffix == '.json':
                loaded_count = self._load_names_json(names_path)
            elif suffix == '.csv':
                loaded_count = self._load_names_csv(names_path)
            else:
                loaded_count = self._load_names_txt(names_path)
            
            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count} additional names from {names_path}")
        except Exception as e:
            logger.warning(f"Failed to load external names from {names_path}: {e}")
        
        return loaded_count

    def _load_names_txt(self, path: Path) -> int:
        """Load names from plain text file (one per line)."""
        count = 0
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                if len(self._all_names) >= MAX_DICTIONARY_SIZE:
                    logger.warning(f"Dictionary limit reached ({MAX_DICTIONARY_SIZE}). Truncating load from {path}.")
                    break
                name = line.strip().lower()
                if name and not name.startswith('#'):
                    self._all_names.add(name)
                    count += 1
        return count

    def _load_names_csv(self, path: Path) -> int:
        """Load names from CSV file."""
        count = 0
        try:
            df = pd.read_csv(path)
            for col in df.columns:
                col_lower = col.lower()
                if 'first' in col_lower or col_lower == 'name':
                    for name in df[col].dropna():
                        self._first_names.add(str(name).lower())
                        self._all_names.add(str(name).lower())
                        count += 1
                elif 'last' in col_lower or 'surname' in col_lower:
                    for name in df[col].dropna():
                        self._last_names.add(str(name).lower())
                        self._all_names.add(str(name).lower())
                        count += 1
        except Exception as e:
            logger.warning(f"Error loading CSV names: {e}")
        return count

    def _load_names_json(self, path: Path) -> int:
        """Load names from JSON file."""
        count = 0
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if 'first_names' in data:
            for name in data['first_names']:
                self._first_names.add(name.lower())
                self._all_names.add(name.lower())
                count += 1
        if 'last_names' in data:
            for name in data['last_names']:
                self._last_names.add(name.lower())
                self._all_names.add(name.lower())
                count += 1
        if 'names' in data:
            for name in data['names']:
                self._all_names.add(name.lower())
                count += 1
        return count

    def add_names(self, names: List[str], name_type: str = "all") -> None:
        """Dynamically add names to the dictionary at runtime (thread-safe)."""
        with self._name_lock:
            for name in names:
                if len(self._all_names) >= MAX_DICTIONARY_SIZE:
                    logger.warning(f"Name dictionary at max capacity ({MAX_DICTIONARY_SIZE}). Skipping remaining.")
                    break
                name_lower = name.lower()
                if name_type in ("first", "all"):
                    self._first_names.add(name_lower)
                if name_type in ("last", "all"):
                    self._last_names.add(name_lower)
                self._all_names.add(name_lower)

    def _get_token(self, pi_type: str, subtype: Optional[str] = None) -> str:
        """
        Get replacement token for a PI type with optional subtype.

        v2.17.0: Added granular token support.
        - With use_granular_tokens=True: [EMP_ID_AD], [PHONE_IN], [TICKET_INC]
        - With use_granular_tokens=False: [EMP_ID], [PHONE], [TICKET]

        Args:
            pi_type: Main PI type (EMAIL, PHONE, EMP_ID, etc.)
            subtype: Optional subtype for granular tokens (AD, PR, IN, UK, etc.)

        Returns:
            Formatted token string
        """
        if self.config.use_typed_tokens:
            if subtype and self.config.use_granular_tokens:
                return f"[{pi_type}_{subtype}]"
            return f"[{pi_type}]"
        return self.config.replacement_token

    def _is_likely_name(self, word: str) -> bool:
        """Check if a word is likely a name using dictionary."""
        return word.lower() in self._all_names

    def _redact_by_positions(self, text: str, positions: List[Tuple[int, int, str]]) -> str:
        """Redact text at given positions using O(N) join pattern."""
        if not positions:
            return text
        # Sort by start position ascending for forward iteration
        sorted_pos = sorted(positions, key=lambda x: x[0])
        text_len = len(text)
        parts = []
        last_end = 0
        for start, end, replacement in sorted_pos:
            if start < 0 or end > text_len or start >= end or start < last_end:
                continue
            parts.append(text[last_end:start])
            parts.append(replacement)
            last_end = end
        parts.append(text[last_end:])
        return ''.join(parts)

    def _cleanup_partial_redactions(self, text: str) -> str:
        """
        v2.14.0: Post-processing cleanup for partial redactions and residual PI.
        
        Handles cases where first-pass redaction leaves residual identifiable information:
        - [EMP_ID] #2919414 -> [EMP_ID] [EMP_ID]
        - [EMP_ID]<tab>Name Lastname -> [EMP_ID]<tab>[NAME]
        - [NAME] #1234567 -> [NAME] [EMP_ID]
        
        This is a second-pass cleanup that runs after initial redaction.
        """
        cleanup_positions = []
        
        # Pattern 1: Token followed by actual employee ID
        # Matches: "[EMP_ID] #2919414", "[NAME], 1234567", "[EMAIL]	2345678"
        for match in self.patterns.EMP_ID_AFTER_TOKEN.finditer(text):
            if match.group(1):
                cleanup_positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))
        
        # Pattern 2: Token followed by name in tabular data
        # Matches: "[EMP_ID]	Souvanik Batabyal", "[NAME],John Smith"
        for match in self.patterns.NAME_AFTER_TOKEN.finditer(text):
            if match.group(1):
                cleanup_positions.append((match.start(1), match.end(1), self._get_token("NAME")))

        # Pattern 3: [NAME] followed by adjacent known name (partial redaction cleanup)
        # Matches: "[NAME] Kumar", "[NAME] Singh" where last name was missed
        for match in self._adjacent_name_re.finditer(text):
            word = match.group(1).lower()
            if word in self._all_names:
                cleanup_positions.append((match.start(1), match.end(1), self._get_token("NAME")))

        # Pattern 4: Email fragment left after name redaction
        # Matches: "[NAME].smith@corp.com", "[EMP_ID]_user@company.org"
        for match in self._email_fragment_re.finditer(text):
            cleanup_positions.append((match.start(1), match.end(1), self._get_token("EMAIL")))

        # Remove overlaps and apply
        if cleanup_positions:
            cleanup_positions = self._remove_overlaps(cleanup_positions)
            text = self._redact_by_positions(text, cleanup_positions)
        
        return text

    def _find_pattern_matches(self, text: str, pattern: re.Pattern,
                              pi_type: str) -> List[Tuple[int, int, str]]:
        """Find all matches for a pattern and return positions."""
        positions = []
        try:
            for match in pattern.finditer(text):
                positions.append((match.start(), match.end(), self._get_token(pi_type)))
        except Exception as e:
            logger.warning(f"Pattern matching failed for {pi_type}: {type(e).__name__}: {e}")
        return positions

    def _detect_signature_block(self, text: str) -> Optional[int]:
        """Detect where signature block starts."""
        match = self.patterns.SIGNATURE_START.search(text)
        if match:
            return match.start()
        return None

    def _remove_overlaps(self, positions: List[Tuple[int, int, str]]) -> List[Tuple[int, int, str]]:
        """Remove overlapping positions, keeping the longest match."""
        if not positions:
            return []
        sorted_pos = sorted(positions, key=lambda x: (x[0], -(x[1] - x[0])))
        result = []
        last_end = -1
        for start, end, replacement in sorted_pos:
            if start >= last_end:
                result.append((start, end, replacement))
                last_end = end
        return result

    # =========================================================================
    # CORE REDACTION METHODS - Part 1: Email, Phone, Employee ID
    # =========================================================================

    def _redact_emails(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark emails for redaction, respecting exclusions."""
        positions = []
        
        # v2.13.1: TCS/corporate domains where numeric local part = employee ID
        emp_id_domains = {
            'tcs.com', 'tcsapps.com', 'tcsappsdev.com', 'tcscomprod.com',
            'tata.com', 'tataconsultancy.com',
        }
        
        # v2.13.1: Prefixes that indicate employee ID accounts
        emp_id_prefixes = {'ad', 'iada', 'cad', 'ws', 'pr', 'sa', 'oth', 'vo', 'da', 'di'}
        
        for match in self.patterns.EMAIL.finditer(text):
            email = match.group(0).lower()
            if email in self.config.excluded_emails:
                continue
            domain = email.split('@')[-1] if '@' in email else ''
            if domain in self.config.excluded_domains:
                continue
            
            local_part = email.split('@')[0] if '@' in email else ''
            
            # v2.13.1: Check if this is an employee ID-based email
            # Case 1: Numeric local part on TCS domain (1234567@tcs.com)
            if local_part.isdigit() and len(local_part) >= 4 and len(local_part) <= 7:
                if domain in emp_id_domains:
                    positions.append((match.start(), match.end(), "[EMP_ID]@[DOMAIN]"))
                    continue

            # Case 2: Prefixed account (ad.1234567@domain.com)
            if '.' in local_part:
                prefix, rest = local_part.split('.', 1)
                if prefix in emp_id_prefixes and rest.isdigit() and len(rest) >= 4 and len(rest) <= 7:
                    positions.append((match.start(), match.end(), f"{prefix.upper()}.[EMP_ID]@[DOMAIN]"))
                    continue
            
            # Regular email
            positions.append((match.start(), match.end(), self._get_token("EMAIL")))
        
        # v2.14.0: Detect partial/orphaned email patterns like ".lastname@tcs.com"
        for match in self.patterns.EMAIL_PARTIAL_LASTNAME.finditer(text):
            # Avoid double-detection by checking if already covered
            if not any(s <= match.start() < e for s, e, _ in positions):
                positions.append((match.start(), match.end(), self._get_token("EMAIL")))
        
        return positions

    def _redact_phones(self, text: str) -> List[Tuple[int, int, str]]:
        """
        v2.17.0: Detect and mark phone numbers with country-specific granular tokens.

        Returns tokens like [PHONE_IN], [PHONE_UK], [PHONE_US], etc.
        """
        positions: List[Tuple[int, int, str]] = []
        detected_ranges: set[Tuple[int, int]] = set()

        # Country-specific patterns with granular tokens
        # Format: (pattern, country_code)
        country_phone_patterns = [
            # India (+91)
            (self.patterns.PHONE_91_DIRECT, "IN"),
            (self.patterns.PHONE_INDIAN, "IN"),
            (self.patterns.PHONE_INDIAN_FORMATTED, "IN"),
            (self.patterns.PHONE_INDIAN_SPACED, "IN"),
            (self.patterns.PHONE_LANDLINE, "IN"),
            # UK (+44)
            (self.patterns.PHONE_UK, "UK"),
            (self.patterns.PHONE_UK_DIRECT, "UK"),
            (self.patterns.PHONE_UK_FULL, "UK"),
            # US/Canada (+1)
            (self.patterns.PHONE_US, "US"),
            # Toll-free
            (self.patterns.PHONE_TOLLFREE, "TOLLFREE"),
            (self.patterns.PHONE_TOLLFREE_800, "TOLLFREE"),
            # Australia (+61)
            (self.patterns.PHONE_AU, "AU"),
            # Germany (+49)
            (self.patterns.PHONE_DE, "DE"),
            # France (+33)
            (self.patterns.PHONE_FR, "FR"),
            # Singapore (+65)
            (self.patterns.PHONE_SG, "SG"),
            # UAE (+971)
            (self.patterns.PHONE_UAE, "AE"),
            # Brazil (+55)
            (self.patterns.PHONE_BR, "BR"),
            (self.patterns.PHONE_BR_MOBILE, "BR"),
            # Japan (+81)
            (self.patterns.PHONE_JP, "JP"),
            # China (+86)
            (self.patterns.PHONE_CN, "CN"),
            # Malaysia (+60)
            (self.patterns.PHONE_MY, "MY"),
            # Mexico (+52)
            (self.patterns.PHONE_MX, "MX"),
            (self.patterns.PHONE_MX_SPACED, "MX"),
            # International (generic fallback)
            (self.patterns.PHONE_INTL, None),
        ]

        for pattern, country_code in country_phone_patterns:
            for match in pattern.finditer(text):
                phone = match.group(0)
                start, end = match.start(), match.end()

                # Skip if already detected (overlapping patterns)
                if any(s <= start < e or s < end <= e for s, e in detected_ranges):
                    continue

                # Check exclusions
                if any(phone.startswith(exc) or phone.replace(' ', '').replace('-', '').startswith(exc)
                       for exc in self.config.excluded_phones):
                    continue

                # Use granular token with country code
                token = self._get_token("PHONE", country_code) if country_code else self._get_token("PHONE")
                positions.append((start, end, token))
                detected_ranges.add((start, end))

        return positions

    def _redact_emp_ids(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark employee IDs for redaction."""
        positions = []

        # Labeled employee IDs
        for match in self.patterns.EMP_ID_LABELED.finditer(text):
            if match.group(1):
                full_match = match.group(0)
                id_value = match.group(1)
                id_start = match.start() + full_match.index(id_value)
                id_end = id_start + len(id_value)
                positions.append((id_start, id_end, self._get_token("EMP_ID")))

        # Prefixed IDs with granular tokens (v2.17.0)
        # Pattern: ad.1234567, pr.1234567, iada.username, etc.
        for match in self._prefixed_id_re.finditer(text):
            prefix = match.group(1).upper()  # AD, PR, IADA, etc.
            positions.append((match.start(), match.end(), self._get_token("EMP_ID", prefix)))

        # IDs in parentheses after names
        for match in self.patterns.EMP_ID_IN_PARENS.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("EMP_ID")))

        # Additional specific patterns
        emp_patterns = [
            self.patterns.EMP_ID_ADD_REMOVE, self.patterns.EMP_ID_ASSIGN,
            self.patterns.EMP_ID_ASSIGNED_TO, self.patterns.EMP_ID_ASSOCIATE,
            self.patterns.EMP_ID_HYPHEN, self.patterns.EMP_ID_WORD_HYPHEN,
            self.patterns.EMP_ID_PORTUGUESE, self.patterns.EMP_ID_THIS_IS,
            self.patterns.EMP_ID_CJK,
        ]
        for pat in emp_patterns:
            positions.extend(self._find_pattern_matches(text, pat, "EMP_ID"))

        # CN=XXXXXXX in LDAP paths - v2.17.0: granular token [EMP_ID_LDAP]
        for match in self.patterns.EMP_ID_LDAP.finditer(text):
            positions.append((match.start(), match.end(), "CN=" + self._get_token("EMP_ID", "LDAP")))

        # v2.13.0: Enhanced explicit label patterns for 6-7 digit employee IDs
        # Catches: "Emp ID - 351690", "Emp ID 445658(Name)", "emp id: 2888351"
        for pattern in [self.patterns.EMP_ID_LABELED_EXPLICIT, self.patterns.EMP_ID_WITH_LABEL]:
            for match in pattern.finditer(text):
                if match.group(1):
                    positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))

        # v2.13.0: Employee ID after asset/password context (tab/space separated)
        for match in self.patterns.EMP_ID_AFTER_ASSET.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))

        # v2.13.0: Spanish context employee IDs
        for match in self.patterns.EMP_ID_SPANISH_CONTEXT.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))

        # v2.13.1: User/ID labeled patterns
        for match in self.patterns.EMP_ID_USER_LABELED.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))

        # =====================================================================
        # v2.13.1: UPN/Email-based employee ID detection
        # =====================================================================
        
        # Numeric emp ID as email: 1234567@tcs.com, 54321@tcsappsdev.com
        # This detects the full UPN as [EMAIL] but also extracts the emp ID portion
        for match in self.patterns.EMP_ID_UPN_NUMERIC.finditer(text):
            if match.group(1):
                # Mark the numeric portion as EMP_ID
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))
        
        # Prefixed emp ID in UPN: ad.1234567@tcs.com, pr.54321@domain.com
        for match in self.patterns.EMP_ID_UPN_PREFIXED.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))
        
        # General UPN with prefix: x.1234567@domain.com
        for match in self.patterns.EMP_ID_UPN_GENERAL.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))
        
        # Prefixed account format: ad.1234567, pr.54321 (extract just the ID)
        for match in self.patterns.EMP_ID_PREFIXED_EXTENDED.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))

        # =====================================================================
        # v2.14.0: Enhanced patterns for missed PI (from production data analysis)
        # =====================================================================
        
        # Teams #ID format: "teams#2531177", "ping teams #2482545"
        # v2.17.0: granular token [EMP_ID_TEAMS]
        for match in self.patterns.EMP_ID_TEAMS_HASH.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID", "TEAMS")))
        
        # Account operation format: "unlock account 1290362", "enable my account 54321"
        for match in self.patterns.EMP_ID_ACCOUNT_OP.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))
        
        # Emp # with space: "Emp # 2893847"
        for match in self.patterns.EMP_ID_EMP_HASH_SPACE.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))
        
        # Hyphen-Name format: "2482545-Reshma Chobe" (captures both ID and Name)
        for match in self.patterns.EMP_ID_HYPHEN_NAME.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EMP_ID")))
            if match.group(2):
                positions.append((match.start(2), match.end(2), self._get_token("NAME")))

        # =====================================================================
        # TIER 2: Context-aware detection for 4-7 digit numbers
        # =====================================================================
        
        # Keywords indicating employee/user context
        emp_keywords_strong = {
            'emp', 'employee', 'user', 'userid', 'username', 'associate', 
            'contact', 'reach', 'ping', 'teams', 'assigned', 'behalf',
            'owner', 'primary', 'secondary', 'requester', 'requestor',
            'caller', 'reporter', 'submitter', 'raised by', 'created by',
        }
        
        emp_keywords_medium = {
            'id', 'mail', 'email', 'call', 'add', 'remove', 'enable', 'disable',
            'access', 'account', 'domain', 'group', 'license', 'unlock', 'reset',
            'intune', 'fingerprint', 'laptop', 'desktop', 'machine', 'device',
            'asset', 'batch', 'login', 'folder', 'path', 'name', 'phone',
            'working', 'password', 'zscaler', 'installation', 'console',
            'please', 'kindly', 'request', 'following', 'below', 'above',
        }
        
        # Negative context - these indicate it's NOT an employee ID
        negative_keywords = {
            'order', 'room', 'floor', 'building', 'version', 'v.', 'ver',
            'port', 'error', 'code', 'year', 'date', 'pin', 'zip', 'postal',
            'amount', 'price', 'cost', 'rs', 'rs.', 'inr', 'usd', '$', 
            'quantity', 'qty', 'count', 'total', 'size', 'length', 'width',
            'height', 'weight', 'number of', 'no. of', 'no of',
            'reference', 'ref', 'case', 'incident', 'ticket', 'sr', 'cr',
            'rfc', 'change', 'problem', 'itil', 'snow',
        }
        
        # Patterns that indicate non-employee numbers
        negative_patterns = self._emp_negative_patterns
        
        def is_negative_context(text_before: str, text_after: str) -> bool:
            """Check if context indicates this is NOT an employee ID."""
            before_lower = text_before.lower()
            
            # Check negative keywords
            for kw in negative_keywords:
                if before_lower.endswith(kw) or before_lower.endswith(kw + ' '):
                    return True
                if before_lower.endswith(kw + ':') or before_lower.endswith(kw + '#'):
                    return True
            
            # Check negative patterns
            for pat in negative_patterns:
                if pat.search(text_before):
                    return True
            
            # Check if followed by decimal (likely price/version)
            if re.match(r'^\.\d', text_after):
                return True
            
            # Check if part of a date pattern
            if re.match(r'^[/.-]\d{1,4}', text_after):
                return True
                
            return False
        
        def get_context_score(match, text: str, num_digits: int) -> int:
            """Calculate context score for employee ID likelihood."""
            score = 0
            context_start = max(0, match.start() - 60)
            context_end = min(len(text), match.end() + 40)
            context_before = text[context_start:match.start()]
            context_after = text[match.end():context_end]
            context_before_lower = context_before.lower()
            context_after_lower = context_after.lower()
            full_context = context_before_lower + context_after_lower
            
            # Negative context check (disqualifies)
            if is_negative_context(context_before, context_after):
                return -100
            
            # Strong keywords (+3 each)
            for kw in emp_keywords_strong:
                if kw in full_context:
                    score += 3
            
            # Medium keywords (+1 each, max +5)
            medium_hits = sum(1 for kw in emp_keywords_medium if kw in full_context)
            score += min(medium_hits, 5)
            
            # Structural indicators
            if '\t' in text[max(0, match.start()-5):match.end()+5]:
                score += 2  # Tab-separated (table format)
            if '  ' in text[max(0, match.start()-5):match.start()]:
                score += 1  # Double-space separated
            if re.search(r'[A-Z][a-z]+\s*$', context_before):
                score += 2  # Name before
            if re.search(r'[A-Z]{2,}\s*$', context_before):
                score += 2  # CAPS name before
            if re.search(r'^\s*[A-Z][a-z]', context_after):
                score += 1  # Name after
            if re.search(r'\[(?:NAME|ASSET_ID|EMP_ID)\]\s*,?\s*$', context_before):
                score += 3  # Follows another redacted token
            if match.start() < 15 or re.search(r'[\n\r]\s*$', context_before):
                score += 1  # Start of line/text
            
            # Digit-length based threshold adjustment
            # Shorter numbers need stronger context
            if num_digits == 4:
                score -= 2  # Higher bar for 4-digit
            elif num_digits == 5:
                score -= 1  # Slightly higher bar for 5-digit
            elif num_digits == 7:
                score += 1  # Lower bar for 7-digit
            
            return score
        
        # Process 4-8 digit numbers with context awareness (v2.16.0: added 8-digit)
        already_detected = {(s, e) for s, e, _ in positions}
        
        for digit_len, pattern in [
            (8, self.patterns.EMP_ID_8DIGIT),  # v2.16.0: 8-digit employee IDs
            (7, self.patterns.EMP_ID_7DIGIT_ANY),
            (6, self.patterns.EMP_ID_6DIGIT_ANY),
            (5, self.patterns.EMP_ID_5DIGIT),
            (4, self.patterns.EMP_ID_4DIGIT),
        ]:
            # Threshold: higher for shorter numbers
            threshold = {4: 4, 5: 3, 6: 2, 7: 1, 8: 1}[digit_len]
            
            for match in pattern.finditer(text):
                # Skip if already detected
                if any(s <= match.start() < e or s < match.end() <= e for s, e in already_detected):
                    continue
                
                # Skip if followed by hyphen-text (likely RFC/ticket)
                after_chars = text[match.end():match.end()+2] if match.end() < len(text) else ''
                if after_chars.startswith('-') and len(after_chars) > 1 and after_chars[1].isalpha():
                    continue
                
                score = get_context_score(match, text, digit_len)
                
                if score >= threshold:
                    positions.append((match.start(), match.end(), self._get_token("EMP_ID")))
                    already_detected.add((match.start(), match.end()))

        return positions

    # =========================================================================
    # CORE REDACTION METHODS - Part 2: Asset, IP, Hostname, URL, UPI
    # =========================================================================

    def _redact_asset_ids(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark asset IDs and serial numbers for redaction."""
        positions = []
        positions.extend(self._find_pattern_matches(text, self.patterns.ASSET_ID, "ASSET_ID"))
        positions.extend(self._find_pattern_matches(text, self.patterns.ASSET_ID_EXTENDED, "ASSET_ID"))
        for match in self.patterns.SERIAL_NUMBER.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("SERIAL")))
        return positions

    def _redact_ip_addresses(self, text: str) -> List[Tuple[int, int, str]]:
        """
        v2.17.0: Detect and mark IP addresses with granular tokens.

        Returns [IP_V4] for IPv4 and [IP_V6] for IPv6 addresses.
        """
        positions = []
        # MAC must be checked BEFORE IPv6 since IPv6 pattern can match MAC addresses
        positions.extend(self._find_pattern_matches(text, self.patterns.MAC, "MAC"))
        # IPv4 -> [IP_V4]
        for match in self.patterns.IPV4.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("IP", "V4")))
        # IPv6 -> [IP_V6]
        for match in self.patterns.IPV6.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("IP", "V6")))
        return positions

    def _redact_hostnames(self, text: str) -> List[Tuple[int, int, str]]:
        """
        v2.17.0: Detect and mark hostnames with granular tokens.

        Returns [HOSTNAME_SVR], [HOSTNAME_DB], [HOSTNAME_GENERIC], [HOSTNAME_MEDIA].
        """
        positions = []
        # Standard server hostnames -> [HOSTNAME_SVR]
        for match in self.patterns.HOSTNAME.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("HOSTNAME", "SVR")))
        # v2.13.0: Enhanced hostname patterns
        # Generic hostnames -> [HOSTNAME_GENERIC]
        for match in self.patterns.HOSTNAME_GENERIC.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("HOSTNAME", "GENERIC")))
        # Database hostnames -> [HOSTNAME_DB]
        for match in self.patterns.HOSTNAME_DB.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("HOSTNAME", "DB")))
        # Labeled hostname in context: "media server INHYDB03" -> [HOSTNAME_MEDIA]
        for match in self.patterns.HOSTNAME_MEDIA_SERVER.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("HOSTNAME", "MEDIA")))
        # v2.15.1: FQDN (Fully Qualified Domain Names)
        positions.extend(self._redact_fqdn(text))
        return positions

    def _redact_fqdn(self, text: str) -> List[Tuple[int, int, str]]:
        """
        v2.17.0: Detect and mark FQDNs with granular tokens.

        Returns [HOSTNAME_FQDN] for FQDNs and [HOSTNAME_INTERNAL] for internal domains.
        Excludes emails (handled separately) and common non-FQDN patterns.
        """
        positions = []

        # Common domain suffixes to exclude (public websites, not internal FQDNs)
        public_domains_exclude = {
            'google.com', 'microsoft.com', 'github.com', 'stackoverflow.com',
            'youtube.com', 'facebook.com', 'twitter.com', 'linkedin.com',
            'amazon.com', 'aws.amazon.com', 'azure.microsoft.com',
        }

        # Internal TLD patterns (always redact) -> [HOSTNAME_INTERNAL]
        for match in self.patterns.FQDN_INTERNAL.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("HOSTNAME", "INTERNAL")))

        # Labeled FQDN patterns -> [HOSTNAME_FQDN]
        for match in self.patterns.FQDN_LABELED.finditer(text):
            if match.group(1):
                fqdn = match.group(1).lower()
                if fqdn not in public_domains_exclude:
                    positions.append((match.start(1), match.end(1), self._get_token("HOSTNAME", "FQDN")))
        
        # General FQDN pattern (be more careful with this one) -> [HOSTNAME_FQDN]
        for match in self.patterns.FQDN.finditer(text):
            if match.group(1):
                fqdn = match.group(1).lower()
                # Skip if it looks like a public domain
                if fqdn in public_domains_exclude:
                    continue
                # Skip if any parent domain is public
                parts = fqdn.split('.')
                skip = any(
                    '.'.join(parts[i:]) in public_domains_exclude
                    for i in range(len(parts) - 1)
                )
                if not skip:
                    positions.append((match.start(1), match.end(1), self._get_token("HOSTNAME", "FQDN")))
        
        return positions

    def _redact_urls(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark URLs for redaction."""
        return self._find_pattern_matches(text, self.patterns.URL, "URL")

    def _redact_upi_ids(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark UPI IDs for redaction."""
        return self._find_pattern_matches(text, self.patterns.UPI, "UPI")

    def _redact_credentials(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark passwords/credentials for redaction."""
        positions = []
        # Passwords with explicit assignment
        for match in self.patterns.PASSWORD.finditer(text):
            password_value = match.group(1).lower().rstrip('.,;:!?')
            if password_value in self.patterns.PASSWORD_NON_CREDENTIALS:
                continue
            positions.append((match.start(), match.end(), self._get_token("CREDENTIAL")))
        # VPN/Remote credentials
        for match in self.patterns.VPN_CREDS.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("CREDENTIAL", "VPN")))
        # API keys and access tokens
        for match in self.patterns.API_KEY.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("API_KEY")))
        # SSH private key headers
        positions.extend(self._find_pattern_matches(text, self.patterns.SSH_KEY, "SSH_KEY"))
        # Domain ID
        for match in self.patterns.DOMAIN_ID.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("DOMAIN_ID")))
        return positions

    def _redact_government_ids(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark government IDs (Aadhaar, PAN, Passport, SSN, DL, Voter ID, NIN)."""
        positions = []
        # Aadhaar: strict pattern (first digit 2-9) with Verhoeff checksum or keyword context
        for match in self.patterns.AADHAAR.finditer(text):
            candidate = re.sub(r'[\s-]', '', match.group())
            if self._verify_aadhaar(candidate):
                positions.append((match.start(), match.end(), self._get_token("AADHAAR")))
            else:
                # Accept without checksum if keyword nearby (within 50 chars before)
                prefix = text[max(0, match.start() - 50):match.start()].lower()
                if any(kw in prefix for kw in ('aadhaar', 'aadhar', 'uid', 'uidai')):
                    positions.append((match.start(), match.end(), self._get_token("AADHAAR")))
        # Aadhaar contextual: keyword + any 12-digit number (catches numbers starting with 0/1)
        for match in self.patterns.AADHAAR_CONTEXTUAL.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("AADHAAR")))
        positions.extend(self._find_pattern_matches(text, self.patterns.PAN, "PAN"))
        positions.extend(self._find_pattern_matches(text, self.patterns.PASSPORT, "PASSPORT"))
        # Credit card moved to _redact_financial()
        # SSN (US) - with separator
        positions.extend(self._find_pattern_matches(text, self.patterns.SSN, "SSN"))
        # SSN with context keyword (no separator needed)
        for match in self.patterns.SSN_CONTEXTUAL.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("SSN")))
        # Driving License (Indian)
        positions.extend(self._find_pattern_matches(text, self.patterns.DRIVING_LICENSE_IN, "DL"))
        # Vehicle Registration (Indian)
        positions.extend(self._find_pattern_matches(text, self.patterns.VEHICLE_REG_IN, "VEHICLE_REG"))
        # National Insurance Number (UK)
        positions.extend(self._find_pattern_matches(text, self.patterns.NIN_UK, "NIN"))
        # Voter ID / EPIC (Indian)
        positions.extend(self._find_pattern_matches(text, self.patterns.VOTER_ID_IN, "VOTER_ID"))
        return positions

    def _redact_banking(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark banking information (account numbers, IFSC, IBAN, SWIFT)."""
        positions = []
        # Bank account with explicit keyword (a/c, account)
        for match in self.patterns.BANK_ACCOUNT_IN.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("BANK_ACCOUNT", "IN")))
        # Bank account with transaction context (transfer to, deposit into, etc.)
        for match in self.patterns.BANK_ACCOUNT_CONTEXTUAL.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("BANK_ACCOUNT", "IN")))
        # IFSC Code (always redact - format is distinctive: 4 letters + 0 + 6 chars)
        positions.extend(self._find_pattern_matches(text, self.patterns.IFSC, "IFSC"))
        # IBAN
        positions.extend(self._find_pattern_matches(text, self.patterns.IBAN, "IBAN"))
        # SWIFT/BIC
        positions.extend(self._find_pattern_matches(text, self.patterns.SWIFT, "SWIFT"))
        # US Routing number with context
        for match in self.patterns.ROUTING_NUMBER.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("ROUTING_NUM")))
        return positions

    def _redact_financial(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark financial info (credit cards, EPF/UAN, insurance)."""
        positions = []
        # Credit/Debit card numbers (16 digits in groups of 4)
        positions.extend(self._find_pattern_matches(text, self.patterns.CREDIT_CARD, "CARD"))
        # EPF/UAN with context keyword
        for match in self.patterns.EPF_UAN.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("EPF_UAN")))
        # EPF Member ID
        positions.extend(self._find_pattern_matches(text, self.patterns.EPF_MEMBER_ID, "EPF_ID"))
        # Insurance policy with context
        for match in self.patterns.INSURANCE_POLICY.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("INSURANCE_POLICY")))
        return positions

    def _redact_dob(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and mark date of birth and age information."""
        positions = []
        # DOB with context keyword (dob, date of birth, born on)
        for match in self.patterns.DOB.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("DOB")))
        # Age with context keyword
        for match in self.patterns.AGE.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("AGE")))
        return positions

    def _redact_windows_paths(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact usernames in Windows paths."""
        positions = []
        for match in self.patterns.WIN_PATH.finditer(text):
            username = match.group(1)
            username_start = match.start() + match.group(0).index(username)
            positions.append((username_start, username_start + len(username), self._get_token("USERNAME")))
        return positions

    # =========================================================================
    # CORE REDACTION METHODS - Part 3: Name Detection (NER, Pattern, Context)
    # =========================================================================

    def _redact_names_ner(self, text: str) -> List[Tuple[int, int, str]]:
        """Use NER to detect names."""
        positions: List[Tuple[int, int, str]] = []
        if not self.config.enable_ner or not self.ner or not self.ner._loaded:
            return positions

        ner_false_positive_blocklist = {
            'email', 'mail', 'phone', 'call', 'text', 'message', 'chat',
            'sent', 'received', 'forward', 'reply', 'response',
            'ticket', 'issue', 'incident', 'problem', 'request', 'change',
            'system', 'server', 'service', 'application', 'database',
            'team', 'group', 'department', 'unit', 'division',
            'support', 'help', 'admin', 'user', 'customer', 'client',
            'today', 'yesterday', 'tomorrow', 'morning', 'evening',
            'please', 'thank', 'thanks', 'hello', 'dear', 'regards',
            'update', 'status', 'review', 'approval', 'action', 'resolution',
            'blue', 'screen', 'bsod', 'global', 'windows', 'mac', 'linux',
            'kmode', 'exception', 'reference', 'pointer', 'pool', 'caller',
            'thread', 'handled', 'bad', 'memory', 'disk', 'driver',
            'acer', 'dell', 'lenovo', 'hp', 'asus', 'intel', 'amd', 'nvidia',
            'bluetooth', 'wifi', 'ethernet', 'usb', 'hdmi',
            'connect', 'resolve', 'work', 'format', 'turn', 'boot', 'reboot',
            'access', 'open', 'close', 'start', 'stop', 'run', 'hear',
            'agent', 'engineer', 'technician', 'analyst', 'associate',
            'colleague', 'member', 'employee', 'staff',
            'urgently', 'immediately', 'quickly', 'properly', 'correctly',
            'manila', 'clark', 'office', 'floor', 'desk', 'seat',
            'no', 'yes', 'ok', 'on', 'off', 'up', 'down', 'in', 'out',
            'ms', 'mr', 'am', 'pm', 'is', 'it', 'as', 'at', 'by', 'to',
            'good', 'bad', 'new', 'old', 'more', 'less', 'done', 'pending',
            'intermittent', 'ongoing', 'working', 'broken',
            'project', 'asset', 'device', 'equipment', 'hardware', 'software',
            'drill', 'backup', 'restore', 'failover', 'switchover',
            'recipients', 'channels', 'delivery', 'response',
            # v2.13.0: IT/tech terms that look like names
            'tag', 'barcode', 'scanner', 'serial', 'label', 'badge',
            'zscaler', 'intune', 'avaya', 'cisco', 'duo', 'okta',
            # v2.15.0: Software/tools incorrectly classified as PERSON by spaCy
            'git', 'putty', 'jupyter', 'postman', 'winscp', 'maven', 'tomcat',
            'eclipse', 'intellij', 'vscode', 'node', 'mongodb', 'chrome',
            'firefox', 'edge', 'safari', 'python', 'java', 'ruby', 'perl',
            # v2.15.0: Microsoft products
            'teams', 'azure', 'outlook', 'excel', 'word', 'powerpoint',
            'sharepoint', 'onedrive', 'onenote', 'visio',
            # v2.15.0: IT/Security products
            'qualys', 'vdi', 'citrix', 'sap', 'oracle', 'vmware', 'tanium',
            'crowdstrike', 'splunk', 'tenable', 'fortinet', 'paloalto',
            # v2.15.0: Countries/locations misclassified as PERSON
            'india', 'hungary', 'bangalore', 'hyderabad', 'chennai', 'mumbai',
            'pune', 'delhi', 'kolkata', 'noida', 'gurgaon', 'america',
            'europe', 'asia', 'africa', 'australia',
            # v2.15.0: Work-related terms
            'home', 'associates', 'recruiter', 'linkedin', 'genai',
            'ultimatix', 'installation', 'infrastructure', 'migration',
            # v2.15.1: Technical terms incorrectly classified as PERSON by spaCy
            'hypervisor', 'hypervior', 'kubernetes', 'docker', 'ansible',
            'terraform', 'jenkins', 'grafana', 'prometheus', 'elasticsearch',
            'android', 'andriod', 'ios', 'iphone', 'ipad',
            'uninstallation', 'configuration', 'deployment', 'provisioning',
        }

        entities = self.ner.extract_entities(text)
        for ent_text, label, start, end in entities:
            if label == "PERSON":
                ent_lower = ent_text.lower()
                # v2.15.0: Check both exact match and any word in entity
                if ent_lower in ner_false_positive_blocklist:
                    continue
                # v2.15.0: Skip if any word in the entity is a known false positive
                # Handles cases like "Postman API" where "postman" is in blocklist
                ent_words = {w.lower() for w in ent_text.split()}
                if ent_words & ner_false_positive_blocklist:
                    continue
                # v2.13.0: Skip internal system names (Zscaler, Intune, etc.)
                if ent_lower in self._systems:
                    continue
                positions.append((start, end, self._get_token("NAME")))
            elif label == "ORG" and self.config.redact_companies:
                if ent_text.lower() in self._companies:
                    positions.append((start, end, self._get_token("ORG")))
            elif label in {"GPE", "LOC"} and self.config.redact_locations:
                # v2.15.0: Skip common country/region names that don't identify individuals
                # These are too generic and cause false positives in IT context
                location_blocklist = {
                    'india', 'hungary', 'america', 'usa', 'uk', 'england', 'germany',
                    'france', 'spain', 'italy', 'china', 'japan', 'australia',
                    'canada', 'brazil', 'mexico', 'singapore', 'malaysia', 'philippines',
                    'europe', 'asia', 'africa', 'americas', 'apac', 'emea', 'latam',
                    # Indian cities commonly mentioned in IT tickets
                    'bangalore', 'bengaluru', 'hyderabad', 'chennai', 'mumbai', 'pune',
                    'delhi', 'kolkata', 'noida', 'gurgaon', 'gurugram',
                }
                if ent_text.lower() in location_blocklist:
                    continue
                positions.append((start, end, self._get_token("LOCATION")))

        return positions

    def _redact_names_pattern(self, text: str) -> List[Tuple[int, int, str]]:
        """Use patterns to detect names."""
        positions = []
        
        # v2.15.0: False positive terms that pattern matching should skip
        # v2.16.1: Extended with high-frequency FPs from Dec 2025 analysis
        pattern_false_positives = {
            # Software/Products
            'teams', 'azure', 'outlook', 'excel', 'word', 'powerpoint',
            'sharepoint', 'onedrive', 'onenote', 'visio', 'windows',
            'office', 'surface', 'bing', 'edge', 'cortana',
            'git', 'putty', 'jupyter', 'postman', 'winscp', 'maven',
            'tomcat', 'eclipse', 'intellij', 'vscode', 'node', 'mongodb',
            'qualys', 'vdi', 'citrix', 'sap', 'oracle', 'vmware',
            'drill', 'tag', 'barcode', 'scanner', 'home', 'associates',
            'duo', 'cyberark', 'zscalar', 'nexpose', 'authenticator',
            'google', 'chrome', 'firefox', 'safari',
            # Common words captured as titles
            'ms', 'mr', 'mrs', 'dr', 'sr', 'jr',
            # Common FPs from ticket analysis
            'urgent', 'procurement', 'requirement', 'leakage', 'protector',
            'controls', 'detection', 'managed', 'digital', 'central', 'owner',
            'helpdesk', 'auto', 'play', 'citi', 'facing', 'types', 'licenses',
            # Common English words
            'as', 'non', 'im', 'only', 'or', 'due', 'so', 'need', 'id', 'day',
            'also', 'any', 'both', 'now', 'an', 'will', 'are', 'fan', 'if', 'get',
            # Time/status
            'automated', 'using', 'hence', 'week', 'past', 'after', 'installed',
            'onwards', 'getting', 'already', 'since', 'through', 'while',
            # IT terms
            'backend', 'requestors', 'customers', 'users', 'clients', 'devices',
            'browser', 'apps', 'parameters', 'artifacts', 'pressing', 'playstore',
            'personal', 'nextgen', 'conformation', 'exchange', 'connecting',
            # v2.16.1: "MS X" pattern false positives (captured after Mr/Ms title)
            'app', 'products', 'product', 'team', 'license', 'access', 'security',
            'mobile', 'store', 'mail', 'service', 'services', 'tools', 'suite',
            # v2.16.2: Additional FPs from 1.68M analysis
            'head', 'mailbox', 'prem', 'toll', 'free', 'security', 'duo',
            'cyberark', 'protector', 'exchange', 'licensing', 'dynamics',
            'power', 'planner', 'forms', 'stream', 'sway', 'whiteboard',
            'bookings', 'todo', 'kaizala', 'graph', 'identity', 'intune', 'defender',
            # v2.16.3: DR pattern FPs (Dr title triggers on DR abbreviation)
            'server', 'servers', 'backup', 'site', 'recovery', 'plan', 'drill', 'test',
            # v2.16.3 batch 2: More FPs from latest analysis
            'microsoft', 'hardening', 'automation', 'group', 'client', 'name',
            'asked', 'changed', 'dropping', 'assigned', 'completed',
        }

        for match in self.patterns.NAME_WITH_TITLE.finditer(text):
            # v2.15.0: Skip if matched name is a known false positive
            matched_name = match.group(1) if match.groups() else match.group(0)
            if matched_name:
                # v2.16.3: Check if any word in matched name is in false positives
                name_words = matched_name.lower().split()
                if any(w in pattern_false_positives for w in name_words):
                    continue
                # Also skip if it looks like a product/service name (all words are FP)
                if matched_name.lower() in pattern_false_positives:
                    continue
            positions.append((match.start(), match.end(), self._get_token("NAME")))

        for match in self.patterns.NAME_LABELED.finditer(text):
            if match.group(1):
                name = match.group(1)
                # v2.16.0: Skip identifiers with underscores (like TCS_ZCC, TCS_5GHz)
                if '_' in name:
                    continue
                # v2.16.0: Skip all-caps words (likely acronyms/tech terms)
                if name.isupper() and len(name) <= 20:
                    continue
                # v2.16.3: Check if any word in name is in false positives
                name_words = name.lower().split()
                if any(w in pattern_false_positives for w in name_words):
                    continue
                name_start = match.start() + match.group(0).index(name)
                positions.append((name_start, name_start + len(name), self._get_token("NAME")))

        for match in self.patterns.MY_NAME_IS.finditer(text):
            if match.group(1):
                name = match.group(1)
                name_start = match.start() + match.group(0).index(name)
                positions.append((name_start, name_start + len(name), self._get_token("NAME")))

        # v2.13.0: Name in parentheses after employee ID
        # Catches: "445658(Dhanalakshmi)", "1234567(Rahul Kumar)"
        for match in self.patterns.NAME_AFTER_EMP_ID.finditer(text):
            if match.group(1):
                name = match.group(1).strip()
                # Skip if it's a system/IT term
                if name.lower() not in self._systems and len(name) > 2:
                    positions.append((match.start(1), match.end(1), self._get_token("NAME")))

        return positions

    def _redact_names_contextual(self, text: str) -> List[Tuple[int, int, str]]:
        """Enhanced contextual name detection (v2.5) - HIGH CONFIDENCE."""
        positions = []
        
        common_word_exclusions = {
            'i', 'me', 'my', 'mine', 'myself', 'you', 'your', 'yours', 'yourself',
            'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
            'it', 'its', 'itself', 'we', 'us', 'our', 'ours', 'ourselves',
            'they', 'them', 'their', 'theirs', 'themselves',
            'seat', 'desk', 'floor', 'room', 'office', 'building',
            'team', 'group', 'department', 'division', 'unit',
            'server', 'system', 'service', 'application', 'database',
            'ticket', 'issue', 'incident', 'problem', 'request', 'change',
            'email', 'phone', 'call', 'chat', 'message', 'meeting', 'mail', 'sent',
            'today', 'yesterday', 'tomorrow', 'morning', 'evening',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'the', 'and', 'but', 'for', 'not', 'all', 'can', 'had', 'was', 'one', 'has', 'been',
            'from', 'by', 'cc', 'bcc', 'via', 'per', 'for', 'to', 'on', 'at', 'in',
            'user', 'admin', 'customer', 'client', 'vendor', 'support', 'help',
            'connect', 'resolve', 'work', 'format', 'turn', 'hear', 'reach', 'submit',
            'urgently', 'immediately', 'quickly', 'slowly', 'properly', 'correctly',
            'blue', 'screen', 'bsod', 'crash', 'hang', 'freeze', 'stuck',
            'agent', 'process', 'thread', 'memory', 'disk', 'drive',
            'acer', 'dell', 'lenovo', 'hp', 'asus', 'microsoft', 'windows', 'mac',
            'pending', 'complete', 'completed', 'finished', 'done', 'ready',
            'colleague', 'associate', 'member', 'employee', 'manager', 'supervisor',
            'project', 'asset', 'device', 'equipment', 'hardware', 'software',
            'no', 'yes', 'ok', 'na', 'nil', 'none', 'null', 'void',
            'ms', 'mr', 'mrs', 'dr', 'sr', 'jr', 'pr', 'qa', 'uat', 'dev', 'prod',
            'informs', 'teams', 'slack', 'jira', 'snow', 'servicenow',
            'am', 'pm', 'hr', 'min', 'sec', 'kb', 'mb', 'gb', 'tb',
            'good', 'bad', 'new', 'old', 'first', 'last', 'next', 'previous',
            'working', 'broken', 'damaged', 'defective', 'faulty',
            'intermittent', 'occasional', 'frequent', 'constant', 'ongoing',
            # v2.13.0: IT/tech terms that cause false positives
            'barcode', 'tag', 'scanner', 'serial', 'code', 'label', 'badge', 'rfid',
            'zscaler', 'intune', 'avaya', 'cisco', 'duo', 'okta', 'qualys',
            # v2.15.1: ITSM/ticket system abbreviations that cause false positives
            'cr', 'sr', 'inc', 'rfc', 'chg', 'prb', 'req', 'sctask', 'ritm',
            'ticketing', 'portal', 'workspace', 'console', 'dashboard',
            # v2.15.1: Common words causing false positives in IT tickets
            'long', 'short', 'times', 'time', 'leave', 'vacation', 'holiday',
            'android', 'andriod', 'ios', 'iphone', 'ipad', 'mobile', 'phone', 'device',
            'hypervisor', 'hypervior', 'vmware', 'hyper', 'vm', 'vms',
            'is', 'it', 'hr', 'admin', 'infra', 'network', 'security', 'ops',
            'tcs', 'provided', 'laptop', 'desktop', 'pc', 'computer',
            'belor', 'below', 'above', 'following', 'attached', 'mentioned',
            # v2.15.0: Countries/regions/cities that cause false positives
            'india', 'hungary', 'america', 'usa', 'uk', 'england', 'germany',
            'france', 'spain', 'italy', 'china', 'japan', 'australia', 'canada',
            'brazil', 'mexico', 'singapore', 'malaysia', 'philippines',
            'bangalore', 'bengaluru', 'hyderabad', 'chennai', 'mumbai', 'pune',
            'delhi', 'kolkata', 'noida', 'gurgaon', 'gurugram',
            'europe', 'asia', 'africa', 'americas', 'apac', 'emea', 'latam',
            # v2.15.0: Software/tools that cause false positives
            'git', 'putty', 'jupyter', 'postman', 'winscp', 'maven', 'tomcat',
            'eclipse', 'intellij', 'vscode', 'node', 'mongodb', 'azure', 'excel',
            'outlook', 'word', 'powerpoint', 'sharepoint', 'vdi', 'citrix', 'sap',
            'home', 'associates', 'recruiter', 'linkedin', 'genai', 'ultimatix',
            # v2.15.1: Technical action words that cause false positives
            'uninstallation', 'uninstall', 'installation', 'install', 'reinstall',
            'reinstallation', 'configuration', 'configure', 'reconfigure', 'reconfiguration',
            'migration', 'migrate', 'upgrade', 'downgrade', 'update', 'patch',
            'deployment', 'deploy', 'provisioning', 'provision', 'deprovisioning',
            'activation', 'deactivation', 'enable', 'disable', 'enablement',
            'engagement', 'onboarding', 'offboarding', 'termination', 'separation',
            # v2.16.0: IT/business terms from 60K analysis
            'emp', 'name', 'asset', 'new', 'location', 'app', 'domain', 'source',
            'management', 'administrator', 'version', 'url', 'contact', 'bank', 'local',
            'services', 'number', 'recording', 'automation', 'protect', 'renewal',
            'horizon', 'sales', 'globe', 'global', 'corporate', 'entrust', 'avd',
            # v2.16.0: Acronyms and abbreviations that cause false positives
            'rfc', 'odc', 'dis', 'ism', 'soe', 'cdc', 'ssl', 'ghd', 'ssid', 'dev',
            'iam', 'edr', 'bms', 'bulk', 'com', 'vlan', 'api', 'noc', 'lan', 'zim',
            'soam', 'noam', 'rights', 'tgim', 'vpn', 'access',
            # v2.16.0: Additional IT/software terms causing false positives
            'firewall', 'store', 'centre', 'center', 'control', 'type', 'nokia',
            'cisco', 'hub', 'portal', 'paas', 'saas', 'iaas', 'proxy', 'gateway',
            'client', 'current', 'existing', 'available', 'required', 'raised',
            'open', 'close', 'closed', 'opened', 'security', 'policy', 'policies',
            # v2.16.0: More common words causing false positives
            'of', 'freeware', 'shareware', 'proprietary', 'licensed', 'opensource',
            'wifi', 'wlan', 'ssid', 'network', 'subnet', 'vrf', 'vlan',
            'enable', 'enabled', 'disabled', 'active', 'inactive',
            # v2.16.0: From 200K analysis - common action/context words
            'end', 'side', 'doing', 'checking', 'updating', 'making', 'click', 'then',
            'encryption', 'loss', 'prevention', 'data', 'disk',
            # v2.16.0: From 150K final validation - gerunds/action words after 'by'
            'configuring', 'clicking', 'running', 'accessing', 'installing', 'restarting',
            'enabling', 'requesting', 'resolving', 'assigning', 'completing', 'processing',
            'performing', 'executing', 'submitting', 'creating', 'deleting', 'removing',
            'adding', 'changing', 'modifying', 'editing', 'saving', 'loading', 'downloading',
            'uploading', 'copying', 'pasting', 'moving', 'renaming', 'replacing', 'restoring',
            'backing', 'syncing', 'synching', 'refreshing', 'clearing', 'resetting', 'rebooting',
            'shutting', 'starting', 'stopping', 'pausing', 'resuming', 'cancelling', 'canceling',
            'opening', 'closing', 'logging', 'signing', 'authenticating', 'verifying',
            'validating', 'testing', 'debugging', 'troubleshooting', 'investigating',
            'escalating', 'forwarding', 'transferring', 'routing', 'assisting', 'helping',
            'providing', 'sharing', 'sending', 'receiving', 'reading', 'writing', 'typing',
            'entering', 'selecting', 'choosing', 'picking', 'navigating', 'browsing', 'searching',
            'finding', 'locating', 'identifying', 'recognizing', 'detecting', 'scanning',
            'mapping', 'assigning', 'allocating', 'granting', 'revoking', 'approving', 'rejecting',
            'confirming', 'acknowledging', 'accepting', 'declining', 'denying', 'blocking',
            'allowing', 'permitting', 'authorizing', 'authenticating', 'encrypting', 'decrypting',
            'compressing', 'extracting', 'archiving', 'zipping', 'unzipping', 'packaging',
            'deploying', 'publishing', 'releasing', 'launching', 'initiating', 'triggering',
            'scheduling', 'queuing', 'monitoring', 'tracking', 'auditing', 'reviewing',
            # v2.16.0: Common IT nouns that appear after action verbs
            'settings', 'script', 'feature', 'machine', 'page', 'button', 'link', 'option',
            'menu', 'tab', 'panel', 'window', 'dialog', 'popup', 'dropdown', 'checkbox',
            'field', 'form', 'table', 'list', 'file', 'folder', 'directory', 'path',
            'icon', 'image', 'logo', 'banner', 'header', 'footer', 'sidebar', 'widget',
            'component', 'module', 'plugin', 'extension', 'addon', 'tool', 'utility',
            'command', 'function', 'method', 'class', 'object', 'variable', 'parameter',
            'argument', 'value', 'key', 'property', 'attribute', 'element', 'item', 'record',
            'row', 'column', 'cell', 'entry', 'data', 'text', 'string', 'number', 'integer',
            'boolean', 'flag', 'status', 'state', 'mode', 'level', 'priority', 'severity',
            'category', 'type', 'kind', 'sort', 'order', 'filter', 'query', 'search', 'result',
            'output', 'input', 'error', 'warning', 'message', 'notification', 'alert', 'prompt',
            'response', 'request', 'connection', 'session', 'token', 'credential', 'permission',
            'role', 'profile', 'account', 'organization', 'workspace', 'environment', 'instance',
            # v2.16.0: From 150K validation - additional context words causing FPs
            'official', 'left', 'right', 'corner', 'top', 'bottom', 'middle', 'center',
            'upper', 'lower', 'inner', 'outer', 'front', 'back', 'inside', 'outside',
            'please', 'kindly', 'thanks', 'thank', 'regards', 'sincerely', 'yours', 'best',
            # v2.16.0: IT infrastructure/policy words
            'servers', 'compliance', 'block', 'audit', 'governance', 'regulatory',
            'infrastructure', 'architecture', 'framework', 'platform', 'solution',
            'endpoint', 'endpoints', 'workstation', 'workstations', 'virtual', 'physical',
            'production', 'staging', 'development', 'testing', 'sandbox', 'backup',
            
            # v2.16.1: From Dec 2025 1M+ ticket/RFC analysis - high-frequency false positives
            # Common words appearing after "by"/"from" that aren't names
            'as', 'non', 'im', 'only', 'or', 'due', 'so', 'need', 'id', 'day', 'also',
            'any', 'both', 'now', 'an', 'pin', 'will', 'are', 'fan', 'if', 'own', 'get',
            'web', 'log', 'ad', 're', 'be', 'do', 'go', 'no', 'up',
            # Tech/IT terms caught as names
            'requestors', 'backend', 'google', 'browser', 'apps', 'devices', 'customers',
            'users', 'parameters', 'artifacts', 'host', 'clients', 'apps', 'pressing',
            'playstore', 'conformation', 'personal', 'nextgen', 'prodinfosync', 'playstore',
            # Time/status words caught as names
            'automated', 'using', 'levels', 'hence', 'week', 'past', 'after', 'installed',
            'onwards', 'getting', 'exchange', 'already', 'connecting', 'month', 'since',
            'raising', 'through', 'while', 'showing',
            # Product names/abbreviations caught as names
            'ms', 'duo', 'cyberark', 'authenticator', 'protector', 'controls', 'leakage',
            'procurement', 'requirement', 'urgent', 'citi', 'play', 'nexpose', 'managed',
            'detection', 'auto', 'helpdesk', 'zscalar', 'digital', 'central', 'owner',
            # Location words
            'indore', 'kochi', 'park', 'tower', 'facing', 'premises', 'golddolphin',
            # Common action/context words appearing after contextual patterns  
            'address', 'company', 'point', 'raise', 'avoid', 'resource', 'destination',
            'types', 'licenses', 'based', 'checked', 'visiting', 'latest', 'tech', 'blocked',
            'added', 'received', 'authenticator', 'sites', 'communication', 'handover',
            'camera', 'charger', 'exclude', 'pin', 'ips', 'artifacts', 'parameters',
            'browser', 'week', 'past', 'premise', 'ongoing', 'zone', 'mail', 'chatting',
            # Words from signature blocks
            'associate', 'associates', 'team', 'teams', 'customer', 'satisfaction', 'survey',
            
            # v2.16.2: From 1.68M sample analysis - additional FPs discovered
            # Verbs/gerunds often caught after "by"/"from" in IT tickets
            'discussed', 'reopening', 'reopened', 'mentioning', 'given', 'provided',
            'following', 'regarding', 'concerning', 'referring', 'directing', 'addressing',
            'clarifying', 'confirming', 'validating', 'approving', 'denying', 'rejecting',
            # Single-word FPs (capitalized but not names)
            'buzz', 'lead', 'leads', 'hard', 'systems', 'links', 'bitlocker',
            'omnissa', 'adibatla', 'excludegcdssync', 'toll', 'free', 'prem',
            # Product/service terms appearing after "MS" pattern
            'license', 'procurement', 'head', 'mailbox', 'security', 'mobile',
            # More location/business terms
            'wing', 'north', 'south', 'east', 'west', 'annex', 'extension',
            'procurement', 'discretion', 'isuhead', 'isu',
            # v2.16.2 batch 2: More verbs/IT terms from 1.68M analysis
            'updated', 'guided', 'implementing', 'attaching', 'shared', 'requested',
            'br', 'li', 'ul', 'ol', 'div', 'span', 'html', 'htm', 'xml',  # HTML tags
            'cloud', 'clone', 'magnum', 'synergy', 'olympus', 'nagpur', 'kerala',
            'kong', 'gitanjali', 'assoicate', 'associate',
            
            # v2.16.3: Comprehensive FP elimination from 1.68M analysis
            # Common verbs/gerunds still being captured
            'everything', 'distribution', 'reinstalling', 'having', 'considering',
            'factor', 'authentication', 'waiting', 'working', 'pending', 'sending',
            'calling', 'checking', 'doing', 'facing', 'getting', 'going', 'looking',
            'needing', 'raising', 'reaching', 'seeing', 'taking', 'telling', 'trying',
            'using', 'asking', 'coming', 'dealing', 'finding', 'giving', 'handling',
            'holding', 'keeping', 'making', 'meeting', 'putting', 'reading', 'showing',
            # v2.16.3 batch 2: More verbs from latest analysis
            'uninstalling', 'replaced', 'signed', 'supplied', 'created', 'approved',
            'removing', 'deleting', 'adding', 'changing', 'moving', 'copying',
            # Product/software names being captured
            'manage', 'engine', 'visual', 'studio', 'golden', 'images', 'image',
            'qradar', 'wintel', 'secops', 'deccan', 'yamuna', 'colleagues',
            'bhuwalka', 'excludegcdsync', 'ids', 'factors', 'multi',
            # v2.16.3 batch 2: More product/org terms
            'microsoft', 'enterprise', 'enterprises', 'client', 'server', 'usaa',
            'intune', 'restriction', 'restrictions', 'online', 'package', 'super',
            'visor', 'supervisor', 'build', 'errors', 'pwc',
            # v2.16.3 batch 3: More FPs from 1.68M analysis
            'hardening', 'asked', 'changed', 'dropping', 'registration', 'ecospace',
            'submit', 'and', 'submitted', 'escalated', 'forwarded', 'transferred',
            # v2.16.3 batch 4: Final FPs from 1.68M analysis
            'booting', 'suggested', 'contacted', 'reimaging', 'platformsolution',
            'organisation', 'organization', 'ecludegcdssync', 'excludegcdssync',
            # v2.16.3 batch 5: More FPs
            'logged', 'excluded', 'being', 'dated', 'justification', 'think',
            # v2.16.3 batch 6: Final verbs and phrases
            'used', 'deleted', 'contacting', 'implementation', 'older', 'operating',
            'platformsolutions', 'platform', 'solution', 'solutions',
            # v2.16.3 batch 7: Final FPs
            'joined', 'needed', 'configured', 'budget', 'management', 'system',
            # Time/quantity words
            'days', 'few', 'two', 'three', 'four', 'five', 'one', 'many', 'some',
            'several', 'multiple', 'single', 'double', 'half', 'full', 'every',
            # Color/description words
            'yellow', 'fields', 'field', 'registry', 'editor', 'training', 'materials',
            'blue', 'red', 'green', 'black', 'white', 'gray', 'grey', 'orange',
            # IT acronyms and abbreviations
            'amc', 'potr', 'mfa', 'sso', 'ldap', 'adfs', 'saml', 'oauth', 'jwt',
            'tcp', 'udp', 'icmp', 'smtp', 'imap', 'pop', 'ftp', 'sftp', 'scp',
            # Common phrases that get captured
            'dont', 'have', 'under', 'above', 'below', 'within', 'without',
            'before', 'after', 'during', 'between', 'across', 'through',
            # More product/company terms
            'trend', 'micro', 'carbon', 'black', 'crowdstrike', 'sentinel',
            'splunk', 'elastic', 'prometheus', 'grafana', 'datadog', 'newrelic',
            'palo', 'alto', 'fortinet', 'checkpoint', 'sophos', 'symantec',
            'mcafee', 'kaspersky', 'bitdefender', 'norton', 'avast', 'avg',
            # Location/geography terms
            'india', 'indian', 'mumbai', 'delhi', 'chennai', 'bangalore', 'hyderabad',
            'pune', 'kolkata', 'ahmedabad', 'jaipur', 'lucknow', 'kanpur', 'surat',
            'floor', 'wing', 'block', 'tower', 'building', 'campus', 'office',
            # Job titles/roles that aren't names
            'manager', 'director', 'executive', 'analyst', 'engineer', 'developer',
            'consultant', 'specialist', 'coordinator', 'administrator', 'supervisor',
            'lead', 'senior', 'junior', 'associate', 'intern', 'trainee',
            
            # v2.16.3: COMPREHENSIVE FP EXCLUSION LIST from 1.68M sample analysis
            # All single-word FPs identified from ticket/RFC data analysis
            'accept', 'accessibility', 'addendum', 'afternoon', 'along', 'amit', 'amount',
            'anchor', 'anyone', 'applications', 'ask', 'assets', 'assigned', 'assoicate',
            'atl', 'attaching', 'automatically', 'autopilot', 'backed', 'banking', 'base',
            'because', 'beginning', 'behalf', 'bhubaneswar', 'bhuwalka', 'box', 'br', 'buzz',
            'case', 'catalog', 'certificate', 'chain', 'choose', 'cin', 'clone', 'cloud',
            'colleagues', 'collect', 'come', 'coming', 'comm', 'common', 'complaince',
            'compliant', 'concern', 'concerned', 'confirm', 'confirmed', 'connected',
            'connectivity', 'considering', 'contained', 'copilot', 'correct', 'cosole',
            'couple', 'credentials', 'date', 'days', 'dear', 'deccan', 'dedicated', 'despite',
            'disabling', 'discussed', 'distribution', 'domains', 'drivers', 'drop', 'during',
            'earlier', 'emails', 'engineer', 'engr', 'epo', 'even', 'everything',
            'excludegcdssync', 'excludegcdsync', 'executive', 'expired', 'feel', 'few',
            'follow', 'formatting', 'gcd', 'ginchnsir', 'giving', 'got', 'gps', 'groups',
            'grp', 'guide', 'guided', 'gws', 'having', 'here', 'hostname', 'hotspot',
            'implement', 'implementing', 'incognito', 'inform', 'informed', 'initial',
            'initiated', 'issues', 'isu', 'ive', 'java', 'keys', 'laptops', 'lead', 'like',
            'linux', 'lockout', 'looping', 'machines', 'mailbox', 'mails', 'manger',
            'maternity', 'members', 'mention', 'mentioning', 'messaging', 'mistake',
            'mistakenly', 'multiple', 'myapp', 'myapps', 'name', 'needful', 'networking',
            'night', 'noncompliance', 'nor', 'numbers', 'offshore', 'once', 'onsite',
            'options', 'others', 'paramters', 'part', 'parts', 'patches', 'person', 'ping',
            'place', 'pls', 'pooja', 'ports', 'post', 'power', 'prem', 'private', 'priyanka',
            'procured', 'provide', 'purpose', 'qradar', 'rahul', 'receiver', 'recovery',
            'registered', 'reinstalling', 'relevant', 'removed', 'reopening', 'replacement',
            'replying', 'requested', 'resolved', 'respective', 'return', 'revert', 'saying',
            'secops', 'securid', 'self', 'sentinel', 'set', 'setting', 'share', 'shared',
            'shipment', 'sign', 'sir', 'siruseri', 'snipping', 'softwares', 'someone',
            'speakers', 'specific', 'stating', 'still', 'sub', 'successfully', 'sync',
            'taking', 'teammate', 'technician', 'tenant', 'than', 'these', 'till', 'tools',
            'tried', 'trivandrum', 'turning', 'ultx', 'uninstall', 'unix', 'updated',
            'usera', 'valid', 'visit', 'voice', 'warranty', 'website', 'well', 'wintel',
            'within', 'without', 'write', 'yamuna',
            # Multi-word FP phrases - first words
            'duo', 'security', 'mobile', 'types', 'licenses', 'user', 'dont', 'factor',
            'authentication', 'ms', 'license', 'procurement', 'toll', 'free', 'isu', 'head',
            'prem', 'exchange', 'mailbox', 'visual', 'studio', 'golden', 'images', 'manage',
            'engine', 'program', 'files', 'dr', 'servers', 'automation', 'continuity',
            'spring', 'tool', 'suite', 'palo', 'alto', 'training', 'materials', 'registry',
            'editor', 'yellow', 'fields', 'fast', 'track', 'proper', 'groups', 'listed',
            'hostnames', 'related', 'accounts', 'usage', 'uba', 'cs', 'contained',
            'concerned', 'person', 'technician', 'soon', 'specifically', 'granted',
            'allocated', 'time', 'slot', 'recording', 'requested', 'ip', 'client',
            # WiFi/network
            'wi', 'fi', 'wifi', 'wlan', 'ssid', 'lan', 'wan', 'vpn', 'dns',
            # More common words
            'group', 'proper', 'listed', 'hostname', 'account', 'domain',
            'respective', 'concerned', 'required', 'necessary', 'available',
        }

        contextual_patterns = [
            self.patterns.NAME_CONTEXT_FROM_BY,
            self.patterns.NAME_GREETING,
            self.patterns.NAME_COMMUNICATION,
            self.patterns.NAME_TICKET_CALLER,
            self.patterns.NAME_USER_ACTION,
            self.patterns.NAME_HAS_ACTION,
            self.patterns.NAME_WITH_PARENS,
            self.patterns.NAME_SIGNATURE_LINE,
            self.patterns.NAME_AFTER_SIGNATURE,  # v2.16.0: "Thanks, Name" signatures
        ]

        for pattern in contextual_patterns:
            for match in pattern.finditer(text):
                if match.group(1):
                    name = match.group(1).strip()
                    name_lower = name.lower()
                    words = name_lower.split()
                    
                    if not words:
                        continue
                    
                    while words and words[-1] in common_word_exclusions:
                        words.pop()
                    while words and words[0] in common_word_exclusions:
                        words.pop(0)
                    
                    if not words:
                        continue
                    
                    original_words = name.split()
                    original_lower_words = name_lower.split()
                    start_strip = 0
                    while start_strip < len(original_lower_words) and original_lower_words[start_strip] in common_word_exclusions:
                        start_strip += 1
                    end_strip = len(original_lower_words)
                    while end_strip > start_strip and original_lower_words[end_strip - 1] in common_word_exclusions:
                        end_strip -= 1
                    
                    cleaned_name = ' '.join(original_words[start_strip:end_strip])
                    
                    # v2.16.0: Skip all-caps words (likely acronyms/tech terms) unless it looks like a name
                    if cleaned_name.isupper() and len(cleaned_name) <= 20:
                        continue  # Skip ERPDEV, NONPROD, etc.
                    
                    # v2.16.0: Skip identifiers with underscores (like TCS_ZCC, IND_DEL_YAM)
                    if '_' in cleaned_name:
                        continue
                    
                    if len(cleaned_name) >= 2 and cleaned_name[0].isalpha():
                        try:
                            name_start = match.start() + match.group(0).index(cleaned_name)
                            positions.append((name_start, name_start + len(cleaned_name), self._get_token("NAME")))
                        except ValueError:
                            positions.append((match.start(1), match.end(1), self._get_token("NAME")))

        return positions

    def _redact_names_from_email(self, text: str) -> List[Tuple[int, int, str]]:
        """Extract names correlated with email addresses (v2.5)."""
        positions = []
        _name_regex_cache: Dict[str, re.Pattern] = {}

        def _get_cached_pattern(name: str) -> re.Pattern:
            if name not in _name_regex_cache:
                _name_regex_cache[name] = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
            return _name_regex_cache[name]

        for match in self.patterns.EMAIL.finditer(text):
            email = match.group(0)
            local_part = email.split('@')[0].lower()
            name_parts = self._email_local_split_re.split(local_part)
            name_parts = [p for p in name_parts if len(p) >= 2 and not p.isdigit()]
            
            if len(name_parts) >= 2:
                first_last = name_parts[0].capitalize() + ' ' + name_parts[1].capitalize()
                search_start = max(0, match.start() - 100)
                search_text = text[search_start:match.start()]
                
                name_pattern = _get_cached_pattern(first_last)
                for name_match in name_pattern.finditer(search_text):
                    actual_start = search_start + name_match.start()
                    actual_end = search_start + name_match.end()
                    positions.append((actual_start, actual_end, self._get_token("NAME")))
                
                last_first = name_parts[1].capitalize() + ' ' + name_parts[0].capitalize()
                name_pattern_rev = _get_cached_pattern(last_first)
                for name_match in name_pattern_rev.finditer(search_text):
                    actual_start = search_start + name_match.start()
                    actual_end = search_start + name_match.end()
                    positions.append((actual_start, actual_end, self._get_token("NAME")))

        return positions

    def _redact_names_dictionary(self, text: str) -> List[Tuple[int, int, str]]:
        """Use dictionary to detect Indian names in specific patterns."""
        positions = []
        
        non_name_prefixes = {
            'contact', 'dear', 'hello', 'hi', 'hey', 'please', 'thanks', 'thank',
            'regards', 'sincerely', 'cheers', 'best', 'warm', 'kind',
            'mr', 'mrs', 'ms', 'miss', 'dr', 'prof', 'sir', 'madam',
            'attn', 'attention', 'fao', 'notify', 'inform', 'cc', 'bcc',
            'call', 'email', 'message', 'reach', 'meet', 'see', 'ask',
            'the', 'a', 'an', 'this', 'that', 'my', 'our', 'your',
            # v2.13.0: IT/tech terms
            'barcode', 'tag', 'id', 'code', 'serial', 'asset', 'device',
        }
        
        # v2.13.0: Single-word false positives that look like names
        # v2.15.0: Expanded with software, products, and location terms
        false_positive_singles = {
            'tag', 'barcode', 'scanner', 'serial', 'code', 'asset',
            'zscaler', 'intune', 'avaya', 'cisco', 'duo', 'okta',
            # v2.15.0: Software/tools
            'git', 'putty', 'jupyter', 'postman', 'winscp', 'maven', 'tomcat',
            'eclipse', 'intellij', 'vscode', 'node', 'mongodb', 'python', 'java',
            # v2.15.0: Microsoft/IT products
            'teams', 'azure', 'outlook', 'excel', 'qualys', 'vdi', 'citrix', 'sap',
            # v2.15.0: Locations
            'india', 'hungary', 'bangalore', 'hyderabad', 'chennai', 'mumbai',
            # v2.15.0: Work terms
            'home', 'associates', 'recruiter', 'linkedin', 'genai', 'ultimatix',
        }
        
        # v2.15.1: Location suffixes - if last word is one of these, it's a place name not a person
        location_suffixes = {
            'park', 'tower', 'towers', 'building', 'buildings', 'plaza', 'center', 'centre',
            'complex', 'campus', 'office', 'offices', 'odc', 'dc', 'hub', 'court', 'courts',
            'heights', 'gardens', 'garden', 'apartments', 'apartment', 'apt', 'residency',
            'mall', 'street', 'road', 'avenue', 'lane', 'drive', 'way', 'blvd', 'boulevard',
            'square', 'circle', 'place', 'floor', 'wing', 'block', 'phase', 'sector',
            'colony', 'nagar', 'vihar', 'enclave', 'layout', 'extension', 'extn', 'east',
            'west', 'north', 'south', 'city', 'town', 'village', 'district', 'area', 'zone',
        }

        name_pattern = self._name_pattern_re

        for match in name_pattern.finditer(text):
            potential_name = match.group(1)
            parts = potential_name.split()
            
            start_offset = 0
            while parts and parts[0].lower() in non_name_prefixes:
                start_offset += len(parts[0]) + 1
                parts.pop(0)
            
            if len(parts) < 2:
                continue
            
            # v2.15.1: Skip if last word is a location suffix (e.g., "Garima Park", "Delta Tower")
            if parts[-1].lower() in location_suffixes:
                continue
            
            parts_lower = [p.lower() for p in parts]
            if any(part in self._all_names for part in parts_lower):
                actual_start = match.start() + start_offset
                actual_end = match.end()
                positions.append((actual_start, actual_end, self._get_token("NAME")))

        caps_pattern = self._caps_name_re
        for match in caps_pattern.finditer(text):
            potential_name = match.group(1)
            parts = potential_name.lower().split()
            if any(part in self._all_names for part in parts) and len(parts) >= 2:
                positions.append((match.start(), match.end(), self._get_token("NAME")))

        # v2.20: Single-word known name after strong context prefix (conservative)
        for match in self._single_name_prefix_re.finditer(text):
            name = match.group(2).lower()
            if name in self._all_names and name not in false_positive_singles:
                positions.append((match.start(2), match.end(2), self._get_token("NAME")))

        return positions

    # =========================================================================
    # IT/ITSM SPECIFIC REDACTION METHODS (v2.6)
    # =========================================================================

    def _redact_ticket_ids(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact ITSM ticket identifiers."""
        positions = []
        
        for match in self.patterns.SERVICENOW_TICKET.finditer(text):
            ticket = match.group(0)
            num_start = 0
            for i, c in enumerate(ticket):
                if c.isdigit():
                    num_start = i
                    break
            actual_start = match.start() + num_start
            positions.append((actual_start, match.end(), self._get_token("TICKET_NUM")))
        
        positions.extend(self._find_pattern_matches(text, self.patterns.JIRA_TICKET, "TICKET"))
        
        for match in self.patterns.TICKET_LABELED.finditer(text):
            if match.group(1):
                ticket_num = match.group(1)
                try:
                    num_start = match.start() + match.group(0).index(ticket_num)
                    positions.append((num_start, num_start + len(ticket_num), self._get_token("TICKET_NUM")))
                except ValueError:
                    positions.append((match.start(1), match.end(1), self._get_token("TICKET_NUM")))
        
        # RFC patterns (original and v2.13.0 enhanced)
        positions.extend(self._find_pattern_matches(text, self.patterns.RFC_NUMBER, "RFC"))
        positions.extend(self._find_pattern_matches(text, self.patterns.RFC_NUMBER_SIMPLE, "RFC"))
        
        # v2.13.0: Contextual RFC patterns
        for pattern in [self.patterns.RFC_CONTEXTUAL, self.patterns.RFC_NUM_LABELED]:
            for match in pattern.finditer(text):
                if match.group(1):
                    positions.append((match.start(1), match.end(1), self._get_token("RFC")))
        
        # v2.13.0: Standalone RFC in install/deploy context
        for match in self.patterns.RFC_STANDALONE_CONTEXT.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("RFC")))
        
        # v2.13.0: Number-prefix format (2743428-Zscaler) - mark as RFC
        for match in self.patterns.RFC_PREFIX_FORMAT.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("RFC")))
        
        positions.extend(self._find_pattern_matches(text, self.patterns.CR_NUMBER, "CR"))
        positions.extend(self._find_pattern_matches(text, self.patterns.ARIBA_PR, "PR"))
        positions.extend(self._find_pattern_matches(text, self.patterns.TICKET_EXTENDED, "TICKET_NUM"))
        
        # v2.13.0: CS ticket patterns
        for pattern in [self.patterns.CS_TICKET_LABELED, self.patterns.TICKET_NUMBER_LABELED]:
            for match in pattern.finditer(text):
                if match.group(1):
                    positions.append((match.start(1), match.end(1), self._get_token("TICKET_NUM")))
        
        return positions

    def _redact_active_directory(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact Active Directory / LDAP identifiers."""
        positions = []
        
        for match in self.patterns.LDAP_DN.finditer(text):
            dn = match.group(0)
            for cn_match in self._cn_pattern_re.finditer(dn):
                cn_value = cn_match.group(1)
                actual_start = match.start() + cn_match.start() + 3
                actual_end = actual_start + len(cn_value)
                positions.append((actual_start, actual_end, self._get_token("AD_NAME")))
        
        for match in self.patterns.SAM_ACCOUNT.finditer(text):
            sam = match.group(0)
            if '\\' in sam:
                username_start = sam.index('\\') + 1
                actual_start = match.start() + username_start
                positions.append((actual_start, match.end(), self._get_token("AD_USER")))
        
        positions.extend(self._find_pattern_matches(text, self.patterns.WINDOWS_SID, "SID"))
        positions.extend(self._find_pattern_matches(text, self.patterns.AD_UPN, "AD_UPN"))
        positions.extend(self._find_pattern_matches(text, self.patterns.SERVICE_ACCOUNT_PREFIXED, "SERVICE_ACCT"))
        positions.extend(self._find_pattern_matches(text, self.patterns.SERVICE_ACCOUNT_NT, "SERVICE_ACCT"))
        positions.extend(self._find_pattern_matches(text, self.patterns.SERVICE_ACCOUNT_GENERIC, "SERVICE_ACCT"))
        
        return positions

    def _redact_remote_access_ids(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact remote access tool identifiers."""
        positions = []
        
        for match in self.patterns.TEAMVIEWER_ID.finditer(text):
            if match.group(1):
                try:
                    id_value = match.group(1)
                    id_start = match.start() + match.group(0).index(id_value)
                    positions.append((id_start, id_start + len(id_value), self._get_token("REMOTE_ID")))
                except ValueError:
                    positions.append((match.start(1), match.end(1), self._get_token("REMOTE_ID")))
        
        for match in self.patterns.ANYDESK_ID.finditer(text):
            if match.group(1):
                try:
                    id_value = match.group(1)
                    id_start = match.start() + match.group(0).index(id_value)
                    positions.append((id_start, id_start + len(id_value), self._get_token("REMOTE_ID")))
                except ValueError:
                    positions.append((match.start(1), match.end(1), self._get_token("REMOTE_ID")))
        
        for match in self.patterns.REMOTE_ID_LABELED.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("REMOTE_ID")))
        
        return positions

    def _redact_database_strings(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact database connection strings."""
        positions = []
        positions.extend(self._find_pattern_matches(text, self.patterns.DB_CONNECTION_STRING, "DB_CONNECTION"))
        positions.extend(self._find_pattern_matches(text, self.patterns.MONGODB_URI, "DB_URI"))
        for match in self.patterns.DB_CREDENTIALS.finditer(text):
            positions.append((match.start(), match.end(), self._get_token("DB_CREDS")))
        return positions

    def _redact_session_tokens(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact session identifiers and auth tokens."""
        positions = []
        for match in self.patterns.SESSION_ID.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("SESSION_ID")))
        positions.extend(self._find_pattern_matches(text, self.patterns.JWT_TOKEN, "JWT_TOKEN"))
        for match in self.patterns.OAUTH_TOKEN.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("AUTH_TOKEN")))
        positions.extend(self._find_pattern_matches(text, self.patterns.COOKIE_SESSION, "SESSION_COOKIE"))
        return positions

    def _redact_encryption_keys(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact encryption and recovery keys."""
        positions = []
        positions.extend(self._find_pattern_matches(text, self.patterns.BITLOCKER_KEY, "RECOVERY_KEY"))
        for match in self.patterns.RECOVERY_KEY.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("RECOVERY_KEY")))
        for match in self.patterns.CERT_THUMBPRINT.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("CERT_HASH")))
        for match in self.patterns.CERT_SERIAL.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("CERT_SERIAL")))
        return positions

    def _redact_workplace_info(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact workplace/physical location identifiers."""
        positions = []
        positions.extend(self._find_pattern_matches(text, self.patterns.LOCATION_WING_ID, "LOCATION"))
        positions.extend(self._find_pattern_matches(text, self.patterns.SEAT_EXTENDED, "SEAT"))
        # v2.13.0: Enhanced seat/location patterns
        positions.extend(self._find_pattern_matches(text, self.patterns.SEAT_AT_LOCATION, "LOCATION"))
        positions.extend(self._find_pattern_matches(text, self.patterns.SEAT_NUMBER_LABELED, "SEAT"))
        # v2.16.0: Underscore-based location identifiers (SP2_9F_ODC8, IND_DEL_YAM_T5)
        positions.extend(self._find_pattern_matches(text, self.patterns.LOCATION_UNDERSCORE_ODC, "LOCATION"))
        positions.extend(self._find_pattern_matches(text, self.patterns.LOCATION_UNDERSCORE_TOWER, "LOCATION"))
        positions.extend(self._find_pattern_matches(text, self.patterns.LOCATION_FLOOR_PATTERN, "LOCATION"))
        for match in self.patterns.ORG_SEAT_PATTERN.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("SEAT")))
        for match in self.patterns.DESK_LOCATION.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("DESK_NUM")))
        for match in self.patterns.FLOOR_LOCATION.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("LOCATION_NUM")))
        for match in self.patterns.BADGE_NUMBER.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("BADGE_NUM")))
        for match in self.patterns.PHONE_EXTENSION.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("EXT")))
        for match in self.patterns.DID_NUMBER.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("DID")))
        positions.extend(self._find_pattern_matches(text, self.patterns.INTERNAL_DOMAIN, "DOMAIN"))
        return positions

    def _redact_chat_handles(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact chat/collaboration platform handles."""
        positions = []
        skip_words = {'team', 'channel', 'here', 'everyone', 'all', 'group'}
        for match in self.patterns.CHAT_MENTION.finditer(text):
            if match.group(1):
                username = match.group(1).lower()
                if username not in skip_words:
                    positions.append((match.start(1), match.end(1), self._get_token("CHAT_USER")))
        for match in self.patterns.CHAT_DM.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("CHAT_USER")))
        return positions

    def _redact_cloud_ids(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact cloud platform identifiers."""
        positions = []
        for match in self.patterns.AZURE_SUBSCRIPTION.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("AZURE_SUB")))
        positions.extend(self._find_pattern_matches(text, self.patterns.AZURE_RESOURCE_ID, "AZURE_RESOURCE"))
        for match in self.patterns.AWS_ACCOUNT_ID.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("AWS_ACCOUNT")))
        positions.extend(self._find_pattern_matches(text, self.patterns.AWS_ARN, "AWS_ARN"))
        for match in self.patterns.GCP_PROJECT.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("GCP_PROJECT")))
        return positions

    def _redact_license_keys(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact software license and product keys."""
        positions = []
        positions.extend(self._find_pattern_matches(text, self.patterns.LICENSE_KEY, "LICENSE_KEY"))
        for match in self.patterns.PRODUCT_KEY.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("LICENSE_KEY")))
        for match in self.patterns.CMDB_CI.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("CI_ID")))
        return positions

    def _redact_audit_info(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact audit log user references."""
        positions = []
        for match in self.patterns.AUDIT_USER_ACTION.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("AUDIT_USER")))
        for match in self.patterns.LOGIN_EVENT.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("LOGIN_USER")))
        return positions

    # =========================================================================
    # v2.13.0: NEW PI DETECTION METHODS
    # =========================================================================

    def _redact_rfid_tags(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact RFID/EPC tag identifiers."""
        positions = []
        # RFID EPC tags: 24-character hex strings
        positions.extend(self._find_pattern_matches(text, self.patterns.RFID_EPC_TAG, "RFID_TAG"))
        # Labeled RFID: "barcode Tag(E28038212000682301AB8A76)"
        for match in self.patterns.RFID_LABELED.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("RFID_TAG")))
        return positions

    def _redact_security_incidents(self, text: str) -> List[Tuple[int, int, str]]:
        """Detect and redact security incident identifiers."""
        positions = []
        # Security incident IDs: ES319725
        positions.extend(self._find_pattern_matches(text, self.patterns.SECURITY_INCIDENT, "INCIDENT_ID"))
        # Labeled security incidents
        for match in self.patterns.SECURITY_INCIDENT_LABELED.finditer(text):
            if match.group(1):
                positions.append((match.start(1), match.end(1), self._get_token("INCIDENT_ID")))
        return positions

    def _redact_signature_block(self, text: str) -> Tuple[str, bool]:
        """Remove or redact signature blocks."""
        sig_start = self._detect_signature_block(text)
        if sig_start is not None:
            return text[:sig_start] + " " + self._get_token("SIGNATURE"), True
        return text, False

    # =========================================================================
    # MAIN REDACTION API
    # =========================================================================

    def redact(self, text: str, clean_first: Optional[bool] = None) -> str:
        """
        Main redaction method. Applies all enabled detection methods.

        Args:
            text: Input text to redact
            clean_first: Override config to run data cleaning

        Returns:
            Redacted text with PI replaced by tokens
        """
        if not isinstance(text, str) or not text.strip():
            return text

        should_clean = clean_first if clean_first is not None else self.config.enable_data_cleaning
        if should_clean:
            cleaning_options = {
                'normalize_unicode': self.config.clean_normalize_unicode,
                'decode_html': self.config.clean_decode_html,
                'normalize_whitespace': self.config.clean_normalize_whitespace,
                'strip_control_chars': self.config.clean_strip_control_chars,
            }
            text = DataCleaner.clean(text, cleaning_options)

        all_positions = []

        # Optimized redaction priority layers:
        # 1. Credentials first (immediate exposure risk)
        # 2. Compound structures (URL/Email) before their components
        # 3. High-specificity patterns before generic ones
        # 4. Context-dependent (names) last to preserve surrounding text

        if self.config.enable_regex:
            # LAYER 0: CRITICAL SECRETS (Highest Priority)
            # Passwords, API keys, tokens - immediate irreversible damage if exposed
            if self.config.redact_credentials:
                all_positions.extend(self._redact_credentials(text))
            if self.config.redact_encryption_keys:
                all_positions.extend(self._redact_encryption_keys(text))
            if self.config.redact_license_keys:
                all_positions.extend(self._redact_license_keys(text))
            if self.config.redact_session_tokens:
                all_positions.extend(self._redact_session_tokens(text))

            # -----------------------------------------------------------------
            # LAYER 1: COMPOUND STRUCTURES (Contain Multiple PI Types)
            # Reason: Database strings contain credentials + hostnames + IPs.
            # Must process these as units before breaking into components.
            # -----------------------------------------------------------------
            if self.config.redact_database_strings:
                all_positions.extend(self._redact_database_strings(text))

            # -----------------------------------------------------------------
            # LAYER 2: URLS (Compound - Contain Multiple PI)
            # Reason: URLs may contain hostnames, IPs, ports, credentials,
            # employee IDs in paths. Process as whole units first.
            # -----------------------------------------------------------------
            if self.config.redact_urls:
                all_positions.extend(self._redact_urls(text))

            # -----------------------------------------------------------------
            # LAYER 3: EMAILS (May Contain Employee IDs)
            # Reason: UPN emails like 1234567@tcs.com or ad.1234567@tcs.com
            # contain employee IDs. Our enhanced _redact_emails extracts these.
            # Must run before standalone employee ID detection.
            # -----------------------------------------------------------------
            if self.config.redact_emails:
                all_positions.extend(self._redact_emails(text))

            # -----------------------------------------------------------------
            # LAYER 4: GOVERNMENT/NATIONAL IDs (Very High Specificity)
            # Reason: Aadhaar (12-digit), PAN (XXXXX0000X), SSN have very
            # specific formats with low false positive rates. Safe to run early.
            # -----------------------------------------------------------------
            if self.config.redact_government_ids:
                all_positions.extend(self._redact_government_ids(text))

            # -----------------------------------------------------------------
            # LAYER 5: PHONE NUMBERS (High Specificity)
            # Reason: Phone formats are distinctive (+91, area codes, etc.)
            # Must run before generic number detection to prevent overlap.
            # -----------------------------------------------------------------
            if self.config.redact_phones:
                all_positions.extend(self._redact_phones(text))

            # -----------------------------------------------------------------
            # LAYER 6: EMPLOYEE IDs (Context-Aware)
            # Reason: 4-7 digit IDs require context scoring. Email-based IDs
            # already captured in Layer 3. This handles labeled/contextual IDs.
            # -----------------------------------------------------------------
            if self.config.redact_emp_ids:
                all_positions.extend(self._redact_emp_ids(text))

            # -----------------------------------------------------------------
            # LAYER 7: ASSET IDs & RFID TAGS
            # Reason: Asset tags have specific prefixes (ASSET-, INV-, etc.)
            # RFID tags have distinctive formats. Medium specificity.
            # -----------------------------------------------------------------
            if self.config.redact_asset_ids:
                all_positions.extend(self._redact_asset_ids(text))
                all_positions.extend(self._redact_rfid_tags(text))

            # -----------------------------------------------------------------
            # LAYER 8: NETWORK IDENTIFIERS (IPs, MACs)
            # Reason: IP addresses can overlap with version numbers (1.2.3.4).
            # Must run after phone/government IDs which have more specific formats.
            # -----------------------------------------------------------------
            if self.config.redact_ip_addresses:
                all_positions.extend(self._redact_ip_addresses(text))

            # -----------------------------------------------------------------
            # LAYER 9: HOSTNAMES
            # Reason: Hostnames may contain employee IDs (already redacted in L6).
            # Running after employee IDs prevents double-detection.
            # -----------------------------------------------------------------
            if self.config.redact_hostnames:
                all_positions.extend(self._redact_hostnames(text))

            # -----------------------------------------------------------------
            # LAYER 10: IT/ITSM IDENTIFIERS
            # Reason: Ticket IDs, cloud IDs, remote access IDs have specific
            # prefixes and formats. Medium-low priority as they're less sensitive.
            # -----------------------------------------------------------------
            if self.config.redact_ticket_ids:
                all_positions.extend(self._redact_ticket_ids(text))
                all_positions.extend(self._redact_security_incidents(text))
            if self.config.redact_remote_access_ids:
                all_positions.extend(self._redact_remote_access_ids(text))
            if self.config.redact_cloud_ids:
                all_positions.extend(self._redact_cloud_ids(text))

            # -----------------------------------------------------------------
            # LAYER 11: PAYMENT & FINANCIAL
            # Reason: Banking info, UPI IDs, credit cards, EPF/UAN, insurance.
            # Run after government IDs (Aadhaar 12-digit may overlap with
            # bank account numbers). Distinctive formats, low false positives.
            # -----------------------------------------------------------------
            all_positions.extend(self._redact_upi_ids(text))
            if self.config.redact_banking:
                all_positions.extend(self._redact_banking(text))
            if self.config.redact_financial:
                all_positions.extend(self._redact_financial(text))
            if self.config.redact_dob:
                all_positions.extend(self._redact_dob(text))

            # -----------------------------------------------------------------
            # LAYER 12: ACTIVE DIRECTORY (Contains Names + Employee IDs)
            # Reason: AD entries like CN=John Doe,OU=Users contain names.
            # Run after employee IDs are marked to avoid double-processing.
            # -----------------------------------------------------------------
            if self.config.redact_active_directory:
                all_positions.extend(self._redact_active_directory(text))

            # -----------------------------------------------------------------
            # LAYER 13: PATHS & MISC STRUCTURED
            # Reason: Windows paths, workplace info are lower priority.
            # These have clear formats and won't conflict with names.
            # -----------------------------------------------------------------
            all_positions.extend(self._redact_windows_paths(text))
            if self.config.redact_workplace_info:
                all_positions.extend(self._redact_workplace_info(text))
            if self.config.redact_chat_handles:
                all_positions.extend(self._redact_chat_handles(text))
            if self.config.redact_audit_info:
                all_positions.extend(self._redact_audit_info(text))

        # =====================================================================
        # NAME DETECTION LAYERS (Run Last - Need Intact Context)
        # =====================================================================
        # Names are detected last because:
        #   1. They have highest false positive potential
        #   2. They need surrounding context for scoring (titles, keywords)
        #   3. Other PI types (emails, AD) may contain names we've already caught
        #   4. Dictionary matching is greedy - run after structured PI removed
        # =====================================================================

        # -----------------------------------------------------------------
        # LAYER 14: NER-BASED NAME DETECTION (ML - High Confidence)
        # Reason: NER models provide high-confidence entity detection.
        # Run first among name detectors as it's most accurate.
        # -----------------------------------------------------------------
        if self.config.enable_ner and self.config.redact_names:
            all_positions.extend(self._redact_names_ner(text))

        # -----------------------------------------------------------------
        # LAYER 15: PATTERN-BASED NAMES (Titles: Mr./Ms./Dr.)
        # Reason: Title patterns like "Mr. John Smith" are high confidence.
        # The title provides strong context for name detection.
        # -----------------------------------------------------------------
        if self.config.enable_regex and self.config.redact_names:
            all_positions.extend(self._redact_names_pattern(text))

        # -----------------------------------------------------------------
        # LAYER 16: CONTEXTUAL NAME DETECTION (Keyword-Based)
        # Reason: Patterns like "assigned to John", "contact: Smith" use
        # surrounding keywords. Requires intact context text.
        # -----------------------------------------------------------------
        if self.config.enable_context_rules and self.config.redact_names:
            all_positions.extend(self._redact_names_contextual(text))

        # -----------------------------------------------------------------
        # LAYER 17: EMAIL-TO-NAME CORRELATION
        # Reason: Extract names from email local parts (john.smith@).
        # Run after emails are detected to correlate with redactions.
        # -----------------------------------------------------------------
        if self.config.enable_regex and self.config.redact_names:
            all_positions.extend(self._redact_names_from_email(text))

        # -----------------------------------------------------------------
        # LAYER 18: DICTIONARY-BASED NAMES (Lowest Priority)
        # Reason: Dictionary matching is most prone to false positives.
        # Common words that are also names (Bill, Mark, Will) need context.
        # Run last after other detection methods have marked clear cases.
        # -----------------------------------------------------------------
        if self.config.enable_dictionaries and self.config.redact_names:
            all_positions.extend(self._redact_names_dictionary(text))

        try:
            all_positions = self._remove_overlaps(all_positions)
            result = self._redact_by_positions(text, all_positions)

            # v2.14.0: Post-processing cleanup for partial redactions
            # Catches residual PI after initial redaction (e.g., "[EMP_ID] #2919414")
            result = self._cleanup_partial_redactions(result)

            if self.config.enable_context_rules:
                result, _ = self._redact_signature_block(result)

            result = re.sub(r'\s{2,}', ' ', result).strip()
            return result
        except Exception as e:
            logger.warning(f"Final redaction processing failed: {type(e).__name__}: {e}")
            return text

    def redact_with_details(self, text: str, clean_first: Optional[bool] = None) -> RedactionResult:
        """Redact text and return detailed information about all redactions."""
        start_time = time.perf_counter()

        if not isinstance(text, str) or not text.strip():
            return RedactionResult(
                redacted_text=text if isinstance(text, str) else "",
                redactions=[],
                processing_time_ms=0.0,
                original_length=len(text) if isinstance(text, str) else 0,
                redacted_count=0
            )

        original_text = text
        original_length = len(text)

        should_clean = clean_first if clean_first is not None else self.config.enable_data_cleaning
        if should_clean:
            cleaning_options = {
                'normalize_unicode': self.config.clean_normalize_unicode,
                'decode_html': self.config.clean_decode_html,
                'normalize_whitespace': self.config.clean_normalize_whitespace,
                'strip_control_chars': self.config.clean_strip_control_chars,
            }
            text = DataCleaner.clean(text, cleaning_options)

        all_positions = []

        def add_positions(positions: List[Tuple[int, int, str]], method: str, confidence: float = 1.0):
            for start, end, replacement in positions:
                pi_type = replacement.strip('[]') if replacement.startswith('[') else 'UNKNOWN'
                all_positions.append((start, end, replacement, pi_type, confidence, method))

        # Optimized redaction priority - same as redact() method
        if self.config.enable_regex:
            # LAYER 0: CRITICAL SECRETS (Highest Priority)
            if self.config.redact_credentials:
                add_positions(self._redact_credentials(text), "regex_critical", 1.0)
            if self.config.redact_encryption_keys:
                add_positions(self._redact_encryption_keys(text), "regex_critical", 1.0)
            if self.config.redact_license_keys:
                add_positions(self._redact_license_keys(text), "regex_critical", 0.95)
            if self.config.redact_session_tokens:
                add_positions(self._redact_session_tokens(text), "regex_critical", 1.0)

            # LAYER 1: COMPOUND STRUCTURES
            if self.config.redact_database_strings:
                add_positions(self._redact_database_strings(text), "regex_compound", 1.0)

            # LAYER 2: URLS
            if self.config.redact_urls:
                add_positions(self._redact_urls(text), "regex", 1.0)

            # LAYER 3: EMAILS (with UPN employee ID handling)
            if self.config.redact_emails:
                add_positions(self._redact_emails(text), "regex", 1.0)

            # LAYER 4: GOVERNMENT/NATIONAL IDs
            if self.config.redact_government_ids:
                add_positions(self._redact_government_ids(text), "regex_high_specificity", 1.0)

            # LAYER 5: PHONE NUMBERS
            if self.config.redact_phones:
                add_positions(self._redact_phones(text), "regex", 1.0)

            # LAYER 6: EMPLOYEE IDs
            if self.config.redact_emp_ids:
                add_positions(self._redact_emp_ids(text), "regex_context", 0.9)

            # LAYER 7: ASSET IDs & RFID
            if self.config.redact_asset_ids:
                add_positions(self._redact_asset_ids(text), "regex", 1.0)
                add_positions(self._redact_rfid_tags(text), "regex", 0.95)

            # LAYER 8: NETWORK (IPs, MACs)
            if self.config.redact_ip_addresses:
                add_positions(self._redact_ip_addresses(text), "regex", 1.0)

            # LAYER 9: HOSTNAMES
            if self.config.redact_hostnames:
                add_positions(self._redact_hostnames(text), "regex", 1.0)

            # LAYER 10: IT/ITSM IDENTIFIERS
            if self.config.redact_ticket_ids:
                add_positions(self._redact_ticket_ids(text), "itsm", 0.95)
                add_positions(self._redact_security_incidents(text), "itsm", 0.95)
            if self.config.redact_remote_access_ids:
                add_positions(self._redact_remote_access_ids(text), "remote_access", 0.90)
            if self.config.redact_cloud_ids:
                add_positions(self._redact_cloud_ids(text), "cloud", 0.95)

            # LAYER 11: PAYMENT & FINANCIAL
            add_positions(self._redact_upi_ids(text), "regex", 1.0)
            if self.config.redact_banking:
                add_positions(self._redact_banking(text), "regex", 1.0)
            if self.config.redact_financial:
                add_positions(self._redact_financial(text), "regex", 1.0)
            if self.config.redact_dob:
                add_positions(self._redact_dob(text), "regex", 0.9)

            # LAYER 12: ACTIVE DIRECTORY
            if self.config.redact_active_directory:
                add_positions(self._redact_active_directory(text), "active_directory", 0.95)

            # LAYER 13: PATHS & MISC
            add_positions(self._redact_windows_paths(text), "regex", 0.9)
            if self.config.redact_workplace_info:
                add_positions(self._redact_workplace_info(text), "workplace", 0.85)
            if self.config.redact_chat_handles:
                add_positions(self._redact_chat_handles(text), "chat", 0.80)
            if self.config.redact_audit_info:
                add_positions(self._redact_audit_info(text), "audit", 0.85)

        # NAME DETECTION LAYERS (Run Last - Need Intact Context)
        # LAYER 14: NER-BASED
        if self.config.enable_ner and self.config.redact_names:
            add_positions(self._redact_names_ner(text), "ner", 0.85)

        # LAYER 15: PATTERN-BASED (Titles)
        if self.config.enable_regex and self.config.redact_names:
            add_positions(self._redact_names_pattern(text), "pattern", 0.8)

        # LAYER 16: CONTEXTUAL
        if self.config.enable_context_rules and self.config.redact_names:
            add_positions(self._redact_names_contextual(text), "context", 0.95)

        # LAYER 17: EMAIL CORRELATION
        if self.config.enable_regex and self.config.redact_names:
            add_positions(self._redact_names_from_email(text), "email_correlation", 0.90)

        # LAYER 18: DICTIONARY (Lowest Priority)
        if self.config.enable_dictionaries and self.config.redact_names:
            add_positions(self._redact_names_dictionary(text), "dictionary", 0.75)

        simple_positions = [(s, e, r) for s, e, r, _, _, _ in all_positions]
        non_overlapping = self._remove_overlaps(simple_positions)

        position_map = {(s, e, r): (s, e, r, pt, c, m) for s, e, r, pt, c, m in all_positions}
        final_positions = []
        for pos in non_overlapping:
            if pos in position_map:
                final_positions.append(position_map[pos])
            else:
                final_positions.append((pos[0], pos[1], pos[2], pos[2].strip('[]'), 1.0, 'unknown'))

        redactions = []
        for start, end, replacement, pi_type, confidence, method in final_positions:
            redactions.append(Redaction(
                original=original_text[start:end] if start < len(original_text) and end <= len(original_text) else "",
                replacement=replacement,
                pi_type=pi_type,
                start=start,
                end=end,
                confidence=confidence,
                detection_method=method
            ))

        redacted_text = self._redact_by_positions(text, [(r.start, r.end, r.replacement) for r in redactions])

        # v2.14.0: Post-processing cleanup for partial redactions
        redacted_text = self._cleanup_partial_redactions(redacted_text)

        if self.config.enable_context_rules:
            redacted_text, sig_found = self._redact_signature_block(redacted_text)
            if sig_found:
                redactions.append(Redaction(
                    original="[signature block]",
                    replacement=self._get_token("SIGNATURE"),
                    pi_type="SIGNATURE",
                    start=-1,
                    end=-1,
                    confidence=0.95,
                    detection_method="context"
                ))

        redacted_text = re.sub(r'\s{2,}', ' ', redacted_text).strip()
        processing_time = (time.perf_counter() - start_time) * 1000

        return RedactionResult(
            redacted_text=redacted_text,
            redactions=redactions,
            processing_time_ms=round(processing_time, 3),
            original_length=original_length,
            redacted_count=len(redactions)
        )

    def redact_batch(self, texts: List[str], clean_first: Optional[bool] = None) -> List[str]:
        """Efficiently redact multiple texts."""
        return [self.redact(text, clean_first) for text in texts]

    def redact_batch_with_details(self, texts: List[str],
                                   clean_first: Optional[bool] = None) -> List[RedactionResult]:
        """Redact multiple texts with detailed information."""
        return [self.redact_with_details(text, clean_first) for text in texts]

    def health_check(self) -> Dict[str, Any]:
        """Return health status for API health endpoints."""
        return {
            "status": "healthy",
            "version": __version__,
            "mode": "full" if self.config.enable_ner else "fast",
            "ner_available": SPACY_AVAILABLE,
            "ner_loaded": self.ner._loaded if self.ner and hasattr(self.ner, '_loaded') else False,
            "ner_model": self.ner.model_name if self.ner and hasattr(self.ner, 'model_name') and self.ner._loaded else None,
            "patterns_loaded": True,
            "pattern_count": 30,
            "dictionary_size": len(self._all_names),
            "config": {
                "enable_ner": self.config.enable_ner,
                "enable_regex": self.config.enable_regex,
                "enable_dictionaries": self.config.enable_dictionaries,
                "enable_context_rules": self.config.enable_context_rules,
                "use_typed_tokens": self.config.use_typed_tokens,
            }
        }

    def get_supported_pi_types(self) -> List[Dict[str, str]]:
        """Return list of supported PI types."""
        return [
            {"type": "EMAIL", "token": "[EMAIL]", "description": "Email addresses"},
            {"type": "PHONE", "token": "[PHONE]", "description": "Phone numbers (all formats)"},
            {"type": "NAME", "token": "[NAME]", "description": "Personal names"},
            {"type": "EMP_ID", "token": "[EMP_ID]", "description": "Employee IDs (7-digit)"},
            {"type": "ASSET_ID", "token": "[ASSET_ID]", "description": "Asset IDs"},
            {"type": "IP", "token": "[IP]", "description": "IP addresses (v4 and v6)"},
            {"type": "MAC", "token": "[MAC]", "description": "MAC addresses"},
            {"type": "HOSTNAME", "token": "[HOSTNAME]", "description": "Server hostnames"},
            {"type": "URL", "token": "[URL]", "description": "URLs"},
            {"type": "CREDENTIAL", "token": "[CREDENTIAL]", "description": "Passwords and credentials"},
            {"type": "AADHAAR", "token": "[AADHAAR]", "description": "Indian Aadhaar numbers"},
            {"type": "PAN", "token": "[PAN]", "description": "Indian PAN card numbers"},
            {"type": "PASSPORT", "token": "[PASSPORT]", "description": "Passport numbers"},
            {"type": "UPI", "token": "[UPI]", "description": "UPI payment IDs"},
            {"type": "USERNAME", "token": "[USERNAME]", "description": "Windows usernames in paths"},
            {"type": "ORG", "token": "[ORG]", "description": "Organization names"},
            {"type": "LOCATION", "token": "[LOCATION]", "description": "Location/place names"},
            {"type": "SIGNATURE", "token": "[SIGNATURE]", "description": "Email signature blocks"},
        ]
