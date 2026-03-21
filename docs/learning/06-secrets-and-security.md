# 06 — Secrets & Security in a Public Repository

## What You'll Learn
- How GitHub Secrets work (encryption, access controls, log masking)
- Why a public repository is safe despite containing CI/CD workflows
- How fork protection prevents unauthorized deployments
- The 5 hardcoded secrets we found and cleaned up
- What goes where: code vs gitignore vs GitHub Secrets vs GCP Secret Manager
- `.gitignore` as a security mechanism

---

## 1. How GitHub Secrets Work

When you run `gh secret set WIF_PROVIDER --body "projects/49982461185/..."`, here's what happens:

### Encryption
- GitHub encrypts the value using **libsodium sealed boxes** (Curve25519 + XSalsa20-Poly1305)
- The encrypted value is stored in GitHub's database
- Only the repo's workflow runners can decrypt it
- **Not even repo admins can view the value after creation** — you can only overwrite or delete

### Access at Runtime
```yaml
# In a workflow:
- run: echo ${{ secrets.WIF_PROVIDER }}
```
During execution:
1. GitHub decrypts the secret
2. Injects it into the runner VM's environment
3. The workflow can use it in commands

### Log Masking
If a secret value appears anywhere in the workflow logs, GitHub automatically replaces it with `***`:

```
# What the workflow runs:
gcloud run deploy --project shared-project-489320

# What appears in logs:
gcloud run deploy --project ***
```

This prevents accidental exposure even if you `echo` a secret or a command prints it.

### Limitations
- Maximum 1000 secrets per repo
- Each secret can be up to 48KB
- Secret names can only contain alphanumeric characters and underscores
- Cannot be accessed in workflow `if:` conditions (only in step `run:` commands and action `with:` inputs)

---

## 2. Why Public Repos Are Safe

**"But my repo is public! Anyone can see my workflow files! How is this secure?"**

This is a common concern. Here's why it's perfectly safe:

### What's Public vs What's Not

| Public (visible to everyone) | Private (secrets) |
|------------------------------|-------------------|
| Workflow YAML files (`.github/workflows/`) | Secret values (`WIF_PROVIDER`, etc.) |
| Dockerfile, source code | GCP project number |
| The *names* of your secrets (in workflow files) | Service account email |
| The *structure* of your deployment | The actual OIDC tokens at runtime |

**Knowing that you use `${{ secrets.WIF_PROVIDER }}` tells an attacker nothing.** They can't read the value.

### Fork Protection: The Key Safety Mechanism

When someone forks your repo and opens a pull request:

```
Your Repo (ErosiousHarsh/pii-shield)        Fork (Attacker/pii-shield)
┌────────────────────────────┐              ┌──────────────────────────┐
│ Secrets: ✅ Available       │              │ Secrets: ❌ NOT available │
│ WIF auth: ✅ Works          │              │ WIF auth: ❌ Token has    │
│                            │              │   wrong repo name       │
│ Deploy job: ✅ Runs on      │              │ Deploy job: ❌ Skipped by │
│   push to master           │              │   if: guard             │
└────────────────────────────┘              └──────────────────────────┘
```

**Three layers of protection:**

1. **GitHub doesn't share secrets with forks.** PR workflows from forks run with NO secrets — `${{ secrets.WIF_PROVIDER }}` is empty.

2. **WIF rejects wrong repo tokens.** Even if an attacker somehow got a token, it would have `repository: "Attacker/pii-shield"`, which fails the attribute condition (see [Doc 05](05-workload-identity-federation.md)).

3. **The `if:` guard in deploy.yml:**
   ```yaml
   if: github.ref == 'refs/heads/master' && github.event_name == 'push'
   ```
   PRs have `github.event_name == 'pull_request'`, so the deploy job doesn't even start.

### Workflow File Protection

**"Can an attacker modify my workflow file in a PR to exfiltrate secrets?"**

No. For PRs from forks, GitHub runs the workflow version from the **base branch** (your master), not the fork's version. The attacker can't change the workflow logic.

