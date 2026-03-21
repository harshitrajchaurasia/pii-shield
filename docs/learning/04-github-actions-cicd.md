# 04 — GitHub Actions CI/CD

## What You'll Learn
- What CI/CD means and why it matters for a PII tool
- Anatomy of a GitHub Actions workflow YAML file
- Deep dive into the CI pipeline (lint, test, typecheck)
- Deep dive into the CD pipeline (test → deploy)
- How CI and CD relate to each other
- Reading workflow logs and re-running failed jobs
- Every issue we faced and how we fixed it

---

## 1. What is CI/CD?

**CI (Continuous Integration):** Every time you push code, automated checks run — linting, tests, type checking. The goal: catch bugs before they reach production.

**CD (Continuous Deployment):** After CI passes, the code is automatically deployed to production. No manual `gcloud run deploy` needed.

**Why this matters for PII Shield specifically:** This tool processes sensitive personal data. If a code change accidentally breaks a regex pattern, names or Aadhaar numbers could leak through to LLMs. Automated tests catch this instantly — before the broken code reaches the live demo.

---

## 2. Workflow YAML Anatomy

Every workflow lives in `.github/workflows/` as a YAML file. Here's the structure:

```yaml
name: CI                          # Display name in GitHub UI

on:                               # WHEN does this workflow run?
  push:
    branches: [master]            # On push to master
  pull_request:
    branches: [master]            # On PR targeting master

jobs:                             # WHAT does it do?
  lint:                           # Job name (your choice)
    name: Lint                    # Display name in GitHub UI
    runs-on: ubuntu-latest        # WHERE does it run? (GitHub-hosted VM)
    continue-on-error: true       # Don't fail the whole workflow if this fails
    steps:                        # Sequential steps within the job
      - uses: actions/checkout@v4               # Step 1: Clone the repo
      - uses: actions/setup-python@v5           # Step 2: Install Python
        with:
          python-version: "3.11"
          cache: pip                            # Cache pip downloads
      - name: Install linter                    # Step 3: Install ruff
        run: pip install ruff
      - name: Lint (ruff)                       # Step 4: Run linter
        run: ruff check src/ tests/ --output-format=github --select=F,E9
```

**Key concepts:**
- **`on`** — trigger events. Can be `push`, `pull_request`, `workflow_dispatch` (manual), `schedule` (cron), etc.
- **`jobs`** — independent units of work. Jobs without `needs:` run **in parallel**.
- **`runs-on: ubuntu-latest`** — GitHub provides free Linux VMs. Each job gets a fresh VM.
- **`steps`** — sequential within a job. Each step either `uses:` a pre-built action or `run:` a shell command.
- **`uses: actions/checkout@v4`** — clones your repo into the VM. Without this, the VM is empty.
- **`cache: pip`** — caches downloaded packages between runs. Saves ~30-60 seconds.

---

## 3. CI Pipeline Deep Dive

**File:** `.github/workflows/ci.yml`

### The Three Parallel Jobs

```
                    Push to master
                         │
              ┌──────────┼──────────┐
              v          v          v
         ┌────────┐ ┌────────┐ ┌──────────┐
         │  Lint  │ │  Test  │ │ Type     │
         │ (ruff) │ │(pytest)│ │  Check   │
         │        │ │        │ │ (mypy)   │
         │ info   │ │ BLOCKS │ │ info     │
         └────────┘ └────────┘ └──────────┘
```

**They run in parallel** because none has `needs:` pointing to another. This saves time — total CI time is the slowest job (~30s), not the sum of all jobs.

### Job 1: Lint (`continue-on-error: true`)

```yaml
lint:
  name: Lint
  runs-on: ubuntu-latest
  continue-on-error: true      # ← THIS IS KEY
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.11", cache: pip }
    - run: pip install ruff
    - run: ruff check src/ tests/ --output-format=github --select=F,E9
```

**`continue-on-error: true`:** The lint job can fail without failing the whole workflow. The overall CI shows as "passed" even if lint shows warnings.

**Why?** The existing codebase has 1245 ruff errors (formatting issues, unused imports, etc.). Making lint blocking would prevent all deploys. Strategy: make it informational now, tighten the rules incrementally.

