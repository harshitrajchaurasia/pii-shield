"""
PI Remover Patterns Module.

Contains all compiled regex patterns for Personal Information (PI) detection.
Patterns are organized by category:
- Email
- Phone (multiple countries/formats)
- Employee IDs
- Asset IDs
- Network (IP, MAC, Hostname)
- URLs
- Identity documents (Aadhaar, PAN, Passport, SSN, etc.)
- Banking (IFSC, IBAN, SWIFT, Account)
- Names (contextual, greeting, signature patterns)
- IT/ITSM (tickets, LDAP, remote access, sessions)
- Cloud (AWS, Azure, GCP)
- Security (passwords, keys, certificates)
- License keys
- Audit logs
- Organization-specific patterns

Usage:
    from pi_remover.patterns import PIPatterns

    if PIPatterns.EMAIL.search(text):
        print("Found email")
"""

import re
from typing import Set


class PIPatterns:
    """Compiled regex patterns for PI detection."""

    # =========================================================================
    # EMAIL PATTERNS
    # =========================================================================

    EMAIL = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        re.IGNORECASE
    )

    # =========================================================================
    # PHONE PATTERNS (Indian and International)
    # =========================================================================

    PHONE_91_DIRECT = re.compile(r'\+91\d{10}\b')  # +91XXXXXXXXXX (no spaces)
    PHONE_INDIAN = re.compile(
        r'\b(?:\+?91[\s.-]?)?[6-9]\d{9}\b'
    )
    PHONE_INDIAN_FORMATTED = re.compile(
        r'\b(?:\+?91[\s.-]?)?[6-9]\d[\s.-]?\d{4}[\s.-]?\d{4}\b'
    )
    # Phone with flexible spacing: +91 98765 43210 or +91 9 8765 43210
    PHONE_INDIAN_SPACED = re.compile(
        r'\+91\s+\d[\s\d]{9,12}(?=\s|$|[^\d])'
    )
    PHONE_LANDLINE = re.compile(
        r'\b0\d{2,4}[\s.-]?\d{6,8}\b'  # Landline: 0XX-XXXXXXXX
    )
    PHONE_INTL = re.compile(
        r'\b\+\d{1,3}[\s.-]?\d{4,14}\b'
    )

    # UK - multiple formats
    PHONE_UK = re.compile(
        r'\b\+?44[\s.-]?\d{4}[\s.-]?\d{6}\b'
    )
    PHONE_UK_DIRECT = re.compile(r'\+44\d{10}\b')  # +44XXXXXXXXXX (no spaces)
    PHONE_UK_FULL = re.compile(
        r'\b\+?44[\s.-]?\(?0?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{4}\b'
    )

    # US
    PHONE_US = re.compile(
        r'\b(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b'
    )

    # Toll-free
    PHONE_TOLLFREE = re.compile(
        r'\b1800[\s.-]?\d{3}[\s.-]?\d{4}\b'  # 1800-XXX-XXXX
    )
    PHONE_TOLLFREE_800 = re.compile(
        r'\b800[\s.-]?\d{3}[\s.-]?\d{4}\b'
    )

    # Australia (+61)
    PHONE_AU = re.compile(
        r'\b\+?61[\s.-]?\d{1,2}[\s.-]?\d{4}[\s.-]?\d{4}\b'
    )
    # Germany (+49)
    PHONE_DE = re.compile(
        r'\b\+?49[\s.-]?\(?0?\d{2,5}\)?[\s.-]?\d{4,10}\b'
    )
    # France (+33)
    PHONE_FR = re.compile(
        r'\b\+?33[\s.-]?\(?0?\)?[\s.-]?\d[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}[\s.-]?\d{2}\b'
    )
    # Singapore (+65)
    PHONE_SG = re.compile(
        r'\b\+?65[\s.-]?\d{4}[\s.-]?\d{4}\b'
    )
    # UAE (+971)
    PHONE_UAE = re.compile(
        r'\b\+?971[\s.-]?\d{1,2}[\s.-]?\d{3}[\s.-]?\d{4}\b'
    )
    # Brazil (+55)
    PHONE_BR = re.compile(
        r'\b\+?55[\s.-]?\d{2}[\s.-]?\d{4,5}[\s.-]?\d{4}\b'
    )
    # Japan (+81)
    PHONE_JP = re.compile(
        r'\b\+?81[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{4}\b'
    )
    # China (+86)
    PHONE_CN = re.compile(
        r'\b\+?86[\s.-]?\d{3}[\s.-]?\d{4}[\s.-]?\d{4}\b'
    )
    # Malaysia (+60) - mobile starts with 1, landline starts with 3/4/5/6/7/8/9
    # Formats: +60146846527, +60 14 684 6527, +60-14-6846527
    PHONE_MY = re.compile(
        r'\b\+?60[\s.-]?\d{1,2}[\s.-]?\d{3,4}[\s.-]?\d{4}\b'
    )
    # Mexico (+52) - mobile 10 digits, formats: +52 55 33682758, +52-55-3368-2758
    PHONE_MX = re.compile(
        r'\b\+?52[\s.-]?\d{2}[\s.-]?\d{4}[\s.-]?\d{4}\b'
    )
    # Mexico with spaces in area code: +52 55 33682758
    PHONE_MX_SPACED = re.compile(
        r'\+52\s+\d{2}\s+\d{8}\b'
    )
    # Brazilian phone format: (22)99902-5226
    PHONE_BR_MOBILE = re.compile(
        r'\(\d{2}\)\s*\d{4,5}-\d{4}\b'
    )

    # =========================================================================
    # EMPLOYEE ID PATTERNS (TCS specific)
    # =========================================================================

    EMP_ID_NUMERIC = re.compile(r'\b[12]\d{6}\b')  # 7-digit starting with 1 or 2
    # v2.14.0: Fixed to not consume hyphen-Name patterns (e.g., 2482545-Reshma)
    # Uses negative lookahead to stop at hyphen followed by uppercase (likely name)
    # v2.16.0: Extended to support 8-digit employee IDs
    EMP_ID_LABELED = re.compile(
        r'(?i)\b(?:emp(?:loyee)?[\s._-]*(?:id|no)?|eid|uid|user[\s._-]*id?)[\s:._-]*'
        r'(\d{4,8})(?!-[A-Z])\b'
    )
    # Prefixed accounts (ad., iada., cad., ws., pr., sa., oth., vo., da., di.)
    EMP_ID_PREFIXED = re.compile(
        r'(?i)\b(?:ad|iada|cad|ws|pr|sa|oth|vo|da|di)\.(?:[a-z0-9]{4,}|\d{4,})\b'
    )
    EMP_ID_IN_PARENS = re.compile(
        r'\((\d{6,7})\)'  # Name (1234567)
    )
    # Standalone 7-digit emp IDs (more aggressive)
    EMP_ID_STANDALONE = re.compile(r'\b[12]\d{6}\b')

    # Additional employee ID patterns
    EMP_ID_ADD_REMOVE = re.compile(r'(?i)\b(?:add|remove|adding|removing)\s+[12]\d{6}\b')
    EMP_ID_ASSIGN = re.compile(r'\b[12]\d{6}\s+assign\b', re.I)
    EMP_ID_ASSIGNED_TO = re.compile(r'(?i)assigned\s+to\s+[12]\d{6}\b')
    EMP_ID_ASSOCIATE = re.compile(r'(?i)\bassociate\s*\(\s*[12]\d{6}\b')
    EMP_ID_LDAP = re.compile(r'(?i)\bCN=[12]\d{6}\b')
    EMP_ID_HYPHEN = re.compile(r'(?i)(?:tcs|assign(?:ed)?(?:\s+to)?)\s*[-:]\s*[12]\d{6}\b')
    # v2.15.1: Exclude RFC, CR, PR from word-hyphen pattern to avoid conflicts
    EMP_ID_WORD_HYPHEN = re.compile(r'(?i)(?!(?:rfc|cr|pr)\s*-)([a-z]+)\s*-\s*[12]\d{6}\b')

    # Portuguese/Spanish patterns (Associado/Associada Name, XXXXXXX)
    EMP_ID_PORTUGUESE = re.compile(
        r'(?i)\b(?:associad[oa]|asociado)\s+[A-Za-z]+(?:\s+[A-Za-z]+){0,3},?\s*[12]\d{6}\b'
    )
    # "This is Name, XXXXXXX" pattern
    EMP_ID_THIS_IS = re.compile(
        r'(?i)this\s+is\s+[A-Za-z]+(?:\s+[A-Za-z]+){0,2},?\s*[12]\d{6}\b'
    )
    # Chinese/Japanese format with colon
    EMP_ID_CJK = re.compile(r'[\u4e00-\u9fff]+:\s*[12]\d{6}\b')

    # v2.13.0 / v2.16.0: Enhanced employee ID patterns for 6-8 digit IDs with explicit labels
    # "Emp ID - 351690", "Emp ID 445658", "emp id: 25648792"
    EMP_ID_LABELED_EXPLICIT = re.compile(
        r'(?i)\b(?:emp(?:loyee)?[\s._-]*(?:id|no|number)?|eid)[\s._:=-]+(\d{4,8})\b'
    )
    # "with Emp ID - 351690" or "Emp ID - 445658(Name)" - v2.16.0: 8-digit support
    EMP_ID_WITH_LABEL = re.compile(
        r'(?i)(?:with\s+)?emp(?:loyee)?[\s._-]*id[\s._:=-]+(\d{4,8})(?:\s*\([^)]+\))?'
    )
    # Emp ID after asset or in list context: "[ASSET_ID] 2888351" with tab/space - v2.16.0: 8-digit support
    EMP_ID_AFTER_ASSET = re.compile(
        r'(?:\[ASSET_ID\]|\[SERIAL\]|password)\s*[\t\s]+(\d{4,8})\b'
    )
    # 6-digit employee IDs (for non-TCS or short format)
    EMP_ID_6DIGIT = re.compile(r'\b[23456]\d{5}\b')
    
    # v2.13.1: Generic numeric patterns for context-aware detection (4-7 digits)
    EMP_ID_4DIGIT = re.compile(r'\b\d{4}\b')
    EMP_ID_5DIGIT = re.compile(r'\b\d{5}\b')
    EMP_ID_6DIGIT_ANY = re.compile(r'\b\d{6}\b')
    EMP_ID_7DIGIT_ANY = re.compile(r'\b\d{7}\b')
    
    # v2.16.0: 8-digit employee IDs (extended format)
    EMP_ID_8DIGIT = re.compile(r'\b[2]\d{7}\b')  # Starts with 2, 8 digits total
    
    # v2.13.1 / v2.16.0: User/ID labeled patterns (more flexible) - 8-digit support
    # "User 54321", "user id: 12345", "ID: 9876", "UID 25648792"
    EMP_ID_USER_LABELED = re.compile(
        r'(?i)\b(?:user[\s._-]*(?:id)?|uid|id)[\s._:=-]+(\d{4,8})\b'
    )
    
    # v2.13.1 / v2.16.0: UPN/Email-based employee ID patterns - 8-digit support
    # Numeric emp ID as email: 1234567@tcs.com, 25648792@tcsappsdev.com
    EMP_ID_UPN_NUMERIC = re.compile(
        r'\b(\d{4,8})@(?:tcs|tcsapps|tcsappsdev|tcscomprod|tata|tataconsultancy)(?:\.[a-z]+)*\.com\b',
        re.IGNORECASE
    )
    # Prefixed emp ID in UPN: ad.1234567@tcs.com, pr.25648792@domain.com
    EMP_ID_UPN_PREFIXED = re.compile(
        r'\b(?:ad|iada|cad|ws|pr|sa|oth|vo|da|di)\.(\d{4,8})@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        re.IGNORECASE
    )
    # General UPN with any prefix and numeric ID: prefix.1234567@domain.com
    EMP_ID_UPN_GENERAL = re.compile(
        r'\b[a-z]{1,5}\.(\d{4,8})@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        re.IGNORECASE
    )
    # Prefixed account in email format without @: ad.1234567, pr.25648792 (extend existing)
    EMP_ID_PREFIXED_EXTENDED = re.compile(
        r'(?i)\b(?:ad|iada|cad|ws|pr|sa|oth|vo|da|di)\.(\d{4,8})\b'
    )

    # =========================================================================
    # v2.14.0: ENHANCED EMPLOYEE ID PATTERNS (from production data analysis)
    # =========================================================================
    
    # --- TEAMS/CHAT FORMAT PATTERNS ---
    # Pattern: "teams#2531177", "teams #2531177", "ping teams#2482545"
    # Common in IT tickets when referencing Teams chat handles
    EMP_ID_TEAMS_HASH = re.compile(
        r'(?i)\bteams\s*#\s*(\d{5,7})\b'
    )
    
    # --- ACCOUNT OPERATION PATTERNS ---
    # Pattern: "unlock account 1290362", "enable account 2227052", "disable my account 54321"
    # Common in IT tickets for account unlock/enable/disable requests
    EMP_ID_ACCOUNT_OP = re.compile(
        r'(?i)(?:unlock|enable|disable|activate|deactivate|reset)\s+(?:my\s+)?(?:ad\s+)?account\s+(\d{5,7})\b'
    )
    
    # --- HYPHEN-NAME FORMAT PATTERNS ---
    # Pattern: "2482545-Reshma Chobe", "1234567-John Doe"
    # Employee ID followed by hyphen and proper name (exposes both ID and name)
    EMP_ID_HYPHEN_NAME = re.compile(
        r'\b(\d{6,7})-([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
    )
    
    # --- EMP # WITH SPACE FORMAT ---
    # Pattern: "Emp # 2893847", "Emp #2893847"
    # Extended pattern with space between Emp and #
    EMP_ID_EMP_HASH_SPACE = re.compile(
        r'(?i)\bemp\s*#\s*(\d{5,7})\b'
    )
    
    # --- PARTIAL REDACTION CLEANUP PATTERNS ---
    # These patterns detect residual IDs after initial redaction
    # Pattern: "[EMP_ID] #2919414" - Token followed by actual ID
    EMP_ID_AFTER_TOKEN = re.compile(
        r'\[(?:EMP_ID|NAME|EMAIL|PHONE)\]\s*[#:,\t\s]+(\d{5,7})\b'
    )
    
    # Pattern: "[EMP_ID]<tab>Name Lastname" - Token followed by name (tabular data)
    NAME_AFTER_TOKEN = re.compile(
        r'\[(?:EMP_ID|NAME|EMAIL)\]\s*[\t,;|]+\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?=\s*[,\t\n|]|\s*$)'
    )
    
    # --- PARTIAL EMAIL PATTERNS ---
    # Pattern: ".lastname@tcs.com", ".firstname@domain.com"
    # Orphaned email parts from partial cleanup
    EMAIL_PARTIAL_LASTNAME = re.compile(
        r'(?<![a-zA-Z0-9])\.[a-zA-Z]{2,20}@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b',
        re.IGNORECASE
    )

    # =========================================================================
    # ASSET ID PATTERNS (TCS format)
    # =========================================================================

    # Format: {CountryCode}{AssetType}{Numbers}
    # Country codes: 01, 02, 03, 07, 50, etc. (2 digits)
    # Asset types: HW/HWCL=Hardware, SW=Software, VD=VDI, VS=Virtual Server,
    #              AD=Admin, NL=Network Link, WH=Warehouse(?), AC=Request number
    ASSET_ID = re.compile(
        r'(?i)\b\d{2}(?:HWCL|HW|SW|VD|VS|AD|NL|WH|AC)\d{4,}\b'
    )
    # Extended patterns with typos (O instead of 0) and regional formats
    ASSET_ID_EXTENDED = re.compile(
        r'\b(?:[0O]\d{1}(?:HW|SW|VD|VS|AD|NL|WH|AC)\d{6,8}|'
        r'\d{2}(?:HW|SW|VD|VS)[A-Z]{2}\d{5,7})\b',
        re.IGNORECASE
    )

    # =========================================================================
    # NETWORK PATTERNS (IP, MAC, Hostname)
    # =========================================================================

    IPV4 = re.compile(
        r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?::\d{2,5})?\b'
    )
    IPV6 = re.compile(
        r'\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b'
    )
    MAC = re.compile(
        r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'
    )
    # Hostnames/Server names (pattern: XXYYSVRZZZZZZZZ)
    HOSTNAME = re.compile(
        r'\b[A-Z]{2}\d{2}[A-Z]{3}\d{8,}\b',
        re.IGNORECASE
    )

    # =========================================================================
    # URL PATTERNS
    # =========================================================================

    URL = re.compile(
        r'(?:https?|ftp)://[^\s<>"{}|\\^`\[\]]+',
        re.IGNORECASE
    )

    # =========================================================================
    # UPI / PAYMENT PATTERNS
    # =========================================================================

    UPI = re.compile(
        r'\b[a-zA-Z0-9._-]{2,}@(?:upi|paytm|gpay|phonepe|ybl|okhdfcbank|okaxis|oksbi|okicici|okboi|apl|axl|ibl|ikwik|freecharge|airtel|jio|mobikwik|amazonpay|slice)\b',
        re.IGNORECASE
    )

    # =========================================================================
    # WINDOWS / PATH PATTERNS
    # =========================================================================

    WIN_PATH = re.compile(
        r'(?i)[A-Z]:\\Users\\([^\\\s]+)'
    )

    # =========================================================================
    # IDENTITY DOCUMENT PATTERNS
    # =========================================================================

    # Aadhaar (12 digits)
    AADHAAR = re.compile(
        r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'
    )
    # PAN Card (case-insensitive)
    PAN = re.compile(
        r'\b[A-Z]{5}\d{4}[A-Z]\b',
        re.IGNORECASE
    )
    # Credit Card (basic pattern)
    CREDIT_CARD = re.compile(
        r'\b(?:\d{4}[\s-]?){3}\d{4}\b'
    )
    # Passport (Indian) - case-insensitive
    PASSPORT = re.compile(
        r'\b[A-Z]\d{7}\b',
        re.IGNORECASE
    )
    # US Social Security Number (SSN) - XXX-XX-XXXX (requires separator or context)
    SSN = re.compile(
        r'(?i)(?:(?:ssn|social\s*security)[\s.:_#-]*)?'
        r'\b(\d{3}[-]\d{2}[-]\d{4})\b'
    )
    # SSN with context keyword (allows no separator when keyword present)
    SSN_CONTEXTUAL = re.compile(
        r'(?i)(?:ssn|social\s*security\s*(?:no|number|#)?)[\s.:_#-]*(\d{9})\b'
    )
    # Driving License (Indian) - varies by state, case-insensitive
    DRIVING_LICENSE_IN = re.compile(
        r'\b[A-Z]{2}[\s-]?\d{2}[\s-]?\d{4}[\s-]?\d{7}\b',
        re.IGNORECASE
    )
    # Vehicle Registration (Indian) - requires context or strict format
    # Strict format: 2-letter state code + 2-digit district + 1-2 letter series + 4-digit number
    VEHICLE_REG_IN = re.compile(
        r'(?i)(?:(?:vehicle|registration|reg|number\s*plate|license\s*plate|car\s*no)[\s.:_#-]*)?'
        r'\b([A-Z]{2}\s?-?\d{2}\s?-?[A-Z]{1,3}\s?-?\d{4})\b'
    )
    # National Insurance Number (UK NIN) - case-insensitive
    NIN_UK = re.compile(
        r'\b[A-Z]{2}\d{6}[A-Z]\b',
        re.IGNORECASE
    )
    # Voter ID / EPIC (Indian) - 3 letters + 7 digits, requires context to avoid false positives
    VOTER_ID_IN = re.compile(
        r'(?i)(?:voter\s*(?:id|card)|epic|electoral)[\s.:_#-]*(?:no|number|#)?[\s.:_#-]*'
        r'([A-Z]{3}\d{7})\b'
    )
    # EPF Universal Account Number (UAN) - 12 digits with context
    EPF_UAN = re.compile(
        r'(?i)(?:uan|epf|pf)[\s.:_#-]*(?:no|number|#)?[\s.:_#-]*(\d{12})\b'
    )
    # EPF Member ID - STATE/OFFICE/ACCOUNT format
    EPF_MEMBER_ID = re.compile(
        r'\b[A-Z]{2}[\s/]?[A-Z]{3}[\s/]?\d{7}[\s/]?\d{3}[\s/]?\d{7}\b',
        re.IGNORECASE
    )

    # =========================================================================
    # BANKING PATTERNS
    # =========================================================================

    # Bank Account Number (Indian - 9 to 18 digits, requires context keyword)
    BANK_ACCOUNT_IN = re.compile(
        r'(?i)\b(?:a/?c|account|acct)[\s.:_-]*(?:no|number|num|#)?[\s.:_-]*(\d{9,18})\b'
    )
    # Bank Account with IFSC context (standalone long number near IFSC)
    BANK_ACCOUNT_STANDALONE = re.compile(
        r'\b(\d{9,18})\b'
    )
    # IFSC Code (Indian bank) - 4 letters + 0 + 6 alphanumeric
    IFSC = re.compile(
        r'\b[A-Z]{4}0[A-Z0-9]{6}\b',
        re.IGNORECASE
    )
    # IFSC with context keyword
    IFSC_CONTEXTUAL = re.compile(
        r'(?i)(?:ifsc)[\s.:_#-]*(?:code)?[\s.:_#-]*([A-Z]{4}0[A-Z0-9]{6})\b'
    )
    # IBAN (International Bank Account Number) - 2 letters + 2 digits + up to 30 alphanumeric
    IBAN = re.compile(
        r'\b[A-Z]{2}\d{2}\s?[A-Z0-9]{4}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b',
        re.IGNORECASE
    )
    # SWIFT/BIC Code - requires context keyword to avoid matching common English words
    # Format: 4 bank + 2 country + 2 location [+ 3 branch] (8 or 11 chars)
    SWIFT = re.compile(
        r'(?i)(?:swift|bic|swift\s*code|bic\s*code)[\s.:_#-]*([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b'
    )
    # Routing Number (US bank) - 9 digits with context
    ROUTING_NUMBER = re.compile(
        r'(?i)(?:routing|aba|transit)[\s.:_#-]*(?:no|number|num|#)?[\s.:_#-]*(\d{9})\b'
    )

    # =========================================================================
    # PASSWORD / CREDENTIAL PATTERNS
    # =========================================================================

    # Passwords in text - requires explicit assignment indicator
    # "is" must be followed by space/colon to avoid matching "issue", "isolation", etc.
    PASSWORD = re.compile(
        r'(?i)(?:password|pwd|pass)\s*(?:(?:is\s*[:\s])|[:\-=])\s*(\S+)',
    )

    # Non-credential words that follow "password" in descriptive contexts
    PASSWORD_NON_CREDENTIALS: Set[str] = {
        'reset', 'change', 'update', 'expired', 'expiry', 'expiration',
        'policy', 'policies', 'requirement', 'requirements', 'rules',
        'forgot', 'forgotten', 'recovery', 'recover', 'request', 'requested',
        'issue', 'issues', 'problem', 'problems', 'error', 'errors',
        'help', 'assistance', 'support', 'ticket', 'case',
        'manager', 'management', 'admin', 'administrator', 'portal',
        'protected', 'protection', 'security', 'secure', 'encryption',
        'length', 'strength', 'complexity', 'criteria', 'validation',
        'field', 'box', 'input', 'entry', 'prompt', 'dialog',
        'incorrect', 'invalid', 'wrong', 'mismatch', 'match',
        'new', 'old', 'current', 'previous', 'temporary', 'temp',
        'lock', 'locked', 'lockout', 'unlock', 'unlocked',
        'sync', 'synced', 'synchronization', 'hash', 'hashed',
    }

    # VPN/Remote connection credentials
    VPN_CREDS = re.compile(
        r'(?i)(?:vpn|remote)[\s._-]*(?:password|pwd|pass|user|username)[\s:_-]*(\S+)'
    )
    # API Key patterns
    API_KEY = re.compile(
        r'(?i)(?:api[_\s-]?key|access[_\s-]?token|bearer)[\s:_=-]*([A-Za-z0-9_\-]{20,})'
    )
    # SSH Private Key header
    SSH_KEY = re.compile(
        r'-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----'
    )
    # Domain ID pattern
    DOMAIN_ID = re.compile(
        r'(?i)\b(?:domain[\s._-]*id|user[\s._-]*id)[\s:._-]*(\d{6,7})\b'
    )

    # =========================================================================
    # NAME PATTERNS
    # =========================================================================

    # Name with title (title can be case-insensitive, but name must start with capital)
    # v2.8.3: Name part requires capital letter to avoid matching "dr drill", "ms teams"
    NAME_WITH_TITLE = re.compile(
        r'\b(?:[Mm][Rr]|[Mm][Ss]|[Mm][Rr][Ss]|[Dd][Rr]|[Ss][Hh][Rr][Ii]|[Ss][Mm][Tt]|[Ss][Rr][Ii])\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
    )

    # Labeled name patterns (case-insensitive)
    # v2.15.1: Exclude domain name, host name, server name, machine name, file name, folder name
    NAME_LABELED = re.compile(
        r'(?i)(?<!domain\s)(?<!host\s)(?<!server\s)(?<!machine\s)(?<!file\s)(?<!folder\s)(?<!computer\s)(?<!device\s)'
        r'\b(?:name|contact|user|employee|emp)[\s]*[:\-]\s*'
        r'([A-Za-z]+(?:\s+[A-Za-z]+){0,3})'
    )

    # "My name is X" pattern (case-insensitive)
    MY_NAME_IS = re.compile(
        r'(?i)\bmy name is\s+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})'
    )

    # =========================================================================
    # ENHANCED NAME DETECTION PATTERNS (v2.5)
    # =========================================================================

    # Contextual name patterns - names preceded by clear indicators (HIGH CONFIDENCE)
    # NOTE: Do NOT include standalone "to" - too many false positives
    NAME_CONTEXT_FROM_BY = re.compile(
        r'(?i)\b(?:from|by|cc|bcc|sent by|sent to|created by|assigned to|resolved by|'
        r'updated by|approved by|rejected by|forwarded by|forwarded to|replied by|'
        r'escalated to|transferred to|delegated to|reported by|submitted by|'
        r'delivered to|addressed to|directed to|email to|emailed to|message to)'
        r'[\s:]+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})'
    )

    # Greeting patterns - "Hi John", "Hello Priya", "Dear Rahul" (case-insensitive)
    NAME_GREETING = re.compile(
        r'(?i)\b(?:hi|hello|dear|hey|good\s*(?:morning|afternoon|evening))'
        r'[\s,]+([A-Za-z]+)(?:[\s,]|$)'
    )

    # Communication patterns - requires capital letter after action
    NAME_COMMUNICATION = re.compile(
        r'(?i)\b(?:spoke\s+(?:to|with)|contacted|emailed|messaged|'
        r'reached\s+out\s+to|got\s+in\s+touch\s+with|heard\s+from|response\s+from)'
        r'\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
        re.IGNORECASE
    )

    # IT Ticket patterns - caller, user, requestor, etc. (HIGH CONFIDENCE)
    NAME_TICKET_CALLER = re.compile(
        r'(?i)\b(?:caller|affected\s*user|end\s*user|requestor|requester|'
        r'raised\s*by|logged\s*by|opened\s*by|closed\s*by|'
        r'ticket\s*owner|incident\s*owner|case\s*owner)'
        r'[\s:]+([A-Za-z]+(?:\s+[A-Za-z]+){0,2})'
    )

    # "User X reported/raised/logged" pattern (case-insensitive)
    NAME_USER_ACTION = re.compile(
        r'(?i)\buser\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+'
        r'(?:reported|raised|logged|called|mentioned|confirmed|requested)'
    )

    # "X has reported/raised" pattern (case-insensitive)
    NAME_HAS_ACTION = re.compile(
        r'\b([A-Za-z]+(?:\s+[A-Za-z]+)?)\s+has\s+'
        r'(?:reported|raised|logged|called|requested|confirmed|approved)',
        re.IGNORECASE
    )

    # Name with parentheses - "Rahul Sharma (1234567)" or "John (IT Support)"
    NAME_WITH_PARENS = re.compile(
        r'\b([A-Za-z]+(?:\s+[A-Za-z]+){1,2})\s*\([^)]+\)',
        re.IGNORECASE
    )

    # Signature line patterns - "- Rahul" or "-- John Smith"
    NAME_SIGNATURE_LINE = re.compile(
        r'(?:^|\n)\s*[-–—]{1,2}\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)',
        re.MULTILINE | re.IGNORECASE
    )

    # v2.16.0: Name after signature closings - "Thanks, Krishna" or "Regards Ramesh"
    NAME_AFTER_SIGNATURE = re.compile(
        r'(?i)(?:thanks?|thank\s*you|regards?|best(?:\s*regards?)?|warm(?:\s*regards?)?|'
        r'sincerely|cheers)[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:[,\n]|$|[\[\(])',
    )

    # v2.13.0: Name in parentheses after employee ID
    # Catches: "445658(Dhanalakshmi)", "1234567(Rahul Kumar)"
    NAME_AFTER_EMP_ID = re.compile(
        r'\d{6,7}\(([A-Za-z][A-Za-z\s]{2,25})\)',
        re.IGNORECASE
    )

    # Signature block patterns
    SIGNATURE_START = re.compile(
        r'(?i)\b(?:thanks?(?:\s*(?:and|&)\s*regards?)?|'
        r'thank\s*you|regards?|best(?:\s*regards?)?|'
        r'warm(?:\s*regards?)?|sincerely|cheers)\b.*',
        re.DOTALL
    )

    # =========================================================================
    # DATE OF BIRTH PATTERNS
    # =========================================================================

    DOB = re.compile(
        r'(?i)\b(?:dob|date\s*of\s*birth|birth\s*date|born\s*(?:on)?)'
        r'[\s.:_-]*(?:is\s*)?'
        r'(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})\b'
    )
    # Age with context
    AGE = re.compile(
        r'(?i)\b(?:age)[\s.:_-]*(?:is\s*)?(\d{1,3})\s*(?:years?|yrs?|y/?o)?\b'
    )

    # =========================================================================
    # INSURANCE / FINANCIAL DOCUMENT PATTERNS (v2.19)
    # =========================================================================

    # Insurance policy number with context
    INSURANCE_POLICY = re.compile(
        r'(?i)(?:policy|insurance)[\s.:_#-]*(?:no|number|num|id|#)?[\s.:_#-]*'
        r'([A-Z0-9]{2,5}[-/]?[A-Z0-9]{5,15})\b'
    )

    # =========================================================================
    # IT/ITSM SPECIFIC PATTERNS (v2.6)
    # =========================================================================

    # --- ITSM TICKET IDENTIFIERS ---
    # ServiceNow ticket patterns (INC, RITM, REQ, CHG, PRB, TASK, SCTASK, KB)
    SERVICENOW_TICKET = re.compile(
        r'\b(?:INC|RITM|REQ|CHG|PRB|TASK|SCTASK|KB|STRY|CTASK)\d{7,10}\b',
        re.IGNORECASE
    )

    # JIRA ticket pattern (PROJECT-123) - case-insensitive
    JIRA_TICKET = re.compile(
        r'\b[A-Z]{2,10}-\d{1,6}\b',
        re.IGNORECASE
    )

    # Generic ticket patterns with labels (case-insensitive)
    # v2.16.0: Require at least one digit to avoid matching common words like "resolved", "raised"
    TICKET_LABELED = re.compile(
        r'(?i)\b(?:ticket|incident|request|case|issue|sr|service\s*request)'
        r'[\s#:_-]*(?:no|number|id)?[\s#:_-]*([A-Za-z]*\d{5,12})\b'
    )

    # "Ticket. No 104630759" format
    TICKET_EXTENDED = re.compile(
        r'\bTicket\.?\s*No\.?\s*:?\s*\d{8,12}\b',
        re.IGNORECASE
    )

    # --- ACTIVE DIRECTORY / LDAP PATTERNS ---
    # Distinguished Name (DN) - CN=John Smith,OU=Users,DC=company,DC=com
    LDAP_DN = re.compile(
        r'\b(?:CN|OU|DC|UID)=[^,\s]+(?:,\s*(?:CN|OU|DC|UID)=[^,\s]+)+',
        re.IGNORECASE
    )

    # SAMAccountName patterns (domain\username or username@domain)
    SAM_ACCOUNT = re.compile(
        r'\b[A-Za-z][A-Za-z0-9_-]{2,20}\\[A-Za-z][A-Za-z0-9._-]{2,30}\b'
    )

    # UPN (User Principal Name) - for AD internal domains
    AD_UPN = re.compile(
        r'\b[A-Za-z][A-Za-z0-9._-]+@[A-Za-z0-9-]+\.(?:local|internal|corp|ad|domain)\b',
        re.IGNORECASE
    )

    # SID (Security Identifier) - S-1-5-21-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx-xxxx
    WINDOWS_SID = re.compile(
        r'\bS-1-\d{1,2}(?:-\d+){1,14}\b'
    )

    # --- REMOTE ACCESS IDENTIFIERS ---
    # TeamViewer ID (9-10 digit, often with spaces: 123 456 789)
    TEAMVIEWER_ID = re.compile(
        r'(?i)(?:teamviewer|tv)[\s:_-]*(?:id)?[\s:_-]*(\d{3}[\s-]?\d{3}[\s-]?\d{3,4})\b'
    )

    # AnyDesk ID (9-digit or formatted)
    ANYDESK_ID = re.compile(
        r'(?i)(?:anydesk)[\s:_-]*(?:id)?[\s:_-]*(\d{3}[\s-]?\d{3}[\s-]?\d{3})\b'
    )

    # Generic Remote ID (when labeled)
    REMOTE_ID_LABELED = re.compile(
        r'(?i)(?:remote[\s_-]*(?:id|access)|rdp[\s_-]*(?:id)?|vnc[\s_-]*(?:id)?)'
        r'[\s:_-]*([A-Za-z0-9._-]{5,30})\b'
    )

    # --- DATABASE CONNECTION STRINGS ---
    # Connection string with credentials (SQL Server, MySQL, PostgreSQL, Oracle)
    DB_CONNECTION_STRING = re.compile(
        r'(?i)(?:connection\s*string|connstr|jdbc|odbc)[\s:=]*["\']?'
        r'[^"\']*(?:password|pwd|pass)\s*=\s*[^;"\'\s]+',
        re.IGNORECASE
    )

    # Database credentials in connection format
    DB_CREDENTIALS = re.compile(
        r'(?i)(?:(?:user(?:name)?|uid)\s*=\s*([^;"\'\s]+)\s*;.*?'
        r'(?:password|pwd|pass)\s*=\s*([^;"\'\s]+))',
        re.IGNORECASE
    )

    # MongoDB connection string
    MONGODB_URI = re.compile(
        r'mongodb(?:\+srv)?://[^:]+:[^@]+@[^\s]+',
        re.IGNORECASE
    )

    # --- SESSION/TOKEN IDENTIFIERS ---
    # Session IDs (JSESSIONID, PHPSESSID, ASP.NET_SessionId)
    SESSION_ID = re.compile(
        r'(?i)(?:jsessionid|phpsessid|asp\.net_sessionid|session[_-]?id|sid)'
        r'[\s:=]*([A-Za-z0-9_-]{16,64})\b'
    )

    # JWT Token (3 base64 parts separated by dots)
    JWT_TOKEN = re.compile(
        r'\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b'
    )

    # OAuth/Bearer tokens (when labeled)
    OAUTH_TOKEN = re.compile(
        r'(?i)(?:bearer|oauth|access[_-]?token|refresh[_-]?token|auth[_-]?token)'
        r'[\s:=]+([A-Za-z0-9_.-]{20,})\b'
    )

    # Cookie values with session data
    COOKIE_SESSION = re.compile(
        r'(?i)(?:cookie|set-cookie)[\s:]*[^;]*(?:session|auth|token|user)[^;]*=[^;\s]+',
        re.IGNORECASE
    )

    # --- ENCRYPTION/SECURITY KEYS ---
    # BitLocker Recovery Key (48 digits in 8 groups of 6)
    BITLOCKER_KEY = re.compile(
        r'\b\d{6}-\d{6}-\d{6}-\d{6}-\d{6}-\d{6}-\d{6}-\d{6}\b'
    )

    # Generic Recovery Key (labeled)
    RECOVERY_KEY = re.compile(
        r'(?i)(?:recovery|backup|restore)[\s_-]*key[\s:_-]*([A-Za-z0-9-]{10,})\b'
    )

    # Certificate Thumbprint/Fingerprint (40 hex chars for SHA1, 64 for SHA256)
    CERT_THUMBPRINT = re.compile(
        r'(?i)(?:thumbprint|fingerprint|sha1|sha256)[\s:_-]*([A-Fa-f0-9]{40,64})\b'
    )

    # Certificate Serial Number
    CERT_SERIAL = re.compile(
        r'(?i)(?:serial\s*(?:no|number)?)[\s:_-]*([A-Fa-f0-9]{8,40})\b'
    )

    # --- WORKPLACE/PHYSICAL LOCATION ---
    # Desk/Seat/Cubicle location (generic)
    DESK_LOCATION = re.compile(
        r'(?i)\b(?:desk|seat|cubicle|workstation|bay|pod)[\s#:_-]*([A-Z]?\d{1,4}[A-Z]?)\b'
    )

    # Organization-specific seat pattern: A1F 102, A5F-456, B2F102
    ORG_SEAT_PATTERN = re.compile(
        r'\b([A-Za-z]\d{1,2}[Ff][\s-]?\d{2,3})\b', re.IGNORECASE
    )

    # Floor/Building location with detail
    FLOOR_LOCATION = re.compile(
        r'(?i)\b(?:floor|flr|level|building|bldg|block|wing)[\s#:_-]*(\d{1,3}[A-Z]?)\s*'
        r'(?:,?\s*(?:desk|seat|cubicle)?[\s#:_-]*[A-Z]?\d{1,4}[A-Z]?)?\b'
    )

    # Badge/Access Card Number
    BADGE_NUMBER = re.compile(
        r'(?i)\b(?:badge|card|access\s*card|id\s*card|employee\s*card)[\s#:_-]*'
        r'(?:no|number|id)?[\s#:_-]*(\d{4,10})\b'
    )

    # --- INTERNAL PHONE/EXTENSION ---
    # Internal extension (3-5 digits)
    PHONE_EXTENSION = re.compile(
        r'(?i)\b(?:ext(?:ension)?|extn|x)[\s.:_-]*(\d{3,5})\b'
    )

    # DID (Direct Inward Dial)
    DID_NUMBER = re.compile(
        r'(?i)\b(?:did|direct\s*(?:dial|line))[\s:_-]*(\+?\d[\d\s-]{7,15})\b'
    )

    # --- CHAT/COLLABORATION HANDLES ---
    # Slack/Teams @mention handle
    CHAT_MENTION = re.compile(
        r'@([A-Za-z][A-Za-z0-9._-]{2,30})\b'
    )

    # Teams/Slack channel with potential user reference
    CHAT_DM = re.compile(
        r'(?i)(?:dm|direct\s*message|private\s*(?:chat|message))[\s:_-]*'
        r'(?:with|to|from)?[\s:_-]*([A-Za-z][A-Za-z0-9._\s-]{2,40})\b'
    )

    # --- CLOUD IDENTIFIERS ---
    # Azure Subscription ID (GUID format)
    AZURE_SUBSCRIPTION = re.compile(
        r'(?i)(?:subscription|sub)[\s:_-]*(?:id)?[\s:_-]*'
        r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})\b'
    )

    # Azure Resource ID
    AZURE_RESOURCE_ID = re.compile(
        r'/subscriptions/[a-f0-9-]{36}/resourceGroups/[^/]+/providers/[^\s]+',
        re.IGNORECASE
    )

    # AWS Account ID (12 digits)
    AWS_ACCOUNT_ID = re.compile(
        r'(?i)(?:aws|amazon)[\s_-]*(?:account)?[\s_-]*(?:id)?[\s:_-]*(\d{12})\b'
    )

    # AWS ARN (Amazon Resource Name)
    AWS_ARN = re.compile(
        r'\barn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}:[^\s]+\b',
        re.IGNORECASE
    )

    # GCP Project ID
    GCP_PROJECT = re.compile(
        r'(?i)(?:gcp|google\s*cloud)[\s_-]*(?:project)?[\s_-]*(?:id)?[\s:_-]*'
        r'([a-z][a-z0-9-]{4,28}[a-z0-9])\b'
    )

    # --- LICENSE KEYS ---
    # Software License Key (XXXXX-XXXXX-XXXXX-XXXXX format) - case-insensitive
    LICENSE_KEY = re.compile(
        r'\b[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}(?:-[A-Z0-9]{5})?\b',
        re.IGNORECASE
    )

    # Product Key (labeled) - case-insensitive
    PRODUCT_KEY = re.compile(
        r'(?i)(?:product|license|activation|serial)[\s_-]*key[\s:_-]*'
        r'([A-Za-z0-9]{5}(?:-[A-Za-z0-9]{5}){3,4})\b'
    )

    # --- CMDB/CONFIGURATION ITEMS ---
    # Generic CI ID (labeled to avoid false positives) - case-insensitive
    CMDB_CI = re.compile(
        r'(?i)\b(?:ci|config(?:uration)?\s*item|cmdb)[\s#:_-]*(?:id)?[\s#:_-]*'
        r'([A-Za-z]{2,4}\d{6,10})\b'
    )

    # Server/Host naming convention (environment-role-number)
    SERVER_NAME_PATTERN = re.compile(
        r'\b(?:PROD|DEV|UAT|QA|STG|TEST)[_-]?[A-Z]{2,8}[_-]?\d{2,4}\b',
        re.IGNORECASE
    )

    # --- AUDIT LOG PATTERNS ---
    # User activity log pattern
    AUDIT_USER_ACTION = re.compile(
        r'(?i)\b(?:user|account)\s+([A-Za-z][A-Za-z0-9._-]+)\s+'
        r'(?:logged\s*in|logged\s*out|signed\s*in|signed\s*out|'
        r'accessed|modified|deleted|created|updated)\b'
    )

    # Login/Logon events
    LOGIN_EVENT = re.compile(
        r'(?i)(?:login|logon|sign[\s-]*in|authentication)\s+'
        r'(?:for|by|from|as)\s+(?:user\s+)?([A-Za-z][A-Za-z0-9._@\\-]+)\b'
    )

    # =========================================================================
    # ORGANIZATION-SPECIFIC PI PATTERNS (v2.8.1)
    # =========================================================================

    # --- LOCATION/WING/SEAT IDENTIFIERS ---
    # Location/Wing ID patterns: TCB4/ODC1/WSN/100, GLAH/7/ODC5/WSN/42, etc.
    LOCATION_WING_ID = re.compile(
        r'\b[A-Z]{2,5}\d?/(?:\d/)?(?:ODC\d?|WING[-\w]*)/(?:WSN/)?\d+\b',
        re.IGNORECASE
    )

    # Additional seat number formats: S2-6F-Z03-056, 12F ODC 3
    SEAT_EXTENDED = re.compile(
        r'\b(?:S\d+-\d+F-Z\d+-\d+|\d{1,2}F\s+ODC\s+\d+)\b',
        re.IGNORECASE
    )

    # v2.13.0: Enhanced seat/location patterns
    # @SFC Z10, Seat No 20 - location with @ prefix
    SEAT_AT_LOCATION = re.compile(
        r'@[A-Z]{2,5}\s*[A-Z]?\d{1,3}(?:\s*,?\s*(?:Seat\s*(?:No\.?|Number)?\s*\d{1,4}))?',
        re.IGNORECASE
    )
    # "Seat No 20", "Seat Number 15", "seat no. 42"
    SEAT_NUMBER_LABELED = re.compile(
        r'\b(?:Seat|Desk|Cubicle|Bay|Pod)\s*(?:No\.?|Number|#)?\s*:?\s*\d{1,4}\b',
        re.IGNORECASE
    )

    # v2.16.0: Underscore-based location identifiers
    # Matches: SP2_9F_ODC8, IND_DEL_YAM_T5, BLR_EC1_3F_ODC2, etc.
    # Pattern: Site/Country_City/Building_Floor_ODC/Tower identifiers
    LOCATION_UNDERSCORE_ODC = re.compile(
        r'\b[A-Z]{2,4}\d?_(?:[A-Z0-9]{1,4}_)*(?:ODC\d*|[A-Z]?\d+F)(?:_[A-Z0-9]+)*\b',
        re.IGNORECASE
    )
    # IND_DEL_YAM_T5 pattern: Country_City_Building_Tower (with optional suffixes)
    # Also matches IND_DEL_YAM_T5_ALL_FLOOR, IND_DEL_YAM_T5_11_UPS, etc.
    LOCATION_UNDERSCORE_TOWER = re.compile(
        r'\b(?:IND|USA|UK|EUR|APAC|EMEA|BLR|CHN|HYD|MUM|PUN|DEL)_[A-Z]{2,5}_[A-Z]{2,5}_[A-Z]?\d+(?:_[A-Z0-9_]+)*\b',
        re.IGNORECASE
    )
    # General floor-based: XX_##F_XX pattern (e.g., SP2_9F_ODC8)
    LOCATION_FLOOR_PATTERN = re.compile(
        r'\b[A-Z]{2,4}\d?_\d{1,2}F_[A-Z0-9]+\b',
        re.IGNORECASE
    )

    # --- INTERNAL DOMAIN/NETWORK ---
    # Internal/regional domains: SOAM, NOAM, APAC, GLOBE, etc.
    # v2.15.0: Removed standalone India matching - too many false positives (16K+)
    # Only match India when followed by domain suffix (.tcs.com)
    INTERNAL_DOMAIN = re.compile(
        r'\b(?:India\.tcs\.com|(?:SOAM|NOAM|GLOBE|APAC|EMEA|LATAM|AMEA)(?:\.tcs\.com)?)\b',
        re.IGNORECASE
    )

    # --- FQDN (Fully Qualified Domain Name) PATTERNS (v2.15.1) ---
    # Matches server.company.com, mail.internal.corp, db01.prod.domain.local
    # Excludes emails (has @), URLs (has ://), and common words
    # Requires: hostname.domain.tld format with at least 2 dots
    FQDN = re.compile(
        r'(?<![@:/])\b(?!www\.)([a-zA-Z][a-zA-Z0-9-]{0,62}(?:\.[a-zA-Z][a-zA-Z0-9-]{0,62}){2,})\b(?![@])',
        re.IGNORECASE
    )
    
    # FQDN with internal/corporate TLDs: .local, .internal, .corp, .lan, .intra
    FQDN_INTERNAL = re.compile(
        r'\b([a-zA-Z][a-zA-Z0-9-]{0,62}(?:\.[a-zA-Z][a-zA-Z0-9-]{0,62})+\.(?:local|internal|corp|lan|intra|private|home))\b',
        re.IGNORECASE
    )
    
    # Labeled FQDN: "server: mail.company.com", "host: db01.prod.local"
    FQDN_LABELED = re.compile(
        r'(?i)(?:server|host|hostname|fqdn|machine|node)[\s:=-]+([a-zA-Z][a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
    )

    # --- RFC/CHANGE REQUEST PATTERNS ---
    # RFC numbers: RFC # 25224330, RFC No: 25228602, RFC-12345678, RFC:25224330, RFC - 1234567
    # v2.15.1: Updated to handle space before hyphen
    RFC_NUMBER = re.compile(
        r'\bRFC\s*(?:#|No[:\s.]*|\s*[-:]\s*)\d{7,10}\b',
        re.IGNORECASE
    )

    # v2.13.0: RFC with minimal prefix - "RFC 25655813" or just "RFC" then number
    RFC_NUMBER_SIMPLE = re.compile(
        r'\bRFC\s+\d{7,10}\b',
        re.IGNORECASE
    )

    # v2.13.0: RFC number in context - "as per RFC 25655813", "refer RFC number 25619353"
    RFC_CONTEXTUAL = re.compile(
        r'(?i)(?:as\s+per|refer(?:ence)?|see|per|for|regarding)\s+(?:RFC\s*(?:num(?:ber)?|no\.?)?|RFC)\s*:?\s*(\d{7,10})\b'
    )

    # v2.13.0: RFC number with "num" label - "RFC num 24926116"
    RFC_NUM_LABELED = re.compile(
        r'(?i)\bRFC\s+(?:num(?:ber)?|no\.?)\s*:?\s*(\d{7,10})\b'
    )

    # v2.13.0: Standalone 8-digit RFC-like numbers preceded by context words
    # Catches: "install avaya work space, 25648792" where context indicates RFC
    RFC_STANDALONE_CONTEXT = re.compile(
        r'(?i)(?:install|update|upgrade|configure|deploy|rollout|provision)[\w\s,]+,\s*(\d{7,8})\b'
    )

    # v2.13.0: Number-prefix format like "2743428-Zscaler" (ticket/RFC number as prefix)
    RFC_PREFIX_FORMAT = re.compile(
        r'\b(\d{7,8})-[A-Za-z][\w\s]+\b'
    )

    # Change Request numbers: CR # 12345678, CR-12345678
    CR_NUMBER = re.compile(
        r'\bCR\s*(?:#|No[:\s.]*|[-:])\s*\d{6,10}\b',
        re.IGNORECASE
    )

    # --- SERVICE ACCOUNT PATTERNS ---
    # Service accounts: sa.rpauser, oth.20873791, svc.appname
    SERVICE_ACCOUNT_PREFIXED = re.compile(
        r'\b(?:sa|svc|oth|srv|app)\.[a-zA-Z0-9._-]+\b',
        re.IGNORECASE
    )

    # NT-style service accounts: NT71853
    SERVICE_ACCOUNT_NT = re.compile(
        r'\bNT\d{4,8}\b',
        re.IGNORECASE
    )

    # Generic service account pattern with sa prefix: sa1234567, sa12345678abc
    SERVICE_ACCOUNT_GENERIC = re.compile(
        r'\bsa\d{6,10}[a-z]*\b',
        re.IGNORECASE
    )

    # --- PROCUREMENT/ARIBA PATTERNS ---
    # ARIBA Purchase Requisition: PR435494, PR:433072, PR 435494
    ARIBA_PR = re.compile(
        r'\bPR\s*[:\-]?\s*\d{6,8}\b',
        re.IGNORECASE
    )

    # --- SERIAL NUMBER PATTERNS (v2.8.2) ---
    # S/N : UNVLGSI137M0278740, S/N: 346139092, Serial: ABC123456
    SERIAL_NUMBER = re.compile(
        r'\b(?:S/?N|Serial(?:\s*(?:No|Number|#))?)\s*[:\s]\s*([A-Z0-9]{8,20})\b',
        re.IGNORECASE
    )

    # =========================================================================
    # v2.13.0: ADDITIONAL PATTERNS FOR MISSED PI TYPES
    # =========================================================================

    # --- RFID/EPC TAG PATTERNS ---
    # RFID EPC tags: 24-character hex strings like E28038212000682301AB8A76
    # Common in asset tracking, barcode systems
    RFID_EPC_TAG = re.compile(
        r'\b[0-9A-F]{24}\b',
        re.IGNORECASE
    )
    # RFID with context label: "barcode Tag(E28038212000682301AB8A76)"
    RFID_LABELED = re.compile(
        r'(?i)(?:barcode|rfid|epc|tag|chip)[\s._-]*(?:id|tag|no)?[\s.:_()=-]*([0-9A-Fa-f]{20,32})'
    )

    # --- ENHANCED HOSTNAME PATTERNS ---
    # Generic server/host naming: INSZCM12PRI1DB, INHYDB03
    # Pattern: 2-3 letter location + service/role code + optional numbers
    HOSTNAME_GENERIC = re.compile(
        r'\b[A-Z]{2,4}[A-Z0-9]{2,}(?:DB|SVR|SRV|APP|WEB|PRI|SEC|BAK|PRD|DEV|UAT|QA)\d*\b',
        re.IGNORECASE
    )
    # Hostnames with DB suffix: INHYDB03, USNYDB01
    HOSTNAME_DB = re.compile(
        r'\b[A-Z]{2,6}DB\d{1,4}\b',
        re.IGNORECASE
    )
    # Media server / backup server names
    HOSTNAME_MEDIA_SERVER = re.compile(
        r'(?i)(?:media\s*server|backup\s*server|client)\s+([A-Z]{2,}[A-Z0-9]+(?:DB|SRV|PRI|SEC)?\d*)\b'
    )

    # --- SECURITY INCIDENT PATTERNS ---
    # Security incident IDs: ES319725, ES + 6 digits
    SECURITY_INCIDENT = re.compile(
        r'\bES\d{5,8}\b',
        re.IGNORECASE
    )
    # Security incident with context: "security incident ES319725"
    SECURITY_INCIDENT_LABELED = re.compile(
        r'(?i)(?:security\s+incident|investigation|alert|case)\s*[\s.:_#-]*([A-Z]{2,4}\d{5,10})'
    )

    # --- CS/CUSTOMER SERVICE TICKET PATTERNS ---
    # CS Ticket numbers: 9-10 digit numbers like 105620792
    CS_TICKET_LABELED = re.compile(
        r'(?i)(?:CS|Customer\s*Service)[\s_-]*(?:ticket|case|incident)?[\s:_#-]*(?:no|number|id)?[\s:_#-]*(\d{8,12})'
    )
    # "Ticket Number 105620792" format
    TICKET_NUMBER_LABELED = re.compile(
        r'(?i)(?:ticket|case|incident)[\s_-]*(?:no|number|id)[\s:_#-]*(\d{7,12})'
    )

    # --- SPANISH LANGUAGE EMPLOYEE ID PATTERNS ---
    # "equipo no permite... 2675509" - Spanish IT context with employee ID
    EMP_ID_SPANISH_CONTEXT = re.compile(
        r'(?i)(?:equipo|usuario|cuenta|asociado)\s+[^.]{0,50}?\s+(\d{6,7})\b'
    )


# ============================================================================
# Export
# ============================================================================

__all__ = ['PIPatterns']
