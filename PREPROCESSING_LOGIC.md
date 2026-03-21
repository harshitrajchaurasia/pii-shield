# Text Data Preprocessing Logic

A comprehensive, reusable guide for cleaning and preprocessing text data in CSV files. This document details all transformations, filters, and logic that can be applied to **any text column** in **any dataset**.

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration Parameters](#configuration-parameters)
3. [Processing Pipeline](#processing-pipeline)
4. [File Reading with Encoding Fallback](#file-reading-with-encoding-fallback)
5. [Column Operations](#column-operations)
6. [Text Cleaning Functions](#text-cleaning-functions)
7. [Invalid Content Detection](#invalid-content-detection)
8. [Output Specifications](#output-specifications)
9. [Performance Considerations](#performance-considerations)

---

## Overview

This preprocessing pipeline provides reusable logic for:
- Reading files with automatic encoding detection
- Removing unwanted columns
- Filtering rows based on column values
- Cleaning and normalizing text in any column
- Detecting and removing invalid/test/gibberish content

**Use Cases:** NLP preprocessing, machine learning data preparation, text analytics, data quality improvement.

---

## Configuration Parameters

Before processing, define these parameters:

```
CONFIG = {
    # Column to remove (optional) - e.g., row number column
    "column_to_remove": {
        "enabled": true/false,
        "position": 0,  # or specify by name
        "detection": "auto"  # auto-detect if unnamed/numeric
    },

    # Columns to filter by value (optional)
    "filter_columns": [
        {
            "column": "<COLUMN_NAME>",
            "remove_if_contains": ["VALUE1", "VALUE2"],
            "case_sensitive": false
        }
    ],

    # Columns to apply text cleaning (required)
    "text_columns": ["<COLUMN_NAME_1>", "<COLUMN_NAME_2>"],

    # Columns to check for invalid content (optional)
    "validate_columns": ["<COLUMN_NAME>"],

    # Output settings
    "output": {
        "encoding": "utf-8",
        "prefix": "cleaned_",
        "directory": "cleaned_output/"
    }
}
```

---

## Processing Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT FILE                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Read with Encoding Fallback                        │
│  Try: UTF-8 → Latin-1 → CP1252 → ISO-8859-1 → UTF-16       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Remove Specified Columns (if configured)           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Filter Rows by Column Values (if configured)       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Clean Text in Specified Columns                    │
│  (Apply all text cleaning functions)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Filter Invalid Rows (if configured)                │
│  (Test data, gibberish, too short, etc.)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   OUTPUT CLEANED FILE                        │
└─────────────────────────────────────────────────────────────┘
```

---

## File Reading with Encoding Fallback

### Logic

Try reading the file with multiple encodings in order. Stop at the first successful read.

### Encoding Priority Order

```
1. UTF-8
2. Latin-1 (ISO-8859-1 Western European)
3. CP1252 (Windows Western European)
4. ISO-8859-1
5. UTF-16
```

### Pseudocode

```
function read_file_with_encoding(file_path):
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16']

    for encoding in encodings:
        try:
            data = read_csv(file_path, encoding=encoding, skip_bad_lines=true)
            return data
        catch UnicodeDecodeError:
            continue

    throw Error("Failed to read file with any encoding")
```

---

## Column Operations

### Remove Column by Position

Remove a column at a specific index (commonly used for row number columns).

```
function remove_column_by_position(dataframe, position):
    column_name = dataframe.columns[position]
    return drop_column(dataframe, column_name)
```

### Auto-Detect Removable Column

Detect if a column should be removed (typically row numbers):

```
function should_remove_column(column_name):
    # Empty or whitespace-only name
    if column_name.strip() == "":
        return true

    # Name is all digits
    if column_name.strip().is_all_digits():
        return true

    # Unnamed column patterns
    if column_name.lower().starts_with("unnamed"):
        return true

    return false
```

### Filter Rows by Column Value

Remove rows where a column contains specific values:

```
function filter_rows_by_value(dataframe, column, values_to_remove, case_sensitive=false):
    for each row in dataframe:
        cell_value = row[column]

        if cell_value is null:
            continue

        compare_value = cell_value
        if not case_sensitive:
            compare_value = cell_value.to_uppercase()

        for value in values_to_remove:
            check_value = value if case_sensitive else value.to_uppercase()

            if compare_value == check_value:
                REMOVE ROW
            if compare_value.contains(check_value):
                REMOVE ROW
            if compare_value.starts_with(check_value + " "):
                REMOVE ROW

    return dataframe
```

---

## Text Cleaning Functions

Apply these functions to any text column. Each function is independent and can be used separately or combined.

### Function 1: Unicode Normalization

Normalize text to NFKC form.

```
function normalize_unicode(text):
    if text is null:
        return ""
    return unicode_normalize(text, form="NFKC")
```

### Function 2: Whitespace Normalization

```
function normalize_whitespace(text):
    # Replace newlines and carriage returns with space
    text = replace(text, /[\r\n]+/, " ")

    # Replace tabs with space
    text = replace(text, /\t/, " ")

    # Remove control characters (ASCII 0-8, 11, 12, 14-31, 127)
    text = remove(text, /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/)

    # Remove zero-width and invisible Unicode characters
    text = remove(text, /[\u200b-\u200f\u2028-\u202f\u205f-\u206f\ufeff]/)

    # Collapse multiple spaces to single space
    text = replace(text, / {2,}/, " ")

    # Trim leading/trailing whitespace
    text = text.trim()

    return text
```

### Function 3: Fix Encoding Artifacts (Mojibake)

```
function fix_encoding_artifacts(text):
    replacements = {
        # Smart quotes and apostrophes
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',

        # Dashes
        "â€"": "-",

        # Accented characters
        "Ã©": "é",
        "Ã¨": "è",
        "Ã ": "à",
        "Ã¢": "â",
        "Ã®": "î",
        "Ã´": "ô",
        "Ã»": "û",
        "Ã§": "ç",
        "Ã±": "ñ",

        # HTML entities
        "&#40;": "(",
        "&#41;": ")",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&nbsp;": " ",

        # Non-breaking space
        "\xa0": " "
    }

    for old, new in replacements:
        text = replace(text, old, new)

    return text
```

### Function 4: Normalize Quotes and Dashes

```
function normalize_quotes_dashes(text):
    # Smart single quotes to regular
    text = replace(text, /[''`]/, "'")

    # Smart double quotes to regular
    text = replace(text, /[""]/, '"')

    # Em dash, en dash, minus sign to regular hyphen
    text = replace(text, /[—–−]/, "-")

    return text
```

### Function 5: Normalize Punctuation

```
function normalize_punctuation(text):
    # Normalize ellipsis
    text = replace(text, /\.{3,}/, "...")
    text = replace(text, "…", "...")

    # Limit repeated punctuation to maximum 2
    text = replace(text, /!{3,}/, "!!")
    text = replace(text, /\?{3,}/, "??")
    text = replace(text, /-{3,}/, "--")
    text = replace(text, /_{3,}/, "__")
    text = replace(text, /\*{3,}/, "**")
    text = replace(text, /={3,}/, "==")

    return text
```

### Function 6: Remove Bullet Points

Remove bullet points and list markers at the START of text.

```
function remove_bullet_points(text):
    # Unicode bullets: • · ▪ ▸ ► ◦ ‣ ⁃ ○ ●
    text = replace(text, /^[\s]*[•·▪▸►◦‣⁃○●]\s*/, "")

    # Dash/asterisk bullets
    text = replace(text, /^[\s]*[-*]\s+/, "")

    return text
```

### Function 7: Remove Greetings (Configurable)

Remove common greetings at the BEGINNING of text.

```
function remove_greetings(text, patterns=DEFAULT_GREETING_PATTERNS):
    for pattern in patterns:
        text = replace(text, pattern, "", flags=CASE_INSENSITIVE)
    return text

DEFAULT_GREETING_PATTERNS = [
    /^(hi|hello|hey|dear)\s+(team|sir|madam|all|support)[,.\s!]*/,
    /^(good\s+(morning|afternoon|evening|day))[,.\s!]*/,
    /^(respected|dear)\s+(sir|madam|team|all)[,.\s!]*/,
    /^(greetings|namaste|namaskar)[,.\s!]*/,
    /^(hi|hello|hey)[,.\s!]+/
]
```

### Function 8: Remove Sign-offs (Configurable)

Remove common sign-offs at the END of text.

```
function remove_signoffs(text, patterns=DEFAULT_SIGNOFF_PATTERNS):
    for pattern in patterns:
        text = replace(text, pattern, "", flags=CASE_INSENSITIVE)
    return text

DEFAULT_SIGNOFF_PATTERNS = [
    /[\s,.]*(thanks|thank\s*you|thanking\s*you|thx|thnx|thnks)[,.\s!]*$/,
    /[\s,.]*(regards|best\s*regards|warm\s*regards|kind\s*regards)[,.\s]*$/,
    /[\s,.]*(sincerely|yours\s*(truly|sincerely|faithfully))[,.\s]*$/,
    /[\s,.]*(cheers|best|take\s*care)[,.\s]*$/,
    /[\s,.]*thanks\s*(and|&)\s*regards[,.\s]*$/,
    /[\s,.]*thanks\s*in\s*advance[,.\s]*$/
]
```

### Function 9: Remove System Metadata (Configurable)

Remove system-generated prefixes.

```
function remove_metadata(text, patterns=DEFAULT_METADATA_PATTERNS):
    for pattern in patterns:
        text = replace(text, pattern, "", flags=CASE_INSENSITIVE)
    return text

DEFAULT_METADATA_PATTERNS = [
    /^ReopenReason:\d+;\s*/,      # Ticket reopen markers
    /^Description\s*[:\-]\s*/,    # Description labels
    /mailto:/                      # Email link prefixes
]
```

### Function 10: Remove Empty Brackets

```
function remove_empty_brackets(text):
    text = replace(text, /\(\s*\)/, "")  # Empty parentheses
    text = replace(text, /\[\s*\]/, "")  # Empty square brackets
    text = replace(text, /\{\s*\}/, "")  # Empty curly braces
    return text
```

### Function 11: Fix Punctuation Spacing

```
function fix_punctuation_spacing(text):
    # Remove space BEFORE punctuation
    text = replace(text, /\s+([.,;:!?])/, "$1")

    # Add space AFTER punctuation if missing (before letter)
    text = replace(text, /([.,;:!?])([A-Za-z])/, "$1 $2")

    return text
```

### Function 12: Remove Repeated Words

```
function remove_repeated_words(text):
    # "the the" → "the", "is is" → "is"
    text = replace(text, /\b(\w+)\s+\1\b/i, "$1")
    return text
```

### Function 13: Clean Leading/Trailing Punctuation

```
function clean_boundary_punctuation(text):
    # Remove leading commas, semicolons, colons
    text = replace(text, /^[,;:\s]+/, "")

    # Remove trailing commas, semicolons, colons
    text = replace(text, /[,;:\s]+$/, "")

    return text
```

### Function 14: Unwrap Quotes

```
function unwrap_quotes(text):
    if text.length < 2:
        return text

    if (text.starts_with('"') AND text.ends_with('"')) OR
       (text.starts_with("'") AND text.ends_with("'")):
        inner = text.substring(1, length-1).trim()
        if inner is not empty:
            return inner

    return text
```

### Master Cleaning Function

Combine all cleaning functions in order:

```
function clean_text(text, config=DEFAULT_CONFIG):
    if text is null or empty:
        return ""

    text = str(text)

    # Core normalization (always apply)
    text = normalize_unicode(text)
    text = normalize_whitespace(text)
    text = fix_encoding_artifacts(text)
    text = normalize_quotes_dashes(text)
    text = normalize_punctuation(text)

    # Optional cleaning (based on config)
    if config.remove_bullets:
        text = remove_bullet_points(text)

    if config.remove_greetings:
        text = remove_greetings(text, config.greeting_patterns)

    if config.remove_signoffs:
        text = remove_signoffs(text, config.signoff_patterns)

    if config.remove_metadata:
        text = remove_metadata(text, config.metadata_patterns)

    # Structural cleaning (always apply)
    text = remove_empty_brackets(text)
    text = fix_punctuation_spacing(text)
    text = remove_repeated_words(text)

    # Final cleanup
    text = normalize_whitespace(text)  # Run again after all changes
    text = clean_boundary_punctuation(text)
    text = unwrap_quotes(text)
    text = text.trim()

    return text
```

---

## Invalid Content Detection

Functions to detect rows that should be removed.

### Detection 1: Empty or Too Short

```
function is_too_short(text, min_length=5):
    if text is null OR text.trim() is empty:
        return true
    if text.trim().length < min_length:
        return true
    return false
```

### Detection 2: Exact Match Patterns (Configurable)

```
function matches_exact_pattern(text, patterns=DEFAULT_TEST_PATTERNS):
    text_lower = text.lower().trim()
    return text_lower in patterns

DEFAULT_TEST_PATTERNS = {
    # Single words
    "test", "testing", "test123", "asdf", "asdfgh", "qwerty",
    "aaa", "bbb", "xxx", "yyy", "zzz",
    "123", "1234", "12345", "abc", "abcd",
    "sample", "demo", "dummy", "foo", "bar", "foobar",
    "hello", "hi", "na", "n/a", "nil", "null", "none",
    "blank", "empty", "tbd", "todo", "check", "ok", "okay",

    # Punctuation only
    "-", "--", "---", ".", "..", "...",

    # Phrases
    "for restart", "for test", "for testing",
    "test purpose", "testing purpose",
    "test ticket", "testing ticket",
    "test entry", "testing entry",
    "this is test", "this is a test",
    "ignore", "ignore this", "please ignore",
    "do not assign", "dont assign",
    "password changes", "password change",
    "display problem"
}
```

### Detection 3: Regex Pattern Matching (Configurable)

```
function matches_regex_pattern(text, patterns=DEFAULT_REGEX_PATTERNS):
    text_lower = text.lower().trim()

    for pattern in patterns:
        if regex_search(pattern, text_lower):
            return true

    return false

DEFAULT_REGEX_PATTERNS = [
    # Test ticket patterns
    /^test\s*ticket/,
    /^testing\s*ticket/,
    /test\s*ticket\.?$/,
    /^test\s*purpose/,
    /^testing\s*purpose/,
    /^testing\s*ptupose/,           # Common typo

    # Short test phrases
    /^for\s*test(ing)?$/,
    /^test(ing)?\s*only$/,
    /^just\s*test(ing)?/,

    # Ignore/assign patterns
    /^ignore\s*this/,
    /^do\s*not\s*assign/,
    /^dont\s*assign/,
    /do\s*no[rt]\s*assign/,         # Handles typo "nor"
    /^please\s*ignore/,

    # Dummy/sample patterns
    /^test\s*data/,
    /^dummy\s*(ticket|entry|data)/,
    /^sample\s*(ticket|entry|data)/,
    /test\s*ticket\s*do\s*no[rt]\s*assign/,

    # Single word patterns
    /^check$/,
    /^checking$/,
    /^trial$/,
    /^temp$/,
    /^temporary$/,
    /^test\s*$/,
    /^testing\s*$/,

    # Compound patterns
    /^\w+\s+test\s+ticket\.?$/,     # "XYZ test ticket"
    /^test\s*entry\.?$/,
    /^testing\s*entry\.?$/,
    /not\s+working\s+test\s+ticket/,
    /created?\s*(a\s+)?test\s+ticket/,
    /test\s+ticket\s+for\s+test/,
    /^testing\s+purpose\s*$/,
    /^test\s+purpose\s*$/
]
```

### Detection 4: Gibberish Patterns

```
function is_gibberish(text):
    patterns = [
        /^[^a-zA-Z]*$/,           # No letters at all
        /^(.)\1{4,}$/,            # Same character repeated 5+ times
        /^[0-9\s\-\.\,]+$/        # Only numbers and punctuation
    ]

    for pattern in patterns:
        if regex_match(pattern, text):
            return true

    return false
```

### Detection 5: Insufficient Words

```
function has_insufficient_words(text, min_words=1, min_word_length=2):
    # Extract words (sequences of letters)
    words = regex_find_all(/[a-zA-Z]+/, text)

    # Filter by minimum length
    valid_words = filter(words, word => word.length >= min_word_length)

    return valid_words.length < min_words
```

### Detection 6: Low Letter Ratio

```
function has_low_letter_ratio(text, min_ratio=0.3, exception_keywords=null):
    if text.length == 0:
        return true

    letter_count = count(text, char => char.is_alphabetic())
    ratio = letter_count / text.length

    if ratio < min_ratio:
        # Check for exception keywords
        if exception_keywords is not null:
            text_lower = text.lower()
            for keyword in exception_keywords:
                if text_lower.contains(keyword):
                    return false  # Keep the row
        return true  # Remove the row

    return false

DEFAULT_EXCEPTION_KEYWORDS = [
    "ticket", "issue", "error", "request", "id", "emp", "employee"
]
```

### Detection 7: Short with Few Words

```
function is_short_with_few_words(text, max_length=15, max_words=3):
    if text.length >= max_length:
        return false

    words = regex_find_all(/[a-zA-Z]{2,}/, text)
    return words.length < max_words
```

### Master Validation Function

```
function is_invalid_content(text, config=DEFAULT_VALIDATION_CONFIG):
    # Check each criterion
    if is_too_short(text, config.min_length):
        return true

    if matches_exact_pattern(text, config.exact_patterns):
        return true

    if matches_regex_pattern(text, config.regex_patterns):
        return true

    if is_gibberish(text):
        return true

    if has_insufficient_words(text, config.min_words):
        return true

    if has_low_letter_ratio(text, config.min_letter_ratio, config.exception_keywords):
        return true

    if is_short_with_few_words(text, config.short_max_length, config.short_max_words):
        return true

    return false
```

---

## Output Specifications

### File Naming

```
output_filename = config.prefix + input_filename
# Example: "cleaned_" + "data.csv" = "cleaned_data.csv"
```

### Encoding

Always save output as **UTF-8** regardless of input encoding.

### Index Handling

Do not include row index in output file.

---

## Performance Considerations

### Parallel Processing

```
function process_files_parallel(file_list, config, num_workers=CPU_COUNT-1):
    results = parallel_map(
        function=process_single_file,
        items=file_list,
        workers=num_workers
    )
    return results
```

### Memory Management

- Use streaming/chunked reading for files > 500MB
- Process one file per worker
- Release memory after each file

### Recommended Chunk Size

```
For files > 500MB:
    chunk_size = 100,000 rows
    process each chunk
    append to output file
```

---

## Usage Examples

### Example 1: Basic Text Cleaning

```
config = {
    text_columns: ["description"],
    remove_greetings: true,
    remove_signoffs: true
}

cleaned_text = clean_text(raw_text, config)
```

### Example 2: Full Pipeline with Validation

```
config = {
    column_to_remove: { position: 0, detection: "auto" },
    text_columns: ["comments", "notes"],
    validate_columns: ["comments"],
    filter_columns: [
        { column: "status", remove_if_contains: ["DEFAULT", "TEST"] }
    ]
}

data = read_file_with_encoding(file_path)
data = remove_column_by_position(data, 0)
data = filter_rows_by_value(data, "status", ["DEFAULT", "TEST"])
data["comments"] = data["comments"].apply(clean_text)
data = data.filter(row => !is_invalid_content(row["comments"]))
save(data, output_path)
```

### Example 3: Custom Patterns

```
custom_config = {
    greeting_patterns: [
        /^dear\s+customer[,.\s]*/i,
        /^hello\s+valued\s+user[,.\s]*/i
    ],
    signoff_patterns: [
        /[\s,.]*best\s+wishes[,.\s]*$/i,
        /[\s,.]*your\s+support\s+team[,.\s]*$/i
    ],
    exact_patterns: {"placeholder", "tbd", "coming soon"},
    regex_patterns: [/^todo:/i, /\[draft\]/i]
}

cleaned = clean_text(text, custom_config)
is_valid = !is_invalid_content(text, custom_config)
```

---

## Summary

This preprocessing logic provides:

| Component | Purpose |
|-----------|---------|
| **Encoding Fallback** | Handle files with various encodings |
| **Column Operations** | Remove/filter columns generically |
| **14 Cleaning Functions** | Modular text normalization |
| **7 Validation Functions** | Detect invalid content |
| **Configurable Patterns** | Customize for any domain |
| **Parallel Processing** | Handle large datasets efficiently |

All functions are:
- **Independent** - Use individually or combined
- **Configurable** - Pass custom patterns
- **Language-agnostic** - Implement in any language with regex support

---

*Document Version: 2.0*
*License: Free to use and modify*
