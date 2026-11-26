# PII Shield - Context-Aware Personal Data Protection

![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![PII Types](https://img.shields.io/badge/PII_types-35+-orange)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://pii-shield.saakura.dev)

**Context-aware PII detection - stop leaking personal data to LLMs.**

When you ask ChatGPT to "review my resume" or "draft a complaint letter," your name, phone number, Social Security number, account numbers and other personal details get sent to external servers. PII Shield sits between you and the AI - it detects and replaces personal information with safe tokens, so the AI still understands your request without ever seeing your real data.

```
 Your Prompt                          Safe Prompt                        AI Response
 ┌──────────────────────┐     ┌────────────────────────────┐     ┌──────────────────┐
 │ "Draft a complaint   │     │ "Draft a complaint         │     │                  │
 │  for Jessica Miller, │ ──> │  for [NAME],               │ ──> │  LLM responds    │
 │  jess@gmail.com,     │     │  [EMAIL],                  │     │  safely          │
 │  SSN 123-45-6789"    │     │  SSN [SSN]"                │     │                  │
 └──────────────────────┘     └────────────────────────────┘     └──────────────────┘
                                      PII Shield
```

> **[Live Demo](https://pii-shield.saakura.dev)** - try it in your browser
>
> Part of my [side projects](https://harshit.saakura.dev/projects/) - more at [harshit.saakura.dev](https://harshit.saakura.dev)

## Why PII Shield?

- You paste a prompt containing your **name, email, phone, address, SSN, credit card number**
- That data travels to third-party servers
- It may be logged, cached, or used for training
- **PII Shield strips it out first** - the AI gets `[NAME]`, `[EMAIL]`, `[SSN]` instead

## Features

- **US formats first** - names, street addresses, ZIP codes, phones, SSN, ITIN, EIN, driver's licenses, passports, credit cards and CVVs, routing and account numbers, Medicare IDs, medical record numbers, DOB
- **International too** - UK, EU, India and other phone and ID formats, IBAN/SWIFT
- **Context-aware detection** - understands surrounding keywords like "transfer to", "Dear", "password:" to catch PII that simple regex misses
- **Web UI** - paste a prompt and copy back the safe version (file upload can be enabled for self-hosted use)
- **Fast** - spaCy NER plus regex and dictionaries, about 20 ms per prompt, no external API calls
- **Dark/light theme** - clean, modern interface
- **Zero data retention** - nothing stored, nothing logged, runs locally or self-hosted
- **Open source** - MIT licensed, free forever

## Quick Start

```bash
git clone https://github.com/harshitrajchaurasia/pii-shield.git
cd pii-shield
pip install -e ".[api,excel,full]"
python -m spacy download en_core_web_md
cd web_service && uvicorn app:app --port 8082
```

Open [http://localhost:8082](http://localhost:8082) in your browser.

## Example

**Your prompt:**
> Help me write a dispute letter to my bank. My name is Jessica Miller, email jessica.miller@gmail.com, phone (415) 555-0132. My SSN is 123-45-6789, routing number 021000021, account 4402871933.

**Safe prompt (sent to AI):**
> Help me write a dispute letter to my bank. My name is [NAME], email [EMAIL], phone [PHONE_US]. My SSN is [SSN], routing number [ROUTING_NUM], account [BANK_ACCOUNT].

The AI can still write the letter, with placeholders you swap back in afterwards.

## PII Types Detected

| Category | Types |
|----------|-------|
| **Identity** | Names, Email, Phone, Date of Birth, Street Address, ZIP, City |
| **Government & tax IDs** | SSN, ITIN, EIN, Driver's License, Passport (plus UK NIN, Aadhaar, PAN) |
| **Financial** | Credit/Debit Card (incl. Amex), CVV, Bank Account, Routing Number, IBAN/SWIFT |
| **Health** | Medicare MBI, Medical Record Number, Health Plan Member ID |
| **Digital** | IP Address, URL, Usernames, Passwords, API Keys |

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐
│             │     │         PII Shield Web Service       │
│   Browser   │────>│                                      │
│             │     │  FastAPI + Redaction Engine (Local)   │
│             │<────│  spaCy NER + Regex + Dictionaries     │
└─────────────┘     └──────────────────────────────────────┘
```

All processing happens locally - your data never leaves the server.

## Python Library

```python
from pi_remover import PIRemover, PIRemoverConfig

remover = PIRemover(PIRemoverConfig(enable_ner=False))  # regex + dictionaries only

print(remover.redact("Email jessica.miller@gmail.com, SSN 123-45-6789"))
# Email [EMAIL], SSN [SSN]

details = remover.redact_with_details("...")  # .redacted_text, .redactions
```

## Tech Stack

Python 3.11+ | FastAPI | Pandas | Pydantic | spaCy NER (`en_core_web_md`)

## License

MIT - free for personal and commercial use.