---

## 3. The Three GitHub Secrets for PII Shield

```bash
gh secret set WIF_PROVIDER \
  --body "projects/49982461185/locations/global/workloadIdentityPools/github-actions/providers/github"

gh secret set WIF_SERVICE_ACCOUNT \
  --body "github-deployer@shared-project-489320.iam.gserviceaccount.com"

gh secret set GCP_PROJECT_ID \
  --body "shared-project-489320"
```

**Critical insight: None of these are passwords.**

- `WIF_PROVIDER` — a resource path (like a URL). Knowing it doesn't grant access.
- `WIF_SERVICE_ACCOUNT` — an email address. You can't impersonate a service account just by knowing its email.
- `GCP_PROJECT_ID` — the project name. It's already visible in your Cloud Run URL.

We store them as secrets because:
1. The project number (`49982461185`) in the WIF_PROVIDER path is best kept private
2. It avoids hardcoding project-specific values (makes the workflow portable)
3. Defense in depth — even non-sensitive values benefit from not being in plain text

**The actual security comes from WIF** — the OIDC token exchange, not from these values being secret.

---

## 4. The 5 Hardcoded Secrets We Cleaned Up

Before going public, we found 5 real secrets scattered across 60+ files:

| # | Secret | Type | Risk if Leaked |
|---|--------|------|----------------|
| 1 | `zn_OCwQX9KpT9WBo...` | JWT signing key (dev) | Forge auth tokens for dev API |
| 2 | `-iFfgAhYWT82x9mp...` | JWT signing key (prod) | Forge auth tokens for prod API |
| 3 | `_wRlqZ_YQ1QVuIPr...` | API client secret (dev) | Authenticate as dev client |
| 4 | `8rwexUor9eUp07kv...` | API client secret (prod) | Authenticate as prod client |
| 5 | `VjK8mNpL2qR9sT4u...` | Web service client secret | Access API as web service |

### Where They Were Found

Not just in config files — they were copy-pasted into:
- Docker Compose files (`docker/docker-compose.dev.yml`, `docker/docker-compose.prod.yml`)
- Shell scripts (`scripts/deploy-dev.sh`, `scripts/deploy-prod.sh`)
- Dockerfiles (`web_service/Dockerfile`, `api_service/Dockerfile`)
- Documentation (example commands showing real secrets)
- Environment file templates
- Test files

### How We Cleaned Them

```bash
# Bulk replace across ALL non-excluded files
find . -path ./others -prune -o -type f -print | \
  xargs sed -i 's/zn_OCwQX9KpT9WBok6GlBJ1GpIhdSsUfGGa69h-X5T4/YOUR_DEV_JWT_SECRET_HERE/g'

# Repeated for all 5 secrets with descriptive placeholder names
```

**Why placeholder names matter:** `YOUR_DEV_JWT_SECRET_HERE` is self-documenting. Anyone reading the code knows "this needs to be replaced with a real secret in production."

### Files Deleted Entirely

- `others/CREDENTIALS.txt` — a text file with JWT secrets in plain text
- `docker/.env.dev`, `docker/.env.prod` — real environment files

---

## 5. What Goes Where: The Security Layers

Think of security as concentric rings — each ring has different visibility:

