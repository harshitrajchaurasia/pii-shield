# 02 — Docker Containerization

## What You'll Learn
- Why Docker is essential for deploying a Python app
- Line-by-line walkthrough of the Cloud Run Dockerfile
- The STANDALONE_MODE design pattern
- Image size optimization (100MB vs 600MB)
- Comparison of the three Dockerfiles in this project
- Docker security practices

---

## 1. Why Docker for PII Shield

PII Shield is a Python app with specific dependencies:
- Python 3.11+ (not 3.10, not 3.12)
- FastAPI, pandas, pydantic, and 15+ packages at specific versions
- Optional: spaCy with a 500MB language model
- System-level dependencies for file processing (lxml needs C libraries)

Without Docker, deploying means: "install Python 3.11, then pip install everything, then figure out why lxml fails because you're missing `libxml2-dev`..." on every server.

**Docker solves this:** Package your app, its dependencies, and its OS-level requirements into a single image that runs identically everywhere — your laptop, a coworker's machine, or Google Cloud Run.

---

## 2. The Root Dockerfile — Line by Line

This is the Dockerfile at the project root (`Dockerfile`), purpose-built for Cloud Run deployment:

```dockerfile
FROM python:3.11-slim
```
**Line 1:** Start with Python 3.11 on Debian "slim" variant.
- `slim` = ~120MB (only essential Debian packages)
- Full `python:3.11` = ~900MB (includes gcc, dev headers, man pages)
- `alpine` = ~50MB but has musl libc issues with many Python packages
- **Decision:** `slim` is the sweet spot — small enough for fast deploys, compatible enough for pip packages

```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    STANDALONE_MODE=true \
    ENVIRONMENT=production \
    LOG_LEVEL=WARNING
```
**Lines 3-8:** Set environment variables that persist in the running container.
- `PYTHONDONTWRITEBYTECODE=1` — don't write `.pyc` files (saves disk, useless in containers since the filesystem is ephemeral)
- `PYTHONUNBUFFERED=1` — print output immediately instead of buffering (critical for Cloud Run logs — buffered output might be lost on container shutdown)
- `PORT=8080` — Cloud Run expects your container to listen on 8080
- `STANDALONE_MODE=true` — **key design decision**, explained in Section 3
- `ENVIRONMENT=production` — used by the app to set security defaults
- `LOG_LEVEL=WARNING` — minimize log noise in production

```dockerfile
WORKDIR /app
```
**Line 10:** All subsequent commands run in `/app`. Created automatically if it doesn't exist.

```dockerfile
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[api,excel]" && \
    pip install --no-cache-dir httpx pdfplumber python-docx python-pptx beautifulsoup4 lxml python-multipart
```
**Lines 13-16:** Install the Python package.
- **Why copy `pyproject.toml` before `src/`?** Docker layer caching. Each `COPY` or `RUN` creates a layer. If a layer's inputs haven't changed, Docker reuses the cached result. By copying `pyproject.toml` first, pip install is cached unless dependencies change. If you only change app code in `src/`, pip install is skipped on rebuild.
- `pip install -e ".[api,excel]"` — install in "editable" mode with FastAPI (`api`) and Excel support (`excel`) extras. See `pyproject.toml` for what these include.
- `--no-cache-dir` — don't store pip's download cache (saves ~50MB in the image)
- Additional packages (`httpx`, `pdfplumber`, etc.) — file processing dependencies not listed in `pyproject.toml` core deps

```dockerfile
COPY web_service/app.py web_service/api_client.py ./web_service/
COPY web_service/templates ./web_service/templates/
COPY web_service/static ./web_service/static/
```
**Lines 19-21:** Copy only the web service files we need. NOT copying `web_service/Dockerfile`, `web_service/requirements.txt`, or anything else we don't need in the runtime image.

```dockerfile
COPY shared/ ./shared/
COPY config/ ./config/
COPY data/ ./data/
```
**Lines 24-26:** Copy supporting modules.
- `shared/` — config loader, logging, utilities
- `config/` — YAML configuration files (ports, limits, defaults)
- `data/` — name dictionaries for PII detection

```dockerfile
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/uploads && chown -R appuser:appuser /app
USER appuser
```
**Lines 29-31:** Security — never run as root.
- Create a non-root user `appuser` with UID 1000
- Create the uploads directory and give `appuser` ownership
- Switch to `appuser` for all subsequent commands and the runtime `CMD`
- **Why?** If someone exploits a vulnerability in the web app, they get `appuser` privileges — not root. They can't install packages, read `/etc/shadow`, or escape the container as easily.

```dockerfile
EXPOSE 8080
```
**Line 33:** Documentation — tells users this container listens on 8080. Doesn't actually open the port (that's done by `docker run -p` or Cloud Run).

```dockerfile
CMD ["sh", "-c", "cd web_service && uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
```
**Line 35:** The startup command.
- `sh -c` — needed for `${PORT}` variable expansion. JSON exec form (`CMD ["uvicorn", ...]`) doesn't expand variables.
- `cd web_service` — the web app expects to be run from its directory (for template/static file paths)
- `--host 0.0.0.0` — listen on all interfaces (required for Cloud Run to reach the container)
- `--port ${PORT}` — uses the PORT env var (Cloud Run sets this to 8080)

---

## 3. The STANDALONE_MODE Design Pattern

PII Shield has two deployment modes:

### Normal Mode (Two Services)
```
Browser → Web Service (port 8082) → API Service (port 8080) → PIRemover Engine
              │                            │
              │    HTTP + JWT Auth         │
              │    Circuit Breaker         │
              └────────────────────────────┘
```
The web service sends requests to the API service over HTTP with JWT authentication. If the API is down, the circuit breaker falls back to local processing.

