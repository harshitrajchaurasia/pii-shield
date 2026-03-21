# Changelog

All notable changes to PI Remover will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Kubernetes deployment support
- Custom dictionary upload via API

---

## [2.16.0] - 2025-01-XX

### Added - Extended False Positive Prevention (Bottom 60K Analysis)

Comprehensive analysis of 120K rows (60K RFC + 60K Ticket data) with NER disabled (FAST mode) to identify and eliminate false positives in name detection.

#### NER Analysis Findings
- FULL mode (with NER): 149 rows/sec, 1,421 NAME tags
- FAST mode (without NER): 1,401 rows/sec, 1,179 NAME tags
- NER-only detections (~242) were ~80% false positives (software names like Gradle, Kibana, OpenJdk classified as PERSON)
- **Recommendation**: Use FAST mode for production workloads

#### New Exclusions Added (60+ terms)

| Category | Terms Added |
|----------|-------------|
| IT/Business Terms | `emp`, `name`, `asset`, `location`, `app`, `domain`, `source`, `management`, `administrator`, `version`, `url`, `contact`, `bank`, `local`, `services`, `number`, `recording`, `automation`, `protect`, `renewal`, `horizon`, `sales`, `globe`, `global`, `corporate`, `entrust`, `avd` |
| Acronyms | `rfc`, `odc`, `dis`, `ism`, `soe`, `cdc`, `ssl`, `ghd`, `ssid`, `iam`, `edr`, `bms`, `bulk`, `com`, `vlan`, `api`, `noc`, `lan`, `zim`, `soam`, `noam`, `rights`, `tgim`, `vpn`, `access` |
| Software/IT Terms | `firewall`, `store`, `centre`, `center`, `control`, `type`, `nokia`, `cisco`, `hub`, `portal`, `paas`, `saas`, `iaas`, `proxy`, `gateway`, `client`, `current`, `existing`, `available`, `required`, `raised`, `open`, `close`, `closed`, `opened`, `security`, `policy`, `policies` |
| Common Words | `of`, `freeware`, `shareware`, `proprietary`, `licensed`, `opensource`, `wifi`, `wlan`, `ssid`, `network`, `subnet`, `vrf`, `vlan`, `enable`, `enabled`, `disabled`, `active`, `inactive` |

#### New Filters Added

1. **All-Caps Filter** - Skip words that are entirely uppercase (likely acronyms/tech terms):
   - `ERPDEV`, `NONPROD`, `PRODSERVER` → not detected as names
   - Applied only to words ≤20 characters

2. **Underscore Identifier Filter** - Skip identifiers containing underscores:
   - `TCS_5GHz`, `TCS_ZCC`, `IND_DEL_YAM_T5` → not detected as names
   - These are typically system/location/configuration identifiers

### Fixed

| Pattern | Before | After |
|---------|--------|-------|
| `Wifi name: TCS_5GHz(@w!f1` | `Wifi name: [NAME]_5GHz(@w!f1` | `Wifi name: TCS_5GHz(@w!f1` |
| `App policy Name : TCS_ZCC Enable` | `[NAME]_ZCC Enable` | `TCS_ZCC Enable` |
| `Type of access (Ultimatix)` | `Type [NAME] access` | `Type of access (Ultimatix)` |
| `Software type Freeware (Third party)` | `type [NAME]` | `Software type Freeware (Third party)` |
| `open Firewall (443) between source` | `open [NAME] (443)` | `open Firewall (443) between source` |
| `security Control - Exception` | `security [NAME]` | `security Control - Exception` |
| `We raised the RFC for the installation` | `We [NAME] the RFC` | `We raised the RFC for the installation` |
| `A new version of Global Protect` | `version [NAME] Global Protect` | `A new version of Global Protect` |
| `access IND_DEL_YAM_T5` | `access [NAME]_DEL_YAM_T5` | `access IND_DEL_YAM_T5` |

### Technical Details

- Applied filters to both `NAME_LABELED` pattern processing and `_redact_names_contextual` method
- Synchronized improvements between main `remover.py` and standalone version
- All 60 core tests passing

### Added - False Negative Detection (Missed PI Analysis)

Analyzed 50K samples from both RFC and Ticket datasets using multiprocessing (11 workers) to identify missed PI.

#### New Patterns Added

| Pattern | Description | Example | Result |
|---------|-------------|---------|--------|
| `NAME_AFTER_SIGNATURE` | Names after "Thanks,", "Regards," etc. | `Thanks, Krishna kanth` | `Thanks, [NAME]` |
| `EMP_ID_8DIGIT` | 8-digit employee IDs starting with 2 | `Employee 25648792` | `Employee [EMP_ID]` |

#### Updated Patterns for 8-Digit Support

Extended the following patterns from `\d{4,7}` to `\d{4,8}`:
- `EMP_ID_LABELED` - General labeled emp ID pattern
- `EMP_ID_LABELED_EXPLICIT` - Explicit "Emp ID:" pattern
- `EMP_ID_WITH_LABEL` - "with Emp ID" pattern
- `EMP_ID_AFTER_ASSET` - Emp ID after asset tokens
- `EMP_ID_USER_LABELED` - "User ID:", "UID:" patterns
- `EMP_ID_UPN_NUMERIC` - Numeric email prefixes
- `EMP_ID_UPN_PREFIXED` - Prefixed UPN patterns
- `EMP_ID_UPN_GENERAL` - General UPN patterns
- `EMP_ID_PREFIXED_EXTENDED` - Extended prefixed accounts
- `EMP_ID_IN_PARENS` - IDs in parentheses

#### Standalone Sync (Thorough Review)

