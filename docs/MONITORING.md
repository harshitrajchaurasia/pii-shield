# PI Remover - Monitoring Guide

> **Production monitoring, logging, health checks, and alerting for PI Remover services.**
>
> **Version:** 2.12.0 | Modular Microservices Architecture

---

## Table of Contents

1. [Health Check Endpoints](#health-check-endpoints)
2. [Logging Configuration](#logging-configuration)
3. [Container Monitoring](#container-monitoring)
4. [Metrics to Track](#metrics-to-track)
5. [Alerting Setup](#alerting-setup)
6. [GCP Cloud Monitoring](#gcp-cloud-monitoring)
7. [Log Analysis](#log-analysis)

---

# Health Check Endpoints

## API Gateway (pi-gateway)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Basic health check |
| `/dev/health` | GET | No | DEV environment health |
| `/prod/health` | GET | No | PROD environment health |

### Health Check Response

```json
{
  "status": "healthy",
  "environment": "production",
  "version": "2.12.0",
  "timestamp": "2025-12-16T10:30:00Z",
  "components": {
    "api": "healthy",
    "core_engine": "healthy",
    "ner_model": "loaded"
  }
}
```

### Health Check Scripts

**Linux/WSL2:**
```bash
# DEV health check
curl -s http://localhost:8080/dev/health | jq .

# PROD health check
curl -s http://localhost:9080/prod/health | jq .

# Web service health
curl -s http://localhost:8082/health | jq .
```

**PowerShell:**
```powershell
# DEV health check
Invoke-RestMethod -Uri "http://localhost:8080/dev/health"

# PROD health check
Invoke-RestMethod -Uri "http://localhost:9080/prod/health"
```

### Automated Health Check Script

```bash
#!/bin/bash
# health-check.sh - Run from cron or monitoring system

API_URL="${API_URL:-http://localhost:8080}"
WEB_URL="${WEB_URL:-http://localhost:8082}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"

check_health() {
    local url=$1
    local name=$2
    
    response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url/health")
    
    if [ "$response" = "200" ]; then
        echo "✓ $name: healthy"
        return 0
    else
        echo "✗ $name: unhealthy (HTTP $response)"
        
        # Send alert if webhook configured
        if [ -n "$ALERT_WEBHOOK" ]; then
            curl -X POST "$ALERT_WEBHOOK" \
                -H "Content-Type: application/json" \
                -d "{\"text\": \"🚨 PI Remover Alert: $name is unhealthy (HTTP $response)\"}"
        fi
        return 1
    fi
}

echo "PI Remover Health Check - $(date)"
echo "================================"

check_health "$API_URL" "API Gateway"
check_health "$WEB_URL" "Web Service"
```

---

# Logging Configuration

## Log Levels

| Level | Description | When to Use |
|-------|-------------|-------------|
| `DEBUG` | Detailed diagnostic info | Development only |
| `INFO` | General operational info | Default for DEV |
| `WARNING` | Something unexpected happened | Default for PROD |
| `ERROR` | Error occurred but service continues | Always logged |
| `CRITICAL` | Service cannot continue | Always logged |

## Environment Variables

```bash
# Set log level
LOG_LEVEL=INFO          # DEV default
LOG_LEVEL=WARNING       # PROD recommended

# Enable JSON logging (for log aggregators)
LOG_FORMAT=json

# Log to file
LOG_FILE=/var/log/pi-remover/app.log
```

## Docker Logging

### View Real-time Logs

```bash
# All containers
docker compose -f docker/docker-compose.prod.yml logs -f

# Specific service
docker logs -f pi-gateway-prod

# Last 100 lines
docker logs --tail 100 pi-gateway-prod

# With timestamps
docker logs -t pi-gateway-prod
```

### Docker Logging Drivers

Configure in `docker-compose.yml`:

```yaml
services:
  pi-gateway:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

For production with log aggregation:

```yaml
services:
  pi-gateway:
    logging:
      driver: "syslog"
      options:
        syslog-address: "tcp://logserver:514"
        tag: "pi-gateway-prod"
```

## Log Format

### Standard Format (Development)
```
2025-12-13 10:30:45 INFO [pi_remover.core] Processing request: 1234 chars
2025-12-13 10:30:45 INFO [pi_remover.core] Detected 5 PI items in 0.023s
```

### JSON Format (Production)
```json
{
  "timestamp": "2025-12-13T10:30:45.123Z",
  "level": "INFO",
  "logger": "pi_remover.core",
  "message": "Processing request",
  "request_id": "abc-123",
  "chars": 1234,
  "duration_ms": 23
}
```

---

# Container Monitoring

## Docker Stats

```bash
# Real-time resource usage
docker stats pi-gateway-prod pi-web-service-prod

# Output:
# CONTAINER         CPU %   MEM USAGE / LIMIT     MEM %   NET I/O
# pi-gateway-prod   2.5%    512MiB / 1GiB         50%     1.2MB / 500KB
# pi-web-prod       0.5%    128MiB / 512MiB       25%     500KB / 200KB
```

## Container Health Status

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' pi-gateway-prod

# Detailed health check history
docker inspect --format='{{json .State.Health}}' pi-gateway-prod | jq .
```

## Resource Limits

Ensure containers have appropriate resource limits:

```yaml
# docker-compose.prod.yml
services:
  pi-gateway:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

# Metrics to Track

## Key Performance Indicators (KPIs)

| Metric | Description | Target | Alert Threshold |
|--------|-------------|--------|-----------------|
| **Response Time (p95)** | 95th percentile latency | < 500ms | > 1000ms |
| **Error Rate** | % of 5xx responses | < 1% | > 5% |
| **Request Rate** | Requests per second | N/A | > 1000/s (capacity) |
| **Memory Usage** | Container memory | < 80% | > 90% |
| **CPU Usage** | Container CPU | < 70% | > 85% |
| **Queue Depth** | Pending requests | < 100 | > 500 |

## Application Metrics

### Request Metrics
- `pi_remover_requests_total` - Total requests processed
- `pi_remover_request_duration_seconds` - Request latency histogram
- `pi_remover_request_size_bytes` - Input text size
- `pi_remover_pi_items_detected` - PI items found per request

### Business Metrics
- `pi_remover_emails_redacted` - Emails redacted count
- `pi_remover_phones_redacted` - Phone numbers redacted
- `pi_remover_names_redacted` - Names redacted (NER)
- `pi_remover_batch_size` - Batch request sizes

### System Metrics
- `pi_remover_ner_model_loaded` - NER model status (1=loaded, 0=not)
- `pi_remover_memory_usage_bytes` - Process memory
- `pi_remover_active_connections` - Current connections

## Prometheus Metrics Endpoint (Future)

```yaml
# Planned for v2.6.0
GET /metrics

# Example output:
pi_remover_requests_total{method="POST",endpoint="/v1/redact",status="200"} 12345
pi_remover_request_duration_seconds_bucket{le="0.1"} 10000
pi_remover_request_duration_seconds_bucket{le="0.5"} 12000
pi_remover_request_duration_seconds_bucket{le="1.0"} 12300
```

---

# Alerting Setup

## Alert Conditions

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| Service Down | Health check fails 3x | Critical | Page on-call |
| High Error Rate | > 5% errors for 5 min | High | Notify team |
| High Latency | p95 > 2s for 5 min | Medium | Investigate |
| Memory Warning | > 85% for 10 min | Medium | Scale or restart |
| Memory Critical | > 95% | High | Auto-restart |
| Rate Limit Hit | 429 responses > 10/min | Low | Review limits |

## Simple Alerting Script

```bash
#!/bin/bash
# monitor.sh - Simple monitoring with alerts

SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
CHECK_INTERVAL=60  # seconds

send_alert() {
    local message=$1
    local severity=$2
    
    curl -X POST "$SLACK_WEBHOOK" \
        -H 'Content-Type: application/json' \
        -d "{
            \"text\": \"$severity PI Remover Alert\",
            \"attachments\": [{
                \"color\": \"$([ \"$severity\" = \"🚨\" ] && echo 'danger' || echo 'warning')\",
                \"text\": \"$message\",
                \"footer\": \"$(hostname) | $(date)\"
            }]
        }"
}

while true; do
    # Check API Gateway
    if ! curl -sf http://localhost:9080/prod/health > /dev/null; then
        send_alert "PROD API Gateway is not responding!" "🚨"
    fi
    
    # Check Web Service
    if ! curl -sf http://localhost:9082/health > /dev/null; then
        send_alert "PROD Web Service is not responding!" "🚨"
    fi
    
    # Check memory usage
    mem_usage=$(docker stats --no-stream --format "{{.MemPerc}}" pi-gateway-prod | tr -d '%')
    if (( $(echo "$mem_usage > 90" | bc -l) )); then
        send_alert "PROD API Gateway memory at ${mem_usage}%!" "⚠️"
    fi
    
    sleep $CHECK_INTERVAL
done
```

---

# GCP Cloud Monitoring

## Cloud Run Metrics

When deployed to GCP Cloud Run, these metrics are automatically available:

| Metric | Description |
|--------|-------------|
| `run.googleapis.com/request_count` | Total requests |
| `run.googleapis.com/request_latencies` | Request latency distribution |
| `run.googleapis.com/container/cpu/utilizations` | CPU usage |
| `run.googleapis.com/container/memory/utilizations` | Memory usage |
| `run.googleapis.com/container/instance_count` | Active instances |

## Enable Cloud Monitoring

```bash
# Enable Cloud Monitoring API
gcloud services enable monitoring.googleapis.com

# View metrics in console
# https://console.cloud.google.com/monitoring
```

## Create Alert Policy (gcloud)

```bash
# Create uptime check
gcloud monitoring uptime-check-configs create pi-remover-prod-uptime \
    --display-name="PI Remover PROD API" \
    --http-check-path="/prod/health" \
    --http-check-request-method=GET \
    --monitored-resource-type=cloud-run-revision \
    --monitored-resource-labels="service_name=pi-remover-api-prod,location=us-central1"

# Create alert policy
gcloud alpha monitoring policies create \
    --display-name="PI Remover High Error Rate" \
    --condition-display-name="Error rate > 5%" \
    --condition-filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class="5xx"' \
    --condition-threshold-value=0.05 \
    --condition-threshold-comparison=COMPARISON_GT \
    --notification-channels="projects/YOUR_PROJECT/notificationChannels/CHANNEL_ID"
```

## Cloud Logging Queries

```sql
-- All errors in last hour
resource.type="cloud_run_revision"
resource.labels.service_name="pi-remover-api-prod"
severity>=ERROR
timestamp>="2025-12-13T09:00:00Z"

-- Slow requests (> 1 second)
resource.type="cloud_run_revision"
resource.labels.service_name="pi-remover-api-prod"
httpRequest.latency>"1s"

-- Auth failures
resource.type="cloud_run_revision"
jsonPayload.message:"authentication failed"
```

---

# Log Analysis

## Common Log Queries

### Find Errors

```bash
# Docker logs
docker logs pi-gateway-prod 2>&1 | grep -i error

# With context
docker logs pi-gateway-prod 2>&1 | grep -B 2 -A 2 -i error
```

### Find Slow Requests

```bash
# Look for duration warnings
docker logs pi-gateway-prod 2>&1 | grep -E "duration.*[0-9]{4,}ms"
```

### Find Authentication Issues

```bash
docker logs pi-gateway-prod 2>&1 | grep -i "auth\|token\|401\|403"
```

### Request Volume Analysis

```bash
# Count requests per minute (if using JSON logging)
docker logs pi-gateway-prod 2>&1 | \
    grep "Processing request" | \
    cut -d'T' -f2 | cut -d':' -f1-2 | \
    sort | uniq -c
```

## Log Rotation

### Docker Log Rotation

```bash
# Configure Docker daemon (/etc/docker/daemon.json)
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "5"
  }
}

# Restart Docker
sudo systemctl restart docker
```

### Application Log Rotation

```bash
# /etc/logrotate.d/pi-remover
/var/log/pi-remover/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
    sharedscripts
    postrotate
        docker kill -s USR1 pi-gateway-prod 2>/dev/null || true
    endscript
}
```

---

# Quick Reference

## Health Check URLs

| Environment | API Gateway | Web Service |
|-------------|-------------|-------------|
| DEV | http://localhost:8080/dev/health | http://localhost:8082/health |
| PROD | http://localhost:9080/prod/health | http://localhost:9082/health |
| GCP DEV | https://pi-remover-api-dev-xxx.run.app/health | https://pi-remover-web-dev-xxx.run.app/health |
| GCP PROD | https://pi-remover-api-prod-xxx.run.app/health | https://pi-remover-web-prod-xxx.run.app/health |

## Essential Commands

```bash
# View all container stats
docker stats

# View logs with follow
docker compose -f docker/docker-compose.prod.yml logs -f

# Restart unhealthy container
docker restart pi-gateway-prod

# Check container health
docker inspect --format='{{.State.Health.Status}}' pi-gateway-prod
```

---

*Document Version: 1.0*  
*Last Updated: December 2025*
