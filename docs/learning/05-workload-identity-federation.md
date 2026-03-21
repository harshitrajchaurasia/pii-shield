# 05 — Workload Identity Federation (WIF)

## What You'll Learn
- Why GitHub Actions needs GCP access and why passwords are a bad solution
- How Workload Identity Federation works (the keyless approach)
- Every `gcloud` command we ran and exactly what each one does
- What happens at runtime during a deploy
- Security guarantees that make this safe for public repos
- WIF vs service account keys comparison

---

## 1. The Problem

GitHub Actions needs to run `gcloud run deploy` to push your code to Cloud Run. That command requires GCP credentials — proof that the caller is allowed to deploy.

**How does a GitHub Actions runner (a VM in Microsoft's cloud) prove its identity to Google Cloud?**

---

## 2. The Bad Solution: Service Account Keys

The traditional approach:

```
1. Create a GCP service account
2. Generate a JSON key file (downloaded to your laptop)
3. Base64-encode it and store as a GitHub Secret
4. In the workflow, decode it and use it as credentials
```

**Why this is dangerous:**

| Problem | Impact |
|---------|--------|
| The key **never expires** | If leaked, attacker has permanent access until you notice and delete it |
| It's a **static file** | Can be copied, emailed, committed to git accidentally |
| No **audit trail** per use | You see "service account used" but not "which workflow run used it" |
| Must be **manually rotated** | People forget. Keys accumulate. |
| **Stored in GitHub** | One more place the key exists and could leak |

---

## 3. The Good Solution: Workload Identity Federation

WIF uses **short-lived tokens** instead of permanent keys. Here's the flow:

```
 GitHub Actions Runner                    Google Cloud
 ┌─────────────────────┐                 ┌─────────────────────────────┐
 │                     │                 │                             │
 │ 1. Workflow starts  │                 │  Workload Identity Pool     │
 │    with permission: │                 │  ┌───────────────────────┐  │
 │    id-token: write  │                 │  │ Provider: "github"    │  │
 │                     │                 │  │                       │  │
 │ 2. Request OIDC     │                 │  │ Issuer: token.actions │  │
 │    token from GitHub│                 │  │ .githubusercontent.com│  │
 │         │           │                 │  │                       │  │
 │         v           │                 │  │ Condition:            │  │
 │ ┌───────────────┐   │                 │  │ repo == ErosiousHarsh │  │
 │ │ GitHub OIDC   │   │  3. Send JWT    │  │ /pii-shield           │  │
 │ │ Provider      │───│─────────────────│─>│                       │  │
 │ │               │   │                 │  └───────────┬───────────┘  │
 │ │ Signs JWT:    │   │                 │              │              │
 │ │ repo: ...     │   │                 │  4. Validate │signature     │
 │ │ branch: ...   │   │                 │     Check conditions        │
 │ │ workflow: ... │   │                 │              │              │
 │ └───────────────┘   │                 │              v              │
 │                     │                 │  5. Exchange for short-lived│
 │                     │  6. Return      │     GCP access token        │
 │                     │<────────────────│     (expires in ~1 hour)    │
 │                     │  temp credentials                             │
 │ 7. gcloud run      │                 │                             │
 │    deploy ...       │─────────────────│─> Cloud Run, Cloud Build   │
 │                     │ using temp token│                             │
 └─────────────────────┘                 └─────────────────────────────┘
```

**The key insight:** No password is ever stored. GitHub proves its identity with a signed JWT (like a digital passport), and GCP gives back a temporary access token that expires in ~1 hour.

---

## 4. Step-by-Step: Every `gcloud` Command

### Step 1: Create a Workload Identity Pool

```bash
gcloud iam workload-identity-pools create "github-actions" \
  --location="global" \
  --display-name="GitHub Actions" \
  --description="WIF pool for GitHub Actions CI/CD"
```

**What this creates:** A logical container that groups external identity providers. Think of it as a "trust group" — you're saying "I want to trust some external identities."

**`--location="global"`:** GitHub isn't region-specific, so use global.

### Step 2: Create an OIDC Provider

```bash
gcloud iam workload-identity-pools providers create-oidc "github" \
  --location="global" \
  --workload-identity-pool="github-actions" \
  --display-name="GitHub" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository=='ErosiousHarsh/pii-shield'"
```

This is the most important command. Let's break down every flag:

**`--issuer-uri="https://token.actions.githubusercontent.com"`**
Tells GCP: "The identity tokens will come from GitHub's OIDC provider." GCP uses this URL to fetch GitHub's public signing keys (JWKS — JSON Web Key Set) so it can verify that tokens are genuinely signed by GitHub and not forged.

**`--attribute-mapping`**
Maps claims from the GitHub JWT to GCP attributes:

| GitHub JWT Claim | GCP Attribute | Example Value |
|------------------|---------------|---------------|
| `assertion.sub` | `google.subject` | `repo:ErosiousHarsh/pii-shield:ref:refs/heads/master` |
| `assertion.repository` | `attribute.repository` | `ErosiousHarsh/pii-shield` |
| `assertion.actor` | `attribute.actor` | `ErosiousHarsh` |

**`--attribute-condition="assertion.repository=='ErosiousHarsh/pii-shield'"`**
**THIS IS THE SECURITY GATE.** Only JWTs where the `repository` claim equals `ErosiousHarsh/pii-shield` are accepted. A token from ANY other repository — including forks — is rejected.

### Step 3: Create a Service Account

```bash
gcloud iam service-accounts create "github-deployer" \
  --display-name="GitHub Actions Deployer" \
  --description="Service account for GitHub Actions CI/CD deployments"
```

Creates a GCP identity (`github-deployer@shared-project-489320.iam.gserviceaccount.com`) that GitHub will impersonate. This identity has specific permissions — only what's needed for deployment.

### Step 4: Grant Roles to the Service Account

```bash
PROJECT_ID="shared-project-489320"
SA_EMAIL="github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Permission to create/update Cloud Run services
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.admin"

# Permission to "act as" the default service account when deploying
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser"

# Permission to trigger Cloud Build (needed for --source deployments)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudbuild.builds.editor"

# Permission to push images to Artifact Registry
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/artifactregistry.writer"

# Permission to upload source to Cloud Storage
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/storage.admin"

# Permission to call GCP APIs (this one was initially missed!)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/serviceusage.serviceUsageConsumer"
```

**What each role allows:**

| Role | What It Allows | Why Needed |
|------|---------------|------------|
| `roles/run.admin` | Create, update, delete Cloud Run services | Deploy new revisions |
| `roles/iam.serviceAccountUser` | Act as another service account | Cloud Run needs a runtime SA |
| `roles/cloudbuild.builds.editor` | Start Cloud Build jobs | `--source .` triggers a build |
| `roles/artifactregistry.writer` | Push container images | Built image goes to registry |
| `roles/storage.admin` | Read/write Cloud Storage | Upload source tarball |
| `roles/serviceusage.serviceUsageConsumer` | Call any GCP API | Required for all API calls |

**Principle of least privilege:** This SA can only deploy. It can't delete the project, create VMs, access databases, or do anything else. If compromised, damage is limited to Cloud Run deployments.

### Step 5: Allow WIF to Impersonate the Service Account

```bash
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")

gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions/attribute.repository/ErosiousHarsh/pii-shield"
```

This is the binding that connects everything:

**Translation:** "Any identity from the `github-actions` pool whose `repository` attribute is `ErosiousHarsh/pii-shield` is allowed to impersonate `github-deployer`."

**The `principalSet://` URI decoded:**
```
principalSet://iam.googleapis.com/
  projects/49982461185/                              ← Your GCP project number
  locations/global/                                   ← Global (not region-specific)
  workloadIdentityPools/github-actions/               ← The pool from Step 1
  attribute.repository/ErosiousHarsh/pii-shield       ← Only this specific repo
```

---

## 5. What Happens at Runtime

When the CD workflow runs, here's the exact sequence:

### In `deploy.yml`:

```yaml
permissions:
  contents: read
  id-token: write    # ← Allows requesting OIDC token
```

**`id-token: write`** tells GitHub: "This workflow needs to request an identity token." Without this permission, the next step fails.

### The Auth Action:

```yaml
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
    service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}
```

Behind the scenes, this action:

1. **Requests OIDC token** from GitHub's internal endpoint (`ACTIONS_ID_TOKEN_REQUEST_URL`)
2. **GitHub signs a JWT** with claims like:
   ```json
   {
     "iss": "https://token.actions.githubusercontent.com",
     "sub": "repo:ErosiousHarsh/pii-shield:ref:refs/heads/master",
     "repository": "ErosiousHarsh/pii-shield",
     "actor": "ErosiousHarsh",
     "ref": "refs/heads/master",
     "workflow": "Deploy to Cloud Run",
     "exp": 1711029600  // Expires in ~15 minutes
   }
   ```
3. **Sends the JWT** to GCP's Security Token Service (STS) at `sts.googleapis.com`
4. **GCP validates:** Is the JWT signed by GitHub? Is the issuer correct? Does the repository match the attribute condition? Is the token expired?
5. **GCP returns** a short-lived access token (~1 hour validity)
6. **The action writes** the credentials to a temp file and sets `$GOOGLE_APPLICATION_CREDENTIALS`

### After Auth:

```yaml
- uses: google-github-actions/setup-gcloud@v2    # Installs gcloud CLI
- run: gcloud run deploy ...                       # Uses the temp credentials
```

The `gcloud` CLI automatically reads `$GOOGLE_APPLICATION_CREDENTIALS` — no additional auth setup needed.

---

## 6. Security Guarantees

### No Stored Credentials
Nothing permanent is stored anywhere. The OIDC token expires in ~15 minutes. The GCP access token expires in ~1 hour. After the workflow finishes, the runner VM is destroyed.

### Repository Scoping
The attribute condition `assertion.repository=='ErosiousHarsh/pii-shield'` means:
- A workflow from `ErosiousHarsh/other-project` → **REJECTED**
- A workflow from `SomeoneElse/pii-shield` (a fork) → **REJECTED**
- A workflow from `ErosiousHarsh/pii-shield` → **ACCEPTED**

### Fork Protection
When someone forks your repo and creates a PR:
- Their fork's workflows get tokens with `repository: "TheirName/pii-shield"` (not `ErosiousHarsh/pii-shield`)
- The GCP attribute condition rejects these tokens
- Even if they modify the workflow file, the token still has their fork's repository name

### Branch Scoping (Optional)
You could add `assertion.ref == 'refs/heads/master'` to the attribute condition to restrict deployments to the master branch only. We didn't need this because the `deploy.yml` already has an `if:` guard.

---

## 7. WIF vs Service Account Key

| Aspect | Service Account Key | Workload Identity Federation |
|--------|--------------------|-----------------------------|
| **Credential type** | JSON file (permanent) | OIDC token (15 min) + access token (1 hour) |
| **Stored where** | GitHub Secret (base64) | Nowhere — generated on demand |
| **Expires** | Never (until deleted) | ~1 hour |
| **Rotation needed** | Yes (manual) | No (automatic) |
| **If leaked** | Attacker has permanent access | Attacker has ~1 hour window |
| **Audit trail** | "SA key used" | "Workflow run X from repo Y used SA" |
| **Setup complexity** | Simple (3 commands) | Medium (5 commands) |
| **GCP recommendation** | Avoid | Preferred |

**Bottom line:** WIF is more setup upfront, but zero maintenance afterward and significantly more secure.

---

## 8. The Three GitHub Secrets

After WIF setup, we stored three values as GitHub Secrets:

```bash
gh secret set WIF_PROVIDER \
  --body "projects/49982461185/locations/global/workloadIdentityPools/github-actions/providers/github"

gh secret set WIF_SERVICE_ACCOUNT \
  --body "github-deployer@shared-project-489320.iam.gserviceaccount.com"

gh secret set GCP_PROJECT_ID \
  --body "shared-project-489320"
```

**Important insight:** None of these are passwords! They're resource identifiers:
- `WIF_PROVIDER` — path to the OIDC provider (like a URL, not a secret)
- `WIF_SERVICE_ACCOUNT` — email of the service account (like a username, not a password)
- `GCP_PROJECT_ID` — project name (publicly visible in Cloud Run URL anyway)

We store them as secrets to avoid hardcoding project-specific values in the workflow file and to avoid exposing the project number. The actual "authentication" happens via the OIDC token exchange — no password involved.

---

## Key Takeaways

1. **WIF eliminates stored credentials** — no JSON keys, no passwords, no secrets to rotate
2. **GitHub signs JWTs** for every workflow run — these prove the identity of the repo and branch
3. **GCP validates the JWT** against the pool/provider config and attribute conditions
4. **Attribute conditions are the security gate** — `assertion.repository=='ErosiousHarsh/pii-shield'` ensures only your repo can deploy
5. **Short-lived tokens** (~1 hour) limit blast radius if anything goes wrong
6. **Five `gcloud` commands** set up the entire trust chain: pool → provider → SA → roles → binding
7. **The GitHub Secrets we store are identifiers, not passwords** — the real auth is the OIDC token exchange

---

Next: [06 — Secrets & Security](06-secrets-and-security.md)