**`--select=F,E9`:** Only check the most critical rules:
- `F` — pyflakes: undefined variables, unused imports, redefined functions (real bugs)
- `E9` — syntax errors (code that won't even parse)

**`--output-format=github`:** Creates inline annotations on pull request diffs — ruff errors appear right next to the offending line in the PR review.

### Job 2: Test (BLOCKING)

```yaml
test:
  name: Tests
  runs-on: ubuntu-latest       # No continue-on-error = BLOCKING
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.11", cache: pip }
    - run: pip install -e ".[dev,excel,api]"
    - run: pytest tests/test_remover.py tests/test_edge_cases.py -v --tb=short
```

**No `continue-on-error`:** If tests fail, the whole CI fails. This is the one gate that must pass.

**`pip install -e ".[dev,excel,api]"`:** Installs the package with all extras needed for testing (pytest from `dev`, openpyxl from `excel`, fastapi from `api`).

**Why only two test files?** The project has 5 test files:
- `test_remover.py` — core redaction tests (60 tests) ✅ Run in CI
- `test_edge_cases.py` — edge cases (1 test) ✅ Run in CI
- `test_comprehensive_pi.py` — PII scenario tests ❌ Slow, some platform-dependent
- `test_api.py` — REST API endpoint tests ❌ Requires running API service
- `test_service_integration.py` — service-to-service tests ❌ Requires both services running

### Job 3: Type Check (`continue-on-error: true`)

```yaml
typecheck:
  name: Type Check
  runs-on: ubuntu-latest
  continue-on-error: true
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.11", cache: pip }
    - run: |
        pip install -e ".[api,excel]"
        pip install mypy
    - run: mypy src/pi_remover --ignore-missing-imports
```

**`--ignore-missing-imports`:** Third-party libraries (pandas, fastapi, etc.) don't all have type stubs. Without this flag, mypy reports errors for every import.

---

## 4. CD Pipeline Deep Dive

**File:** `.github/workflows/deploy.yml`

### Sequential Job Flow

```
              Push to master
                    │
                    v
            ┌──────────────┐
            │ Pre-deploy   │
            │ Tests        │
            │ (pytest)     │
            └──────┬───────┘
                   │ needs: test
                   v
            ┌──────────────┐
            │ Deploy       │
            │              │
            │ 1. Auth (WIF)│
            │ 2. gcloud   │
            │ 3. Deploy    │
            └──────────────┘
```

### Trigger and Concurrency

```yaml
on:
  push:
    branches: [master]
  workflow_dispatch:          # Manual trigger button in GitHub UI

concurrency:
  group: deploy-production
  cancel-in-progress: false   # Don't cancel running deploys
```

**`workflow_dispatch`:** Adds a "Run workflow" button in the GitHub Actions UI. Useful for re-deploying without pushing code.

**`concurrency`:** If two pushes happen quickly:
- `cancel-in-progress: true` would cancel the first deploy (dangerous — could leave a half-deployed state)
- `cancel-in-progress: false` makes the second push wait until the first deploy finishes (safe)

### Job 1: Pre-deploy Tests

```yaml
test:
  name: Pre-deploy Tests
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.11", cache: pip }
    - run: |
        pip install -e ".[dev,excel,api]"
        pytest tests/ -v --tb=short --ignore=tests/test_service_integration.py --ignore=tests/test_api.py
```

**Runs more tests than CI** — all test files except the two that require running services. This is the last safety check before deployment.

### Job 2: Deploy

```yaml
deploy:
  name: Deploy
  needs: test                 # ← Wait for tests to pass
  runs-on: ubuntu-latest
  if: github.ref == 'refs/heads/master' && github.event_name == 'push' || github.event_name == 'workflow_dispatch'
```

**`needs: test`:** This job only starts after the test job succeeds. If tests fail, deploy is skipped.

**`if:` guard:** This is critical for security. Breaking it down:

```
(github.ref == 'refs/heads/master' && github.event_name == 'push')
  → Deploy on pushes to master only

|| github.event_name == 'workflow_dispatch'
  → Also deploy on manual triggers
```

**Why this matters:** Without this guard, a pull request from a fork could trigger a deployment. The `if:` ensures only direct pushes to master (by repo owners) or manual triggers cause a deploy.

### Permissions Block

```yaml
permissions:
  contents: read              # Read repo code (for checkout)
  id-token: write             # Request OIDC token (for WIF auth)
```

**`id-token: write`** is required for Workload Identity Federation. It allows the workflow to request a signed JWT from GitHub's OIDC provider. Without this, the auth step fails. See [Doc 05](05-workload-identity-federation.md) for the full WIF explanation.

### Authentication Steps

```yaml
- name: Authenticate to Google Cloud
  uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: ${{ secrets.WIF_PROVIDER }}
    service_account: ${{ secrets.WIF_SERVICE_ACCOUNT }}

- name: Set up Cloud SDK
  uses: google-github-actions/setup-gcloud@v2
```

**Step 1 (auth):** Exchanges a GitHub OIDC token for GCP credentials. After this step, the runner has a temporary GCP access token stored in `$GOOGLE_APPLICATION_CREDENTIALS`.

**Step 2 (setup-gcloud):** Installs the `gcloud` CLI on the runner and configures it to use the credentials from step 1.

### Deploy Step

```yaml
- name: Deploy to Cloud Run
  run: |
    gcloud run deploy pii-shield \
      --project ${{ secrets.GCP_PROJECT_ID }} \
      --source . \
      --region us-central1 \
      --memory 512Mi --cpu 1 \
      --max-instances 1 --min-instances 0 \
      --allow-unauthenticated \
      --set-env-vars "STANDALONE_MODE=true,ENVIRONMENT=production,LOG_LEVEL=WARNING" \
      --quiet
```

This is the same command you'd run manually (see [Doc 03](03-cloud-run-deployment.md)), but with `${{ secrets.* }}` for project-specific values.

---

## 5. How CI and CD Relate

When you push to master, **both workflows trigger independently:**

```
git push origin master
    │
    ├──> CI Workflow (ci.yml)
    │    ├── Lint (parallel)
    │    ├── Test (parallel)
    │    └── Type Check (parallel)
    │
    └──> CD Workflow (deploy.yml)
         ├── Pre-deploy Test (sequential)
         └── Deploy (sequential, after test)
```

**They don't depend on each other.** The CD workflow has its own test job. Even if the CI lint job fails, CD can still deploy (because CD only depends on its own test job, not on CI).

**Why two separate workflows?** Separation of concerns:
- CI runs on PRs too (for PR review feedback)
- CD only runs on master pushes (not PRs)
- You can re-run them independently

---

## 6. Reading Workflow Logs

### From the Command Line

```bash
# List recent runs
gh run list --limit 5
# STATUS      TITLE                    WORKFLOW              BRANCH  EVENT  ID           ELAPSED
# completed   success  Fix tests...   CI                    master  push   23381266469  32s
# in_progress          Fix tests...   Deploy to Cloud Run   master  push   23381266484  22s

# View a specific run
gh run view 23381266469
# Shows: job names, step statuses (✓ or X), timing

# See ONLY failed step logs (KEY debugging tool)
gh run view 23381266469 --log-failed
# Shows: the actual error output from failed steps

# Re-run only failed jobs (no need to push again)
gh run rerun 23381266469 --failed
```

### From GitHub UI

1. Go to your repo → **Actions** tab
2. Click a workflow run
3. Click a failed job → click a failed step → see the log output

---

## 7. Troubleshooting

### 33 Test Failures: Typed Token Mismatch

**What happened:** Tests expected generic tokens like `[PHONE]`, but the engine outputs typed tokens like `[PHONE_IN]`, `[PHONE_UK]`, `[PHONE_US]`.

**Example:**
```python
# Test expected:
assert "[PHONE]" in result     # ❌ FAILED

# Engine actually returned:
"Call me at [PHONE_IN]"        # Indian phone number

# Fix:
assert "[PHONE_IN]" in result  # ✅ PASSED
```

**Root cause:** The tests were written for an older version of the engine that used generic `[PHONE]` tokens. The engine was later updated to use typed tokens (`[PHONE_IN]`, `[PHONE_UK]`, `[PHONE_US]`) for better accuracy, but the tests weren't updated.

**How we fixed it:** Updated all 33 failing test assertions to match the actual typed tokens. Ran tests locally first, then pushed.

### 1245 Ruff Errors: Triage Strategy

**What happened:** The entire codebase has 1245 linting violations (formatting, unused imports, naming conventions, etc.).

**Why not fix all 1245?** That would be a massive code change touching every file — high risk of introducing bugs, and not related to CI/CD setup.

**Strategy:**
1. Make lint `continue-on-error: true` (informational, not blocking)
2. Only check critical rules (`F` = real bugs, `E9` = syntax errors)
3. Auto-fix the easy ones: `ruff check --fix` fixed 17 unused imports
4. Leave the remaining 12 non-critical issues for later

### CD Permission Error: `serviceusage.services.use`

**What happened:** First CD deploy failed with:
```
PERMISSION_DENIED: Caller does not have required permission to use project.
Grant the caller the roles/serviceusage.serviceUsageConsumer role
```

**Root cause:** The `github-deployer` service account could deploy to Cloud Run but couldn't "use" the project's APIs.

**Fix:**
```bash
gcloud projects add-iam-policy-binding shared-project-489320 \
  --member="serviceAccount:github-deployer@shared-project-489320.iam.gserviceaccount.com" \
  --role="roles/serviceusage.serviceUsageConsumer"
```

**Then re-ran** the failed job (no code push needed):
```bash
gh run rerun 23381266484 --failed
```

---

## Key Takeaways

1. **CI and CD are separate workflows** — CI catches bugs, CD deploys. They run independently.
2. **Jobs without `needs:` run in parallel** — lint, test, typecheck all run simultaneously (~30s total)
3. **`continue-on-error: true`** makes a job informational — it can fail without blocking the workflow
4. **`needs: test`** creates a dependency chain — deploy waits for tests to pass
5. **`if:` guards prevent unauthorized deploys** — PRs from forks can't trigger deployment
6. **`permissions: id-token: write`** is required for WIF — without it, GCP auth fails
7. **`gh run view --log-failed`** is your best debugging tool — shows exactly what went wrong
8. **`gh run rerun --failed`** re-runs failed jobs without a new push — saves time and keeps git history clean

---

Next: [05 — Workload Identity Federation](05-workload-identity-federation.md)
