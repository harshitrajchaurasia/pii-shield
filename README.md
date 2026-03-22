# PII Shield - Context-Aware Personal Data Protection

![Python](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)
![PII Types](https://img.shields.io/badge/PII_types-35+-orange)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen?logo=googlecloud)](https://pii-shield-49982461185.us-central1.run.app)

**Context-aware PII detection - stop leaking personal data to LLMs.**

When you ask ChatGPT to "review my resume" or "draft a complaint letter," your name, phone number, Aadhaar, PAN, and other personal details get sent to external servers. PII Shield sits between you and the AI - it detects and replaces personal information with safe tokens, so the AI still understands your request without ever seeing your real data.

```
 Your Prompt                          Safe Prompt                        AI Response
 ┌──────────────────────┐     ┌────────────────────────────┐     ┌──────────────────┐
 │ "Draft a complaint   │     │ "Draft a complaint         │     │                  │
 │  for Rajesh Kumar,   │ ──> │  for [NAME],               │ ──> │  LLM responds    │
 │  rajesh@gmail.com,   │     │  [EMAIL],                  │     │  responds safely │
 │  Aadhaar 1234 5678"  │     │  Aadhaar [AADHAAR]"        │     │                  │
 └──────────────────────┘     └────────────────────────────┘     └──────────────────┘
                                      PII Shield
```

> **[Live Demo](https://pii-shield-49982461185.us-central1.run.app)** - try it in your browser

## Why PII Shield?

- You paste a prompt containing your **name, email, phone, Aadhaar, PAN, credit card number**
- That data travels to third-party servers
- It may be logged, cached, or used for training
- **PII Shield strips it out first** - the AI gets `[NAME]`, `[EMAIL]`, `[AADHAAR]` instead

## Features

- **35+ PII types** - names, emails, phones, Aadhaar, PAN, SSN, passport, credit cards, DOB, bank accounts, UPI, and more
- **Context-aware detection** - understands surrounding keywords like "transfer to", "Dear", "password:" to catch PII that simple regex misses
- **Web UI** - paste text or drag-and-drop files (CSV, Excel, JSON, DOCX, PDF)
- **Instant results** - regex + dictionary detection, no external API calls
- **Dark/light theme** - clean, modern interface
- **Zero data retention** - nothing stored, nothing logged, runs locally or self-hosted
- **Open source** - MIT licensed, free forever

## Quick Start

```bash
git clone https://github.com/ErosiousHarsh/pii-shield.git
cd pii-shield
pip install -e ".[api,excel]"
cd web_service && uvicorn app:app --port 8082
```

Open [http://localhost:8082](http://localhost:8082) in your browser.

## Example

**Your prompt:**
> Help me write a complaint letter to my bank. My name is Rajesh Kumar, email rajesh.kumar@gmail.com, phone +91 98765 43210. My Aadhaar is 1234 5678 9012, PAN: ABCDE1234F. Account number 50100123456789.

**Safe prompt (sent to AI):**
> Help me write a complaint letter to my bank. My name is [NAME], email [EMAIL], phone [PHONE]. My Aadhaar is [AADHAAR], PAN: [PAN]. Account number [BANK_ACCT].

The AI writes the letter perfectly - using placeholders you can swap back in later.

## PII Types Detected

| Category | Types |
|----------|-------|
| **Identity** | Names, Email, Phone, Date of Birth, Addresses |
| **Government IDs** | Aadhaar, PAN, SSN, Passport, Driving License |
| **Financial** | Credit/Debit Card, Bank Account, UPI, IFSC/SWIFT |
| **Digital** | IP Address, URL, Usernames, Passwords, API Keys |

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────┐
│             │     │         PII Shield Web Service       │
│   Browser   │────>│                                      │
│             │     │  FastAPI + Redaction Engine (Local)   │
│             │<────│  Regex (35+ patterns) + Dictionaries  │
└─────────────┘     └──────────────────────────────────────┘
```

All processing happens locally - your data never leaves the server.

## Python Library

```python
from pi_remover import PIRemover, PIRemoverConfig

remover = PIRemover(PIRemoverConfig(enable_ner=False))

result = remover.redact("Email rajesh@gmail.com, Aadhaar 1234 5678 9012")
print(result.redacted_text)
# "Email [EMAIL], Aadhaar [AADHAAR]"
```

## Tech Stack

Python 3.11+ | FastAPI | Pandas | Pydantic | spaCy NER (optional)

## License

MIT - free for personal and commercial use.
