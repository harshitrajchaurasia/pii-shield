# 03 — Cloud Run Deployment

## What You'll Learn
- What Google Cloud Run is and why we chose it
- What `gcloud run deploy --source .` actually does behind the scenes
- Every deployment flag and why we chose those values
- Free tier math — why this costs $0
- GCP APIs and IAM permissions required
- How we evaluated 8 hosting alternatives

---

## 1. What is Google Cloud Run?

Cloud Run is **serverless containers**. You give it a Docker image, it runs it and gives you an HTTPS URL. Key properties:

| Property | Value for PII Shield |
|----------|---------------------|
| **Scale to zero** | When nobody is using it, zero instances run. $0. |
| **Auto-scale up** | When a request comes in, Cloud Run starts a container in ~5-15 seconds |
| **HTTPS** | Automatic TLS certificate, no setup needed |
| **URL** | `https://pii-shield-49982461185.us-central1.run.app` |
| **Max instances** | 1 (to stay in free tier) |
| **Container port** | 8080 (Cloud Run's default) |

**Think of it as:** "Run my Docker container when someone visits the URL. Turn it off when nobody's using it."

---

## 2. The `--source .` Deployment Flow

When you run:
```bash
gcloud run deploy pii-shield --source . --region us-central1
```

Here's what actually happens — four GCP services working together:

```
Your Code                   Google Cloud
┌──────────┐
│ Dockerfile│
│ src/      │
│ web_svc/  │    (1) Upload         ┌─────────────────┐
│ shared/   │ ──────────────────>  │ Cloud Storage    │
│ config/   │    source tarball     │ (temp bucket)    │
│ data/     │                       └────────┬────────┘
└──────────┘                                 │
                                    (2) Build│
                                             v
                              ┌─────────────────────────┐
                              │ Cloud Build              │
                              │                          │
                              │ 1. Reads your Dockerfile │
                              │ 2. Runs FROM, COPY, RUN  │
                              │ 3. Creates container image│
                              └────────────┬─────────────┘
                                           │
                                  (3) Push │image
                                           v
                              ┌─────────────────────────┐
                              │ Artifact Registry        │
                              │                          │
                              │ Stores the built image   │
                              │ (like Docker Hub, but    │
                              │  inside your GCP project)│
                              └────────────┬─────────────┘
                                           │
                                  (4) Deploy│
                                           v
                              ┌─────────────────────────┐
                              │ Cloud Run                │
                              │                          │
                              │ Pulls image, creates     │
                              │ a "revision", routes     │
                              │ traffic to it            │
                              │                          │
                              │ URL: https://pii-shield- │
                              │ 49982461185.us-central1  │
                              │ .run.app                 │
                              └─────────────────────────┘
```

**Step by step:**
1. **Cloud Storage:** `gcloud` tarballs your local directory and uploads it to a temporary Cloud Storage bucket
2. **Cloud Build:** Reads your `Dockerfile`, executes each instruction (FROM, COPY, RUN, etc.), produces a container image
3. **Artifact Registry:** The built image is pushed here (GCP's private container registry)
4. **Cloud Run:** Pulls the image from Artifact Registry, creates a new "revision" (version), and routes the public URL to it

**Total time:** ~2-3 minutes for PII Shield (most time spent on pip install in the Dockerfile)

---

## 3. Every Deployment Flag Explained

Here's the full deploy command from our CD pipeline:

```bash
gcloud run deploy pii-shield \
  --project shared-project-489320 \      # Which GCP project
  --source . \                           # Build from current directory
  --region us-central1 \                 # Data center location
  --memory 512Mi \                       # RAM per container instance
  --cpu 1 \                              # vCPUs per container instance
  --max-instances 1 \                    # Maximum concurrent containers
  --min-instances 0 \                    # Minimum (0 = scale to zero)
  --allow-unauthenticated \              # Public access (no login)
  --set-env-vars "STANDALONE_MODE=true,ENVIRONMENT=production,LOG_LEVEL=WARNING" \
  --quiet                                # No interactive prompts (for CI)
```

### `--project shared-project-489320`
Specifies which GCP project to deploy to. In CI/CD, this comes from `${{ secrets.GCP_PROJECT_ID }}` so it's not hardcoded.

### `--source .`
Instead of pre-building a Docker image and pushing it, this tells GCP "here's my source code, you build it." GCP uses Cloud Build to run your Dockerfile. The alternative is `--image gcr.io/my-project/my-image:tag` if you pre-built the image yourself.

### `--region us-central1`
Which GCP data center. `us-central1` (Iowa) is the most popular — lowest pricing, most free tier availability, good latency for US users.

### `--memory 512Mi`
RAM per container. PII Shield needs:
- Python runtime: ~50MB
- FastAPI + uvicorn: ~30MB
- pandas + loaded libraries: ~100MB
- Regex engine + name dictionaries: ~50MB
- Request handling headroom: ~200MB
- **Total: ~430MB, so 512Mi is sufficient**

If we included spaCy: +700MB. That would need `1Gi` or `2Gi`, which costs more.

### `--cpu 1`
One virtual CPU. PII detection is CPU-bound (regex matching), but for a demo/portfolio project, one CPU handles concurrent requests fine.

### `--max-instances 1`
**Critical for cost control.** If someone DDoSes your URL, Cloud Run would normally auto-scale up to 100+ instances — and you'd get a massive bill. `max-instances 1` caps it at one container, ever. Worst case: requests queue up and some get slow. Best case: $0.

### `--min-instances 0`
Scale to zero. When nobody's using the app, zero containers run, zero cost. The trade-off: the first request after idle has a "cold start" delay of 5-15 seconds while a container spins up.

### `--allow-unauthenticated`
Makes the URL publicly accessible. Without this, every request would need a valid GCP IAM token. For a public demo tool, we want anyone to access it.

### `--set-env-vars`
Runtime environment variables injected into the container. These override the `ENV` defaults in the Dockerfile.

### `--quiet`
Suppresses interactive "Are you sure?" prompts. Essential in CI/CD where there's no human to type "yes".

---

## 4. Free Tier Math

Google Cloud Run free tier (per month):
- **2 million requests**
- **360,000 GB-seconds** of memory
- **180,000 vCPU-seconds** of compute

With our config (512Mi, 1 CPU, max 1 instance):

| Resource | Free Allowance | Our Usage (est.) | Cost |
|----------|---------------|-------------------|------|
| Requests | 2,000,000 | ~1,000 (portfolio project) | $0 |
| Memory | 360,000 GB-s | 512Mi × ~3,600s/day × 30 = ~55,000 GB-s | $0 |
| CPU | 180,000 vCPU-s | 1 CPU × ~3,600s/day × 30 = ~108,000 | $0 |
| Cloud Build | 120 min/day | ~3 min per deploy | $0 |

**Cloud Build also has a free tier:** 120 build-minutes per day. Each deploy takes ~2.5 minutes. You'd need to deploy 48 times in a day to exceed this.

**Result: $0/month** for a portfolio project with occasional traffic.

---

## 5. GCP APIs That Must Be Enabled

Cloud Run `--source` deployment uses three GCP APIs that aren't enabled by default:

```bash
# Enable required APIs
gcloud services enable artifactregistry.googleapis.com  # Store container images
gcloud services enable cloudbuild.googleapis.com         # Build Dockerfiles
gcloud services enable run.googleapis.com                # Run containers
```

**How you'll know they're not enabled:** The first `gcloud run deploy` will fail with an error like:
```
API [artifactregistry.googleapis.com] not enabled on project [shared-project-489320].
Would you like to enable it? (y/N)
```

In CI/CD (`--quiet` flag), there's no prompt — it just fails. Enable them manually first.

---

## 6. IAM Permissions

### For Manual Deployment (Your Personal Account)

When you run `gcloud run deploy` from your laptop, you're authenticated as your Google account (via `gcloud auth login`). You need:
- `roles/run.admin` — create/update Cloud Run services
- `roles/cloudbuild.builds.builder` — trigger Cloud Build
- `roles/storage.objectViewer` — read source from Cloud Storage

If you're the project owner, you already have these.

### For CI/CD Deployment (Service Account)

GitHub Actions uses a dedicated service account (`github-deployer`). It needs more roles because it's not a project owner. See [Doc 05 — Workload Identity Federation](05-workload-identity-federation.md) for the full list.

---

## 7. Why Cloud Run? Alternatives Comparison

We evaluated 8 platforms:

| Platform | Free Tier | Cold Start | Python Containers | Why Not |
|----------|-----------|------------|-------------------|---------|
| **Heroku** | No free tier (removed 2022) | N/A | Yes | Costs $5+/month |
| **Render** | Yes (750 hrs) | ~30s | Yes | 15-min spin-down, slow starts |
| **Koyeb** | Yes (limited) | Fast | Yes | Limited regions, less known |
| **Railway** | $5 credit/month | Fast | Yes | Credits run out with usage |
| **HuggingFace Spaces** | Yes | Slow | Gradio only | No FastAPI support |
| **Fly.io** | Yes (3 VMs) | Fast | Yes | Requires credit card |
| **Vercel** | Yes | Fast | No Python containers | Serverless functions only |
| **Cloud Run** | Yes (2M req) | 5-15s | Yes | **Winner** |

**Why Cloud Run won:**
- Scale-to-zero = true $0 (not just "free credits that run out")
- Professional URL (`.run.app` domain)
- Existing GCP project with free credits
- Great interview talking point ("I deployed with Cloud Run using Workload Identity Federation and GitHub Actions CI/CD")
- Fast cold starts compared to Render
- No credit card required (user already had GCP billing set up)

---

## 8. The `render.yaml` Alternative

We also created a `render.yaml` for Render.com as a backup option:

```yaml
services:
  - type: web
    name: pii-shield
    runtime: python
    plan: free
    buildCommand: >
      pip install -e ".[api,excel]" &&
      pip install httpx pdfplumber python-docx python-pptx beautifulsoup4 lxml python-multipart
    startCommand: cd web_service && uvicorn app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: STANDALONE_MODE
        value: "true"
```

**Key difference:** Render uses `buildCommand` + `startCommand` (no Dockerfile needed). It detects `pyproject.toml` and installs dependencies. Simpler, but less control over the image.

---

## 9. Troubleshooting

### `PERMISSION_DENIED: ... cloudbuild.builds.create`
**Cause:** The default compute service account lacks Cloud Build permissions.
**Fix:**
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/cloudbuild.builds.builder"
```

### `API [X] not enabled on project`
**Fix:** `gcloud services enable X` for each missing API.

### Cold start latency (5-15 seconds)
**Cause:** `min-instances 0` means no containers are running when idle. First request after idle must wait for container startup (pull image + Python startup + FastAPI init + load dictionaries).
**Mitigation:** Set `min-instances 1` to keep one container warm (but costs ~$0.50/month).

---

## Key Takeaways

1. **`--source .`** is the simplest deployment — GCP handles building, storing, and deploying your Docker image
2. **Four GCP services** work together: Cloud Storage → Cloud Build → Artifact Registry → Cloud Run
3. **`--max-instances 1`** is your cost safety net — prevents runaway scaling
4. **`--min-instances 0`** enables scale-to-zero ($0) but adds cold start latency
5. **Enable APIs first** (`run`, `cloudbuild`, `artifactregistry`) — they're not on by default
6. **512Mi memory** is enough for regex-based PII detection but not for spaCy NER (~700MB)
7. **Free tier is generous** — 2M requests/month, more than enough for a portfolio project

---

Next: [04 — GitHub Actions CI/CD](04-github-actions-cicd.md)
