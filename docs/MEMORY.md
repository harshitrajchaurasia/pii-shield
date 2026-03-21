# PI Removal Project - Complete Memory & Learning Documentation

> **Purpose**: This file captures ALL learnings, decisions, patterns, edge cases, debugging insights, and architectural knowledge accumulated during the development of this PI Removal project. It serves as institutional memory for future development.
>
> **Version:** 2.12.0 | Modular Microservices Architecture

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Domain Understanding](#2-problem-domain-understanding)
3. [Architecture & Design Decisions](#3-architecture--design-decisions)
4. [Detection Layers - Deep Dive](#4-detection-layers---deep-dive)
5. [Regex Patterns - Complete Reference](#5-regex-patterns---complete-reference)
6. [Indian Names Dictionary](#6-indian-names-dictionary)
7. [Context-Aware Detection Logic](#7-context-aware-detection-logic)
8. [Edge Cases & Solutions](#8-edge-cases--solutions)
9. [Performance Optimization](#9-performance-optimization)
10. [Multiprocessing Implementation](#10-multiprocessing-implementation)
11. [spaCy NER Integration](#11-spacy-ner-integration)
12. [File Processing Pipeline](#12-file-processing-pipeline)
13. [Output Format & Tokens](#13-output-format--tokens)
14. [Google Cloud Deployment](#14-google-cloud-deployment)
15. [Debugging Lessons Learned](#15-debugging-lessons-learned)
16. [Testing & Validation](#16-testing--validation)
17. [Known Limitations](#17-known-limitations)
18. [Future Improvements](#18-future-improvements)
19. [Quick Reference Commands](#19-quick-reference-commands)
20. [File Inventory](#20-file-inventory)

---

## 1. Project Overview

### What This Project Does
- **Automatically redacts Personal Information (PI)** from IT support ticket CSV files
- Works **completely offline** (no cloud APIs required for processing)
- Handles **large datasets** (1M+ rows) efficiently with multiprocessing
- Provides **two processing modes**: Fast (regex-only) and Enterprise (with NER)

### Business Context
- IT support tickets contain sensitive personal information
- Manual redaction is time-consuming, error-prone, and doesn't scale
- Compliance requirements demand PII protection before data sharing/analysis
- Solution must be fast, accurate, and auditable

### Key Metrics Achieved
| Metric | Fast Mode | Enterprise Mode |
|--------|-----------|-----------------|
| Speed | ~10,000 rows/sec | ~1,000-2,000 rows/sec |
| Miss Rate | ~0.05% | ~0.02% |
| Workers | 11 (auto-detected) | 11 (auto-detected) |
| Memory | Low | Higher (spaCy model ~400MB) |

---

## 2. Problem Domain Understanding

### Types of PI in IT Support Tickets

| Category | Examples | Frequency |
|----------|----------|-----------|
| **Contact Info** | Emails, phone numbers | Very High |
| **Employee IDs** | 7-digit IDs (1xxxxxx, 2xxxxxx), prefixed accounts | Very High |
| **Names** | Indian names, international names | High |
| **System IDs** | Asset IDs, hostnames, IP addresses | High |
| **Credentials** | Passwords, PINs | Medium |
| **Government IDs** | Aadhaar, PAN, Passport | Low |
| **Financial** | UPI IDs, credit card numbers | Low |

### Data Characteristics
- **Languages**: Primarily English, with some Hindi, Portuguese, Spanish, Chinese text
- **Formats**: Formal tickets, informal notes, email chains, signature blocks
- **Quality**: Inconsistent formatting, typos, mixed case
- **Volume**: 600K+ tickets, 150-500MB files

### Input Files Processed
| File | Rows | Size | Columns |
|------|------|------|---------|
| `rfc_12-12-2025.csv` | ~429,448 | ~154 MB | `description` |
| `ticket_12-12-2025.csv` | ~606,791 | ~502 MB | `Problem Description`, `Solution` |

---

## 3. Architecture & Design Decisions

### Why Multi-Layer Detection?

Single-approach solutions fail because:
1. **Regex alone** misses unstructured names
2. **NER alone** is slow and misses structured data (IDs, phones)
3. **Dictionary alone** has false positives and limited coverage

**Solution**: Combine all approaches in layers, with each layer catching what others miss.

### The 5-Layer Detection Stack

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 5: SIGNATURE BLOCK DETECTION                              │
│ Detects "Thanks & Regards" blocks and redacts entire signature  │
├─────────────────────────────────────────────────────────────────┤
│ Layer 4: SPACY NER (Enterprise only)                            │
│ PERSON, ORG, GPE/LOC entities using en_core_web_lg model        │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: DICTIONARY-BASED NAME DETECTION                        │
│ 350+ Indian names, pattern matching for Firstname Lastname      │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: CONTEXT-AWARE EMPLOYEE ID DETECTION                    │
│ 50+ keywords, table format detection, position-based rules      │
├─────────────────────────────────────────────────────────────────┤
│ Layer 1: REGEX PATTERN DETECTION                                │
│ 30+ compiled patterns for structured data                       │
└─────────────────────────────────────────────────────────────────┘
```

### Processing Order Matters!

The order of pattern application is critical:
1. **Emails first** - Prevents partial matches on domain names
2. **Specific phone patterns before general** - Toll-free before international
3. **Prefixed employee IDs before standalone** - `ad.1234567` before `1234567`
4. **Context-based IDs last** - After other patterns have been applied

### Design Principles Applied

1. **Fail-safe over fail-fast**: Better to over-redact than miss PI
2. **Composability**: Each layer is independent and testable
3. **Performance-first**: Compile patterns once, apply many times
4. **Configurability**: Toggle each detection type on/off
5. **Auditability**: Use typed tokens `[EMAIL]`, `[PHONE]` for tracking

---

## 4. Detection Layers - Deep Dive

### Layer 1: Regex Pattern Detection

**What it catches**: All structured, predictable PI formats
- Emails, phone numbers (10+ patterns)
- Employee IDs with prefixes
- Asset IDs, IP/MAC addresses
- URLs, UPI IDs, credentials
- Government IDs (Aadhaar, PAN)

**Why regex?**
- Extremely fast (compiled patterns)
- Deterministic - same input = same output
- Easy to test and validate
- No external dependencies

### Layer 2: Context-Aware Employee ID Detection

**The Challenge**: 7-digit numbers starting with 1 or 2 could be:
- Employee IDs ✓
- Dates (2023xxxx)
- Phone number fragments
- Random numbers in text

**Solution**: Contextual analysis using:
- **Keyword proximity**: 50+ keywords indicating employee context
- **Position rules**: Start/end of line, after names, in tables
- **Format detection**: Tab-separated, comma-separated lists
- **Token proximity**: After `[NAME]`, `[ASSET_ID]` tokens

### Layer 3: Dictionary-Based Name Detection

**Coverage**: 350+ Indian names including:
- Male first names (150+)
- Female first names (100+)
- Surnames (100+)

**Detection patterns**:
- Two-word names: `Firstname Lastname`
- Names with titles: `Mr. Rahul Sharma`
- ALL CAPS names: `SUMAN KUMAR`

**False positive prevention**:
- Require at least 2-word match for standalone detection
- Skip common words that happen to be names (e.g., "Asha" meaning hope)

### Layer 4: spaCy NER

**Model**: `en_core_web_lg` (~400MB)

**Entities extracted**:
- `PERSON` → `[NAME]`
- `ORG` → `[ORG]` (if in company whitelist)
- `GPE`/`LOC` → `[LOCATION]`

**Optimization**:
- Disabled unnecessary pipeline components (parser, lemmatizer)
- Process in batches for efficiency

### Layer 5: Signature Block Detection

**Trigger phrases**:
```
Thanks, Thank you, Thanks & Regards, Regards,
Best Regards, Warm Regards, Sincerely, Cheers
```

**What gets redacted**: Everything after trigger phrase to end of text

---

## 5. Regex Patterns - Complete Reference

### Email Patterns
```python
EMAIL = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
```

### Phone Number Patterns

```python
# Indian - Direct format
PHONE_91_DIRECT = r'\+91\d{10}\b'  # +919876543210

# Indian - Formatted
PHONE_INDIAN = r'\b(?:\+?91[\s.-]?)?[6-9]\d{9}\b'  # 9876543210, +91 98765 43210
PHONE_INDIAN_FORMATTED = r'\b(?:\+?91[\s.-]?)?[6-9]\d[\s.-]?\d{4}[\s.-]?\d{4}\b'

# Landline
PHONE_LANDLINE = r'\b0\d{2,4}[\s.-]?\d{6,8}\b'  # 022-12345678

# International
PHONE_INTL = r'\b\+\d{1,3}[\s.-]?\d{4,14}\b'

# UK specific
PHONE_UK = r'\b\+?44[\s.-]?\d{4}[\s.-]?\d{6}\b'  # +44 2030 028019

# US format
PHONE_US = r'\b(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b'

# Toll-free
PHONE_TOLLFREE = r'\b1800[\s.-]?\d{3}[\s.-]?\d{4}\b'
```

### Employee ID Patterns

```python
# Prefixed accounts (CRITICAL - catches ad., pr., vo., da., di., etc.)
EMP_ID_PREFIXED = r'(?i)\b(?:ad|iada|cad|ws|pr|sa|oth|vo|da|di)\.(?:[a-z0-9]{4,}|\d{4,})\b'

# Labeled patterns
EMP_ID_LABELED = r'(?i)\b(?:emp(?:loyee)?[\s._-]*(?:id|no)?|eid|uid|user[\s._-]*id?)[\s:._-]*([A-Za-z0-9._-]{4,})\b'

# In parentheses after names
EMP_ID_IN_PARENS = r'\((\d{6,7})\)'  # Name (1234567)

# Standalone 7-digit
EMP_ID_NUMERIC = r'\b[12]\d{6}\b'

# Special patterns
EMP_ID_ADD_REMOVE = r'(?i)\b(?:add|remove|adding|removing)\s+[12]\d{6}\b'
EMP_ID_ASSIGN = r'\b[12]\d{6}\s+assign\b'
EMP_ID_ASSIGNED_TO = r'(?i)assigned\s+to\s+[12]\d{6}\b'
EMP_ID_LDAP = r'(?i)\bCN=[12]\d{6}\b'  # LDAP paths
EMP_ID_PORTUGUESE = r'(?i)\b(?:associad[oa]|asociado)\s+[A-Za-z]+(?:\s+[A-Za-z]+){0,3},?\s*[12]\d{6}\b'
EMP_ID_THIS_IS = r'(?i)this\s+is\s+[A-Za-z]+(?:\s+[A-Za-z]+){0,2},?\s*[12]\d{6}\b'
```

### Asset & System Patterns

```python
# Asset IDs (TCS format)
ASSET_ID = r'(?i)\b\d{1,2}(?:HW|SW|HWCL|NL)\d{6,}\b'  # 01HW1742875, 02SW058325

# IP Addresses
IPV4 = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?::\d{2,5})?\b'
IPV6 = r'\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b'

# MAC Address
MAC = r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b'

# Hostnames (pattern: XXYYSVRZZZZZZZZ)
HOSTNAME = r'\b[A-Z]{2}\d{2}[A-Z]{3}\d{8,}\b'

# URLs
URL = r'https?://[^\s<>"{}|\\^`\[\]]+'

# UPI IDs
UPI = r'\b[a-zA-Z0-9._-]{2,}@(?:upi|paytm|gpay|phonepe|ybl|okhdfcbank|okaxis|oksbi)\b'
```

### Credential & Government ID Patterns

```python
# Passwords in text
PASSWORD = r'(?i)(?:password|pwd|pass)[\s]*(?:is|:|\s)*[\s:=-]*(\S+)'

# Windows paths with usernames
WIN_PATH = r'(?i)[A-Z]:\\Users\\([^\\\s]+)'

# Aadhaar (12 digits)
AADHAAR = r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'

# PAN Card
PAN = r'\b[A-Z]{5}\d{4}[A-Z]\b'

# Passport (Indian)
PASSPORT = r'\b[A-Z]\d{7}\b'
```

### Name Patterns

```python
# With title
NAME_WITH_TITLE = r'\b(?:Mr|Ms|Mrs|Dr|Shri|Smt|Sri)\.?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b'

# Labeled
NAME_LABELED = r'(?i)\b(?:name|contact|user|employee|emp)[\s]*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})'

# "My name is X"
MY_NAME_IS = r'(?i)\bmy name is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})'
```

---

## 6. Indian Names Dictionary

### Male First Names (Sample)
```python
"aakash", "aarav", "abhay", "abhijit", "abhilash", "abhinav", "abhishek",
"aditya", "ajay", "ajit", "akash", "akhil", "akshay", "alok", "aman",
"amit", "amitabh", "amol", "anand", "aniket", "anil", "anirudh",
"ankur", "anmol", "anshul", "anuj", "anupam", "aravind", "arjun", "arun",
"arvind", "ashish", "ashok", "ashwin", "balaji", "bhaskar", "bhavesh",
"chandan", "chandresh", "chirag", "darshan", "deepak", "dev", "devendra",
"dhananjay", "dhruv", "dilip", "dinesh", "gaurav", "gautam", "girish",
"gopal", "govind", "hari", "harish", "hemant", "hitesh", "ishaan",
"jagdish", "jai", "jayant", "jayesh", "jitendra", "karan", "kartik",
"keshav", "kishore", "krishna", "kumar", "lalit", "lokesh", "madhav",
"mahesh", "manoj", "manish", "mayank", "milan", "mohit", "mukesh",
"nandan", "naresh", "naveen", "nikhil", "nilesh", "niraj", "nishant",
"om", "pankaj", "paras", "parth", "pavan", "prakash", "pramod", "pranav",
"prashant", "pratik", "praveen", "priyank", "rahul", "raj", "rajat",
"rajeev", "rajesh", "rajiv", "rakesh", "ramesh", "ravi", "rohit", "sachin",
"sagar", "sahil", "sameer", "sandeep", "sanjay", "sanjiv", "santosh",
"satish", "shailesh", "shashank", "shekhar", "shivam", "shubham", "siddharth",
"sudhir", "sumit", "sundar", "sunil", "suraj", "suresh", "tanmay", "tarun",
"tushar", "uday", "umesh", "vaibhav", "varun", "vijay", "vikas", "vikram",
"vinay", "vineet", "vinod", "vipin", "vishal", "vivek", "yash", "yogesh"
```

### Female First Names (Sample)
```python
"aishwarya", "akshata", "amrita", "ananya", "anju", "ankita", "anushka",
"anusha", "aparna", "archana", "arti", "asha", "bhavna", "chitra",
"deepa", "deepika", "devika", "diya", "divya", "ekta", "garima", "gayatri",
"geeta", "harini", "hema", "isha", "ishita", "jaya", "jyoti", "kajal",
"kamala", "kanchan", "kavita", "keya", "khushi", "kiran", "komal", "kriti",
"lakshmi", "lata", "laxmi", "madhu", "mamta", "manisha", "meena", "meera",
"megha", "menaka", "mira", "mohini", "nandini", "neelam", "neeta", "neha",
"nidhi", "nisha", "nita", "pallavi", "payal", "pooja", "poonam", "prachi",
"pragya", "pratibha", "preeti", "prerna", "priya", "priyanka", "puja",
"radha", "ranjana", "rashmi", "reena", "rekha", "renuka", "renu", "ritu",
"ruchi", "rupal", "sadhana", "sakshi", "sangeeta", "sanjana", "sapna",
"sarita", "savita", "seema", "shanti", "shikha", "shilpa", "shraddha",
"shreya", "shruti", "shweta", "simran", "sita", "smita", "sneha", "sonia",
"sudha", "suman", "sunita", "surbhi", "sushmita", "swati", "tanuja",
"tara", "tripti", "uma", "usha", "vaishali", "vandana", "vani", "varsha",
"vidya", "vimala", "vineeta", "yamini", "vaishnavi", "jayashree", "anwesha"
```

### Surnames (Sample)
```python
"agarwal", "aggarwal", "ahuja", "arora", "bajaj", "banerjee", "basu",
"batra", "bhardwaj", "bhat", "bhatt", "bhattacharya", "bose", "chakraborty",
"chandra", "chatterjee", "chauhan", "chopra", "das", "desai", "deshmukh",
"deshpande", "dey", "dhawan", "dixit", "dutta", "gandhi", "ganguly",
"garg", "ghosh", "gill", "goel", "goyal", "grover", "gupta", "iyer",
"jain", "jha", "joshi", "kakkar", "kapoor", "kaul", "kaur", "khanna",
"kohli", "krishnan", "kulkarni", "kumar", "mahajan", "malhotra", "malik",
"manchanda", "mathur", "mehra", "mehta", "menon", "mishra", "misra",
"mittal", "mukherjee", "murthy", "nair", "nanda", "narang", "narayan",
"natarajan", "nayak", "nehru", "oberoi", "padmanabhan", "pai", "pandey",
"pandit", "parekh", "parikh", "patel", "patil", "prasad", "puri", "rai",
"rajan", "rajagopal", "rajput", "raman", "ramachandran", "rana", "rao",
"rastogi", "rathi", "rawat", "reddy", "roy", "saha", "sahni", "saini",
"sarkar", "saxena", "sen", "sethi", "shah", "sharma", "shastri", "shetty",
"shukla", "singh", "sinha", "soni", "srivastava", "subramanian", "sundaram",
"swamy", "tandon", "thakur", "tiwari", "trivedi", "upadhyay", "varma",
"venkatesh", "verma", "vyas", "yadav", "saswade", "mahapatra", "mapui", "ponnada"
```

---

## 7. Context-Aware Detection Logic

### Employee ID Context Keywords (50+)

```python
emp_keywords = [
    # Direct identifiers
    'emp', 'user', 'id', 'contact', 'teams', 'ping', 'mail', 'email',
    'reach', 'call', '@', 'drop', 'reply', 'me-', 'me on', 'to us',

    # Communication tools
    'gchat', 'g-chat', 'buzz', 'free', 'toll', 'tfn', 'support',

    # Ticket context
    'issue', 'ticket', 'help', 'assist', 'for', 'of', 'behalf',

    # System access
    'enable', 'account', 'domain', 'access', 'asset', 'asociado',
    'numero', 'installation', 'console', 'add', 'remove', 'group',
    'block', 'intune', 'owner', 'primary', 'secondary', 'ltp',

    # Hardware/Software
    'compliant', 'batch', 'machine', 'laptop', 'desktop', 'server',
    'reboot', 'shutdown', 'login', 'below', 'above', 'following',

    # Actions
    'assign', 'associate', 'provide', 'license', 'folder', 'kindly',
    'fingerprint', 'reset', 'unlock', 'please', 'unable', 'system',
    'request', 'userid', 'username', 'path', 'serial', 'password',
    'name', 'asset', 'emp_id', 'phone', 'device'
]
```

### Position-Based Detection Rules

1. **Table Format Detection**:
   - Tab character before/after number
   - Multiple spaces before number
   - Example: `NAME\t1234567\tDEPT`

2. **Name Proximity**:
   - Capitalized word immediately before: `Rahul Sharma 1234567`
   - ALL CAPS before: `KUMAR 2789257`

3. **Line Position**:
   - Start of line (first 10 chars)
   - End of line (last 5 chars)
   - After newline

4. **Token Proximity**:
   - After `[NAME]`: `[NAME], 1234567`
   - After `[ASSET_ID]`: `[ASSET_ID], 1234567`
   - In comma-separated lists: `[EMP_ID], [EMP_ID], 1234567`

---

## 8. Edge Cases & Solutions

### Phone Number Edge Cases

| Edge Case | Pattern | Solution |
|-----------|---------|----------|
| No spaces: `+919876543210` | `PHONE_91_DIRECT` | Direct match |
| UK format: `+442030028019` | `PHONE_UK` | Specific UK pattern |
| UK with spaces: `+44 2030 028019` | `PHONE_UK` with `[\s.-]?` | Flexible separators |
| Toll-free: `1800-267-6563` | `PHONE_TOLLFREE` | Specific pattern |
| Landline: `022-12345678` | `PHONE_LANDLINE` | Leading 0 detection |

### Employee ID Edge Cases

| Edge Case | Example | Solution |
|-----------|---------|----------|
| Prefixed accounts | `ad.2349024`, `vo.1234567` | `EMP_ID_PREFIXED` pattern |
| In parentheses | `Rahul (1234567)` | `EMP_ID_IN_PARENS` pattern |
| Portuguese format | `Associado Felipe, 2203296` | `EMP_ID_PORTUGUESE` pattern |
| LDAP paths | `CN=1860950,OU=Users` | `EMP_ID_LDAP` pattern |
| After "assign" | `1234567 assign to group` | `EMP_ID_ASSIGN` pattern |
| Table format | `NAME\t1234567` | Tab detection in context |
| Comma list | `1234567, 2345678, 3456789` | Token proximity check |

### Name Edge Cases

| Edge Case | Example | Solution |
|-----------|---------|----------|
| ALL CAPS | `SUMAN KUMAR` | Caps pattern + dictionary |
| With title | `Dr. Rahul Sharma` | `NAME_WITH_TITLE` pattern |
| Single word in context | `Contact: Rahul` | `NAME_LABELED` pattern |
| Non-Indian names | `John Smith` | spaCy NER fallback |

### Known Problem: UK Phone `+442030028019`

**Issue discovered during debugging**:
- The number `+442030028019` was not being redacted in output
- Debug prints confirmed regex matched the number
- Isolation test (`debug_regex_2.py`) confirmed regex works

**Root cause analysis needed**:
- Check order of regex application in `clean_text` method
- Verify `cleaned_text` variable is being updated correctly
- Check if another pattern is overwriting the redaction

**Solution patterns tried**:
```python
# Pattern 1: Word boundary
r'\b\+?44[\s.-]?\d{4}[\s.-]?\d{6}\b'

# Pattern 2: Negative lookahead (to avoid trailing digits)
r'(?<!\w)(?:\+?44|0)(?:\s+)?\d{10}(?!\d)'

# Pattern 3: More flexible
r'\+?44[\s.-]?\d{10}'
```

---

## 9. Performance Optimization

### Pattern Compilation

```python
# SLOW: Compiling on every call
def redact(text):
    return re.sub(r'pattern', '[REDACTED]', text)

# FAST: Pre-compiled patterns
PATTERN = re.compile(r'pattern')
def redact(text):
    return PATTERN.sub('[REDACTED]', text)
```

### Chained Substitution

```python
# Apply all patterns in sequence
def clean_text(self, text):
    for pattern, replacement in self.patterns:
        text = pattern.sub(replacement, text)
    return text
```

### Batch Processing

```python
# Process DataFrame in chunks
for chunk in pd.read_csv(file, chunksize=5000):
    chunk['cleaned'] = chunk['text'].apply(remover.redact)
    # Write chunk to output
```

### Memory Optimization

- Use generators for large files
- Clear DataFrames after processing chunks
- Disable unnecessary spaCy pipeline components

---

## 10. Multiprocessing Implementation

### Worker Pool Setup

```python
import multiprocessing as mp

NUM_WORKERS = max(1, mp.cpu_count() - 1)  # Leave 1 CPU for system

def process_chunk(chunk_data):
    idx, df, columns = chunk_data
    # Process dataframe
    return df

with mp.Pool(NUM_WORKERS) as pool:
    results = pool.map(process_chunk, chunks)
```

### Worker Initialization

```python
# Global variable for worker state
_worker_remover = None

def _init_worker(config_dict):
    global _worker_remover
    _worker_remover = PIRemover(config_dict)

# Initialize workers with shared state
with mp.Pool(NUM_WORKERS, initializer=_init_worker, initargs=(config,)) as pool:
    results = pool.map(process_chunk, chunks)
```

### Windows Compatibility

```python
if __name__ == "__main__":
    mp.freeze_support()  # Required for Windows
    main()
```

### Chunking Strategy

```python
chunk_size = max(1000, len(df) // num_workers)
chunks = [df[i:i+chunk_size].copy() for i in range(0, len(df), chunk_size)]
```

---

## 11. spaCy NER Integration

### Model Loading

```python
import spacy

nlp = spacy.load("en_core_web_lg")
# Disable unnecessary components for speed
nlp.disable_pipes(["parser", "lemmatizer"])
```

### Entity Extraction

```python
def extract_entities(text):
    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "LOC"}:
            entities.append((ent.text, ent.label_, ent.start_char, ent.end_char))
    return entities
```

### Position-Based Replacement

```python
def redact_with_ner(text):
    doc = nlp(text)
    # Sort entities by position (reverse) to maintain correct positions
    entities = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
    for ent in entities:
        if ent.label_ == "PERSON":
            text = text[:ent.start_char] + "[NAME]" + text[ent.end_char:]
    return text
```

### Installation

```bash
pip install spacy
python -m spacy download en_core_web_lg  # ~400MB download
```

---

## 12. File Processing Pipeline

### Input → Output Flow

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Input CSV      │────▶│    PIRemover     │────▶│   Output CSV     │
│                  │     │   (Multi-layer)  │     │                  │
│  - description   │     │                  │     │  - description   │
│  - Problem Desc  │     │  1. Load chunk   │     │  - desc_cleaned  │
│  - Solution      │     │  2. Apply redact │     │  - ProbDesc_cln  │
│                  │     │  3. Write chunk  │     │  - Sol_cleaned   │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

### Chunk-Based Processing

```python
def process_csv(input_path, output_path, columns, config, chunksize=5000):
    first_chunk = True
    for chunk in pd.read_csv(input_path, chunksize=chunksize):
        # Process each column
        for col in columns:
            chunk[f"{col}_cleaned"] = chunk[col].apply(remover.redact)

        # Write to output
        mode = 'w' if first_chunk else 'a'
        header = first_chunk
        chunk.to_csv(output_path, mode=mode, header=header, index=False)
        first_chunk = False
```

### Progress Tracking

```python
from tqdm import tqdm

with tqdm(total=total_rows, desc="Processing") as pbar:
    for chunk in pd.read_csv(input_path, chunksize=chunksize):
        process_chunk(chunk)
        pbar.update(len(chunk))
```

---

## 13. Output Format & Tokens

### Replacement Tokens

| PI Type | Token | Examples Matched |
|---------|-------|------------------|
| Email | `[EMAIL]` | `user@domain.com` |
| Phone | `[PHONE]` | `+91 9876543210`, `+44 2030 028019` |
| Employee ID | `[EMP_ID]` | `1234567`, `ad.2349024` |
| Asset ID | `[ASSET_ID]` | `01HW1742875` |
| IP Address | `[IP]` | `192.168.1.1` |
| MAC Address | `[MAC]` | `00:1A:2B:3C:4D:5E` |
| Hostname | `[HOSTNAME]` | `ER06SVR40615265` |
| URL | `[URL]` | `https://example.com/path` |
| Name | `[NAME]` | `Rahul Sharma`, `Mr. Kumar` |
| Organization | `[ORG]` | `TCS`, `EDF Energy` |
| Location | `[LOCATION]` | `UK London`, `Kolkata` |
| Credential | `[CREDENTIAL]` | `password is: TempPass@123` |
| Aadhaar | `[AADHAAR]` | `1234 5678 9012` |
| PAN | `[PAN]` | `ABCDE1234F` |
| UPI | `[UPI]` | `user@paytm` |
| Username | `[USERNAME]` | In Windows paths |
| Signature | `[SIGNATURE]` | `Thanks & Regards, Name...` |

### Configuration Options

```python
config = PIRemoverConfig(
    use_typed_tokens=True,   # [NAME], [EMAIL], etc.
    # OR
    use_typed_tokens=False,  # All become [REDACTED]
    replacement_token="[REDACTED]"
)
```

### Output File Naming

```
# Fast solution
rfc_cleaned_fast_YYYYMMDD_HHMMSS.csv
ticket_cleaned_fast_YYYYMMDD_HHMMSS.csv

# Enterprise solution
rfc_cleaned_enterprise_YYYYMMDD_HHMMSS.csv
ticket_cleaned_enterprise_YYYYMMDD_HHMMSS.csv
```

---

## 14. Three Deployment Modes (v2.4 Architecture)

### Unified Architecture Principle

**Key Decision**: All three deployment modes share the **same core detection engine** (`src/pi_remover/`).
This ensures:
1. **No code duplication** - Fix a bug once, fixed everywhere
2. **Consistent behavior** - Same detection across all interfaces
3. **Easy maintenance** - Single source of truth

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INTERFACE LAYERS                                 │
├─────────────────┬─────────────────────┬─────────────────────────────────┤
│   MODE 1        │     MODE 2          │         MODE 3                  │
│   CLI Script    │    Web Service      │      LLM Gateway API            │
│                 │                     │                                 │
│  python         │  FastAPI + HTML     │   FastAPI (Docker)              │
│  -m pi_remover  │  File Upload UI     │   REST endpoint                 │
│  -i file.csv    │  Text Input UI      │   Ultra-low latency             │
│  --fast         │  Cloud Run          │   LLM-safe proxy                │
└────────┬────────┴──────────┬──────────┴──────────────┬──────────────────┘
         │                   │                         │
         └───────────────────┼─────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      CORE ENGINE (v2.12.0 Modular)                       │
│                     src/pi_remover/ (9 modules)                         │
│                                                                          │
│   Enhancements for API support (v2.4):                                  │
│   ├── redact_with_details() → RedactionResult with confidence           │
│   ├── redact_batch() → Efficient batch processing                       │
│   ├── health_check() → API health endpoints                             │
│   └── RedactionResult dataclass with positions and confidence           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Mode 1: CLI Script (File Processing)

**Purpose**: Process CSV, Excel, JSON, TXT files from command line
**Status**: ✅ Fully Implemented
**File**: `src/pi_remover/`

```bash
# Fast mode (~10K rows/sec)
python -m pi_remover -i data.csv -c "Description" --fast

# Full mode with NER (~1K rows/sec, most accurate)
python -m pi_remover -i data.csv -c "Description"
```

### Mode 2: Web Service (User Interface)

**Purpose**: Web-based file upload and text input for non-technical users
**Status**: 🔨 Implementation Ready
**Directory**: `web_service/`

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                      Google Cloud Run                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    HTML Frontend                          │   │
│  │  - File upload (drag-and-drop)                           │   │
│  │  - Text input area                                        │   │
│  │  - Column selection (for tabular data)                   │   │
│  │  - Fast/Full mode toggle                                  │   │
│  │  - Download button                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                             │                                    │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    FastAPI Backend                        │   │
│  │  POST /upload      - Upload file, return columns          │   │
│  │  POST /process     - Process file with selected columns   │   │
│  │  POST /redact-text - Redact text directly                 │   │
│  │  GET  /download    - Download processed file              │   │
│  │  GET  /health      - Health check                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Files to create**:
- `web_service/app.py` - FastAPI backend
- `web_service/templates/index.html` - HTML frontend
- `web_service/Dockerfile` - Container image
- `web_service/docker-compose.yml` - Local development

### Mode 3: LLM Gateway API (Critical)

**Purpose**: Real-time PI removal before sending data to LLMs
**Status**: 🔨 Implementation Ready
**Directory**: `api_service/`

**Why This Matters**:
- Any system communicating with LLMs MUST first remove PI
- This service acts as a gateway/proxy
- Ultra-low latency required (<50ms for real-time chat)
- Must work offline and be self-contained

**Architecture**:
```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐
│ Application │────▶│ PI Gateway API  │────▶│    LLM      │
│             │     │                 │     │  (Claude,   │
│ "Contact    │     │ Removes PI      │     │   GPT,      │
│  john@..."  │     │ before sending  │     │   etc.)     │
└─────────────┘     │                 │     └─────────────┘
                    │ "Contact        │
                    │  [EMAIL]..."    │
                    └─────────────────┘
```

**API Endpoints**:
```
POST /v1/redact       - Single text redaction
POST /v1/redact/batch - Batch text redaction
GET  /health          - Health check with metrics
```

**Request/Response**:
```json
// Request
POST /v1/redact
{
    "text": "Contact john@example.com at +91 9876543210",
    "include_details": false
}

// Response
{
    "redacted_text": "Contact [EMAIL] at [PHONE]",
    "request_id": "uuid-v4",
    "processing_time_ms": 8.5
}
```

**Files to create**:
- `api_service/app.py` - FastAPI application
- `api_service/Dockerfile` - Minimal Docker image (no spaCy)
- `api_service/requirements.txt` - Minimal dependencies
- `api_service/docker-compose.yml` - Local testing

**Docker Image Requirements**:
- Base: `python:3.11-slim`
- No spaCy (Fast mode only for <50ms latency)
- Dependencies: fastapi, uvicorn, pydantic
- Size target: <100MB

**Performance Targets**:
| Metric | Target |
|--------|--------|
| p50 latency | <20ms |
| p95 latency | <50ms |
| p99 latency | <100ms |
| Throughput | 1000+ req/sec |

### Core Library Enhancements (v2.4)

To support API use cases, `src/pi_remover/` needs these additions:

```python
# New dataclasses
@dataclass
class Redaction:
    original: str           # Original text that was redacted
    replacement: str        # Replacement token (e.g., "[EMAIL]")
    pi_type: str           # Type of PI (EMAIL, PHONE, NAME, etc.)
    start: int             # Start position in original text
    end: int               # End position in original text
    confidence: float      # Confidence score (0.0 - 1.0)
    detection_method: str  # How it was detected (regex, ner, dictionary, context)

@dataclass
class RedactionResult:
    redacted_text: str           # Final redacted text
    redactions: List[Redaction]  # List of all redactions made
    processing_time_ms: float    # Processing time in milliseconds

# New methods on PIRemover
def redact_with_details(self, text: str) -> RedactionResult:
    """Returns detailed redaction info for API responses."""

def redact_batch(self, texts: List[str]) -> List[str]:
    """Efficient batch processing for multiple texts."""

def health_check(self) -> dict:
    """Returns health status for API health endpoints."""
```

### Directory Structure (v2.4)

```
PI_Removal/
├── src/pi_remover/          # Core library (USE THIS)
├── config.yaml               # Configuration file
├── requirements.txt          # Python dependencies
│
├── api_service/              # Mode 3: LLM Gateway API
│   ├── app.py                # FastAPI application
│   ├── Dockerfile            # Docker container (no spaCy)
│   ├── requirements.txt      # Minimal: fastapi, uvicorn
│   ├── docker-compose.yml    # Local testing
│   └── README.md             # API documentation
│
├── web_service/              # Mode 2: Web UI
│   ├── app.py                # FastAPI backend
│   ├── templates/
│   │   └── index.html        # HTML frontend
│   ├── static/               # CSS, JS
│   ├── Dockerfile            # Docker container
│   ├── docker-compose.yml    # Local testing
│   └── cloudbuild.yaml       # GCP deployment
│
├── tests/                    # Test suite
│   ├── test_remover.py       # Core functionality tests
│   ├── test_patterns.py      # Regex pattern tests
│   └── test_api.py           # API endpoint tests
│
├── output/                   # Processed files
└── docs/                     # Documentation
    ├── CLAUDE.md
    ├── README.md
    ├── MEMORY.md
    ├── API_REFERENCE.md
    ├── GOOGLE_CLOUD.md
    └── CHAT_SERVICE.md
```

---

## 14a. Google Cloud Deployment

### Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    API Layer    │────▶│    Workers      │
│  (Cloud Run)    │     │  (Cloud Run)    │     │  (Cloud Run)    │
│                 │     │                 │     │                 │
│  - File upload  │     │  - /upload      │     │  - Fast Worker  │
│  - Column select│     │  - /process     │     │  - NER Worker   │
│  - NER toggle   │     │  - /status      │     │                 │
│  - Download     │     │  - /download    │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │                       │
         └──────────────────────┼───────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Cloud Storage  │  │     Pub/Sub     │  │    Firestore    │
│  (File Storage) │  │   (Job Queue)   │  │  (Job Metadata) │
│                 │  │                 │  │                 │
│  - /uploads/    │  │ pi-removal-jobs │  │  - job_id       │
│  - /processed/  │  │                 │  │  - status       │
└─────────────────┘  └─────────────────┘  │  - progress     │
                                          └─────────────────┘
```

### Cost Estimates

| Usage Level | Files/Month | Est. Cost |
|-------------|-------------|-----------|
| Light | 10 files, 50MB avg | $0-2 (free tier) |
| Medium | 100 files, 100MB avg | $5-15 |
| Heavy | 500 files, 200MB avg | $30-60 |
| Enterprise | 2000+ files, 500MB avg | $100-250 |

### Key GCP Services

| Service | Purpose | Configuration |
|---------|---------|---------------|
| Cloud Run | API, Frontend, Workers | Auto-scaling, pay-per-use |
| Cloud Storage | File storage | Lifecycle rules for auto-cleanup |
| Pub/Sub | Job queue | Async processing |
| Firestore | Job metadata | Real-time status updates |

### Worker Configurations

| Worker | RAM | CPU | Speed | Use Case |
|--------|-----|-----|-------|----------|
| Fast | 512MB-1GB | 1 | ~10K rows/sec | Default |
| NER | 4GB | 2 | ~500-1K rows/sec | When NER enabled |

### API Endpoints

```
POST /upload     - Upload CSV, get columns
POST /process    - Start processing job
GET  /status/:id - Get job status/progress
GET  /download/:id - Get download URL
DELETE /job/:id  - Delete job and files
```

---

## 15. Debugging Lessons Learned

### Lesson 1: Regex Debugging

**Problem**: Pattern matches in isolation but not in full pipeline

**Debug approach**:
1. Create isolated test script (`debug_regex_2.py`)
2. Test exact string with exact pattern
3. Add debug prints showing match/no-match
4. Compare compiled vs raw patterns

```python
# Debug script example
import re
pattern = re.compile(r'\+?44[\s.-]?\d{10}')
test = "UK DID : +442030028019"
match = pattern.search(test)
print(f"Match: {match}")  # Verify pattern works
print(f"Replaced: {pattern.sub('<PHONE>', test)}")
```

### Lesson 2: Order of Operations

**Problem**: Earlier pattern undoing later pattern's work

**Solution**: Order patterns from most specific to least specific:
1. Full patterns first (e.g., complete phone numbers)
2. Partial patterns later (e.g., digit sequences)
3. Context-based patterns last

### Lesson 3: Word Boundaries

**Problem**: `\b` doesn't work well with special characters like `+`

**Solution**: Use negative lookbehind/lookahead:
```python
# Instead of:
r'\b\+44\d{10}\b'

# Use:
r'(?<!\w)\+44\d{10}(?!\d)'
```

### Lesson 4: Variable Assignment

**Problem**: Regex matches but result not saved

**Check**: Ensure the substituted text is assigned back:
```python
# WRONG - result discarded
pattern.sub('[PHONE]', text)

# RIGHT - result saved
text = pattern.sub('[PHONE]', text)
```

### Lesson 5: Multiprocessing State

**Problem**: Worker processes don't share state

**Solution**: Use initializer function to set up worker state:
```python
def _init_worker(config):
    global _worker_instance
    _worker_instance = PIRemover(config)
```

---

## 16. Testing & Validation

### Unit Testing Patterns

```python
def test_email_detection():
    remover = PIRemover()
    assert remover.redact("email: test@domain.com") == "email: [EMAIL]"

def test_phone_detection():
    remover = PIRemover()
    assert remover.redact("+919876543210") == "[PHONE]"
    assert remover.redact("+442030028019") == "[PHONE]"

def test_emp_id_detection():
    remover = PIRemover()
    assert remover.redact("ad.2349024") == "[EMP_ID]"
    assert remover.redact("Contact: 1234567") == "Contact: [EMP_ID]"
```

### Validation Script

```python
# Check for missed employee IDs in output
import pandas as pd
import re

df = pd.read_csv('output/ticket_cleaned.csv')
pattern = re.compile(r'\b[12]\d{6}\b')

missed = 0
for idx, row in df.iterrows():
    text = str(row.get('Problem Description_cleaned', ''))
    if pattern.search(text):
        missed += 1
        print(f"Row {idx}: {text[:100]}")

print(f"Miss rate: {missed/len(df)*100:.4f}%")
```

### Grep Verification (PowerShell)

```powershell
# Check if specific pattern still exists in output
Select-String -Path "output\ticket_cleaned.csv" -Pattern "\+442030028019"

# Count remaining phone patterns
(Select-String -Path "output\*.csv" -Pattern "\+\d{10,}" | Measure-Object).Count
```

---

## 17. Known Limitations

### Detection Limitations

1. **Novel name formats**: Unusual spellings not in dictionary
2. **Context ambiguity**: 7-digit numbers without clear context
3. **Code/technical content**: Regex patterns in code may be misidentified
4. **Embedded in URLs**: Email/phone in query strings may be missed
5. **Image/PDF content**: Only processes text, not embedded images

### Performance Limitations

1. **Memory with NER**: Large files + NER can exhaust memory
2. **Cold start**: First request slower due to model loading
3. **Single-threaded NER**: spaCy model not easily parallelized

### Accuracy Trade-offs

| Setting | False Positives | False Negatives |
|---------|-----------------|-----------------|
| Conservative | Low | Higher |
| Aggressive | Higher | Low |
| Balanced (current) | Medium | Low |

---

## 18. Future Improvements

### ✅ Implemented (v2.1 - December 2025)

- [x] **Excel file support** (.xlsx, .xls) via `process_file()` function
- [x] **YAML configuration file** (`config.yaml`) for externalized settings
- [x] **Per-row error handling** - single bad row won't crash entire job
- [x] **More international phone patterns** - Australia (+61), Germany (+49), France (+33), Singapore (+65), UAE (+971), Brazil (+55), Japan (+81), China (+86)
- [x] **Exclusion/whitelist support** - exclude specific emails, phone prefixes, domains, terms
- [x] **YAML config loader** - `load_config_from_yaml()` function

### ✅ Implemented (v2.2 - December 2025)

- [x] **Fix UK phone number edge case** (`+442030028019`) - added `PHONE_UK_DIRECT` pattern
- [x] **Expand names dictionary** - added 100+ South Indian, Bengali, Punjabi, and International names
- [x] **CLI interface** - full command-line interface with argparse
- [x] **Audit reports** - generate JSON/HTML reports of redactions
- [x] **Input validation** - validate files, columns, and config before processing

### Short-term (Pending)

- [ ] Add confidence scoring for each redaction
- [ ] Add dry-run mode to preview redactions without saving

### Medium-term

- [ ] Build interactive correction UI (web-based)
- [ ] Add diff view showing original vs redacted

### Long-term

- [ ] Train custom NER model on IT support data
- [ ] Add support for Hindi text
- [ ] Implement federated learning for pattern improvement
- [ ] Build MLOps pipeline for model updates

---

## 18a. Version 2.1 Changes Summary

### New Features

| Feature | File | Description |
|---------|------|-------------|
| Excel Support | `src/pi_remover/`, `run_fast.py` | Process .xlsx/.xls files via `process_file()` |
| YAML Config | `config.yaml` | Externalized configuration with all options |
| Config Loader | `src/pi_remover/` | `load_config_from_yaml()` function |
| Safe Apply | Both files | Per-row try/except prevents job failures |
| Int'l Phones | Both files | 12+ new country patterns (AU, DE, FR, SG, UAE, BR, JP, CN) |
| Exclusions | `src/pi_remover/` | Skip specified emails, phones, domains, terms |

### New Configuration Fields (PIRemoverConfig)

```python
# Error handling
continue_on_error: bool = True
error_log_file: str = "pi_remover_errors.log"
include_original_in_log: bool = False
max_errors: int = 0

# Exclusions / Whitelist
excluded_emails: Set[str] = set()  # e.g., {"support@example.com"}
excluded_phones: Set[str] = set()  # e.g., {"1800"} for prefixes
excluded_terms: Set[str] = set()   # e.g., {"ServiceNow", "JIRA"}
excluded_domains: Set[str] = set() # e.g., {"example.com"}
```

### Usage Examples

```python
# Load from YAML config (v2.12.0 modular imports)
from pi_remover import PIRemover, PIRemoverConfig
from pi_remover.config import load_config_from_yaml
from pi_remover.processors import process_file

config = load_config_from_yaml("config.yaml")
process_file("input.xlsx", "output.xlsx", ["Description"], config)

# Process Excel file
process_file("data.xlsx", "data_cleaned.xlsx", ["Problem Description"])

# With custom exclusions
config = PIRemoverConfig(
    excluded_emails={"support@company.com"},
    excluded_phones={"1800", "+1-800"},
    excluded_terms={"ServiceNow", "JIRA"}
)
```

---

## 18b. Version 2.2 Changes Summary (December 2025)

### New Features

| Feature | File | Description |
|---------|------|-------------|
| **CLI Interface** | `src/pi_remover/` | Full command-line interface with argparse |
| **Audit Reports** | `src/pi_remover/` | Generate JSON/HTML reports of redactions |
| **Input Validation** | `src/pi_remover/` | Validate files, columns, and config before processing |
| **Expanded Names** | Both files | 100+ new names (South Indian, Bengali, Punjabi, International) |
| **UK Phone Fix** | Both files | Fixed `+442030028019` edge case with `PHONE_UK_DIRECT` pattern |

### CLI Usage

```bash
# Show help
python -m pi_remover --help

# Process single file
python -m pi_remover -i data.csv -o cleaned.csv -c "Description"

# Process Excel with audit report
python -m pi_remover -i tickets.xlsx --columns "Problem" "Solution" --audit --audit-format html

# Fast mode (no NER)
python -m pi_remover -i data.csv --no-ner --workers 8

# Use YAML config
python -m pi_remover --config config.yaml -i data.csv
```

### Audit Report Example

```bash
# Generate JSON audit report
python -m pi_remover -i tickets.csv -c "Description" --audit

# Generate HTML audit report
python -m pi_remover -i tickets.csv -c "Description" --audit --audit-format html
```

The audit report includes:
- Processing statistics (rows, time, speed)
- Redaction counts by type (EMAIL, PHONE, NAME, etc.)
- Error count
- Input/output file metadata

### Validation Functions

```python
# Validation with modular architecture (v2.12.0)
from pi_remover import PIRemover, PIRemoverConfig
from pi_remover.utils import validate_file, validate_columns

# Validate file exists and is supported type
path = validate_file("data.csv")

# Validate columns exist in DataFrame
valid_cols = validate_columns(df, ["Col1", "Col2"])

# Configuration is validated in PIRemoverConfig dataclass
config = PIRemoverConfig()
```

### Expanded Names Dictionary

Added names for:
- **South Indian**: Venkat, Karthik, Murali, Senthil, Shankar, etc.
- **Bengali**: Arnab, Partha, Prasenjit, Rituparna, etc.
- **Punjabi**: Gurpreet, Harjeet, Manpreet, Navjot, etc.
- **International**: David, Michael, James, Mary, Patricia, Smith, Johnson, etc.

---

## 19. Quick Reference Commands

### Run Fast Processing
```bash
python run_fast.py
```

### Run Enterprise Processing (with NER)
```bash
# First-time setup
pip install spacy
python -m spacy download en_core_web_lg

# Run
python run_pi_removal.py
```

### Run with CLI
```bash
# Single file with audit
python -m pi_remover -i data.csv -c "Description" --audit

# Excel file, no NER
python -m pi_remover -i data.xlsx --no-ner --audit-format html
```

### Check Output for Missed Patterns
```powershell
# Check for remaining phone numbers
Select-String -Path "output\*.csv" -Pattern "\+\d{10,}"

# Check for remaining employee IDs
Select-String -Path "output\*.csv" -Pattern "\b[12]\d{6}\b"

# Check specific pattern
Select-String -Path "output\ticket_cleaned*.csv" -Pattern "\+442030028019"
```

### Validate Sample Output
```powershell
Get-Content "output\ticket_cleaned*.csv" | Select-Object -First 20
```

### Debug Regex Pattern
```python
import re
pattern = re.compile(r'YOUR_PATTERN')
test_string = "your test string"
print(f"Match: {pattern.search(test_string)}")
print(f"Result: {pattern.sub('[REPLACED]', test_string)}")
```

---

## 20. File Inventory (v2.3 - Unified)

### Primary Files (Use These)

| File | Purpose | Mode |
|------|---------|------|
| `src/pi_remover/` | **UNIFIED PI Remover** - Use this for all processing | Full + Fast modes |
| `config.yaml` | YAML configuration file | All options |
| `requirements.txt` | Python dependencies | pip install |

### How to Use

```bash
# Full mode (NER enabled - most accurate)
python -m pi_remover -i data.csv -c "Description"

# Fast mode (~10x faster)
python -m pi_remover -i data.csv -c "Description" --fast

# With config file
python -m pi_remover --config config.yaml -i data.csv
```

### Legacy Files (Deprecated)

| File | Purpose | Status |
|------|---------|--------|
| `run_fast.py` | Old fast solution | ⚠️ Use `--fast` flag instead |
| `run_pi_removal.py` | Old NER solution | ⚠️ Use `src/pi_remover/` instead |
| `pi_remover.py` | Legacy version | ⚠️ Deprecated |
| `clean.py` | Original regex-only | ⚠️ Deprecated |

### Supporting Files

| File | Purpose | Status |
|------|---------|--------|
| `debug_regex_2.py` | Regex debugging utility | 🔧 Debug tool |
| `test_comparison.py` | Solution comparison tests | 🧪 Testing |
| `test_regex.py` | Regex pattern tests | 🧪 Testing |

### Documentation

| File | Purpose |
|------|---------|
| `MEMORY.md` | Complete project learnings (this file) |
| `CHAT_SERVICE.md` | Chat service deployment guide |
| `CLAUDE.md` | Project context and background |
| `GOOGLE_CLOUD.md` | GCP deployment reference |
| `README_PI_Remover.md` | User documentation |
| `LLM_Orchestration_Guide.md` | LLM orchestration guide |

### Output Directory

```
output/
├── data_cleaned.csv           # Processed output
├── data_audit.json            # Audit report (JSON)
├── data_audit.html            # Audit report (HTML)
└── pi_remover.log             # Processing log
```

---

## Appendix A: Complete Configuration Reference (v2.3)

```python
@dataclass
class PIRemoverConfig:
    # Detection layers
    enable_ner: bool = True              # spaCy NER for names
    enable_regex: bool = True            # Pattern-based detection
    enable_dictionaries: bool = True     # Custom word lists
    enable_context_rules: bool = True    # Signature blocks, etc.

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

    # Output format
    replacement_token: str = "[REDACTED]"
    use_typed_tokens: bool = True        # [NAME], [EMAIL], etc.

    # Performance
    batch_size: int = 1000
    show_progress: bool = True
    num_workers: int = 11                # Auto: max(1, cpu_count() - 1)
    use_multiprocessing: bool = True
```

---

## Appendix B: Transformation Examples

### Before:
```
I need to migrate my TCS email from MS Exchange to GWS, unfortunately,
I am not able to send email to - gws.support@tcs.com
I am based in TCS UK London and can be reached via +44 7405186893.
My employee ID is 1321823 and asset ID is 01HW1742875.

Thanks & Regards,
Vaishnavi Saswade
Employee ID: 1321823
```

### After:
```
I need to migrate my TCS email from MS Exchange to GWS, unfortunately,
I am not able to send email to - [EMAIL]
I am based in TCS UK London and can be reached via [PHONE].
My employee ID is [EMP_ID] and asset ID is [ASSET_ID].

[SIGNATURE]
```

---

## Appendix C: Google Cloud Security & Operations

### Security Best Practices

#### 1. Authentication & Authorization
```bash
# Restrict API access with IAP (Identity-Aware Proxy)
gcloud run services update pi-remover-api \
    --ingress=internal-and-cloud-load-balancing
```

#### 2. CORS Configuration (Production)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.run.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

#### 3. Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/upload")
@limiter.limit("10/minute")
async def upload_file(request: Request, file: UploadFile = File(...)):
    ...
```

#### 4. File Size Limits
```python
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large. Max 500MB allowed.")
```

### Monitoring & Logging

#### Key Metrics to Monitor
| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `run.googleapis.com/request_count` | Total requests | N/A |
| `run.googleapis.com/request_latencies` | Response time | > 30s |
| `run.googleapis.com/container/cpu/utilizations` | CPU usage | > 80% |
| `run.googleapis.com/container/memory/utilizations` | Memory usage | > 90% |
| `pubsub.googleapis.com/subscription/num_undelivered_messages` | Queue depth | > 100 |

#### Cloud Logging Integration
```python
import logging
from google.cloud import logging as cloud_logging

client = cloud_logging.Client()
client.setup_logging()
logger = logging.getLogger(__name__)

logger.info(f"Processing job {job_id}", extra={
    "job_id": job_id,
    "rows": total_rows,
    "ner_enabled": config.get("enable_ner"),
})
```

#### Debug Commands (Cloud Environment)
```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=pi-remover-api" --limit=100

# Check Pub/Sub messages
gcloud pubsub subscriptions pull pi-jobs-fast-sub --auto-ack --limit=10

# View Firestore jobs
gcloud firestore documents list jobs --limit=10
```

### Terraform Deployment

```hcl
# Key resources created:
# - Storage buckets with lifecycle policies
# - Pub/Sub topic for job queue
# - Firestore database
# - Service account for Pub/Sub invoker

terraform init
terraform plan -var="project_id=$PROJECT_ID"
terraform apply -var="project_id=$PROJECT_ID"
```

### Cost Optimization Strategies

1. **NER Toggle** - Let users disable NER for 5x cost reduction
2. **Chunked Processing** - Process large files in chunks to avoid timeouts
3. **Auto-scaling to Zero** - Cloud Run scales to 0 when not in use
4. **Regional Storage** - Keep all resources in same region (no egress fees)
5. **Cleanup Policies** - Auto-delete processed files after 24-48 hours
6. **Committed Use Discounts** - 20-50% savings for predictable workloads

---

## Appendix D: Internal Systems & Company Names

### Company Names to Redact
```python
COMPANY_NAMES = {
    "tcs", "tata consultancy services", "tata", "infosys", "wipro", "hcl",
    "cognizant", "tech mahindra", "accenture", "capgemini", "ibm", "microsoft",
    "google", "amazon", "oracle", "sap", "deloitte", "pwc", "kpmg", "ey",
    "edf energy", "edf", "ultimatix", "nextgenghd",
}
```

### Internal Systems (Whitelist - Don't redact system names themselves)
```python
INTERNAL_SYSTEMS = {
    "ultimatix", "nextgenghd", "global helpdesk", "ghd", "italent",
    "tcscomprod", "sharepoint", "teams", "outlook", "gws",
}
```

---

## Appendix E: Multilingual Patterns

### Portuguese/Spanish
- `Associado Felipe, 2203296` - Associate pattern
- `Asociado` - Spanish variant

### Chinese/CJK
- Pattern: `[\u4e00-\u9fff]+:\s*[12]\d{6}`
- Matches: `员工编号: 1234567`

### Hindi Context (Future)
- Currently English-only
- Hindi transliterated names in dictionary

---

## Appendix F: Changelog

### Version 2.3 (2025-12-12) - UNIFIED SOLUTION

**Major Change**: Consolidated `run_fast.py` and `src/pi_remover/` into a single unified file.

#### Unified File Architecture
- **Single file to maintain**: `src/pi_remover/`
- **Two modes available**:
  - **Full Mode** (default): NER + Regex + Dictionaries (~1K rows/sec)
  - **Fast Mode** (`--fast` or `--no-ner`): Regex + Dictionaries only (~10K rows/sec)

#### New Features in v2.3

| Feature | Description |
|---------|-------------|
| **`--fast` CLI flag** | Easy toggle for fast mode (no NER) |
| **JSON file support** | Process JSON arrays/objects, nested structures |
| **TXT file support** | Process plain text files line-by-line |
| **Structured logging** | Python `logging` module with log levels and file output |
| **Data cleaning** | Pre-process text before redaction for improved accuracy |
| **More PI patterns** | SSN, Bank accounts, IFSC, IBAN, SWIFT, Driving License, etc. |

#### Data Cleaning (Preprocessing)

Before PI detection, text is cleaned:
1. **Unicode normalization**: Smart quotes → regular quotes
2. **HTML decoding**: `&amp;` → `&`, `&nbsp;` → space
3. **Whitespace normalization**: Collapse multiple spaces
4. **Control character removal**: Strip non-printable characters
5. **Encoding fixes**: Fix mojibake (UTF-8 encoded as Latin-1)

```python
# Data cleaning example (v2.12.0 modular)
from pi_remover.utils import DataCleaner

text = "Hello's   test &amp; email\xa0john@test.com"
cleaned = DataCleaner.clean(text)
# Result: "Hello's test & email john@test.com"
```

#### CLI Usage

```bash
# Full mode (NER enabled - more accurate)
python -m pi_remover -i data.csv -c "Description"

# Fast mode (~10x faster)
python -m pi_remover -i data.csv -c "Description" --fast

# Process JSON file
python -m pi_remover -i data.json --fast

# Process TXT file
python -m pi_remover -i notes.txt --fast

# With structured logging
python -m pi_remover -i data.csv --log-level DEBUG --log-file process.log

# Generate audit report
python -m pi_remover -i data.csv --audit --audit-format html
```

#### File Type Support

| Type | Extension | Columns | Notes |
|------|-----------|---------|-------|
| CSV | `.csv` | Required | Chunked processing for large files |
| Excel | `.xlsx`, `.xls` | Required | Full DataFrame load |
| JSON | `.json` | Optional | Nested objects supported |
| TXT | `.txt` | N/A | Line-by-line processing |

#### Migration from run_fast.py

If you were using `run_fast.py`:
```bash
# Old way
python run_fast.py

# New way (equivalent)
python -m pi_remover --fast
```

#### Structured Logging

```python
# Structured logging (v2.12.0 modular)
from pi_remover.utils import setup_logging

# Configure logging
logger = setup_logging(level="DEBUG", log_file="pi_remover.log")

# Log messages
logger.info("Processing started")
logger.debug("Detailed info")
logger.warning("Something unusual")
logger.error("Error occurred")
```

#### Additional PI Patterns Added

| Pattern | Format | Example |
|---------|--------|---------|
| SSN | `XXX-XX-XXXX` | `123-45-6789` |
| Bank Account (India) | `A/C: XXXXXXXXX` | `A/C: 1234567890123` |
| IFSC | `XXXX0XXXXXX` | `HDFC0001234` |
| IBAN | `CCXX...` | `DE89370400440532013000` |
| SWIFT/BIC | `XXXXXXXX` | `HDFCINBBXXX` |
| Driving License (IN) | `XX-XX-XXXX-XXXXXXX` | `KA-05-2020-1234567` |
| UK NIN | `XXDDDDDDX` | `AB123456C` |
| DOB | `dob: XX/XX/XXXX` | `DOB: 15/08/1990` |
| API Keys | `api_key: XXX...` | `api_key: sk-abc123...` |

### Version 2.2 (2025-12-12)
- CLI interface with argparse
- Audit reports (JSON/HTML)
- Input validation functions
- 100+ new Indian names

### Version 2.1 (2025-12-12)
- Excel file support
- YAML configuration
- Per-row error handling
- 12+ international phone patterns
- Exclusion/whitelist support

### Version 1.0 (2025-12-12)
- Initial release
- 5-layer detection stack
- Multiprocessing support

---

## Version 2.5.0 Learnings (December 13, 2025)

### JWT Authentication Implementation

1. **Mandatory Auth**
   - **Change**: Authentication is always enabled, cannot be disabled
   - **Reason**: Security-first approach, no bypass option
   - **Implementation**: Removed `AUTH_ENABLED` config from security.py

2. **Token Flow**
   - **Endpoint**: POST /auth/token with client_id + client_secret
   - **Response**: JWT access_token with 30-minute expiry
   - **Algorithm**: HMAC-SHA256

3. **Client Configuration**
   - **Format**: AUTH_CLIENTS=client_id:secret:description,client2:secret2:desc
   - **Dev Credentials**: dev-client:devsecret123456789012345678901234:development

### BuildKit Optimization

- **Pip Cache Mounts**: `--mount=type=cache,target=/root/.cache/pip`
- **Syntax Directive**: `# syntax=docker/dockerfile:1.4`
- **Build Time**: Rebuilds now take <1 second for code-only changes
- **Helper Scripts**: Added build.ps1 and build.sh for easy builds

### Documentation Updates

- **README.md**: v2.5.0, tech stack table with versions, JWT quick start
- **API_REFERENCE.md**: Full auth section with token flow
- **HOWTO.md**: Auth examples for API Gateway section
- **api_service/README.md**: Auth examples in quick start
- **SECURITY.md**: Updated with mandatory auth

---

## Version 2.4.0 Learnings (December 13, 2025)

### Bug Fixes Applied

1. **Credential Over-matching Fix**
   - **Problem**: "password reset" was incorrectly redacted as `[CREDENTIAL]`
   - **Root Cause**: PASSWORD regex `(?:is|:|\s)` matched partial words like "is" in "issue"
   - **Solution**: 
     - Require explicit assignment indicators (`:`, `=`, `is `) 
     - Added `PASSWORD_NON_CREDENTIALS` blocklist with 40+ words (reset, forgot, policy, change, etc.)
     - Updated `_redact_credentials()` to skip blocklisted words

2. **IP Address Corruption Fix**
   - **Problem**: "192.168.1.100" was being corrupted to "192 168 1.100"
   - **Root Cause**: Phone normalization replaced dots after digits
   - **Solution**: Protect IP addresses with placeholder before phone normalization, restore after

3. **FTP URL Support**
   - **Problem**: `ftp://` URLs were not detected
   - **Solution**: Updated URL regex to `(?:https?|ftp)://`

4. **Spaced Phone Format**
   - **Problem**: "+91 98765 43210" not detected
   - **Solution**: Added `PHONE_INDIAN_SPACED` pattern with flexible spacing

### Docker Optimization

- **Layer Caching**: Reordered Dockerfile to copy requirements before code
- **Build Time**: Reduced from ~150 seconds to ~4 seconds for code-only changes
- **Key Insight**: Never use `--no-cache` unless requirements.txt changed

### Web UI Redesign

- **Theme Toggle**: Added light/dark mode with localStorage persistence
- **Modern Design**: Inter font, CSS variables, responsive grid layout
- **Port Configuration**: Web service on 8082, API gateway on 8080

### Testing Improvements

- **Comprehensive Test Suite**: 58 edge cases across all PI types
- **Context Preservation**: Verified non-PI text remains intact
- **Pass Rate**: 100% (148 total tests = 90 unit + 58 edge)

---

*Last Updated: 2025-12-16*
*Version: 2.12.0*
*Maintained by: Development Team*
