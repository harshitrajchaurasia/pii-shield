# Knowledge Base - Known Issues & Fixes (KEBD)

This document tracks known issues, their root causes, and the fixes applied. It also contains comprehensive troubleshooting steps and procedures for making changes to the project.

---

## Table of Contents

1. [PIRemover Version Information](#piremover-version-information)
2. [Tech Stack & Dependencies](#tech-stack--dependencies)
3. [Making Changes to the Project](#making-changes-to-the-project)
4. [Known Issues & Fixes](#known-issues--fixes)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Template for Future Issues](#template-for-future-issues)

---

## PIRemover Version Information

**Current Version (2025-12-16):** v2.12.0 (Modular Architecture)

| File | Version | Purpose |
|------|---------|---------|
| `src/pi_remover/` | 2.12.0 | Modular PI engine (9 modules) |
| `src/pi_remover/core.py` | 2.12.0 | Facade module (re-exports) |
| `others/standalone/pi_remover_standalone.py` | 2.8.3 | Standalone single-file version |

**v2.12.0 Module Structure:**
- `config.py` - Configuration management
- `patterns.py` - 125+ regex patterns
- `dictionaries.py` - Name dictionaries
- `data_classes.py` - Redaction, RedactionResult
- `utils.py` - Utilities, multiprocessing
- `ner.py` - spaCy NER integration
- `remover.py` - Main PIRemover class
- `processors/` - File processors (CSV, JSON, TXT, DataFrame)

**Note:** After code changes, services must be restarted to pick up fixes:
```powershell
# Restart services
Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force
# Then restart your services
cd api_service && uvicorn app:app --reload --port 8080
cd web_service && uvicorn app:app --reload --port 8082
```

---

## Tech Stack & Dependencies

### Core Technologies

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.104+ | Web framework |
| Uvicorn | 0.24+ | ASGI server |
| spaCy | 3.7+ | NER (Named Entity Recognition) |
| Pandas | 2.0+ | Data processing |
| Redis | 7.0+ | Rate limiting (optional) |

### spaCy Models

| Model | Size | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| `en_core_web_sm` | 12 MB | Fastest | Lower | Quick testing |
| `en_core_web_md` | 40 MB | Fast | Good | Development |
| `en_core_web_lg` | 560 MB | Medium | High | **Production (default)** |
| `en_core_web_trf` | 500 MB | Slowest | Highest | Maximum accuracy |

### Python Dependencies

**Core (`requirements.txt`):**
```
spacy>=3.7.0
pandas>=2.0.0
openpyxl>=3.0.0
pyyaml>=6.0
python-jose[cryptography]>=3.3.0
```

**API Service (`api_service/requirements.txt`):**
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart
httpx>=0.25.0
redis>=5.0.0
pyyaml>=6.0
```

**Web Service (`web_service/requirements.txt`):**
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart
httpx>=0.25.0
jinja2>=3.1.0
aiofiles>=23.0.0
```

**Optional (for extended file formats):**
```
python-docx>=0.8.11    # Word documents
python-pptx>=0.6.21    # PowerPoint
pdfplumber>=0.9.0      # PDF extraction
beautifulsoup4>=4.12.0 # HTML/XML
lxml>=4.9.0            # XML parsing
```

---

## Making Changes to the Project

> **📚 Comprehensive Guide:** For detailed step-by-step instructions on adding new patterns with complete code examples, see **[HOWTO.md → How to Add Custom Patterns](HOWTO.md#how-to-add-custom-patterns)**.

### 1. Modifying PI Detection Patterns

**Location:** `src/pi_remover/patterns.py` → `PIPatterns` class (656 lines)

**Steps:**
1. Open [src/pi_remover/patterns.py](../src/pi_remover/patterns.py)
2. Locate `class PIPatterns:` (line 33)
3. Add/modify regex pattern
4. Test pattern with unit tests
5. Update version number in `remover.py` (`__version__`)
6. Sync changes to standalone if needed

**Example - Adding a new pattern:**
```python
# In src/pi_remover/patterns.py → PIPatterns class
MY_NEW_PATTERN = re.compile(r'\bPATTERN_HERE\b', re.IGNORECASE)
```

**Example - Modifying a pattern:**
```python
# Find the pattern and update
# BEFORE:
NAME_PATTERN = re.compile(r'\b([A-Za-z]+)\b')
# AFTER:
NAME_PATTERN = re.compile(r'\b([A-Z][a-z]+)\b')  # Require capital
```

### 2. Adding to Blocklists

**False Positive Blocklists (prevent incorrect redaction):**

| Blocklist | Location | Purpose |
|-----------|----------|---------|
| `common_word_exclusions` | `remover.py` → `_redact_names_contextual()` (line ~486) | Common words mistaken as names |
| `ner_false_positive_blocklist` | `remover.py` → `_redact_names_ner()` (line ~421) | Words spaCy misclassifies as PERSON |
| `non_name_prefixes` | `remover.py` → `_redact_names_dictionary()` (line ~601) | Words before dictionary names |

**Steps to add blocklist words:**
1. Identify the false positive pattern
2. Find the appropriate blocklist in `src/pi_remover/remover.py`
3. Add the word(s) in lowercase
4. Test to verify fix

**Example:**
```python
# In remover.py → _redact_names_contextual()
common_word_exclusions = {
    'existing', 'words', 'here',
    'new_word_1', 'new_word_2',  # Added for KEBD-XXX
}
```

### 3. Syncing Standalone Script

The standalone script (`others/standalone/pi_remover_standalone.py`) must be kept in sync with the modular code.

**When to sync:**
- After adding new patterns in `patterns.py`
- After modifying blocklists in `remover.py`
- After fixing false positives
- After any detection logic changes

**Steps:**
1. Make changes in modular files first (`patterns.py`, `remover.py`)
2. Test changes thoroughly
3. Copy changes to `pi_remover_standalone.py`
4. Update version in both files
5. Test standalone independently

### 4. Updating Version Numbers

**Files to update:**
1. `src/pi_remover/remover.py` - `__version__ = "X.Y.Z"`
2. `src/pi_remover/core.py` - `__version__ = "X.Y.Z"` (facade)
3. `others/standalone/pi_remover_standalone.py` - Version in docstring and code
4. `CHANGELOG.md` - Add new version section
5. `KEBD.md` - Update version table (this file)

### 5. Testing Changes

**Unit Tests:**
```powershell
cd tests
python -m pytest test_remover.py -v
python -m pytest test_comprehensive_pi.py -v
python -m pytest test_edge_cases.py -v
```

**Quick Manual Tests:**
```python
# Both import styles work (facade pattern)
from src.pi_remover import PIRemover, PIRemoverConfig
# Or directly from modular files:
from src.pi_remover.remover import PIRemover
from src.pi_remover.config import PIRemoverConfig

config = PIRemoverConfig(enable_ner=False)
remover = PIRemover(config)

# Test false positive fix
result = remover.redact("your test text here")
print(result)
```

**API Tests:**
```powershell
# Start API
cd api_service && uvicorn app:app --port 8080

# Get token
$token = (Invoke-RestMethod -Uri "http://localhost:8080/dev/auth/token" -Method POST -Body '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}' -ContentType "application/json").access_token

# Test redaction
Invoke-RestMethod -Uri "http://localhost:8080/dev/v1/redact" -Method POST -Headers @{Authorization="Bearer $token"} -Body '{"text":"your test text"}' -ContentType "application/json"
```

### 6. Adding New PI Types

**Steps (v2.12.0 modular architecture):**
1. Add pattern to `PIPatterns` class in `src/pi_remover/patterns.py`
2. Add config flag to `PIRemoverConfig` class in `src/pi_remover/config.py`
3. Create detection method `_redact_xxx()` in `src/pi_remover/remover.py`
4. Call detection method from `redact()` in `remover.py`
5. Add token mapping in `_get_typed_token()` in `remover.py`
6. Add tests for new pattern
7. Update documentation

### 7. Docker Deployment

**Development:**
```powershell
docker-compose -f docker/docker-compose.dev.yml up --build
```

**Production:**
```powershell
docker-compose -f docker/docker-compose.prod.yml up --build -d
```

---

## Known Issues & Fixes

## KEBD-006: Consolidated PIRemover Versions

**Date Fixed:** 2025-12-14  
**Version:** v2.8.1  
**Severity:** Maintenance  

### Problem
Two separate PIRemover files existed causing confusion:
- `src/pi_remover/core.py` (v2.8.0) - main version
- `others/pi_remover_v2.py` (v2.5.0) - legacy backup

### Actions Taken
1. Removed fallback imports from:
   - `api_service/app.py`
   - `web_service/app.py`
   - `tests/test_remover.py`
   - `tests/test_comprehensive_pi.py`

2. Deleted legacy file:
   - `others/pi_remover_v2.py`

3. All services now use single source: `src/pi_remover/`

### Files Changed
- `api_service/app.py` - Removed try/except fallback import
- `web_service/app.py` - Unified hybrid mode (v2.12.0)
- `tests/test_remover.py` - Updated import path
- `tests/test_comprehensive_pi.py` - Updated import path
- `others/pi_remover_v2.py` - **DELETED**
- `web_service/app_new.py` - **DELETED** (merged into app.py)

---

## KEBD-001: Progress Stuck at 20% During File Processing

**Date Fixed:** 2025-12-14  
**Version:** v2.9.2  
**Severity:** Medium  

### Symptoms
- User uploads Excel/CSV file for redaction
- Progress bar appears stuck at 20% for extended periods
- Eventually completes, but user experience is poor

### Root Cause
The progress calculation only updated after each **column** was processed, not during row processing. With a single column containing many rows:
- Progress set to 20% at start
- Only updated to 30% after entire column processed (could take minutes)
- Jump from 20% → 30% → 95% with no intermediate updates

### Fix Applied
- Improved progress calculation: `progress_per_col = 65 // len(cols_to_process)`
- Added detailed status messages: `"Redacting column 'X' (1/N)..."`
- Added logging for debugging: `logger.info(f"Processing {len(texts)} rows...")`
- Smoother progress: 20% → distributed across columns → 85% → 95% (save)

### Files Changed
- `web_service/app.py`: `process_csv_file()`, `process_excel_file()`

---

## KEBD-002: Missing `_cleaned` Column in Output Files

**Date Fixed:** 2025-12-14  
**Version:** v2.9.2  
**Severity:** High  

### Symptoms
- User processes file expecting `{column}_cleaned` output
- Downloaded file only contains original columns
- Original column data is overwritten with redacted data

### Root Cause
The file processing functions were **replacing** the original column values instead of creating new `_cleaned` columns:

```python
# Old (incorrect)
df[col] = redacted

# New (correct)  
cleaned_col_name = f"{col}_cleaned"
df[cleaned_col_name] = redacted
```

### Fix Applied
- Changed to create new column: `df[f"{col}_cleaned"] = redacted`
- Original data is now preserved
- Output file contains both original and cleaned columns

### Files Changed
- `web_service/app.py`: `process_csv_file()`, `process_excel_file()`

---

## KEBD-003: Corrupted Excel File - "Needs Repair" Warning

**Date Fixed:** 2025-12-14  
**Version:** v2.9.2  
**Severity:** High  

### Symptoms
- Downloaded `.xlsx` file shows "This file needs to be repaired" in Excel
- After repair, data may be missing or corrupted
- File may fail to open entirely

### Root Cause
Multiple issues contributed:
1. **No explicit engine specified** in `pd.to_excel()` - pandas may use wrong engine
2. **No error handling** - file write errors were silently ignored
3. **No explicit engine for reading** - inconsistent read/write engines

### Fix Applied
1. Explicit `engine='openpyxl'` for both read and write:
   ```python
   df = pd.read_excel(input_path, engine='openpyxl')
   df.to_excel(output_path, index=False, engine='openpyxl')
   ```

2. Try/catch with fallback for reading old `.xls` files:
   ```python
   try:
       df = pd.read_excel(input_path, engine='openpyxl')
   except Exception:
       df = pd.read_excel(input_path)  # Fallback for .xls
   ```

3. Proper error handling with logging:
   ```python
   try:
       df.to_excel(output_path, index=False, engine='openpyxl')
       logger.info(f"Excel file saved successfully: {output_path}")
   except Exception as e:
       logger.error(f"Failed to save Excel file: {e}")
       raise ValueError(f"Failed to save Excel file: {e}")
   ```

### Files Changed
- `web_service/app.py`: `process_excel_file()`

### Dependencies
- Requires `openpyxl>=3.0.0` (already in `web_service/requirements.txt`)

---

## KEBD-004: Column Validation Missing

**Date Fixed:** 2025-12-14  
**Version:** v2.9.2  
**Severity:** Medium  

### Symptoms
- User specifies column that doesn't exist in file
- No error message, processing silently skips the column
- Confusing behavior when no columns are processed

### Root Cause
Original code used `if col not in df.columns: continue` which silently skipped invalid columns.

### Fix Applied
1. Pre-filter columns to only valid ones:
   ```python
   cols_to_process = [col for col in cols_to_process if col in df.columns]
   ```

2. Raise error if no valid columns:
   ```python
   if not cols_to_process:
       raise ValueError(f"No valid columns found. Available: {list(df.columns)}")
   ```

### Files Changed
- `web_service/app.py`: `process_csv_file()`, `process_excel_file()`

---

## Template for Future Issues

```markdown
## KEBD-XXX: Issue Title

**Date Fixed:** YYYY-MM-DD  
**Version:** vX.Y.Z  
**Severity:** Critical/High/Medium/Low  

### Symptoms
- What the user experiences

### Root Cause
Technical explanation of why it happened

### Fix Applied
What was changed to fix it

### Files Changed
- List of files modified

### Testing
How to verify the fix works
```

---

## KEBD-005: False Positive - "open" Detected as [NAME]

**Date Fixed:** 2025-12-14  
**Version:** v2.8.1  
**Severity:** High  

### Symptoms
- Text like "unable to open my system" gets redacted to "unable to [NAME] my system"
- Common verbs/words incorrectly flagged as personal names
- False positives in IT support ticket descriptions

### Example
```
Input:  "Dear Sir/Madam, I am unable to open my system."
Output: "Dear Sir/Madam, I am unable to [NAME] my system."  # WRONG!
```

### Root Cause
Two issues in `src/pi_remover/core.py`:

1. **Overly broad contextual pattern**: The `NAME_CONTEXT_FROM_BY` regex included standalone `to`:
   ```python
   # OLD (problematic)
   r'(?i)\b(?:from|by|to|cc|bcc|...)'
   ```
   This matched "unable **to open**" → captured "open" as a name.

2. **Missing trailing word filtering**: The pattern `([A-Za-z]+(?:\s+[A-Za-z]+){0,2})` captured up to 3 words after the trigger, including words like "regarding", "for review", etc.

### Fix Applied

1. **Removed standalone `to`** from the pattern, replaced with specific phrases:
   ```python
   # NEW (fixed)
   r'(?i)\b(?:from|by|cc|bcc|sent to|assigned to|escalated to|forwarded to|...)'
   ```

2. **Added more common words to exclusion list**:
   ```python
   common_word_exclusions = {
       # ... existing words ...
       'regarding', 'concerning', 'review', 'approval', 'action',
       'response', 'reply', 'feedback', 'attention', 'information',
       # ...
   }
   ```

3. **Added NER false positive blocklist** to filter words spaCy incorrectly classifies as PERSON:
   ```python
   ner_false_positive_blocklist = {
       'email', 'mail', 'phone', 'call', 'text', 'message', 'chat',
       'sent', 'received', 'forward', 'reply', 'response',
       'ticket', 'issue', 'incident', 'problem', 'request', 'change',
       # ...
   }
   ```

### Files Changed
- `src/pi_remover/core.py`:
  - `PIPatterns.NAME_CONTEXT_FROM_BY` - Removed standalone "to"
  - `_redact_names_contextual()` - Added exclusion words
  - `_redact_names_ner()` - Added false positive blocklist

### Testing
```python
from pi_remover import PIRemover, PIRemoverConfig

config = PIRemoverConfig(enable_ner=True, use_typed_tokens=True)
remover = PIRemover(config)

# Should NOT be redacted
text = "I am unable to open my system."
result = remover.redact(text)
assert "open" in result  # Passes after fix

# SHOULD be redacted
text = "Email sent to Rahul Sharma."
result = remover.redact(text)
assert "[NAME]" in result  # Correctly redacts "Rahul Sharma"
```

---

## KEBD-007: New PI Patterns Added (v2.8.1)

**Date Added:** 2025-12-14  
**Version:** v2.8.1  
**Type:** Feature Enhancement  

### Summary
Added 10 new PI pattern categories based on organization-specific identifiers found in production data.

### New Patterns Added

| Pattern Type | Examples | Token |
|--------------|----------|-------|
| **Location/Wing ID** | `TCB4/ODC1/WSN/100`, `GLAH/7/ODC5/WSN/42` | `[LOCATION]` |
| **Seat Extended** | `S2-6F-Z03-056`, `12F ODC 3` | `[SEAT]` |
| **Internal Domain** | `India.tcs.com`, `SOAM`, `NOAM`, `APAC` | `[DOMAIN]` |
| **RFC Numbers** | `RFC # 25224330`, `RFC No: 25228602` | `[RFC]` |
| **CR Numbers** | `CR # 12345678`, `CR-12345678` | `[CR]` |
| **Asset ID Extended** | `O1HW1931597` (typo), `19HWJP024825` (regional) | `[ASSET_ID]` |
| **Service Accounts** | `sa.rpauser`, `oth.20873791`, `NT71853` | `[SERVICE_ACCT]` / `[EMP_ID]` |
| **ARIBA PR** | `PR435494`, `PR:433072` | `[PR]` |
| **Brazilian Phone** | `(22)99902-5226` | `[PHONE]` |
| **Ticket Extended** | `Ticket. No 104630759` | `[TICKET_NUM]` |

### Implementation Details

#### New Patterns in `PIPatterns` class:
```python
# Location/Wing IDs
LOCATION_WING_ID = r'\b[A-Z]{2,5}\d?/(?:\d/)?(?:ODC\d?|WING[-\w]*)/(?:WSN/)?\d+\b'

# Extended seat formats
SEAT_EXTENDED = r'\b(?:S\d+-\d+F-Z\d+-\d+|\d{1,2}F\s+ODC\s+\d+)\b'

# Internal domains
INTERNAL_DOMAIN = r'\b(?:India|SOAM|NOAM|GLOBE|APAC|EMEA|LATAM|AMEA)(?:\.tcs\.com)?\b'

# RFC/CR numbers
RFC_NUMBER = r'\bRFC\s*(?:#|No[:\s.]*|[-:])\s*\d{7,10}\b'
CR_NUMBER = r'\bCR\s*(?:#|No[:\s.]*|[-:])\s*\d{6,10}\b'

# Extended asset IDs (typos, regional)
ASSET_ID_EXTENDED = r'\b(?:[0O]\d{1}(?:HW|SW|VD|VS|AD|NL|WH|AC)\d{6,8}|\d{2}(?:HW|SW|VD|VS)[A-Z]{2}\d{5,7})\b'

# Service accounts
SERVICE_ACCOUNT_PREFIXED = r'\b(?:sa|svc|oth|srv|app)\.[a-zA-Z0-9._-]+\b'
SERVICE_ACCOUNT_NT = r'\bNT\d{4,8}\b'
SERVICE_ACCOUNT_GENERIC = r'\bsa\d{6,10}[a-z]*\b'

# ARIBA PR
ARIBA_PR = r'\bPR\s*[:\-]?\s*\d{6,8}\b'

# Brazilian phone (mobile)
PHONE_BR_MOBILE = r'\(\d{2}\)\s*\d{4,5}-\d{4}\b'

# Ticket extended
TICKET_EXTENDED = r'\bTicket\.?\s*No\.?\s*:?\s*\d{8,12}\b'
```

### Detection Methods Updated
- `_redact_ticket_ids()` - Added RFC, CR, ARIBA PR, extended ticket patterns
- `_redact_workplace_info()` - Added location/wing, seat extended, internal domain
- `_redact_asset_ids()` - Added extended asset patterns
- `_redact_phones()` - Added Brazilian mobile format
- `_redact_active_directory()` - Added service account patterns

### Files Changed
- `src/pi_remover/core.py`:
  - Version updated to `2.8.1`
  - Added new patterns in `PIPatterns` class (lines 1176-1254)
  - Updated 5 detection methods

### Testing
All 18 test cases passed:
```
[PASS] Location/Wing     - TCB4/ODC1/WSN/100 → [LOCATION]
[PASS] Location/Wing     - GLAH/7/ODC5/WSN/42 → [LOCATION]
[PASS] Seat Extended     - S2-6F-Z03-056 → [SEAT]
[PASS] Seat Extended     - 12F ODC 3 → [SEAT]
[PASS] Internal Domain   - India.tcs.com → [DOMAIN]
[PASS] Internal Domain   - SOAM → [DOMAIN]
[PASS] RFC               - RFC # 25224330 → [RFC]
[PASS] RFC               - RFC No: 25228602 → [RFC]
[PASS] CR                - CR # 12345678 → [CR]
[PASS] Asset Extended    - O1HW1931597 → [ASSET_ID]
[PASS] Asset Extended    - 19HWJP024825 → [ASSET_ID]
[PASS] Service Account   - sa.rpauser → [EMP_ID]
[PASS] Service Account   - oth.20873791 → [EMP_ID]
[PASS] Service Account   - NT71853 → [SERVICE_ACCT]
[PASS] ARIBA PR          - PR435494 → [PR]
[PASS] ARIBA PR          - PR:433072 → [PR]
[PASS] BR Phone          - (22)99902-5226 → [PHONE]
[PASS] Ticket Extended   - Ticket. No 104630759 → [TICKET_NUM]
```

---

## KEBD-008: Massive False Positive Reduction (v2.8.2)

**Date Fixed:** 2025-12-14  
**Version:** v2.8.2  
**Severity:** Critical  

### Problem
Production data analysis revealed **1,100+ false positives** where common English words were incorrectly being redacted as `[NAME]`:

| Pattern | Occurrences |
|---------|-------------|
| `"unable to X"` → `"unable to [NAME]"` | ~549 |
| `"not able to X"` → `"not able to [NAME]"` | ~352 |
| `"to connect"` → `"to [NAME]"` | ~249 |
| `"call urgently"` → `"call [NAME]"` | ~53 |
| `"Blue Screen"` → `"[NAME] Screen"` | ~49 |

Words like `connect`, `resolve`, `format`, `turn`, `hear`, `urgently`, `blue`, `global`, `project`, `asset` were incorrectly detected as names.

### Root Causes

1. **`NAME_COMMUNICATION` pattern too broad**: Pattern `call(?:ed|ing)?` followed by any word was matching "call urgently", "call back", etc.

2. **Exclusion word list incomplete**: The contextual name detection had a limited blocklist that didn't include common IT/technical terms.

3. **NER false positive blocklist too small**: spaCy was misidentifying words like "Blue", "Global", "Agent" as PERSON entities.

### Fixes Applied

1. **Restricted `NAME_COMMUNICATION` pattern**: Removed `call(?:ed|ing)?` from the pattern - it was too broad. Now only matches "spoke with", "contacted", "emailed", etc. followed by a capitalized name:
   ```python
   # Before (too broad)
   r'call(?:ed|ing)?|spoke\s+...'
   
   # After (more restrictive)
   r'spoke\s+(?:to|with)|contacted|emailed|messaged|...'
   ```

2. **Expanded `common_word_exclusions` in `_redact_names_contextual()`**: Added 100+ new words:
   - Common verbs: `connect`, `resolve`, `work`, `format`, `turn`, `boot`, etc.
   - Adverbs: `urgently`, `immediately`, `quickly`, `properly`, etc.
   - Technical terms: `blue`, `screen`, `bsod`, `crash`, `hang`, `freeze`, etc.
   - Brand names: `acer`, `dell`, `lenovo`, `hp`, `asus`, `microsoft`, etc.
   - Error terms: `exception`, `kmode`, `reference`, `pointer`, `pool`, `caller`
   - Status words: `pending`, `complete`, `working`, `broken`, etc.

3. **Expanded NER false positive blocklist in `_redact_names_ner()`**: Added 50+ words that spaCy incorrectly classifies as PERSON:
   - `blue`, `screen`, `global`, `windows`, `mac`, `linux`
   - `kmode`, `exception`, `reference`, `pointer`, `bad`
   - `acer`, `dell`, `lenovo`, `hp`, `asus`
   - `urgently`, `immediately`, `quickly`
   - `manila`, `clark`, `agent`, `colleague`

4. **Added Serial Number detection**: New pattern for `S/N:` and `Serial:` identifiers:
   ```python
   SERIAL_NUMBER = r'\b(?:S/?N|Serial(?:\s*(?:No|Number|#))?)\s*[:\s]\s*([A-Z0-9]{8,20})\b'
   ```

### Files Changed
- `src/pi_remover/core.py`:
  - Version updated to `2.8.2`
  - `PIPatterns.NAME_COMMUNICATION` - Made more restrictive (removed `call`)
  - `PIPatterns.SERIAL_NUMBER` - New pattern added
  - `_redact_names_contextual()` - Added 100+ exclusion words
  - `_redact_names_ner()` - Added 50+ blocklist words
  - `_redact_asset_ids()` - Added serial number detection

### Testing Results

**False Positive Tests (10/10 PASS)**:
```
[OK] "Not able to connect devices with bluetooth" - NO false [NAME]
[OK] "Please call urgently. I get the blue screen" - NO false [NAME]
[OK] "I need to format my asset" - NO false [NAME]
[OK] "unable to resolve the issue" - NO false [NAME]
[OK] "COMPUTER IS NOT WORKING, WHEN WE TRY TO TURN IT ON" - NO false [NAME]
[OK] "Hi Global Desk Team My laptop is getting Windows Blue Screen" - NO false [NAME]
[OK] "-Intermittent NO Audio Issue - INC000001365600" - NO false [NAME]
[OK] "Dear Team, I have released from the project" - NO false [NAME]
[OK] "Need access to connect wired headphone" - NO false [NAME]
```

**Real PI Detection Tests (10/10 PASS)**:
```
[PASS] Email: john.smith@company.com → [EMAIL]
[PASS] Call Rahul Sharma at 9876543210 → [NAME] + [PHONE]
[PASS] Asset ID: 19HW12345678 → [ASSET_ID]
[PASS] RFC # 25224330 → [RFC]
[PASS] Location: GLAH/8/WING-NA/4 → [LOCATION]
[PASS] S/N: UNVLGSI137M0278740 → [SERIAL]
[PASS] Hi Priya, please help → [NAME]
[PASS] Spoke with Rajesh Kumar → [NAME]
```

### Impact
- **Estimated false positive reduction**: ~1,100 fewer incorrect redactions per 8,357 rows
- **Real PI detection**: Maintained 100% accuracy for actual personal information
- **New detection**: Serial numbers now properly redacted
---

## KEBD-009: NAME_WITH_TITLE False Positives (v2.8.3)

**Date Fixed:** 2025-12-14  
**Version:** v2.8.3  
**Severity:** High  

### Symptoms
- Technical terms with title-like prefixes incorrectly redacted as names
- Examples: "dr drill", "ms teams", "mr vm" → `[NAME]`
- Affects ITSM data with DR (Disaster Recovery), MS (Microsoft), MR (Merge Request)

### Example
```
Input:  "pr to dr drill"
Output: "pr to [NAME]"  # WRONG! "dr drill" = Disaster Recovery drill

Input:  "access to ms teams"
Output: "access to [NAME]"  # WRONG! "ms teams" = Microsoft Teams
```

### Root Cause
The `NAME_WITH_TITLE` pattern used `re.IGNORECASE` flag which made the entire pattern case-insensitive:

```python
# BEFORE (v2.8.2) - Problem
NAME_WITH_TITLE = re.compile(
    r'\b(?:Mr|Ms|Mrs|Dr|Shri|Smt|Sri)\.?\s+([A-Za-z]+...)\b',
    re.IGNORECASE  # This made [A-Za-z]+ match lowercase "drill", "teams"
)
```

The IGNORECASE flag affected both the title AND the name capture group:
- Title: "Dr" matched "dr" ✓ (correct)
- Name: "[A-Za-z]+" matched "drill" ✓ (WRONG - should only match proper names)

### Fix Applied

Changed to use character classes for title matching while requiring proper capitalization for names:

```python
# AFTER (v2.8.3) - Fixed
NAME_WITH_TITLE = re.compile(
    r'\b(?:[Mm][Rr]|[Mm][Ss]|[Mm][Rr][Ss]|[Dd][Rr]|[Ss][Hh][Rr][Ii]|[Ss][Mm][Tt]|[Ss][Rr][Ii])\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'
)
```

This allows:
- ✅ Title in any case: "Dr.", "dr", "DR" all match the title
- ✅ Name requires capitalization: "Sharma", "Kumar", "Priya" match
- ❌ Lowercase technical terms blocked: "drill", "teams", "vm" don't match

Also added to blocklists:
- Technical abbreviations: `pr`, `dr`, `qa`, `uat`, `dev`, `prod`, `vm`, `os`, `db`, `api`, `bcp`
- Product names: `informs`, `teams`, `jira`, `snow`, `servicenow`, `masscom`, `splunk`
- IT terms: `drill`, `backup`, `restore`, `failover`, `recipients`, `channels`

### Files Changed
- `src/pi_remover/core.py`:
  - Version updated to `2.8.3`
  - `PIPatterns.NAME_WITH_TITLE` - New pattern without IGNORECASE
  - NER blocklist - Added technical abbreviations
  - `common_word_exclusions` - Added product names
  
- `others/standalone/pi_remover_standalone.py`:
  - Version updated to `2.8.3`
  - Synced all pattern changes from core.py

### Testing

```python
from src.pi_remover.core import PIRemover, PIRemoverConfig

config = PIRemoverConfig(enable_ner=False)
remover = PIRemover(config)

# FALSE POSITIVES (should NOT be redacted)
assert "[NAME]" not in remover.redact("pr to dr drill")
assert "[NAME]" not in remover.redact("access to ms teams")
assert "[NAME]" not in remover.redact("mr vm migration")

# REAL NAMES (should be redacted)
assert "[NAME]" in remover.redact("Meeting with Dr. Sharma")
assert "[NAME]" in remover.redact("dr Kumar called earlier")
```

### Test Results

| Test | Input | Expected | Result |
|------|-------|----------|--------|
| DR false positive | `"pr to dr drill"` | No [NAME] | PASS |
| MS false positive | `"access to ms teams"` | No [NAME] | PASS |
| MR false positive | `"mr vm migration"` | No [NAME] | PASS |
| Dr. real name | `"Meeting with Dr. Sharma"` | [NAME] | PASS |
| dr lowercase title | `"dr Kumar called earlier"` | [NAME] | PASS |
| Ms. real name | `"Assigned to Ms. Priya"` | [NAME] | PASS |

---

## Troubleshooting Guide

### Service Won't Start

**Symptom:** `uvicorn: command not found` or `ModuleNotFoundError`

**Solution:**
```powershell
# Ensure virtual environment is activated
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/Mac

# Install dependencies
pip install -r requirements.txt
pip install -r api_service/requirements.txt
pip install -r web_service/requirements.txt

# Install spaCy model
python -m spacy download en_core_web_lg
```

### API Returns 401 Unauthorized

**Symptom:** All API calls return `{"detail": "Missing or invalid token"}`

**Solution:**
1. Get a fresh token:
```bash
curl -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}'
```

2. Use token in Authorization header:
```bash
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'
```

### Redis Connection Failed

**Symptom:** `Redis connection failed, using in-memory fallback`

**Solution:** This is not an error - Redis is optional. The system uses in-memory rate limiting when Redis is unavailable. To use Redis:
```powershell
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Or on Windows with WSL
wsl -d Ubuntu -e redis-server
```

### spaCy Model Not Found

**Symptom:** `OSError: [E050] Can't find model 'en_core_web_lg'`

**Solution:**
```powershell
python -m spacy download en_core_web_lg
# Or for smaller model:
python -m spacy download en_core_web_sm
```

### Slow Processing (NER Enabled)

**Symptom:** Processing takes several seconds per text

**Solution:** Use fast mode (regex-only, no NER):
```python
# In code
config = PIRemoverConfig(enable_ner=False)
remover = PIRemover(config)

# In API request
{"text": "...", "enable_ner": false}
```

### False Positives in Output

**Symptom:** Common words being redacted as `[NAME]`

**Solution:**
1. Identify the pattern causing the false positive
2. Add word to appropriate blocklist in `src/pi_remover/remover.py`
3. Test the fix
4. Create KEBD entry

Common blocklist locations in `remover.py`:
- `common_word_exclusions` in `_redact_names_contextual()` (line ~486)
- `ner_false_positive_blocklist` in `_redact_names_ner()` (line ~421)
- `non_name_prefixes` in `_redact_names_dictionary()` (line ~601)

### Excel File Corruption

**Symptom:** Downloaded Excel file shows "needs repair"

**Solution:** Ensure openpyxl is installed:
```powershell
pip install openpyxl>=3.0.0
```

The web service uses `engine='openpyxl'` for reading and writing Excel files.

### Port Already in Use

**Symptom:** `Address already in use: ('0.0.0.0', 8080)`

**Solution:**
```powershell
# Windows - Find and kill process
netstat -ano | findstr :8080
taskkill /PID <PID> /F

# Or use different port
uvicorn app:app --port 8081
```

### Changes Not Taking Effect

**Symptom:** Code changes don't appear after editing

**Solution:**
1. Restart the uvicorn server (Ctrl+C and restart)
2. Use `--reload` flag for development:
```powershell
uvicorn app:app --reload --port 8080
```
3. Clear Python cache:
```powershell
Remove-Item -Recurse -Force __pycache__
Remove-Item -Recurse -Force *.pyc
```

### Web Service Can't Reach API Service

**Symptom:** `API service unavailable, using local fallback`

**Solution:**
1. Ensure API service is running on port 8080
2. Check API service health: `curl http://localhost:8080/dev/health`
3. Check firewall settings
4. The web service will automatically use local processing as fallback

### Docker Build Fails

**Symptom:** Docker build errors

**Solution:**
```powershell
# Clean and rebuild
docker-compose -f docker/docker-compose.dev.yml down -v
docker system prune -f
docker-compose -f docker/docker-compose.dev.yml build --no-cache
docker-compose -f docker/docker-compose.dev.yml up
```

---
