# PI Remover - Troubleshooting Guide

> **Complete troubleshooting reference for common issues and their solutions.**
> 
> **Version**: 2.12.0 | Modular Microservices Architecture

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Microservices Issues](#microservices-issues)
3. [Docker Issues](#docker-issues)
4. [API Gateway Issues](#api-gateway-issues)
5. [Authentication Issues](#authentication-issues)
6. [Performance Issues](#performance-issues)
7. [Memory Issues](#memory-issues)
8. [File Processing Issues](#file-processing-issues)
9. [GCP Deployment Issues](#gcp-deployment-issues)
10. [NER/spaCy Issues](#nerspacy-issues)
11. [Network Issues](#network-issues)

---

# Quick Diagnostics

## System Status Check (v2.12.0)

Run this quick diagnostic script:

```bash
#!/bin/bash
echo "=== PI Remover v2.12.0 Diagnostics ==="
echo ""

echo "1. Docker Status:"
docker info > /dev/null 2>&1 && echo "   ✓ Docker running" || echo "   ✗ Docker not running"

echo ""
echo "2. Container Status:"
docker ps --filter "name=pi-" --format "   {{.Names}}: {{.Status}}"

echo ""
echo "3. Redis Status:"
redis-cli ping > /dev/null 2>&1 && echo "   ✓ Redis running" || echo "   ⚠ Redis not running (in-memory fallback active)"

echo ""
echo "4. Config Files:"
[ -f "config/api_service.yaml" ] && echo "   ✓ api_service.yaml exists" || echo "   ✗ api_service.yaml missing"
[ -f "config/web_service.yaml" ] && echo "   ✓ web_service.yaml exists" || echo "   ✗ web_service.yaml missing"
[ -f "config/clients.yaml" ] && echo "   ✓ clients.yaml exists" || echo "   ✗ clients.yaml missing"

echo ""
echo "5. Health Checks:"
curl -sf http://localhost:8080/dev/health > /dev/null && echo "   ✓ API Service (8080): healthy" || echo "   ✗ API Service (8080): not responding"
curl -sf http://localhost:8082/health > /dev/null && echo "   ✓ Web Service (8082): healthy" || echo "   ✗ Web Service (8082): not responding"

echo ""
echo "6. Port Usage:"
netstat -tlnp 2>/dev/null | grep -E "8080|8082|6379" | awk '{print "   " $4 " -> " $7}'
```

### PowerShell Version (Windows)

```powershell
Write-Host "=== PI Remover v2.12.0 Diagnostics ===" -ForegroundColor Cyan

# Config files
Write-Host "`nConfig Files:" -ForegroundColor Yellow
@("api_service.yaml", "web_service.yaml", "clients.yaml", "redis.yaml") | ForEach-Object {
    $path = "config\$_"
    if (Test-Path $path) { Write-Host "  ✓ $_ exists" -ForegroundColor Green }
    else { Write-Host "  ✗ $_ missing" -ForegroundColor Red }
}

# Health checks
Write-Host "`nService Health:" -ForegroundColor Yellow
try {
    $null = Invoke-WebRequest -Uri "http://localhost:8080/dev/health" -TimeoutSec 2
    Write-Host "  ✓ API Service (8080): healthy" -ForegroundColor Green
} catch {
    Write-Host "  ✗ API Service (8080): not responding" -ForegroundColor Red
}

try {
    $null = Invoke-WebRequest -Uri "http://localhost:8082/health" -TimeoutSec 2
    Write-Host "  ✓ Web Service (8082): healthy" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Web Service (8082): not responding" -ForegroundColor Red
}
```

---

# Microservices Issues

## Web Service Can't Connect to API

### Symptoms
```
Connection refused: http://localhost:8080
Circuit breaker is OPEN
```

### Cause
The Web Service calls the API Service via HTTP. If the API is down, connections fail.

### Solutions

1. **Check API Service is running:**
   ```bash
   curl http://localhost:8080/dev/health
   ```

2. **Verify API URL in config:**
   ```yaml
   # config/web_service.yaml
   api:
     base_url: "http://localhost:8080"  # Must match API port
   ```

3. **Check circuit breaker state:**
   The circuit breaker opens after 5 consecutive failures. Wait 30 seconds and retry.

4. **Start API Service first:**
   ```bash
   cd api_service && uvicorn app:app --port 8080
   ```

---

## Circuit Breaker is OPEN

### Symptoms
```
CircuitBreaker: state=OPEN, requests failing fast
```

### Cause
The circuit breaker opens after 5 consecutive API failures to prevent cascading failures.

### Solutions

1. **Wait for recovery timeout (30 seconds by default)**

2. **Fix the underlying API issue:**
   ```bash
   curl http://localhost:8080/dev/health
   ```

3. **Adjust circuit breaker settings:**
   ```yaml
   # config/web_service.yaml
   circuit_breaker:
     failure_threshold: 10   # More tolerant
     recovery_timeout: 60    # Longer recovery
   ```

4. **Force reset (restart web service):**
   ```bash
   # Restart clears circuit breaker state
   ```

---

## Redis Connection Failed

### Symptoms
```
Redis unavailable, using in-memory fallback
```

### Impact
- Rate limiting works per-instance (not shared)
- No impact on core functionality

### Solutions

1. **Start Redis:**
   ```bash
   docker run --rm -p 6379:6379 redis:alpine
   ```

2. **Check Redis config:**
   ```yaml
   # config/redis.yaml
   redis:
     host: "localhost"
     port: 6379
   ```

3. **Ignore warning (fallback is working):**
   In-memory fallback is intentional for single-instance deployments.

---

## YAML Configuration Error

### Symptoms
```
yaml.scanner.ScannerError: mapping values are not allowed here
Config file not found: config/api_service.yaml
```

### Solutions

1. **Verify YAML syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('config/api_service.yaml'))"
   ```

2. **Check indentation (use 2 spaces, not tabs):**
   ```yaml
   # CORRECT
   server:
     host: "0.0.0.0"
     port: 8080
   
   # WRONG (tabs)
   server:
   	host: "0.0.0.0"
   ```

3. **Ensure config directory exists:**
   ```bash
   ls -la config/
   ```

---

## Internal Client Authentication Failed

### Symptoms
```
401 Unauthorized for pi-internal-web-service
```

### Cause
The Web Service uses `pi-internal-web-service` client to authenticate with API.

### Solutions

1. **Verify client exists in clients.yaml:**
   ```yaml
   # config/clients.yaml
   clients:
     pi-internal-web-service:
       secret: "YOUR_WEB_CLIENT_SECRET_HERE"
       rate_limit: 10000
   ```

2. **Check secret matches in web_service config**

3. **Restart both services after config changes**

---

# Docker Issues

## Docker daemon not running

### Symptoms
```
Cannot connect to the Docker daemon. Is the docker daemon running?
```

### Solutions

**WSL2:**
```bash
# Start Docker service
sudo service docker start

# Check status
sudo service docker status

# If using systemd in WSL2
sudo systemctl start docker
sudo systemctl enable docker
```

**RHEL/Linux:**
```bash
# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Check status
sudo systemctl status docker
```

**Podman (RHEL):**
```bash
# Podman runs rootless, no daemon needed
podman info
```

---

## Permission denied when running docker

### Symptoms
```
Got permission denied while trying to connect to the Docker daemon socket
```

### Solutions

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Apply group changes immediately
newgrp docker

# Or log out and back in
exit
# Then reconnect to WSL/terminal
```

**Verify:**
```bash
# Should work without sudo
docker ps
```

---

## Port already in use

### Symptoms
```
Error starting userland proxy: listen tcp4 0.0.0.0:8080: bind: address already in use
```

### Solutions

**Find the process:**
```bash
# Linux/WSL2
sudo lsof -i :8080
# or
sudo netstat -tlnp | grep 8080

# Windows PowerShell
netstat -ano | findstr :8080
```

**Kill the process:**
```bash
# Linux
sudo kill -9 <PID>

# Windows
taskkill /PID <PID> /F
```

**Or stop existing containers:**
```bash
docker compose -f docker/docker-compose.dev.yml down
docker compose -f docker/docker-compose.prod.yml down
```

---

## Container won't start

### Symptoms
```
Container exited with code 1
Container keeps restarting
```

### Solutions

**Check logs:**
```bash
# View logs
docker logs pi-gateway-dev

# Follow logs
docker logs -f pi-gateway-dev

# View last 50 lines
docker logs --tail 50 pi-gateway-dev
```

**Common causes:**

1. **Missing environment file:**
```bash
# Check if .env file exists
ls -la docker/.env.dev docker/.env.prod

# Create from template
cp docker/.env.dev.template docker/.env.dev
```

2. **Invalid configuration:**
```bash
# Validate docker-compose file
docker compose -f docker/docker-compose.dev.yml config
```

3. **Missing dependencies:**
```bash
# Rebuild image
docker compose -f docker/docker-compose.dev.yml build --no-cache
```

---

## Image build fails

### Symptoms
```
failed to solve: failed to compute cache key
```

### Solutions

```bash
# Clear Docker cache
docker builder prune -f

# Rebuild without cache
docker compose -f docker/docker-compose.dev.yml build --no-cache

# Full cleanup (WARNING: removes all unused images)
docker system prune -a
```

---

# API Gateway Issues

## 404 Not Found

### Symptoms
```json
{"detail": "Not Found"}
```

### Solutions

**Check endpoint path:**
- DEV: `http://localhost:8080/dev/v1/redact` (not `/v1/redact`)
- PROD: `http://localhost:9080/prod/v1/redact`

**Correct request:**
```bash
# DEV
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "test@example.com"}'

# PROD  
curl -X POST http://localhost:9080/prod/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "test@example.com"}'
```

---

## 500 Internal Server Error

### Symptoms
```json
{"detail": "Internal server error"}
```

### Solutions

**Check container logs:**
```bash
docker logs pi-gateway-dev 2>&1 | tail -50
```

**Common causes:**

1. **NER model not loaded:**
```bash
# Check if spaCy model is installed
docker exec pi-gateway-dev python -c "import spacy; spacy.load('en_core_web_sm')"
```

2. **Memory exhaustion:**
```bash
# Check memory usage
docker stats pi-gateway-dev

# Increase memory limit in docker-compose.yml
# deploy.resources.limits.memory: 2G
```

3. **Configuration error:**
```bash
# Validate config.yaml
docker exec pi-gateway-dev python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

---

## 503 Service Unavailable

### Symptoms
```
Connection refused
Service temporarily unavailable
```

### Solutions

```bash
# Check if container is running
docker ps | grep pi-gateway

# Check container health
docker inspect --format='{{.State.Health.Status}}' pi-gateway-dev

# Restart container
docker restart pi-gateway-dev

# Check if port is exposed
docker port pi-gateway-dev
```

---

# Authentication Issues

## 401 Unauthorized - Token missing

### Symptoms
```json
{"detail": "Not authenticated"}
```

### Solutions

**Include Authorization header:**
```bash
# Get token first
TOKEN=$(curl -s -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}' \
  | jq -r '.access_token')

# Use token
curl -X POST http://localhost:8080/dev/v1/redact \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "test@example.com"}'
```

---

## 401 Unauthorized - Invalid credentials

### Symptoms
```json
{"detail": "Invalid client credentials"}
```

### Solutions

**Use correct credentials:**

| Environment | Client ID | Client Secret |
|-------------|-----------|---------------|
| DEV | `pi-dev-client` | `YOUR_DEV_CLIENT_SECRET_HERE` |
| PROD | `pi-prod-client` | `YOUR_PROD_CLIENT_SECRET_HERE` |

**Check environment file:**
```bash
# Verify credentials in environment
grep CLIENT docker/.env.dev
```

---

## 401 Unauthorized - Token expired

### Symptoms
```json
{"detail": "Token has expired"}
```

### Solutions

```bash
# Get a new token
TOKEN=$(curl -s -X POST http://localhost:8080/dev/auth/token \
  -H "Content-Type: application/json" \
  -d '{"client_id":"pi-dev-client","client_secret":"YOUR_DEV_CLIENT_SECRET_HERE"}' \
  | jq -r '.access_token')

echo "New token: $TOKEN"
```

**Token expiry times:**
- DEV: 24 hours
- PROD: 1 hour

---

## 429 Too Many Requests

### Symptoms
```json
{"detail": "Rate limit exceeded. Try again in X seconds."}
```

### Solutions

**Wait and retry:**
```bash
# Check rate limit headers in response
curl -v http://localhost:8080/dev/v1/redact ... 2>&1 | grep -i "x-ratelimit"
```

**Rate limits:**
- DEV: 100 requests/minute
- PROD: 1000 requests/minute

**For bulk processing, use batch endpoint:**
```bash
curl -X POST http://localhost:8080/dev/v1/redact/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"texts": ["text1", "text2", "text3"]}'
```

---

# Performance Issues

## Slow response times

### Symptoms
- Requests taking > 1 second
- Timeouts on large texts

### Solutions

**1. Disable NER for faster processing:**
```bash
# CLI
python -m pi_remover -i data.csv --fast

# API - set in config.yaml
detection:
  enable_ner: false
```

**2. Increase resources:**
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
```

**3. Use batch processing:**
```bash
# Process multiple texts in one request
curl -X POST http://localhost:8080/dev/v1/redact/batch \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"texts": ["text1", "text2", ...]}'
```

**4. Check container resources:**
```bash
docker stats pi-gateway-dev
```

---

## High CPU usage

### Solutions

```bash
# Check which process is consuming CPU
docker exec pi-gateway-dev top -b -n 1

# NER is CPU-intensive - consider disabling
# Set in docker-compose.yml:
# ENABLE_NER=false
```

---

# Memory Issues

## Container killed (OOM)

### Symptoms
```
Container killed: OOMKilled
Exited (137)
```

### Solutions

**1. Increase memory limit:**
```yaml
# docker-compose.yml
services:
  pi-gateway:
    deploy:
      resources:
        limits:
          memory: 2G  # Increase from 1G
```

**2. Disable NER (saves ~500MB):**
```yaml
environment:
  - ENABLE_NER=false
```

**3. Reduce batch size:**
```yaml
# config.yaml
general:
  batch_size: 1000  # Reduce from 5000
```

---

## Memory leak

### Symptoms
- Memory usage grows over time
- Eventually leads to OOM

### Solutions

```bash
# Monitor memory over time
watch -n 5 'docker stats --no-stream pi-gateway-dev'

# Restart container (temporary fix)
docker restart pi-gateway-dev

# Set restart policy
# docker-compose.yml
services:
  pi-gateway:
    restart: unless-stopped
```

---

# File Processing Issues

## CSV encoding errors

### Symptoms
```
UnicodeDecodeError: 'utf-8' codec can't decode byte
```

### Solutions

```bash
# Detect encoding
file -bi input.csv

# Convert to UTF-8
iconv -f ISO-8859-1 -t UTF-8 input.csv > input_utf8.csv

# Or specify encoding in CLI
python -m pi_remover -i input.csv --encoding latin-1
```

---

## Excel file not recognized

### Symptoms
```
ValueError: Excel file format cannot be determined
```

### Solutions

```bash
# Install openpyxl
pip install openpyxl

# Ensure file has correct extension
mv file file.xlsx

# Try re-saving from Excel as .xlsx
```

---

## Large file processing timeout

### Symptoms
- Processing hangs
- Container becomes unresponsive

### Solutions

**1. Use CLI instead of API for large files:**
```bash
python -m pi_remover -i large_file.csv -c "Column1,Column2" --fast
```

**2. Split large files:**
```bash
# Split into 100k line chunks
split -l 100000 large_file.csv chunk_
```

**3. Increase timeout:**
```yaml
# docker-compose.yml
environment:
  - REQUEST_TIMEOUT=600  # 10 minutes
```

---

# GCP Deployment Issues

## Permission denied for Secret Manager

### Symptoms
```
PermissionDenied: 403 Permission denied on resource
```

### Solutions

```bash
# Grant Cloud Run service account access to secrets
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud secrets add-iam-policy-binding pi-jwt-secret-prod \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

---

## Image not found in Artifact Registry

### Symptoms
```
Failed to pull image: not found
```

### Solutions

```bash
# Check if image exists
gcloud artifacts docker images list \
    ${REGION}-docker.pkg.dev/${PROJECT_ID}/pi-remover

# Re-push image
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/pi-remover/pi-gateway:latest

# Check repository exists
gcloud artifacts repositories list --location=$REGION
```

---

## Cloud Run deployment fails

### Symptoms
```
Revision failed to become ready
Container failed to start
```

### Solutions

```bash
# Check Cloud Run logs
gcloud run services logs read pi-remover-api-dev --region=us-central1 --limit=50

# Check revision details
gcloud run revisions describe [REVISION_NAME] --region=us-central1

# Common fixes:
# 1. Increase memory
gcloud run services update pi-remover-api-dev \
    --memory=2Gi \
    --region=us-central1

# 2. Increase timeout
gcloud run services update pi-remover-api-dev \
    --timeout=300 \
    --region=us-central1
```

---

# NER/spaCy Issues

## spaCy model not found

### Symptoms
```
OSError: [E050] Can't find model 'en_core_web_sm'
```

### Solutions

```bash
# Download model
python -m spacy download en_core_web_sm

# In Docker, ensure Dockerfile includes:
RUN python -m spacy download en_core_web_sm
```

---

## NER taking too long

### Solutions

**1. Disable NER:**
```bash
# CLI
python -m pi_remover -i data.csv --fast

# API - environment variable
ENABLE_NER=false
```

**2. Use smaller model:**
```bash
# en_core_web_sm (smallest, fastest)
# en_core_web_md (medium)
# en_core_web_lg (largest, most accurate)
```

---

# Network Issues

## Cannot connect to localhost from Windows

### Symptoms
- API works in WSL2 but not from Windows browser
- Connection refused from Windows

### Solutions

```bash
# In WSL2, bind to all interfaces (already done in docker-compose)
# Ports should be accessible via localhost from Windows

# If not working, check WSL2 networking:
wsl hostname -I

# Access via WSL2 IP:
http://[WSL2-IP]:8080/health
```

---

## CORS errors in browser

### Symptoms
```
Access to fetch has been blocked by CORS policy
```

### Solutions

**Check CORS configuration in app:**
```python
# api_service/app.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8082", "http://localhost:9082"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

# Quick Reference

## Diagnostic Commands

```bash
# Container status
docker ps -a | grep pi-

# Container logs
docker logs pi-gateway-dev --tail 100

# Container resources
docker stats pi-gateway-dev

# Container health
docker inspect --format='{{.State.Health.Status}}' pi-gateway-dev

# Enter container shell
docker exec -it pi-gateway-dev /bin/bash

# Test API endpoint
curl -s http://localhost:8080/health | jq .
```

## Emergency Recovery

```bash
# Restart all services
docker compose -f docker/docker-compose.dev.yml restart

# Full rebuild
docker compose -f docker/docker-compose.dev.yml down
docker compose -f docker/docker-compose.dev.yml build --no-cache
docker compose -f docker/docker-compose.dev.yml up -d

# Nuclear option (removes everything)
docker compose -f docker/docker-compose.dev.yml down -v
docker system prune -a -f
docker compose -f docker/docker-compose.dev.yml up -d --build
```

---

*Document Version: 1.0*  
*Last Updated: December 2025*
