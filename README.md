# PII Shield

**Stop leaking personal data to LLMs.**

PII Shield is a middleware that sits between your prompts and the LLM, automatically detecting and replacing 35+ types of personal information with safe placeholder tokens — so the LLM still understands the context, but never sees the real data.

```
 Your Prompt                        Safe Prompt                         LLM
 ┌─────────────────────┐     ┌─────────────────────────┐     ┌──────────────────┐
 │ "Help me draft an   │     │ "Help me draft an       │     │                  │
 │  email to John at   │ ──> │  email to [NAME] at     │ ──> │  ChatGPT/Claude  │
 │  john@acme.com,     │     │  [EMAIL], employee      │     │  processes safely │
 │  employee #EMP-4523"│     │  #[EMP_ID]"             │     │                  │
 └─────────────────────┘     └─────────────────────────┘     └──────────────────┘
                                    PII Shield
```

<!-- > **[Live Demo](https://pii-shield.onrender.com)** — try it in your browser (first load may take ~30s on free tier) -->

## Features

- **35+ PII types detected** — names, emails, phones, Aadhaar, PAN, employee IDs, IPs, hostnames, credentials, cloud IDs, and more
- **Fast mode** — regex + dictionary detection at ~1,500 rows/sec (no ML model needed)
- **Full mode** — adds spaCy NER for highest accuracy (~150 rows/sec)
- **Web UI** — paste text or upload files (CSV, Excel, JSON, DOCX, PDF, HTML)
- **REST API** — JWT-authenticated endpoints for programmatic access
- **Dark/light theme** — modern responsive interface
- **Zero data retention** — nothing is stored or logged

## Quick Start

```bash
git clone https://github.com/<your-username>/pii-shield.git
cd pii-shield
pip install -e ".[api,excel]"
cd web_service && uvicorn app:app --port 8082
```

Open [http://localhost:8082](http://localhost:8082) in your browser.

## Example

**Before (your prompt with PII):**
> Summarize this ticket: User john.smith (John Smith, john.smith@acme.com) reports VPN issues from IP 10.0.1.55. Badge: B-78432. Employee ID: EMP-45231. Incident: INC0012345.

**After (safe for LLM):**
> Summarize this ticket: User [AD_USER] ([NAME], [EMAIL]) reports VPN issues from IP [IP_ADDRESS]. Badge: [BADGE_ID]. Employee ID: [EMP_ID]. Incident: [TICKET_NUM].

The LLM understands the structure and context perfectly — but never sees the actual personal information.

## PII Types Detected

| Category | Types |
|----------|-------|
| **Personal** | Names, Email, Phone, Aadhaar, PAN Card, Credit/Debit Card |
| **Enterprise** | Employee ID, Asset ID, Ticket Number, Seat/Desk, Badge, Extension |
| **IT Infrastructure** | IP Address, URL, Hostname, AD Username, Windows SID |
| **Credentials** | Passwords, API Keys, Session Tokens, DB Connection Strings |
| **Cloud/Remote** | Azure AD ID, AWS Account ID, Remote Session ID |

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Browser   │────>│  Web Service     │────>│  API Service     │
│   (UI)      │     │  (Port 8082)     │     │  (Port 8080)     │
└─────────────┘     │  FastAPI + UI    │     │  FastAPI + JWT   │
                    │                  │     │  Rate Limiting   │
                    │  Local PIRemover │     │  PIRemover Core  │
                    │  (fallback)      │     │  + spaCy NER     │
                    └──────────────────┘     └──────────────────┘
```

The web service works **standalone** — if the API service is unavailable, it automatically falls back to local processing with a built-in circuit breaker.

## API Usage

```bash
# Get a token
TOKEN=$(curl -s -X POST http://localhost:8080/dev/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"your-secret"}' | jq -r '.access_token')

# Redact text
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Contact john@acme.com or call 555-867-5309"}'
```

## Python Library

```python
from pi_remover import PIRemover, PIRemoverConfig

config = PIRemoverConfig(enable_ner=False)  # Fast mode
remover = PIRemover(config)

result = remover.redact("Email john@acme.com, EMP-45231")
print(result.redacted_text)  # "Email [EMAIL], [EMP_ID]"
```

## Running with Docker

```bash
docker-compose -f docker/docker-compose.dev.yml up -d
```

## Tech Stack

Python 3.11+ | FastAPI | spaCy NER | Pandas | Pydantic | HTTPX | Docker

## License

MIT