Fixed missing components in standalone:
- Added `MY_NAME_IS.finditer()` processing (pattern existed but wasn't used)
- Added `NAME_AFTER_EMP_ID.finditer()` processing (pattern existed but wasn't used)  
- Added `self._systems` initialization (was referenced but never initialized)
- Updated all 8-digit pattern references

#### Analysis Results
- RFC: 50,000 samples, 7,051 potential issues (10.2%) - mostly false detections
- Ticket: 50,000 samples, 90,026 potential issues (66.4%) - mostly false detections
- Real missed PI: 8-digit employee IDs, names after signature closings

---

## [2.15.1] - 2025-12-17

### Added - FQDN (Fully Qualified Domain Name) Detection

This release adds detection for FQDNs (Fully Qualified Domain Names) like `server.company.com`, `mail.internal.corp`, `db01.prod.domain.local`.

#### New Patterns Added

| Pattern | Description | Example |
|---------|-------------|---------|
| `FQDN` | Generic FQDN with 2+ dots | `mail.prod.company.com` |
| `FQDN_INTERNAL` | Internal TLDs (.local, .corp, .lan, .internal, .intra, .private, .home) | `db01.datacenter.local` |
| `FQDN_LABELED` | Labeled FQDNs (server:, host:, hostname:, fqdn:, machine:, node:) | `host: app.internal.corp` |

#### Exclusions (Not Redacted)
- Public domains: google.com, microsoft.com, github.com, etc.
- Email addresses (handled by EMAIL pattern)
- URLs with `://` prefix (handled by URL pattern)

### Fixed - False Positive Reduction (Bottom 40K Analysis)

Analyzed bottom 40,000 rows from RFC and Ticket data (avoiding overfitting from previous top 40K analysis) to identify and fix additional false positives.

#### Issues Fixed

1. **Location Suffix Detection** - Names followed by location suffixes (Park, Tower, Building, Plaza, Campus, ODC, etc.) are now preserved:
   - `Garima Park DC server` → preserved (not `[NAME] DC server`)
   - `Delta Park Location` → preserved
   - `Sahyadri Park building` → preserved

2. **Technical Action Words** - Added 40+ technical action words to exclusion lists:
   - `uninstallation`, `installation`, `reinstallation`, `configuration`
   - `migration`, `deployment`, `provisioning`, `activation`
   - `engagement`, `onboarding`, `offboarding`, `termination`

3. **ITSM/Ticket System Terms** - Added IT ticket abbreviations:
   - `cr`, `sr`, `inc`, `rfc`, `chg`, `prb`, `req`, `sctask`, `ritm`
   - `ticketing`, `portal`, `workspace`, `console`, `dashboard`

4. **Common IT Context Words** - Added frequently misclassified words:
   - Time: `long`, `short`, `times`, `time`, `leave`, `vacation`, `holiday`
   - Devices: `android`, `andriod`, `ios`, `iphone`, `ipad`, `mobile`
   - Infrastructure: `hypervisor`, `hypervior`, `tcs`, `provided`, `laptop`
   - Context: `belor`, `below`, `above`, `following`, `attached`, `mentioned`

5. **NER False Positive Blocklist** - Added technical terms incorrectly classified as PERSON by spaCy:
   - `hypervisor`, `hypervior`, `kubernetes`, `docker`, `ansible`
   - `terraform`, `jenkins`, `grafana`, `prometheus`, `elasticsearch`
   - `android`, `andriod`, `ios`, `iphone`, `ipad`
   - `uninstallation`, `configuration`, `deployment`, `provisioning`

6. **NAME_LABELED Pattern Fix** - Added negative lookbehinds for domain/host/server contexts:
   - `Domain Name : India` → preserved (not `Domain [NAME]`)
   - `Host Name : server01` → preserved (not `Host [NAME]`)

#### Results

| Dataset | Initial NAME | Final NAME | Reduction |
|---------|--------------|------------|-----------|
| RFC (40K) | 6,915 | 6,230 | 685 (9.9%) |
| Ticket (40K) | 21,349 | 20,632 | 717 (3.4%) |
| **Combined** | **28,264** | **26,862** | **1,402 (5.0%)** |

#### Files Updated
- `patterns.py` - Added FQDN patterns, updated NAME_LABELED, RFC_NUMBER patterns
- `remover.py` - Added `_redact_fqdn()`, expanded NER blocklist and exclusion lists
- `pi_remover_standalone.py` - Synced all patterns, methods, and exclusion lists
- `dictionaries.py` - Extended regional names (already in previous release)

---

## [2.15.0] - 2025-12-17

### Fixed - False Positive Reduction

This release addresses **major false positive issues** identified from analysis of 40K+ cleaned records where software names, products, and locations were incorrectly redacted as `[NAME]`.

#### False Positives Fixed

| Term | RFC Count | Ticket Count | Total |
|------|-----------|--------------|-------|
| India | 1,188 | 15,412 | **16,600** |
| Teams | 94 | 1,554 | **1,648** |
| Git | 250 | 1,025 | **1,275** |
| Home | 39 | 385 | **424** |
| VDI | 150 | 188 | **338** |
| Azure | 329 | 37 | **366** |
| SAP | 91 | 177 | **268** |
| associates | 9 | 178 | **187** |

#### Changes Made

1. **Expanded NER False Positive Blocklist** (`remover.py`)
   - Added 50+ software/product terms: git, putty, jupyter, postman, maven, tomcat, eclipse, etc.
   - Added Microsoft products: teams, azure, outlook, excel, word, powerpoint, sharepoint
   - Added IT/Security products: qualys, vdi, citrix, sap, oracle, vmware, tanium, crowdstrike
   - Added locations: india, hungary, bangalore, hyderabad, chennai, mumbai, pune, delhi
   - Added work terms: home, associates, recruiter, linkedin, genai, ultimatix

2. **Enhanced NER Entity Checking** (`remover.py`)
   - Now checks if ANY word in a multi-word entity is in the blocklist
   - Fixes cases like "Postman API" where "postman" is blocked

3. **Pattern False Positive Protection** (`remover.py`)
   - Added false positive check in `_redact_names_pattern()` method
   - Prevents "MS Teams", "Dr Drill", "Ms Office" from being matched as names

4. **Fixed INTERNAL_DOMAIN Pattern** (`patterns.py`)
   - Changed pattern to require `.tcs.com` suffix for "India"
   - Prevents standalone "India" from being redacted as `[DOMAIN]`
   - SOAM, NOAM, APAC, EMEA, LATAM still matched standalone

5. **Added Location Blocklist for NER** (`remover.py`)
   - Countries (india, hungary, usa, uk, germany, etc.) no longer redacted as `[LOCATION]`
   - Indian cities (bangalore, hyderabad, chennai, mumbai, pune, delhi) preserved
   - Regional terms (apac, emea, latam) preserved

6. **Updated Contextual Name Exclusions** (`remover.py`)
   - Added 50+ country/city/software terms to prevent "from Hungary" → "from [NAME]"
   - Added software tools to prevent "from Git repository" false positives

7. **Standalone Program Updated** (`pi_remover_standalone.py`)
   - All v2.15.0 fixes applied to standalone version
   - NER blocklist, pattern blocklist, location blocklist synchronized
   - **Comprehensive Pattern Sync**: Added 70+ patterns missing from standalone:
     - ITSM: SERVICENOW_TICKET (INC/CHG/PRB/RITM/REQ)
     - AD/LDAP: LDAP_DN, SAM_ACCOUNT, AD_UPN, WINDOWS_SID
     - Remote Access: TEAMVIEWER_ID, ANYDESK_ID, REMOTE_ID_LABELED
     - Database: DB_CONNECTION_STRING, MONGODB_URI, DB_CREDENTIALS
     - Session/Token: SESSION_ID, JWT_TOKEN, OAUTH_TOKEN, COOKIE_SESSION
     - Encryption: BITLOCKER_KEY, RECOVERY_KEY, CERT_THUMBPRINT, CERT_SERIAL
     - Cloud: AZURE_SUBSCRIPTION, AZURE_RESOURCE_ID, AWS_ACCOUNT_ID, AWS_ARN, GCP_PROJECT
     - License: PRODUCT_KEY
     - CMDB: CMDB_CI, SERVER_NAME_PATTERN
     - Audit: AUDIT_USER_ACTION, LOGIN_EVENT
     - Physical: DESK_LOCATION, FLOOR_LOCATION, BADGE_NUMBER
     - Phone: PHONE_EXTENSION, DID_NUMBER
     - Chat: CHAT_MENTION, CHAT_DM
     - Additional phone patterns: AU, DE, FR, SG, UAE, BR, JP, CN
     - Name patterns: MY_NAME_IS, NAME_USER_ACTION, NAME_HAS_ACTION, NAME_WITH_PARENS, NAME_SIGNATURE_LINE
   - **New Dictionaries**: Added COMPANY_NAMES (24 entries), INTERNAL_SYSTEMS (28 entries)
   - **Extended Names**: Added regional Indian names (South Indian, Bengali, Gujarati, Marathi, Punjabi)

---

## [2.14.0] - 2025-01-15

### Added - Production Data Analysis Fixes

This release addresses **8 categories of PI detection issues** identified from analysis of 1M+ production cleaned records (RFC: 429K rows, Tickets: 644K rows).

#### New Patterns Added

| Pattern | Description | Example | Frequency |
|---------|-------------|---------|-----------|
| `EMP_ID_TEAMS_HASH` | Teams chat handle format | `teams#2531177` | 14/10K tickets |
| `EMP_ID_ACCOUNT_OP` | Account unlock/enable/disable | `unlock account 1290362` | 16/10K RFC |
| `EMP_ID_HYPHEN_NAME` | ID-Name hyphen format | `2482545-Reshma Chobe` | 7/10K RFC |
| `EMP_ID_EMP_HASH_SPACE` | Emp # with space | `Emp # 2893847` | 6 total |
| `EMAIL_PARTIAL_LASTNAME` | Orphaned email parts | `.lastname@tcs.com` | 4/10K tickets |
| `EMP_ID_AFTER_TOKEN` | Residual ID after token | `[EMP_ID] #2919414` | 11/10K RFC |
| `NAME_AFTER_TOKEN` | Name in tabular data | `[EMP_ID]\tJohn Smith` | 106/10K RFC |

#### Post-Processing Cleanup

Added `_cleanup_partial_redactions()` function that runs after initial redaction to catch:
- Employee IDs appearing after redaction tokens (partial cleanup)
- Names in tabular data columns after redacted IDs
- This is a **second-pass cleanup** to catch edge cases

#### Fix Categories & Impact

| Issue Category | RFC Impact | Ticket Impact | Status |
|----------------|------------|---------------|--------|
| Standalone 7-digit Emp IDs | 32/10K | 27/10K | ✅ Context scoring enhanced |
| Teams # Format | - | 14/10K | ✅ New pattern added |
| Account Unlock Pattern | 16/10K | - | ✅ New pattern added |
| EMP ID Hyphen Name | 7/10K | 4/10K | ✅ New pattern (both ID & Name) |
| Partial Redaction | 11/10K | 3/10K | ✅ Post-processing cleanup |
| Name After Token | 106/10K | 70/10K | ✅ Post-processing cleanup |
| Partial Email | - | 4/10K | ✅ New pattern added |
| Emp # Format | 6 total | - | ✅ New pattern added |

### Changed

- Version bumped to 2.14.0
- Standalone file synced with all new patterns

---

## [2.13.2] - 2025-12-16

### Added - Priority Layer Architecture & UPN Email Handling

This release introduces a **19-layer priority architecture** for optimal redaction ordering and **UPN email handling** for employee ID extraction from corporate emails.

#### Priority Layer Architecture

The redaction engine now processes PI types in a carefully designed order:

| Layer | Category | PI Types | Rationale |
|-------|----------|----------|----------|
| 0 | Critical Secrets | PASSWORD, LICENSE_KEY, API_KEY | Highest risk, immediate exposure |
| 1 | Compound Structures | URL | Contains multiple PI types |
| 2 | Emails | EMAIL, UPN | Must process before emp ID extraction |
| 3 | Government IDs | AADHAAR, PAN, IFSC | High specificity |
| 4 | Phone Numbers | All phone patterns | Distinct formats |
| 5 | Employee IDs | Tiered context-aware | After email (UPN handling) |
| 6 | Asset IDs | ASSET_ID, RFID, SERIAL | Physical identifiers |
| 7 | Network | IP, MAC | Infrastructure identifiers |
| 8 | Hostnames | All hostname patterns | After emp ID (may contain) |
| 9 | IT/ITSM | RFC, TICKET, JIRA | Workflow identifiers |
| 10 | Financial | UPI, ARIBA_PR | Payment identifiers |
| 11 | Misc | SERVICE_ACCT, LOCATION, SEAT | Various |
| 12-18 | Names | NER → Pattern → Dictionary | Last (context-dependent) |

#### Design Principles

1. **Risk Level**: Credentials first (immediate, irreversible exposure)
2. **Compound Structures**: URL/Email before components they contain
3. **Specificity**: High-specificity patterns before generic ones
4. **Context Dependency**: Name detection last (needs intact surrounding text)

#### UPN Email Handling

Corporate UPN-style emails now extract employee IDs:

| Input | Output | Pattern |
|-------|--------|--------|
| `1234567@tcs.com` | `[EMP_ID]@[DOMAIN]` | Numeric local part |
| `ad.1234567@tcs.com` | `AD.[EMP_ID]@[DOMAIN]` | Prefixed account |
| `iada.9876543@tcsappsdev.com` | `IADA.[EMP_ID]@[DOMAIN]` | Extended prefix |

**Supported Domains**: tcs.com, tcsapps.com, tcsappsdev.com, tcscomprod.com, tata.com, tataconsultancy.com

**Supported Prefixes**: ad, iada, cad, ws, pr, sa, oth, vo, da, di

#### Standalone Sync

The standalone file (`others/standalone/pi_remover_standalone.py`) has been fully synchronized with all v2.13.2 improvements:
- All 125+ patterns from main implementation
- UPN email handling
- Tiered employee ID detection
- RFID and security incident detection
- Priority layer ordering

### Test Results
- **Main Implementation**: 61/61 tests passing
- **UPN Detection**: 100% accuracy
- **False Positive Prevention**: 0/28 for non-employee numbers
- **Standalone Parity**: 100% feature sync

---

## [2.13.1] - 2025-12-16

### Improved - Comprehensive Employee ID Detection

This release significantly enhances Employee ID detection with a **tiered context-aware scoring system** that handles 4-7 digit IDs while preventing false positives.

#### New Detection Architecture

**Tiered Scoring System:**
- **Tier 1 (High Confidence)**: Explicit labels always detected (Emp ID, Employee, User ID, EID, UID)
- **Tier 2 (Context-Aware)**: 4-7 digit numbers with context scoring
- **Tier 3 (Negative Filtering)**: Prevents false positives for prices, dates, versions, etc.

**Context Score Factors:**
| Factor | Score | Example |
|--------|-------|---------|
| Strong keyword (emp, user, contact) | +3 | "Contact 12345" |
| Medium keyword (access, account) | +1 (max 5) | "enable 12345 account" |
| Name before number | +2 | "JOHN SMITH 1234567" |
| Tab-separated (table format) | +2 | "Asset\t1234567" |
| After redacted token | +3 | "[NAME], 1234567" |

**Digit-Length Thresholds:**
| Digits | Required Score | Rationale |
|--------|----------------|-----------|
| 4-digit | 4+ | Highest bar (avoid false positives) |
| 5-digit | 3+ | Medium bar |
| 6-digit | 2+ | Lower bar |
| 7-digit | 1+ | Lowest bar (most likely emp ID) |

#### New Patterns Added
- `EMP_ID_4DIGIT`, `EMP_ID_5DIGIT`, `EMP_ID_6DIGIT_ANY`, `EMP_ID_7DIGIT_ANY`
- `EMP_ID_USER_LABELED`: "User 54321", "user id: 12345", "ID: 9876"

#### Negative Context Filtering
Numbers following these are NOT detected as employee IDs:
- Currency: `Rs.`, `$`, `INR`, `USD`
- ITSM: `order`, `ticket`, `case`, `ref`, `sr`, `cr`, `rfc`
- Location: `room`, `floor`, `building`, `seat`
- Technical: `port`, `error`, `code`, `version`, `pin`, `zip`
- Numeric: `amount`, `price`, `cost`, `quantity`, `total`

#### Test Results
- **Detection Rate**: 18/18 (100%) for valid employee IDs
- **False Positive Rate**: 0/28 (0%) for non-employee numbers
- **Regression Tests**: 60/60 passed

---

## [2.13.0] - 2025-12-16

### Added - Comprehensive PI Detection Fixes

This release addresses production issues where specific PI types were escaping detection.

#### New Phone Patterns
- **Malaysian phones** (`+60`): `PHONE_MY` pattern
- **Mexican phones** (`+52`): `PHONE_MX` and `PHONE_MX_SPACED` patterns

#### Enhanced Employee ID Detection
- `EMP_ID_LABELED_EXPLICIT`: "Emp ID - 351690" format
- `EMP_ID_WITH_LABEL`: "with Emp ID - 351690" or "Emp ID - 445658(Name)"
- `EMP_ID_AFTER_ASSET`: Employee ID after [ASSET_ID] with tab/space
- `EMP_ID_6DIGIT`: 6-digit employee IDs with explicit context
- `EMP_ID_SPANISH_CONTEXT`: Spanish IT context patterns
- Skip pattern for RFC-prefix format (prevents false positive)

#### New Location/Seat Patterns
- `SEAT_AT_LOCATION`: `@SFC Z10` format with optional seat number
- `SEAT_NUMBER_LABELED`: "Seat No 20" format

#### Enhanced RFC/Ticket Detection
- `RFC_NUMBER_SIMPLE`: "RFC 25655813" format
- `RFC_CONTEXTUAL`: "as per RFC", "refer RFC number" context
- `RFC_NUM_LABELED`: "RFC num 24926116" format
- `RFC_STANDALONE_CONTEXT`: Install/deploy context detection
- `RFC_PREFIX_FORMAT`: "2743428-Zscaler" number-prefix format
- `CS_TICKET_LABELED`: CS ticket 9-12 digit numbers
- `TICKET_NUMBER_LABELED`: "Ticket Number 105620792" format

#### New Hostname Patterns
- `HOSTNAME_GENERIC`: Generic server naming (INSZCM12PRI1DB)
- `HOSTNAME_DB`: DB suffix pattern (INHYDB03)
- `HOSTNAME_MEDIA_SERVER`: Labeled hostname in context

#### New Security Incident/RFID Detection
- `SECURITY_INCIDENT`: ES+5-8 digits
- `SECURITY_INCIDENT_LABELED`: With context label
- `RFID_EPC_TAG`: 24-character hex strings (barcode tags)
- `RFID_LABELED`: Labeled RFID with context

#### Improved False Positive Prevention
- Added IT/security product names to NER blocklist (Zscaler, Intune, Avaya, etc.)
- Added tech terms to name exclusion lists (tag, barcode, scanner, etc.)
- Enhanced internal systems dictionary with 15+ product names
- Added `NAME_AFTER_EMP_ID` pattern for names in parentheses after IDs

### Fixed
- "Zscaler" no longer incorrectly detected as [NAME]
- "barcode Tag" no longer incorrectly detected as [NAME]
- RFC numbers with hyphen-prefix format now detected correctly
- 6-7 digit employee IDs with explicit labels now detected
- Names in parentheses after employee IDs (e.g., "Dhanalakshmi") now redacted

---

## [2.12.0] - 2025-12-16

### Changed - Modular Architecture Refactoring

This release introduces a **complete architectural refactoring** of the PI Remover core, splitting the monolithic `core.py` (2500+ lines) into 9 focused, maintainable modules.


#### Architecture Changes

**Before (v2.11.x)**:
- Single monolithic `core.py` file with all functionality
- Difficult to maintain, test, and extend
- Tight coupling between components

**After (v2.12.0)**:
- 9 focused modules with clear responsibilities
- Facade pattern for backward compatibility
- 100% functional parity verified

#### New Module Structure

| Module | Lines | Purpose |
|--------|-------|---------|
| `config.py` | 274 | Configuration dataclass (40+ options) and YAML loading |
| `patterns.py` | 656 | **125+ regex patterns** organized by category (Email, Phone, ID, Network, IT/ITSM, Cloud, etc.) |
| `dictionaries.py` | 162 | Indian names (first/last), company names, internal systems |
| `data_classes.py` | 282 | Redaction, RedactionResult, RedactionStats dataclasses |
| `utils.py` | ~200 | Logging, multiprocessing, DataCleaner utilities |
| `ner.py` | 195 | spaCy NER integration with model management |
| `remover.py` | 1,047 | Main PIRemover class with all redaction methods |
| `model_manager.py` | 351 | Thread-safe spaCy model loading singleton |
| `security.py` | 1,176 | JWT auth, API security, rate limiting helpers |
| `sanitizer.py` | 499 | Input sanitization (SQL/XSS/Command injection detection) |
| `processors/__init__.py` | ~300 | File processing (CSV, JSON, TXT, DataFrame) |

#### Backward Compatibility

The `core.py` file now acts as a **facade module**, re-exporting all public APIs from the modular architecture:

```python
# All existing imports continue to work
from pi_remover.core import PIRemover, PIRemoverConfig, Redaction
from pi_remover import PIRemover  # Also works via __init__.py
```

#### Testing

- **61 pytest tests pass** (test_remover.py, test_edge_cases.py)
- **85 E2E verification tests** executed
- **100% functional parity** with v2.11.x confirmed

#### Files Changed

- `src/pi_remover/core.py` - Converted to facade module
- `src/pi_remover/config.py` - NEW: Configuration management
- `src/pi_remover/patterns.py` - NEW: PI regex patterns
- `src/pi_remover/dictionaries.py` - NEW: Name dictionaries
- `src/pi_remover/data_classes.py` - NEW: Result dataclasses
- `src/pi_remover/utils.py` - NEW: Utilities and multiprocessing
- `src/pi_remover/ner.py` - NEW: spaCy NER integration
- `src/pi_remover/remover.py` - NEW: Main PIRemover class
- `src/pi_remover/processors/__init__.py` - NEW: File processors
- `src/pi_remover/__init__.py` - Updated exports

#### Benefits

1. **Maintainability**: Each module has a single responsibility
2. **Testability**: Modules can be unit tested independently
3. **Extensibility**: Easy to add new patterns or processors
4. **Code Navigation**: Developers can find code faster
5. **Reduced Merge Conflicts**: Changes isolated to specific modules

---

## [2.11.0] - 2025-12-16

### Added - Observability & Developer Experience Improvements

This release adds comprehensive observability features and developer experience improvements.

#### New Features

**Prometheus Metrics (`/metrics` endpoint)**
- Request counters with labels (endpoint, status, mode)
- Request duration histograms
- Redaction counters by PI type
- Model loading metrics
- Active request gauges
- Graceful fallback when `prometheus_client` not installed

**Input Sanitization Module (`src/pi_remover/sanitizer.py`)**
- SQL injection detection
- Command injection detection
- XSS/script injection detection
- Path traversal detection
- Control character removal
- Unicode normalization (NFKC)
- Null byte stripping

**Singleton spaCy Model Manager (`src/pi_remover/model_manager.py`)**
- Thread-safe singleton pattern for model loading
- Prevents duplicate ~500MB model loads
- Shared model instances across PIRemover instances
- Model preloading support
- Memory usage tracking
- Load time metrics for observability

**Kubernetes Health Probes**
- `/livez` - Liveness probe (unauthenticated)
- `/readyz` - Readiness probe (checks model availability)
- Enhanced `/health` with model status

**Makefile for Developer Experience**
- `make install`, `make install-dev`, `make install-full`
- `make test`, `make test-cov`, `make test-fast`
- `make lint`, `make format`, `make type-check`
- `make run-api`, `make run-web`
- `make docker-build`, `make docker-up`
- `make clean`, `make help`

**Structured Logging Integration**
- Request logging middleware with correlation IDs
- `X-Correlation-ID` header propagation
- JSON structured logging for log aggregation

#### Changed
- Updated `SpacyNER` class to use `SpacyModelManager` singleton
- Added `X-Correlation-ID` to allowed CORS headers
- Enhanced startup logging with Prometheus status

#### Dependencies
- Added `prometheus_client>=0.19.0` to api_service requirements

---

## [2.10.0] - 2025-12-15

### Added - Auto-Scaling & Platform-Aware Multiprocessing

- Level 1-4 auto-scaling implementation
- Platform-aware multiprocessing (Windows/Unix)
- Resource detection with fallback chains
- Exception handling audit across all modules

---

## [2.8.3] - 2025-12-14

### Fixed - NAME_WITH_TITLE False Positive Prevention

This release fixes critical false positives in the `NAME_WITH_TITLE` pattern that were matching technical terms like "dr drill", "ms teams", "mr vm" as personal names.

#### Problem Solved
Production data analysis of 1M+ ITSM records revealed the `NAME_WITH_TITLE` pattern was too broad:
- `"pr to dr drill"` → `"pr to [NAME]"` (DR = Disaster Recovery)
- `"access to ms teams"` → `"access to [NAME]"` (MS = Microsoft)
- `"mr vm migration"` → `"[NAME]"` (MR = Merge Request, VM = Virtual Machine)

#### Root Cause
The regex used `re.IGNORECASE` flag which caused `[A-Za-z]+` to match lowercase technical terms:
```python
# BEFORE (v2.8.2) - Matched "dr drill" as "Dr. Drill"
NAME_WITH_TITLE = re.compile(
    r'\b(?:Mr|Ms|Mrs|Dr|Shri|Smt|Sri)\.?\s+([A-Za-z]+...)\b',
    re.IGNORECASE  # This caused the issue
)
```

#### Fix Applied
Changed to use character classes for title matching while requiring proper capitalization for names:
```python
# AFTER (v2.8.3) - Only matches "Dr. Sharma", "dr Sharma", NOT "dr drill"
NAME_WITH_TITLE = re.compile(
    r'\b(?:[Mm][Rr]|[Mm][Ss]|[Mm][Rr][Ss]|[Dd][Rr]|[Ss][Hh][Rr][Ii]|[Ss][Mm][Tt]|[Ss][Rr][Ii])\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
)
```

This allows:
- ✅ Title in any case: "Dr.", "dr", "DR" all match
- ✅ Name requires capitalization: "Sharma", "Kumar" match
- ❌ Lowercase technical terms blocked: "drill", "teams", "vm" don't match

#### Extended Blocklists (v2.8.3)
Added 20+ new words to false positive blocklists:

**Technical Abbreviations:**
`pr`, `dr`, `qa`, `uat`, `dev`, `prod`, `vm`, `os`, `db`, `api`, `bcp`

**Product/Tool Names:**
`informs`, `teams`, `jira`, `snow`, `servicenow`, `masscom`, `splunk`

**IT Infrastructure Terms:**
`drill`, `backup`, `restore`, `failover`, `recipients`, `channels`

#### Files Changed
- `src/pi_remover/core.py`:
  - Version updated to `2.8.3`
  - `PIPatterns.NAME_WITH_TITLE` - New pattern without IGNORECASE
  - NER blocklist - Added technical abbreviations
  - `common_word_exclusions` - Added product names
  
- `others/standalone/pi_remover_standalone.py`:
  - Version updated to `2.8.3`
  - Synced all pattern changes from core.py

#### Test Results (All Pass)

**False Positive Tests (7/7 PASS):**
| Test | Input | Output | Result |
|------|-------|--------|--------|
| DR Drill | `"pr to dr drill"` | `"pr to dr drill"` | PASS |
| MS Teams | `"access to ms teams"` | `"access to ms teams"` | PASS |
| MS Teams (standalone) | `"ms teams channel"` | `"ms teams channel"` | PASS |
| DR BCP | `"dr bcp testing"` | `"dr bcp testing"` | PASS |
| MR VM | `"mr vm migration"` | `"mr vm migration"` | PASS |
| Informs | `"Informs Team notification"` | `"Informs Team notification"` | PASS |
| Recipients | `"recipients list"` | `"recipients list"` | PASS |

**Real Name Tests (6/6 PASS):**
| Test | Input | Output | Result |
|------|-------|--------|--------|
| Dr. Title | `"Meeting with Dr. Sharma"` | `"Meeting with [NAME]"` | PASS |
| Ms. Title | `"Assigned to Ms. Priya Kumar"` | `"Assigned to [NAME]"` | PASS |
| Mr. Title | `"Contact Mr. Raj about ticket"` | `"Contact [NAME] about ticket"` | PASS |
| Mrs. Title | `"Mrs. Singh is the manager"` | `"[NAME] is the manager"` | PASS |
| Dr (no dot) | `"Email from Dr Patel"` | `"Email from [NAME]"` | PASS |
| lowercase dr | `"dr Kumar called earlier"` | `"[NAME] called earlier"` | PASS |

---

## [2.9.1] - 2025-01-15

### Fixed - Instant Fallback Performance Optimization

This release addresses the **17+ second delay** when API is unavailable by implementing intelligent status caching.

#### Problem Solved
- **Before**: API timeout caused 4 retry attempts × ~4 seconds = 17.6 seconds delay
- **After**: Cached API status enables instant routing (0ms for subsequent requests)

#### Backend Improvements (`web_service/app.py`)
- **`APIStatusCache`** - Dataclass caching API availability with 30-second TTL
  - `is_available` - Current API availability status
  - `last_check` - Timestamp of last health check
  - `response_time_ms` - API response time when available
  - `consecutive_failures` - Failure count for smart routing
  - `should_try_api()` - Instant routing decision (no network call)
  
- **Background Health Check** - Proactive API monitoring
  - Runs every 30 seconds (configurable: `HEALTH_CHECK_INTERVAL`)
  - 3-second timeout for health checks (vs 30+ second retry cascade)
  - Updates cache asynchronously - no user-facing delay
  
- **`/api/status` Endpoint** - Real-time status for frontend
  ```json
  {
    "api_available": true,
    "last_check": "2025-01-15T10:30:00Z",
    "response_time_ms": 45,
    "consecutive_failures": 0,
    "cache_ttl_seconds": 30
  }
  ```

- **Cache-First Routing** - Optimized hybrid functions
  - `redact_text_hybrid()` checks `should_try_api()` first
  - `redact_batch_hybrid()` checks `should_try_api()` first
  - If cache says API unavailable → immediate local fallback (0ms)
  - No retry cascade when API known to be down

#### Frontend Improvements (`web_service/templates/index.html`)
- **API Status Badge** - Visual indicator in header
  - 🟢 **API Online** - Green badge with pulse animation
  - 🔴 **Local Mode** - Red badge when using local processing
  - 🟡 **Checking...** - Yellow during initial status check
  
- **Status Polling** - Automatic updates
  - Initial check on page load (5-second timeout)
  - Polls `/api/status` every 60 seconds
  - Updates badge dynamically without page refresh

#### Performance Comparison
| Scenario | Before v2.9.1 | After v2.9.1 |
|----------|:-------------:|:------------:|
| API online | ~200ms | ~200ms |
| API down (1st request) | 17.6s | 17.6s* |
| API down (subsequent) | 17.6s | **0ms** |
| API flaky | 4-17s | **3s max** |

\* First request after cache expires may hit retry; all subsequent use cached status

---

## [2.9.0] - 2025-12-14

### Added - Hybrid Microservices Architecture

This release introduces a **Hybrid Microservices Architecture** with automatic local fallback for enterprise deployments.

#### Hybrid Mode (`web_service/app.py`)
- **Automatic API fallback** - Web Service tries API first, falls back to local PIRemover if unavailable
- **`--standalone` flag** - Force local-only processing (no API calls)
- **`redact_text_hybrid()`** - Hybrid text redaction with automatic fallback
- **`redact_batch_hybrid()`** - Hybrid batch redaction with automatic fallback
- **`redact_text_locally()`** - Direct local PIRemover processing
- **`redact_batch_locally()`** - Direct local batch processing
- **Zero downtime** - Users experience no interruption regardless of API state

#### New Startup Options
| Mode | Command | API Required |
|------|---------|:------------:|
| Web Hybrid | `uvicorn app:app` | Optional |
| Web Force Local | `python app.py --standalone` | ❌ |
| Full Stack | `.\scripts\run_comprehensive_tests.ps1` | ✅ |

#### New Shared Infrastructure (`shared/`)
- **`shared/config_loader.py`** - YAML configuration loading with CLI argument support
  - `ConfigLoader.from_yaml()` - Load from YAML files
  - `ConfigLoader.from_args()` - Override via command line arguments
  - Dot notation access: `config.get("service.port", 8080)`
  - Deep merge for nested configurations
  
- **`shared/logging_config.py`** - Structured JSON logging for ELK/Splunk
  - `PIRedactingFilter` - Automatically masks PI in log messages
  - `StructuredJSONFormatter` - JSON output for log aggregation
  - `RequestLoggingMiddleware` - Correlation ID propagation
  - Timezone-aware timestamps
  
- **`shared/redis_client.py`** - Redis connection with in-memory fallback
  - `RedisClient` - Async Redis operations with connection pooling
  - `InMemoryFallback` - Graceful degradation when Redis unavailable
  - Rate limiting, caching, and health check methods

#### New API Client (`web_service/api_client.py`)
- **`PIRemoverAPIClient`** - HTTP client for web→API communication
  - JWT token management with automatic refresh
  - Connection pooling via httpx
  - Retry with exponential backoff
  - Correlation ID propagation

- **`CircuitBreaker`** - Resilience pattern for API outages
  - Configurable failure threshold (default: 5)
  - Recovery timeout (default: 30 seconds)
  - States: CLOSED → OPEN → HALF-OPEN → CLOSED

#### New Configuration System (`config/`)
- **YAML-based configuration** - No environment variables required
- **`config/api_service.yaml`** - API service settings (port, NER, security)
- **`config/web_service.yaml`** - Web service + circuit breaker config
- **`config/clients.yaml`** - Client credentials (⚠️ add to .gitignore)
- **`config/redis.yaml`** - Redis connection and pooling settings
- **`config/logging.yaml`** - Centralized logging configuration

#### New Docker Compose
- **`docker/docker-compose.base.yml`** - Base microservices configuration
  - Redis service for distributed rate limiting
  - `pi-internal` network for service communication
  - Shared volumes for logs and config
  - Health checks for all services
  
- **`docker/docker-compose.dev.yml`** - Development overrides
- **`docker/docker-compose.prod.yml`** - Production configuration

#### New Service-to-Service Authentication
- **`pi-internal-web-service`** - Dedicated client for web→API calls
  - 10,000 requests/minute rate limit (vs 1,000 for external clients)
  - 30-minute JWT token expiration
  - Auto-refresh before expiry

#### New Test Infrastructure
- **`scripts/test_components.py`** - Component test suite
  - Tests all module imports
  - Validates YAML configuration files
  - Circuit breaker functionality tests
  - In-memory fallback tests
  
- **`scripts/run_comprehensive_tests.ps1`** - Full test runner (PowerShell)
  - Starts services in separate terminals
  - Runs all test suites
  - Generates pass/fail summary
  
- **`scripts/run_comprehensive_tests.sh`** - Full test runner (Bash)
- **`tests/test_service_integration.py`** - Integration tests

#### New Documentation
- **`docs/ARCHITECTURE.md`** - Complete architecture documentation
- **`docs/IMPLEMENTATION_TRACKER.md`** - Implementation progress tracking

### Changed
- **`security.py`** - Updated to v2.9.0
  - Added YAML import for configuration loading
  - Enhanced `load_clients()` to support YAML config files
  - Priority: YAML config → Environment → Legacy JSON → Defaults
  
- **`web_service/requirements.txt`** - Added dependencies
  - `httpx>=0.25.0` - Async HTTP client
  - `pyyaml>=6.0` - YAML configuration
  - Removed spaCy (handled by API service)
  
- **`api_service/requirements.txt`** - Added `pyyaml>=6.0`
- **`scripts/deploy-dev.ps1`** - Updated for microservices deployment

### Architecture Changes

```
BEFORE (v2.8.x - Monolith):
┌─────────────┐     ┌─────────────┐
│ Web Service │     │ API Service │  (Independent, each has PIRemover)
│ + PIRemover │     │ + PIRemover │
└─────────────┘     └─────────────┘

AFTER (v2.9.0 - Microservices):
┌─────────────┐           ┌─────────────┐     ┌───────┐
│ Web Service │──HTTP────▶│ API Service │────▶│ Redis │
│ (UI only)   │  +JWT     │ + PIRemover │     │       │
│ + API Client│           │ (core logic)│     │       │
└─────────────┘           └─────────────┘     └───────┘
```

### Migration Notes (v2.12.0 Complete)

Migration to microservices mode is complete:
1. ✅ `web_service/app.py` is now the unified hybrid service
2. ✅ `web_service/app_new.py` has been deleted (merged into app.py)
3. Start services via: `docker-compose -f docker/docker-compose.base.yml up`
4. Ensure `config/clients.yaml` is in `.gitignore`

---

## [2.8.0] - 2025-12-14

### Added
- **Extended File Type Support** - Process many more document formats
  - Word documents: `.docx`, `.doc`
  - PowerPoint presentations: `.pptx`, `.ppt`
  - PDF files: `.pdf` (extracted to TXT)
  - HTML/XML: `.html`, `.htm`, `.xml`
  - Additional text formats: `.md`, `.log`, `.rtf`
  
- **New Dependencies** (optional, install as needed)
  - `python-docx` for Word documents
  - `python-pptx` for PowerPoint files
  - `pdfplumber` for PDF text extraction
  - `beautifulsoup4` + `lxml` for HTML/XML parsing

- **New API Endpoint: GET /v1/models**
  - List all available spaCy NER models
  - Shows installation status for each model
  - Returns which model is the default
  - Indicates if NER is enabled in current config

- **Enhanced Security - All Endpoints Require Authentication**
  - `/health` now requires JWT authentication
  - `/v1/pi-types` now requires JWT authentication
  - `/v1/models` now requires JWT authentication
  - `/` (root) now requires JWT authentication
  - Only `/auth/token` remains public (to obtain tokens)

### Changed
- Web UI now shows all supported file formats
- `process_file()` routes new file types automatically
- Unknown file extensions treated as plain text
- Updated Postman collection to v2.8.0 with auth on all endpoints
- All API documentation updated to reflect auth requirements

---

## [2.7.1] - 2025-12-13

### Added
- **API Model Selection** - Select spaCy NER model per request
  - New request parameters: `enable_ner` (boolean) and `spacy_model` (string)
  - Available models: `en_core_web_sm`, `en_core_web_md`, `en_core_web_lg` (default), `en_core_web_trf`
  - Model caching for performance - models loaded once and reused
  - Automatic fallback to default model if requested model unavailable
  - New response fields: `mode`, `spacy_model`, `used_fallback`

- **Enhanced Health Endpoint**
  - `available_models`: List of installed spaCy models on the server
  - `default_model`: Shows the default model (`en_core_web_lg`)

- **Fast Mode via API**
  - Set `enable_ner: false` for 10x faster processing
  - Skips spaCy NER, uses regex and dictionary detection only
  - Response shows `mode: "fast"` and `spacy_model: null`

### Changed
- Default spaCy model changed from `en_core_web_trf` to `en_core_web_lg` for better performance/accuracy balance
- Updated Postman collection to v2.7.0 format (removed emojis, added model selection examples)
- Web UI PI Types section redesigned as collapsible panel

### Technical Details
- `get_remover_for_model()` function for model caching/validation
- `check_available_models()` runs at startup to detect installed models
- `ALLOWED_SPACY_MODELS` whitelist prevents arbitrary model loading

---

## [2.7.0] - 2025-12-13

### Added
- **Comprehensive IT/ITSM PI Detection** - 35+ new patterns specifically for IT environments
  
  #### ITSM Ticket Identifiers
  - ServiceNow tickets: INC, RITM, REQ, CHG, PRB, TASK, SCTASK, KB, STRY, CTASK
  - JIRA tickets: PROJECT-123 format
  - Generic labeled tickets: "Ticket #12345", "Case: ABC123"
  - **Context preserved**: "INC[TICKET_NUM]" keeps ticket type visible
  
  #### Active Directory / LDAP
  - Distinguished Names (DN): CN=John,OU=Users,DC=company
  - SAMAccountName: domain\username
  - User Principal Names (internal domains): user@company.local
  - Windows SID: S-1-5-21-xxx
  - **Context preserved**: Only CN values redacted, structure maintained
  
  #### Remote Access Tools
  - TeamViewer IDs: 123 456 789 format
  - AnyDesk IDs: 9-digit format
  - Generic remote access IDs (when labeled)
  - **Context preserved**: Tool names kept, only IDs redacted
  
  #### Database Security
  - Connection strings with credentials
  - User/Password in connection format
  - MongoDB URIs with credentials
  - **Full redaction**: Connection strings fully redacted for security
  
  #### Session/Auth Tokens
  - Session IDs: JSESSIONID, PHPSESSID, ASP.NET_SessionId
  - JWT Tokens (eyJ... format)
  - OAuth/Bearer tokens
  - Cookie session data
  
  #### Encryption/Recovery Keys
  - BitLocker recovery keys (48-digit format)
  - Generic recovery keys (when labeled)
  - Certificate thumbprints (SHA1/SHA256)
  - Certificate serial numbers
  
  #### Workplace Information
  - Desk/Seat/Cubicle locations
  - Floor/Building numbers
  - Badge/Access card numbers
  - Phone extensions (3-5 digit)
  - DID (Direct Inward Dial) numbers
  - **Organization-specific seat pattern**: A1F 102, A5F-456, B2F102 format
  - **Context preserved**: "Desk [DESK_NUM]" or "[SEAT]" format
  
  #### Cloud Identifiers
  - Azure Subscription IDs (GUID)
  - Azure Resource IDs
  - AWS Account IDs (12-digit)
  - AWS ARN (Amazon Resource Names)
  - GCP Project IDs
  
  #### License/Product Keys
  - Standard format: XXXXX-XXXXX-XXXXX-XXXXX
  - Labeled product/license keys
  - CMDB Configuration Item IDs
  
  #### Chat/Collaboration
  - @mentions (Slack/Teams handles)
  - DM/Direct message references
  - **Smart filtering**: Skips @team, @channel, @here, @everyone
  
  #### Audit Log Patterns
  - User action logs: "user john.smith modified..."
  - Login/Logon events: "login from user john@domain"

### Configuration Options
New config flags in `PIRemoverConfig`:
```python
redact_ticket_ids: bool = True
redact_active_directory: bool = True
redact_remote_access_ids: bool = True
redact_database_strings: bool = True
redact_session_tokens: bool = True
redact_encryption_keys: bool = True
redact_workplace_info: bool = True
redact_cloud_ids: bool = True
redact_license_keys: bool = True
redact_chat_handles: bool = True
redact_audit_info: bool = True
```

### Context Preservation Strategy
All new redaction methods follow the principle of **preserving context**:
- Labels/prefixes are kept: "Ticket: [TICKET_NUM]" not "[TICKET]"
- Tool names preserved: "TeamViewer ID: [REMOTE_ID]"
- Structural info maintained: "CN=[AD_NAME],OU=Users,DC=company"

### Technical Details
- 35+ new regex patterns in `PIPatterns` class
- 11 new redaction methods in `PIRemover` class
- Detection confidence scores: 0.80-1.0 based on pattern type
- All patterns tested for minimal false positives

---

## [2.6.0] - 2025-12-13

### Added
- **Enhanced Name Detection** - Significantly improved name detection coverage without false positives
  - **Contextual patterns** (HIGH CONFIDENCE): Detects names in context like "Hi John", "Called Rahul", "Assigned to Priya"
  - **IT Ticket patterns**: "Caller: John Smith", "Requestor: Priya", "Raised by: Rahul"
  - **Communication patterns**: "Spoke with John", "Emailed Priya", "Response from Rahul"
  - **Greeting patterns**: "Dear Rahul", "Hello Priya", "Good morning John"
  - **Email-to-name correlation**: Extracts names from nearby email addresses (e.g., "John Smith (john.smith@company.com)")
  - **Signature line detection**: "-- Rahul Sharma" or "- John"
- **External Name Dictionary Support**
  - Load additional names from `data/names.txt` (plain text) or `data/names.json`
  - Supports CSV format with `first_name`/`last_name` columns
  - Runtime name addition via `add_names()` method
- **Sample name dictionaries** with 150+ additional names
  - International names (European, Middle Eastern, East Asian)
  - Extended Indian regional names
- **Confidence scoring** for all name detection methods
  - Contextual patterns: 0.95 confidence
  - Email correlation: 0.90 confidence
  - NER detection: 0.85 confidence
  - Pattern-based: 0.80 confidence
  - Dictionary-based: 0.75 confidence

### Changed
- Name detection now uses 6 layers instead of 4
- Improved overlap handling for better accuracy
- Updated documentation with new features

### Technical Details
- New patterns added to `PIPatterns` class:
  - `NAME_CONTEXT_FROM_BY`
  - `NAME_GREETING`
  - `NAME_COMMUNICATION`
  - `NAME_TICKET_CALLER`
  - `NAME_USER_ACTION`
  - `NAME_HAS_ACTION`
  - `NAME_WITH_PARENS`
  - `NAME_SIGNATURE_LINE`
- New methods in `PIRemover` class:
  - `_redact_names_contextual()`
  - `_redact_names_from_email()`
  - `_load_external_names()`
  - `add_names()`

---

## [2.5.0] - 2025-12-13

### Added
- **Docker Engine deployment scripts** for commercial environments (avoiding Docker Desktop licensing)
  - `setup-docker-wsl2.sh` - Install Docker Engine in WSL2 Ubuntu
  - `setup-docker-rhel.sh` - Install Docker Engine/Podman on RHEL 8/9
  - `deploy-dev.sh` / `deploy-prod.sh` - Linux deployment scripts
  - `deploy-gcp.sh` - Google Cloud Run deployment
  - `promote-to-prod.sh` / `promote-to-prod-gcp.sh` - Promotion scripts with rollback
- **Comprehensive DEPLOYMENT.md** covering WSL2, RHEL, and GCP deployment
- **Monitoring documentation** (`docs/MONITORING.md`)
- **Troubleshooting guide** (`docs/TROUBLESHOOTING.md`)
- Environment template files (`.env.example`)

### Changed
- Updated `GOOGLE_CLOUD.md` to clarify it's for advanced async architecture
- Reorganized scripts directory with clear naming conventions

### Security
- Docker Engine (Apache 2.0) used instead of Docker Desktop for enterprise licensing compliance
- JWT authentication with separate DEV/PROD credentials
- Secrets stored in GCP Secret Manager for cloud deployments

---

## [2.4.0] - 2025-12-01

### Added
- **DEV/PROD environment separation**
  - DEV endpoints: `http://localhost:8080/dev/v1/redact` (ports 8080/8082)
  - PROD endpoints: `http://localhost:9080/prod/v1/redact` (ports 9080/9082)
- Separate Docker Compose files (`docker-compose.dev.yml`, `docker-compose.prod.yml`)
- Environment-specific credentials
- PowerShell deployment scripts (`deploy-dev.ps1`, `deploy-prod.ps1`, `promote-to-prod.ps1`)

### Changed
- Swagger UI disabled in production for security
- Debug endpoints disabled in production
- Increased rate limits for production environment

---

## [2.3.0] - 2025-11-15

### Added
- **Data cleaning/preprocessing** configuration in `config.yaml`
- Text normalization options (Unicode, whitespace, smart quotes)
- Batch processing performance improvements
- Configurable batch size and worker processes

### Changed
- Improved regex patterns for edge cases
- Better handling of multi-line text blocks
- Enhanced progress bar with ETA

### Fixed
- Memory leak in large file processing
- False positives in phone number detection
- Unicode handling in CSV files

---

## [2.2.0] - 2025-11-01

### Added
- **LLM Gateway API** (`api_service/`)
  - REST API for real-time PI redaction
  - JWT authentication with configurable expiry
  - Rate limiting (DEV: 100/min, PROD: 1000/min)
  - Batch endpoint for multiple texts
  - `/v1/pi-types` endpoint to list supported PI types
- **Web Service** (`web_service/`)
  - Browser-based UI for file upload
  - Light/dark theme toggle
  - Column selection for CSV files
  - Real-time text redaction

### Changed
- Core engine refactored for better API integration
- Improved error messages with context

---

## [2.1.0] - 2025-10-15

### Added
- **NER (Named Entity Recognition)** using spaCy
  - Detects names not in dictionary
  - Improves recall for unusual names
  - Toggleable via `--fast` flag (disables NER)
- Custom name dictionaries with confidence scoring
- Context-aware detection (names near keywords like "contact", "from", etc.)

### Changed
- Default mode now uses NER (slower but more accurate)
- Fast mode (`--fast`) uses regex + dictionary only

### Fixed
- False positives with common words
- Better handling of international names

---

## [2.0.0] - 2025-10-01

### Added
- **Complete rewrite** with enterprise features
- Support for CSV, Excel (.xlsx), JSON, and plain text files
- Configurable PI types via `config.yaml`
- Whitelisting for domains, phone numbers, and email addresses
- Custom replacement tokens (e.g., `[EMAIL-REDACTED]`, `[PHONE-REDACTED]`)
- Docker support for all deployment modes
- Comprehensive logging with configurable levels

### Changed
- Modular architecture (`src/pi_remover/`)
- Configuration-driven approach
- Improved pattern accuracy

### Breaking Changes
- New command-line interface (see README.md)
- Configuration file format changed
- Output file naming convention changed

---

## [1.0.0] - 2025-09-01

### Added
- Initial release
- Basic PI removal for text and CSV files
- Email, phone, SSN, and credit card detection
- Command-line interface
- Simple regex-based detection

---

## Version Comparison

| Version | NER | API | Web UI | Docker | DEV/PROD | Model Selection |
|---------|-----|-----|--------|--------|----------|------------------|
| 1.0.0 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 2.0.0 | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| 2.1.0 | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| 2.2.0 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 2.3.0 | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| 2.4.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| 2.5.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| 2.6.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| 2.7.0 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **2.7.1** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Upgrade Guide

### From 2.4.x to 2.5.0

No breaking changes. New deployment scripts are additive.

```bash
# Use new Linux scripts instead of PowerShell on WSL2/Linux
./scripts/deploy-dev.sh
./scripts/deploy-prod.sh
```

### From 2.3.x to 2.4.0

Update endpoint URLs to include environment prefix:
- Old: `http://localhost:8080/v1/redact`
- New DEV: `http://localhost:8080/dev/v1/redact`
- New PROD: `http://localhost:9080/prod/v1/redact`

### From 1.x to 2.x

Complete migration required. See README.md for new CLI options.

---

[Unreleased]: https://github.com/your-org/pi-remover/compare/v2.5.0...HEAD
[2.5.0]: https://github.com/your-org/pi-remover/compare/v2.4.0...v2.5.0
[2.4.0]: https://github.com/your-org/pi-remover/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/your-org/pi-remover/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/your-org/pi-remover/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/your-org/pi-remover/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/your-org/pi-remover/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/your-org/pi-remover/releases/tag/v1.0.0