### Standalone Mode (Single Service)
```
Browser → Web Service (port 8080) → PIRemover Engine (local, in-process)
```
The web service does everything locally. No HTTP calls, no JWT auth, no API gateway.

**Why standalone for Cloud Run?**
- Cloud Run runs a **single container**. Running two services (API + Web) in one container requires a process manager (supervisord), which adds complexity.
- The API gateway's value (JWT auth, rate limiting) is for enterprise deployments. For a public demo, Cloud Run handles external auth at the infrastructure level.
- Less moving parts = fewer things to break = faster startup.

**How it works in code:** `web_service/app.py` checks `os.environ.get("STANDALONE_MODE")`. If `true`, it instantiates `PIRemover` directly instead of calling the API service via HTTP.

---

## 4. Image Size Optimization

### Size Comparison

| Image | Base | spaCy Model | Approx Size | Use Case |
|-------|------|-------------|-------------|----------|
| Root `Dockerfile` | python:3.11-slim | No | ~100MB | Cloud Run (free tier) |
| `web_service/Dockerfile` | python:3.11-slim | en_core_web_lg (~500MB) | ~600MB | Enterprise Docker Compose |
| `api_service/Dockerfile` | python:3.11-slim | en_core_web_lg (~500MB) | ~600MB | Enterprise Docker Compose |

### Why Skip spaCy for Cloud Run?

spaCy's `en_core_web_lg` model is ~500MB. Loading it requires ~700MB of RAM.

- Cloud Run free tier gives 512Mi memory. After Python + FastAPI + pandas, only ~200MB free. Not enough for spaCy.
- The regex-only "fast mode" (`enable_ner=False`) catches 35+ PII patterns. spaCy NER adds ~5% more accuracy for names but costs 10x more memory and startup time.
- Trade-off: skip spaCy, stay in free tier, accept slightly lower name detection accuracy.

### Docker Layer Caching Strategy

```
Layer 1: FROM python:3.11-slim           ← Rarely changes (months)
Layer 2: COPY pyproject.toml             ← Changes when deps change
Layer 3: RUN pip install                 ← Cached if pyproject.toml unchanged
Layer 4: COPY src/ web_service/ etc.     ← Changes on every code change
Layer 5: RUN useradd                     ← Rarely changes
```

**Key insight:** Put things that change rarely at the top, things that change often at the bottom. When you change code, only layers 4+ rebuild — pip install (the slow part) is cached.

---

## 5. Three-Dockerfile Comparison

| Feature | Root (Cloud Run) | web_service/ | api_service/ |
|---------|------------------|--------------|--------------|
| **Purpose** | Lightweight single-service | Full web UI with NER | Full API gateway with NER |
| **spaCy** | No | Yes (en_core_web_lg) | Yes (en_core_web_lg) |
| **gcc** | No | Yes (then removed) | No |
| **BuildKit** | No | Yes (cache mounts) | Yes (cache mounts) |
| **HEALTHCHECK** | No | Yes (30s interval) | Yes (30s interval) |
| **User shell** | Default (`/bin/sh`) | `/usr/sbin/nologin` | `/usr/sbin/nologin` |
| **File perms** | `chown` only | `chmod 550/770` | `chmod 550/770` |
| **Cleanup** | None | `apt-get remove gcc`, cache cleanup | Cache cleanup |
| **Image size** | ~100MB | ~600MB | ~600MB |

**Why the differences?** The root Dockerfile is optimized for simplicity and size (Cloud Run free tier). The service Dockerfiles are hardened for enterprise deployments with full security measures.

---

## 6. Docker Security Practices

### Non-Root User (All Three Dockerfiles)
```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```
Containers run as root by default. That's dangerous — a vulnerability in your app gives root access to the container (and potentially the host). Always create and switch to a non-root user.

### No-Login Shell (Enterprise Dockerfiles)
```dockerfile
RUN useradd -m -u 1000 -s /usr/sbin/nologin appuser
```
`/usr/sbin/nologin` prevents interactive shell access. Even if an attacker gets into the container, they can't get a bash shell as `appuser`.

### Restrictive File Permissions (Enterprise Dockerfiles)
```dockerfile
RUN chmod -R 550 /app && \           # read + execute, no write
    chmod -R 770 /app/uploads /app/logs && \  # read + write + execute for uploads
    chmod -R 555 /app/templates /app/static    # read + execute for web assets
```
- `550` = owner and group can read and execute, nobody can write. The app can't modify its own code.
- `770` = only uploads and logs are writable (the app needs to write uploaded files and logs).
- This limits damage from code injection attacks.

### Cleanup Steps
```dockerfile
RUN apt-get remove -y gcc && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /root/.cache
```
Remove build tools and caches from the final image. Less software = smaller attack surface.

---

## Key Takeaways

1. **`python:3.11-slim`** is the standard base for Python containers — balance of size and compatibility
2. **Layer caching** is crucial: copy dependency files first, code second, so pip install is cached
3. **STANDALONE_MODE** lets you deploy a multi-service architecture as a single container when needed
4. **Skip expensive dependencies** (like spaCy ~500MB) for constrained environments — use feature flags
5. **Always run as non-root** — it's one line (`USER appuser`) and prevents a whole class of attacks
6. **`--no-cache-dir`** on pip install saves ~50MB in your image
7. **`PYTHONUNBUFFERED=1`** is critical in containers — without it, logs are buffered and may be lost

---

Next: [03 — Cloud Run Deployment](03-cloud-run-deployment.md)