```
┌─────────────────────────────────────────────────────────────────┐
│                         Public Code                             │
│  (committed to git, visible to everyone)                        │
│                                                                 │
│  - Port numbers (8080, 8082)                                    │
│  - Region names (us-central1)                                   │
│  - Service names (pii-shield)                                   │
│  - Default configs (rate limits, timeouts)                      │
│  - Placeholder values (YOUR_DEV_JWT_SECRET_HERE)                │
│  - Dockerfile, workflow files, pyproject.toml                   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    .gitignore'd Files                    │    │
│  │  (on your laptop, NOT in git)                           │    │
│  │                                                         │    │
│  │  - .env (real env vars)                                 │    │
│  │  - config/clients.yaml (real API client credentials)    │    │
│  │  - *.csv, *.xlsx (data files with real PII)             │    │
│  │  - logs/ (may contain leaked PII)                       │    │
│  │                                                         │    │
│  │  ┌─────────────────────────────────────────────────┐    │    │
│  │  │              GitHub Secrets                      │    │    │
│  │  │  (encrypted, only in workflow runners)           │    │    │
│  │  │                                                  │    │    │
│  │  │  - WIF_PROVIDER (resource path)                  │    │    │
│  │  │  - WIF_SERVICE_ACCOUNT (SA email)                │    │    │
│  │  │  - GCP_PROJECT_ID (project name)                 │    │    │
│  │  │                                                  │    │    │
│  │  │  ┌──────────────────────────────────────────┐    │    │    │
│  │  │  │       GCP Secret Manager                 │    │    │    │
│  │  │  │  (for runtime secrets in Cloud Run)      │    │    │    │
│  │  │  │                                          │    │    │    │
│  │  │  │  - JWT signing keys (production)         │    │    │    │
│  │  │  │  - Database passwords                    │    │    │    │
│  │  │  │  - API keys for external services        │    │    │    │
│  │  │  └──────────────────────────────────────────┘    │    │    │
│  │  └─────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Decision Guide

| If the value is... | Store it in... | Example |
|--------------------|---------------|---------|
| Safe for anyone to see | Code (committed) | Port numbers, region names |
| Needed by developers, not the public | `.gitignore`'d file + `.env.example` template | Local env vars, test credentials |
| Needed by CI/CD only | GitHub Secrets | WIF provider, project ID |
| Needed at runtime in production | GCP Secret Manager | JWT keys, DB passwords |

---

## 6. `.gitignore` as a Security Mechanism

Several `.gitignore` entries exist specifically for security:

### `config/clients.yaml`
Contains real API client IDs and secrets for authenticating with the API gateway. Template committed as `config/clients.yaml.example`.

### `.env` and `.env.*`
Environment files with real values. The `!.env.example` negation ensures the template (with placeholder values) IS committed.

### `*.csv`, `*.xlsx`, `*.xls`
Data files that may contain real PII. The project processes support ticket data — CSV exports could have names, emails, phone numbers.

### `data/*.json` (but `!data/names.json`)
JSON data files excluded by default. Exception: `names.json` contains a dictionary of common names (not real people's data) needed for PII detection.

### `logs/`
Even though the app has PI-safe logging (a log filter that redacts PII from log output), logs might still contain fragments or metadata. Belt-and-suspenders: exclude them.

---

## 7. Secret Rotation Strategy

### GitHub Secrets
```bash
# Overwrite with new value — next workflow run uses the new value immediately
gh secret set WIF_SERVICE_ACCOUNT --body "new-deployer@project.iam.gserviceaccount.com"
```

### WIF Credentials
**No rotation needed.** Tokens are generated on-demand and expire in ~1 hour. There's nothing to rotate.

### Application Secrets (JWT keys, client credentials)
If you use GCP Secret Manager for runtime secrets:
```bash
# Add a new version (old versions are preserved)
echo -n "new-secret-value" | gcloud secrets versions add JWT_SECRET --data-file=-

# Cloud Run can use "latest" to always get the newest version
```

---

## Key Takeaways

1. **GitHub Secrets are encrypted with libsodium** — not even admins can read them after creation
2. **Public repos are safe** because of three layers: no secret sharing with forks, WIF token validation, and `if:` guards in workflows
3. **Fork PRs can't access secrets or modify workflows** — GitHub uses the base branch's workflow version
4. **The WIF secrets we store aren't passwords** — they're resource identifiers. Real auth is via OIDC tokens.
5. **Clean secrets BEFORE first commit** — they were in 60+ files including docs and scripts
6. **Use concentric security rings:** public code → gitignored files → GitHub Secrets → GCP Secret Manager
7. **`.gitignore` is your first line of defense** — one missed entry can leak PII or credentials

---

Next: [07 — Troubleshooting Guide](07-troubleshooting-guide.md)
