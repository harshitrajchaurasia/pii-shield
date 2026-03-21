# PII Shield — DevOps Learning Guide

You built a PII redaction tool. These docs explain every DevOps decision that turns it from local Python code into a deployed, continuously-delivered service with automated testing.

## The Complete Pipeline

```
 Your Laptop                    GitHub                        Google Cloud
 ┌──────────┐    git push     ┌──────────────┐             ┌──────────────────┐
 │           │ ─────────────> │  pii-shield   │             │                  │
 │  Code +   │                │  (public repo)│             │  Cloud Run       │
 │  Dockerfile│               │              │             │  (live service)  │
 │           │                │  ┌──────────┐ │   WIF Auth  │                  │
 └──────────┘                │  │ GitHub   │ │ ──────────> │  Cloud Build     │
                              │  │ Actions  │ │  (keyless)  │  Artifact Reg.   │
                              │  │          │ │             │  Cloud Storage   │
                              │  │ CI: test │ │             │                  │
                              │  │ CD: deploy│ │             │                  │
                              │  └──────────┘ │             └──────────────────┘
                              │              │                      │
                              │  Secrets:    │                      │
                              │  WIF_PROVIDER│                      v
                              │  WIF_SA      │             https://pii-shield-
                              │  GCP_PROJECT │              ...run.app
                              └──────────────┘
```

**What happens when you `git push`:**

1. Code goes to GitHub (`master` branch)
2. GitHub Actions triggers **two workflows** simultaneously:
   - **CI** (`ci.yml`): lint, test, typecheck — catches bugs
   - **CD** (`deploy.yml`): test → authenticate to GCP → build container → deploy to Cloud Run
3. CD authenticates to GCP using **Workload Identity Federation** (no stored passwords)
4. GCP **Cloud Build** reads the `Dockerfile`, builds a container image
5. Image stored in **Artifact Registry**
6. **Cloud Run** pulls the image and serves it at the public URL

No manual steps. Push code, get a deployed service.

## Reading Order

| # | Document | What You'll Learn |
|---|----------|-------------------|
| 1 | [Git & GitHub Setup](01-git-github-setup.md) | How code goes from your laptop to GitHub safely |
| 2 | [Docker Containerization](02-docker-containerization.md) | How your Python app becomes a portable container |
| 3 | [Cloud Run Deployment](03-cloud-run-deployment.md) | How that container runs on Google's servers for free |
| 4 | [GitHub Actions CI/CD](04-github-actions-cicd.md) | How pushes automatically test and deploy |
| 5 | [Workload Identity Federation](05-workload-identity-federation.md) | How GitHub deploys to GCP without storing passwords |
| 6 | [Secrets & Security](06-secrets-and-security.md) | How a public repo stays secure |
| 7 | [Troubleshooting Guide](07-troubleshooting-guide.md) | Every error we hit and how we fixed it |

Read them in order — each builds on the previous.

## Project DevOps File Map

| File | Purpose | Doc |
|------|---------|-----|
| `.gitignore` | Keeps secrets and data out of git | [01](01-git-github-setup.md) |
| `Dockerfile` (root) | Lightweight image for Cloud Run (~100MB) | [02](02-docker-containerization.md) |
| `web_service/Dockerfile` | Full image with spaCy NER (~600MB) | [02](02-docker-containerization.md) |
| `api_service/Dockerfile` | Full API gateway image (~600MB) | [02](02-docker-containerization.md) |
| `docker/docker-compose.dev.yml` | Local dev environment (both services) | [02](02-docker-containerization.md) |
| `docker/docker-compose.prod.yml` | Production Docker Compose stack | [02](02-docker-containerization.md) |
| `.github/workflows/ci.yml` | CI: lint + test + typecheck on every push | [04](04-github-actions-cicd.md) |
| `.github/workflows/deploy.yml` | CD: auto-deploy to Cloud Run on push | [04](04-github-actions-cicd.md) |
| `render.yaml` | Alternative deployment config (Render.com) | [03](03-cloud-run-deployment.md) |
| `pyproject.toml` | Python package config + tool settings | [01](01-git-github-setup.md) |
| `config/` | YAML service configs (ports, limits, etc.) | [06](06-secrets-and-security.md) |

## Prerequisites

To follow along with these docs, you need:
- Python 3.11+
- Git
- [GitHub CLI](https://cli.github.com/) (`gh`)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for local testing)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- A GCP project with billing enabled
