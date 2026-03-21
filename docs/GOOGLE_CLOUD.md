# PI Remover as a Service - Google Cloud Architecture Guide

> **Version:** 2.12.0 | Modular Microservices Architecture
>
> **📋 Related Documentation:**
> - For **quick deployment steps**, see [DEPLOYMENT.md](./DEPLOYMENT.md) - covers WSL2, RHEL, and basic GCP Cloud Run deployment
> - This document provides the **advanced cloud-native architecture** with async processing, Pub/Sub workers, and enterprise scaling

## Executive Summary

This guide details the architecture for deploying PI Remover as a **scalable, cost-effective cloud service** on Google Cloud Platform (GCP). This is an advanced architecture document covering enterprise-grade GCP deployment with async processing workers, Pub/Sub message queues, and Firestore state management.

For simpler containerized deployments to Cloud Run, start with [DEPLOYMENT.md](./DEPLOYMENT.md).

### Key Features
- **Web UI** for file upload and configuration
- **Toggleable NER** (spaCy) for accuracy vs speed tradeoff
- **Column selection** - users choose which columns to clean
- **PI type selection** - users choose what types of PI to redact
- **Async processing** - large files processed in background
- **Cost-effective** - pay only for what you use

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACE                                  │
│                     (Cloud Run - Static Frontend)                           │
│    ┌──────────────────────────────────────────────────────────────────┐    │
│    │  1. Upload CSV file                                               │    │
│    │  2. Select columns to clean                                       │    │
│    │  3. Toggle NER (on/off)                                          │    │
│    │  4. Select PI types to redact                                    │    │
│    │  5. Submit for processing                                        │    │
│    └──────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│                        (Cloud Run - FastAPI)                                │
│    ┌──────────────────────────────────────────────────────────────────┐    │
│    │  POST /upload          - Upload file, get signed URL             │    │
│    │  POST /process         - Start processing job                    │    │
│    │  GET  /status/{job_id} - Check job status                        │    │
│    │  GET  /download/{job_id} - Get download URL                      │    │
│    │  GET  /columns         - Get columns from uploaded file          │    │
│    └──────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌───────────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐
│   CLOUD STORAGE       │  │    PUB/SUB      │  │        FIRESTORE            │
│   (File Storage)      │  │  (Job Queue)    │  │    (Job Metadata)           │
│  ┌─────────────────┐  │  │                 │  │  ┌───────────────────────┐  │
│  │ /uploads/       │  │  │ pi-removal-jobs │  │  │ job_id: string        │  │
│  │ /processed/     │  │  │     topic       │  │  │ status: pending/      │  │
│  │ /temp/          │  │  │                 │  │  │         processing/   │  │
│  └─────────────────┘  │  │                 │  │  │         completed     │  │
└───────────────────────┘  └─────────────────┘  │  │ progress: 0-100       │  │
                                      │         │  │ config: {...}         │  │
                                      │         │  │ created_at: timestamp │  │
                                      ▼         │  └───────────────────────┘  │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PROCESSING WORKERS                                 │
│                                                                              │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │   FAST WORKER (Cloud Run)   │    │    NER WORKER (Cloud Run)           │ │
│  │   - 512MB RAM               │    │    - 4GB RAM (spaCy model)          │ │
│  │   - Regex + Dictionary      │    │    - Full NER + Regex + Dictionary  │ │
│  │   - ~10,000 rows/sec        │    │    - ~500-1000 rows/sec             │ │
│  │   - Cost: ~$0.00002/request │    │    - Cost: ~$0.00008/request        │ │
│  └─────────────────────────────┘    └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Cost Analysis

### Pricing Breakdown (2025)

| Component | Pricing | Free Tier |
|-----------|---------|-----------|
| **Cloud Run** | $0.000024/vCPU-sec + $0.0000025/GiB-sec | 180,000 vCPU-sec/month |
| **Cloud Storage** | $0.020/GB/month (Standard) | 5 GB/month |
| **Pub/Sub** | $40/TiB throughput | 10 GB/month |
| **Firestore** | $0.18/100K reads, $0.18/100K writes | 50K reads, 20K writes/day |

### Cost Estimates by Usage

| Usage Level | Files/Month | Avg Size | NER Usage | Est. Monthly Cost |
|-------------|-------------|----------|-----------|-------------------|
| **Light** | 10 files | 50 MB | 20% | **$0 - $2** (free tier) |
| **Medium** | 100 files | 100 MB | 30% | **$5 - $15** |
| **Heavy** | 500 files | 200 MB | 50% | **$30 - $60** |
| **Enterprise** | 2000+ files | 500 MB | 40% | **$100 - $250** |

### Cost Optimization Strategies

1. **NER Toggle** - Let users disable NER for 5x cost reduction
2. **Chunked Processing** - Process large files in chunks to avoid timeouts
3. **Auto-scaling to Zero** - Cloud Run scales to 0 when not in use
4. **Regional Storage** - Keep all resources in same region (no egress fees)
5. **Cleanup Policy** - Auto-delete processed files after 24-48 hours

---

## Project Structure

```
pi-remover-service/
├── frontend/                    # React/Vue frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── FileUpload.tsx
│   │   │   ├── ColumnSelector.tsx
│   │   │   ├── PITypeSelector.tsx
│   │   │   ├── NERToggle.tsx
│   │   │   ├── ProcessingStatus.tsx
│   │   │   └── DownloadButton.tsx
│   │   ├── App.tsx
│   │   └── api.ts
│   ├── Dockerfile
│   └── package.json
│
├── api/                         # FastAPI backend
│   ├── main.py
│   ├── routes/
│   │   ├── upload.py
│   │   ├── process.py
│   │   └── status.py
│   ├── services/
│   │   ├── storage.py
│   │   ├── pubsub.py
│   │   └── firestore.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── worker-fast/                 # Fast processing worker (no NER)
│   ├── main.py
│   ├── pi_remover_fast.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── worker-ner/                  # NER processing worker
│   ├── main.py
│   ├── pi_remover/
│   ├── Dockerfile
│   └── requirements.txt
│
├── terraform/                   # Infrastructure as Code
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── cloudbuild.yaml             # CI/CD pipeline
└── README.md
```

---

## Step-by-Step Deployment

### Prerequisites

```bash
# Install Google Cloud SDK
# https://cloud.google.com/sdk/docs/install

# Login and set project
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Enable required APIs
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    storage.googleapis.com \
    pubsub.googleapis.com \
    firestore.googleapis.com \
    artifactregistry.googleapis.com
```

### Step 1: Create Cloud Storage Buckets

```bash
# Create buckets (replace YOUR_PROJECT_ID)
PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"

# Uploads bucket (temporary, auto-delete after 2 days)
gsutil mb -l $REGION gs://${PROJECT_ID}-pi-uploads
gsutil lifecycle set lifecycle-2days.json gs://${PROJECT_ID}-pi-uploads

# Processed bucket (auto-delete after 7 days)
gsutil mb -l $REGION gs://${PROJECT_ID}-pi-processed
gsutil lifecycle set lifecycle-7days.json gs://${PROJECT_ID}-pi-processed
```

Create `lifecycle-2days.json`:
```json
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 2}
    }
  ]
}
```

Create `lifecycle-7days.json`:
```json
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 7}
    }
  ]
}
```

### Step 2: Create Pub/Sub Topic and Subscription

```bash
# Create topic for job processing
gcloud pubsub topics create pi-removal-jobs

# Create push subscription to worker
gcloud pubsub subscriptions create pi-removal-jobs-sub \
    --topic=pi-removal-jobs \
    --push-endpoint=https://pi-worker-fast-HASH.run.app/process \
    --ack-deadline=600
```

### Step 3: Create Firestore Database

```bash
# Create Firestore in Native mode
gcloud firestore databases create --location=$REGION
```

### Step 4: Build and Deploy API Service

Create `api/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run expects port 8080
ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Create `api/requirements.txt`:
```
fastapi==0.109.0
uvicorn==0.27.0
google-cloud-storage==2.14.0
google-cloud-pubsub==2.19.0
google-cloud-firestore==2.14.0
pandas==2.1.4
python-multipart==0.0.6
pydantic==2.5.3
```

Create `api/main.py`:
```python
"""
PI Remover API Service
======================
FastAPI backend for PI Remover cloud service
"""

import os
import uuid
import json
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage, pubsub_v1, firestore
import pandas as pd

app = FastAPI(title="PI Remover API", version="2.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
db = firestore.Client()

# Configuration
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
UPLOAD_BUCKET = f"{PROJECT_ID}-pi-uploads"
PROCESSED_BUCKET = f"{PROJECT_ID}-pi-processed"
PUBSUB_TOPIC = f"projects/{PROJECT_ID}/topics/pi-removal-jobs"


# ============ MODELS ============

class ProcessConfig(BaseModel):
    job_id: str
    columns: List[str]
    enable_ner: bool = False
    pi_types: dict = {
        "emails": True,
        "phones": True,
        "emp_ids": True,
        "names": True,
        "ips": True,
        "urls": True,
        "credentials": True,
        "asset_ids": True,
        "hostnames": True,
    }


class JobStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    message: Optional[str] = None
    download_url: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    config: Optional[dict] = None
    stats: Optional[dict] = None


# ============ ENDPOINTS ============

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "2.0"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a CSV file and get column information.
    Returns job_id and list of columns for user selection.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    # Generate unique job ID
    job_id = str(uuid.uuid4())

    # Upload to Cloud Storage
    bucket = storage_client.bucket(UPLOAD_BUCKET)
    blob = bucket.blob(f"{job_id}/input.csv")

    # Read file content
    content = await file.read()
    blob.upload_from_string(content, content_type="text/csv")

    # Parse CSV to get columns
    import io
    df = pd.read_csv(io.BytesIO(content), nrows=5)
    columns = df.columns.tolist()

    # Get file stats
    file_size = len(content)
    row_count = sum(1 for _ in io.BytesIO(content)) - 1  # Approximate

    # Create job record in Firestore
    job_ref = db.collection("jobs").document(job_id)
    job_ref.set({
        "job_id": job_id,
        "status": "uploaded",
        "progress": 0,
        "filename": file.filename,
        "file_size": file_size,
        "columns": columns,
        "created_at": datetime.utcnow().isoformat(),
    })

    return {
        "job_id": job_id,
        "filename": file.filename,
        "file_size": file_size,
        "columns": columns,
        "message": "File uploaded successfully. Select columns and PI types to process."
    }


@app.post("/process")
async def start_processing(config: ProcessConfig):
    """
    Start processing a previously uploaded file.
    Publishes job to Pub/Sub for async processing.
    """
    job_id = config.job_id

    # Verify job exists
    job_ref = db.collection("jobs").document(job_id)
    job = job_ref.get()

    if not job.exists:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = job.to_dict()
    if job_data["status"] not in ["uploaded", "failed"]:
        raise HTTPException(status_code=400, detail=f"Job already {job_data['status']}")

    # Validate columns
    available_columns = job_data.get("columns", [])
    invalid_columns = [c for c in config.columns if c not in available_columns]
    if invalid_columns:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid columns: {invalid_columns}. Available: {available_columns}"
        )

    # Update job status
    job_ref.update({
        "status": "pending",
        "config": config.dict(),
        "processing_started_at": datetime.utcnow().isoformat(),
    })

    # Determine which worker to use based on NER toggle
    worker_type = "ner" if config.enable_ner else "fast"

    # Publish to Pub/Sub
    message_data = json.dumps({
        "job_id": job_id,
        "worker_type": worker_type,
        "config": config.dict(),
    }).encode("utf-8")

    future = publisher.publish(PUBSUB_TOPIC, message_data)
    message_id = future.result()

    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Processing started with {'NER enabled' if config.enable_ner else 'fast mode'}",
        "pubsub_message_id": message_id,
    }


@app.get("/status/{job_id}")
async def get_status(job_id: str) -> JobStatus:
    """Get the status of a processing job."""
    job_ref = db.collection("jobs").document(job_id)
    job = job_ref.get()

    if not job.exists:
        raise HTTPException(status_code=404, detail="Job not found")

    job_data = job.to_dict()

    # Generate download URL if completed
    download_url = None
    if job_data["status"] == "completed":
        bucket = storage_client.bucket(PROCESSED_BUCKET)
        blob = bucket.blob(f"{job_id}/output.csv")
        if blob.exists():
            download_url = blob.generate_signed_url(
                expiration=timedelta(hours=24),
                method="GET"
            )

    return JobStatus(
        job_id=job_id,
        status=job_data.get("status", "unknown"),
        progress=job_data.get("progress", 0),
        message=job_data.get("message"),
        download_url=download_url,
        created_at=job_data.get("created_at", ""),
        completed_at=job_data.get("completed_at"),
        config=job_data.get("config"),
        stats=job_data.get("stats"),
    )


@app.get("/columns/{job_id}")
async def get_columns(job_id: str):
    """Get available columns for a job."""
    job_ref = db.collection("jobs").document(job_id)
    job = job_ref.get()

    if not job.exists:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"columns": job.to_dict().get("columns", [])}


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files."""
    # Delete from Firestore
    db.collection("jobs").document(job_id).delete()

    # Delete from Cloud Storage
    for bucket_name in [UPLOAD_BUCKET, PROCESSED_BUCKET]:
        bucket = storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=f"{job_id}/")
        for blob in blobs:
            blob.delete()

    return {"message": "Job deleted successfully"}
```

Deploy API:
```bash
cd api

# Build and push to Artifact Registry
gcloud builds submit --tag gcr.io/$PROJECT_ID/pi-remover-api

# Deploy to Cloud Run
gcloud run deploy pi-remover-api \
    --image gcr.io/$PROJECT_ID/pi-remover-api \
    --platform managed \
    --region $REGION \
    --memory 512Mi \
    --timeout 300 \
    --allow-unauthenticated \
    --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID
```

### Step 5: Build and Deploy Fast Worker

Create `worker-fast/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Create `worker-fast/requirements.txt`:
```
fastapi==0.109.0
uvicorn==0.27.0
google-cloud-storage==2.14.0
google-cloud-firestore==2.14.0
pandas==2.1.4
tqdm==4.66.1
```

Create `worker-fast/main.py`:
```python
"""
PI Remover Fast Worker
======================
Processes CSV files using regex + dictionary (no NER)
Triggered by Pub/Sub messages
"""

import os
import json
import base64
import re
from datetime import datetime
from typing import List, Set

from fastapi import FastAPI, Request, HTTPException
from google.cloud import storage, firestore
import pandas as pd
from tqdm import tqdm

app = FastAPI(title="PI Remover Fast Worker")

# Initialize clients
storage_client = storage.Client()
db = firestore.Client()

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
UPLOAD_BUCKET = f"{PROJECT_ID}-pi-uploads"
PROCESSED_BUCKET = f"{PROJECT_ID}-pi-processed"


# ============ PI REMOVAL PATTERNS ============

class PIPatterns:
    """Compiled regex patterns for PI detection."""

    # Emails
    EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')

    # Phone numbers
    PHONE_INDIAN = re.compile(r'(?:\+91[\s.-]?)?[6-9]\d{9}\b')
    PHONE_INTL = re.compile(r'\+\d{1,3}[\s.-]?\d{4,14}')
    PHONE_TOLL_FREE = re.compile(r'\b1800[\s.-]?\d{3}[\s.-]?\d{4}\b')

    # Employee IDs
    EMP_ID_PREFIXED = re.compile(r'(?i)\b(?:ad|iada|cad|ws|pr|sa|oth|vo|da|di)\.(?:[a-z0-9]{4,}|\d{4,})\b')
    EMP_ID_LABELED = re.compile(r'(?i)(?:emp(?:loyee)?[\s._-]*(?:id|no|number)?|user[\s._-]*(?:id)?|associate[\s._-]*id)[\s:=]*(\d{6,8})')

    # Asset IDs
    ASSET_ID = re.compile(r'\b\d{1,2}(?:HW|SW|HWCL|NL)\d{6,}\b', re.IGNORECASE)

    # IP Addresses
    IPV4 = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?::\d{1,5})?\b')
    MAC = re.compile(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b')

    # Hostnames
    HOSTNAME = re.compile(r'\b[A-Z]{2}\d{2}[A-Z]{3}\d{8}\b')

    # URLs
    URL = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

    # Credentials
    PASSWORD = re.compile(r'(?i)(?:password|pwd|pass(?:word)?|passwd)[\s]*(?:is|:|=|-)[\s]*[^\s,]{4,30}')

    # Government IDs
    AADHAAR = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')
    PAN = re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b')

    # Windows paths with usernames
    WIN_PATH = re.compile(r'[Cc]:\\[Uu]sers\\[^\\]+\\')

    # UPI IDs
    UPI = re.compile(r'\b[a-zA-Z0-9._-]+@(?:paytm|gpay|phonepe|upi|ybl|okaxis|okhdfcbank|oksbi|axisbank)\b')


# Indian names dictionary (subset for demo)
INDIAN_NAMES: Set[str] = {
    "aakash", "aarav", "abhay", "abhijit", "abhilash", "abhinav", "abhishek",
    "aditya", "ajay", "amit", "anand", "anil", "arjun", "arun", "ashish",
    "deepak", "gaurav", "hari", "karan", "mahesh", "manoj", "nikhil",
    "pankaj", "rahul", "raj", "rajesh", "rakesh", "ravi", "rohit", "sachin",
    "sanjay", "sunil", "vijay", "vikas", "vikram", "vishal", "vivek",
    "aishwarya", "ananya", "ankita", "divya", "jyoti", "kavita", "lakshmi",
    "neha", "pooja", "priya", "priyanka", "sakshi", "shreya", "sneha",
    "agarwal", "arora", "banerjee", "chauhan", "das", "gupta", "jain",
    "kumar", "mehta", "mishra", "patel", "sharma", "singh", "verma",
    "vaishnavi", "saswade", "keya", "sarkar", "jayashree", "mahapatra",
    "anwesha", "mapui", "suman", "ramya", "felipe", "priya",
}


def redact_text(text: str, config: dict) -> str:
    """Apply PI redaction to text based on config."""
    if not text or pd.isna(text):
        return text

    text = str(text)
    pi_types = config.get("pi_types", {})

    # Apply patterns based on config
    if pi_types.get("emails", True):
        text = PIPatterns.EMAIL.sub("[EMAIL]", text)

    if pi_types.get("phones", True):
        text = PIPatterns.PHONE_TOLL_FREE.sub("[PHONE]", text)
        text = PIPatterns.PHONE_INDIAN.sub("[PHONE]", text)
        text = PIPatterns.PHONE_INTL.sub("[PHONE]", text)

    if pi_types.get("emp_ids", True):
        text = PIPatterns.EMP_ID_PREFIXED.sub("[EMP_ID]", text)
        text = PIPatterns.EMP_ID_LABELED.sub(r"[EMP_ID]", text)
        # Context-aware 7-digit detection
        text = re.sub(r'(?i)(?:teams|ping|mail|contact|reach|call)[\s(]*([12]\d{6})', r'[EMP_ID]', text)

    if pi_types.get("asset_ids", True):
        text = PIPatterns.ASSET_ID.sub("[ASSET_ID]", text)

    if pi_types.get("ips", True):
        text = PIPatterns.IPV4.sub("[IP]", text)
        text = PIPatterns.MAC.sub("[MAC]", text)

    if pi_types.get("hostnames", True):
        text = PIPatterns.HOSTNAME.sub("[HOSTNAME]", text)

    if pi_types.get("urls", True):
        text = PIPatterns.URL.sub("[URL]", text)

    if pi_types.get("credentials", True):
        text = PIPatterns.PASSWORD.sub("[CREDENTIAL]", text)
        text = PIPatterns.WIN_PATH.sub(r"C:\\Users\\[USER]\\", text)

    if pi_types.get("names", True):
        # Dictionary-based name detection
        for name in INDIAN_NAMES:
            pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
            text = pattern.sub("[NAME]", text)

    return text


def process_csv(job_id: str, config: dict, update_progress):
    """Process a CSV file with PI removal."""

    # Download input file
    upload_bucket = storage_client.bucket(UPLOAD_BUCKET)
    input_blob = upload_bucket.blob(f"{job_id}/input.csv")
    input_data = input_blob.download_as_bytes()

    # Read CSV
    import io
    df = pd.read_csv(io.BytesIO(input_data))
    total_rows = len(df)

    columns_to_clean = config.get("columns", [])

    # Process each column
    processed_rows = 0
    for col in columns_to_clean:
        if col in df.columns:
            new_col = f"{col}_cleaned"
            df[new_col] = df[col].apply(lambda x: redact_text(x, config))

        processed_rows += total_rows
        progress = min(95, int((processed_rows / (len(columns_to_clean) * total_rows)) * 95))
        update_progress(progress)

    # Upload processed file
    processed_bucket = storage_client.bucket(PROCESSED_BUCKET)
    output_blob = processed_bucket.blob(f"{job_id}/output.csv")

    output_buffer = io.BytesIO()
    df.to_csv(output_buffer, index=False)
    output_buffer.seek(0)
    output_blob.upload_from_file(output_buffer, content_type="text/csv")

    return {
        "total_rows": total_rows,
        "columns_cleaned": columns_to_clean,
    }


@app.post("/process")
async def handle_pubsub(request: Request):
    """Handle Pub/Sub push message."""

    # Parse Pub/Sub message
    envelope = await request.json()
    if not envelope:
        raise HTTPException(status_code=400, detail="No Pub/Sub message received")

    pubsub_message = envelope.get("message", {})
    if not pubsub_message:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub message format")

    # Decode message data
    data = base64.b64decode(pubsub_message.get("data", "")).decode("utf-8")
    message = json.loads(data)

    job_id = message.get("job_id")
    worker_type = message.get("worker_type", "fast")
    config = message.get("config", {})

    # Skip if this is meant for NER worker
    if worker_type != "fast":
        return {"status": "skipped", "reason": "Message for NER worker"}

    # Update job status to processing
    job_ref = db.collection("jobs").document(job_id)
    job_ref.update({
        "status": "processing",
        "progress": 0,
        "worker": "fast",
    })

    def update_progress(progress: int):
        job_ref.update({"progress": progress})

    try:
        # Process the file
        stats = process_csv(job_id, config, update_progress)

        # Update job as completed
        job_ref.update({
            "status": "completed",
            "progress": 100,
            "completed_at": datetime.utcnow().isoformat(),
            "stats": stats,
        })

        return {"status": "completed", "job_id": job_id}

    except Exception as e:
        job_ref.update({
            "status": "failed",
            "message": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy", "worker": "fast"}
```

Deploy Fast Worker:
```bash
cd worker-fast

gcloud builds submit --tag gcr.io/$PROJECT_ID/pi-worker-fast

gcloud run deploy pi-worker-fast \
    --image gcr.io/$PROJECT_ID/pi-worker-fast \
    --platform managed \
    --region $REGION \
    --memory 1Gi \
    --timeout 900 \
    --concurrency 1 \
    --max-instances 10 \
    --no-allow-unauthenticated \
    --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID
```

### Step 6: Build and Deploy NER Worker

Create `worker-ner/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model during build
RUN python -m spacy download en_core_web_lg

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Create `worker-ner/requirements.txt`:
```
fastapi==0.109.0
uvicorn==0.27.0
google-cloud-storage==2.14.0
google-cloud-firestore==2.14.0
pandas==2.1.4
spacy==3.7.2
tqdm==4.66.1
```

Create `worker-ner/main.py`:
```python
"""
PI Remover NER Worker
=====================
Processes CSV files using spaCy NER + regex + dictionary
Triggered by Pub/Sub messages
"""

import os
import json
import base64
import re
from datetime import datetime
from typing import List, Set

from fastapi import FastAPI, Request, HTTPException
from google.cloud import storage, firestore
import pandas as pd
import spacy

app = FastAPI(title="PI Remover NER Worker")

# Initialize clients
storage_client = storage.Client()
db = firestore.Client()

# Load spaCy model at startup
print("Loading spaCy model...")
nlp = spacy.load("en_core_web_lg")
print("spaCy model loaded!")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "your-project-id")
UPLOAD_BUCKET = f"{PROJECT_ID}-pi-uploads"
PROCESSED_BUCKET = f"{PROJECT_ID}-pi-processed"


# ============ PI REMOVAL WITH NER ============

class PIPatterns:
    """Compiled regex patterns for PI detection."""
    EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
    PHONE_INDIAN = re.compile(r'(?:\+91[\s.-]?)?[6-9]\d{9}\b')
    PHONE_INTL = re.compile(r'\+\d{1,3}[\s.-]?\d{4,14}')
    PHONE_TOLL_FREE = re.compile(r'\b1800[\s.-]?\d{3}[\s.-]?\d{4}\b')
    EMP_ID_PREFIXED = re.compile(r'(?i)\b(?:ad|iada|cad|ws|pr|sa|oth|vo|da|di)\.(?:[a-z0-9]{4,}|\d{4,})\b')
    EMP_ID_LABELED = re.compile(r'(?i)(?:emp(?:loyee)?[\s._-]*(?:id|no|number)?|user[\s._-]*(?:id)?|associate[\s._-]*id)[\s:=]*(\d{6,8})')
    ASSET_ID = re.compile(r'\b\d{1,2}(?:HW|SW|HWCL|NL)\d{6,}\b', re.IGNORECASE)
    IPV4 = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?::\d{1,5})?\b')
    MAC = re.compile(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b')
    HOSTNAME = re.compile(r'\b[A-Z]{2}\d{2}[A-Z]{3}\d{8}\b')
    URL = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')
    PASSWORD = re.compile(r'(?i)(?:password|pwd|pass(?:word)?|passwd)[\s]*(?:is|:|=|-)[\s]*[^\s,]{4,30}')
    WIN_PATH = re.compile(r'[Cc]:\\[Uu]sers\\[^\\]+\\')


INDIAN_NAMES: Set[str] = {
    "aakash", "aarav", "abhay", "abhijit", "abhilash", "abhinav", "abhishek",
    "aditya", "ajay", "amit", "anand", "anil", "arjun", "arun", "ashish",
    "deepak", "gaurav", "hari", "karan", "mahesh", "manoj", "nikhil",
    "pankaj", "rahul", "raj", "rajesh", "rakesh", "ravi", "rohit", "sachin",
    "vaishnavi", "saswade", "keya", "sarkar", "jayashree", "mahapatra",
    "sharma", "kumar", "singh", "patel", "gupta", "verma", "mishra",
}


def redact_text_with_ner(text: str, config: dict) -> str:
    """Apply PI redaction using spaCy NER + regex."""
    if not text or pd.isna(text):
        return text

    text = str(text)
    pi_types = config.get("pi_types", {})

    # Apply NER for names, orgs, locations
    if pi_types.get("names", True):
        doc = nlp(text)
        # Sort entities by start position (reverse) to replace from end
        entities = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)
        for ent in entities:
            if ent.label_ == "PERSON":
                text = text[:ent.start_char] + "[NAME]" + text[ent.end_char:]
            elif ent.label_ == "ORG":
                text = text[:ent.start_char] + "[ORG]" + text[ent.end_char:]
            elif ent.label_ in ("GPE", "LOC"):
                text = text[:ent.start_char] + "[LOCATION]" + text[ent.end_char:]

    # Apply regex patterns (same as fast worker)
    if pi_types.get("emails", True):
        text = PIPatterns.EMAIL.sub("[EMAIL]", text)

    if pi_types.get("phones", True):
        text = PIPatterns.PHONE_TOLL_FREE.sub("[PHONE]", text)
        text = PIPatterns.PHONE_INDIAN.sub("[PHONE]", text)
        text = PIPatterns.PHONE_INTL.sub("[PHONE]", text)

    if pi_types.get("emp_ids", True):
        text = PIPatterns.EMP_ID_PREFIXED.sub("[EMP_ID]", text)
        text = PIPatterns.EMP_ID_LABELED.sub(r"[EMP_ID]", text)
        text = re.sub(r'(?i)(?:teams|ping|mail|contact|reach|call)[\s(]*([12]\d{6})', r'[EMP_ID]', text)

    if pi_types.get("asset_ids", True):
        text = PIPatterns.ASSET_ID.sub("[ASSET_ID]", text)

    if pi_types.get("ips", True):
        text = PIPatterns.IPV4.sub("[IP]", text)
        text = PIPatterns.MAC.sub("[MAC]", text)

    if pi_types.get("hostnames", True):
        text = PIPatterns.HOSTNAME.sub("[HOSTNAME]", text)

    if pi_types.get("urls", True):
        text = PIPatterns.URL.sub("[URL]", text)

    if pi_types.get("credentials", True):
        text = PIPatterns.PASSWORD.sub("[CREDENTIAL]", text)
        text = PIPatterns.WIN_PATH.sub(r"C:\\Users\\[USER]\\", text)

    # Dictionary names (catch any missed by NER)
    if pi_types.get("names", True):
        for name in INDIAN_NAMES:
            pattern = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
            text = pattern.sub("[NAME]", text)

    return text


def process_csv_with_ner(job_id: str, config: dict, update_progress):
    """Process a CSV file with NER-based PI removal."""

    upload_bucket = storage_client.bucket(UPLOAD_BUCKET)
    input_blob = upload_bucket.blob(f"{job_id}/input.csv")
    input_data = input_blob.download_as_bytes()

    import io
    df = pd.read_csv(io.BytesIO(input_data))
    total_rows = len(df)

    columns_to_clean = config.get("columns", [])

    # Process each column with progress updates
    for col_idx, col in enumerate(columns_to_clean):
        if col in df.columns:
            new_col = f"{col}_cleaned"

            # Process in batches for progress updates
            batch_size = max(1, total_rows // 20)
            results = []

            for i in range(0, total_rows, batch_size):
                batch = df[col].iloc[i:i+batch_size]
                batch_results = batch.apply(lambda x: redact_text_with_ner(x, config))
                results.extend(batch_results.tolist())

                # Update progress
                overall_progress = ((col_idx * total_rows + i + len(batch)) /
                                   (len(columns_to_clean) * total_rows)) * 95
                update_progress(int(overall_progress))

            df[new_col] = results

    # Upload processed file
    processed_bucket = storage_client.bucket(PROCESSED_BUCKET)
    output_blob = processed_bucket.blob(f"{job_id}/output.csv")

    output_buffer = io.BytesIO()
    df.to_csv(output_buffer, index=False)
    output_buffer.seek(0)
    output_blob.upload_from_file(output_buffer, content_type="text/csv")

    return {
        "total_rows": total_rows,
        "columns_cleaned": columns_to_clean,
        "ner_enabled": True,
    }


@app.post("/process")
async def handle_pubsub(request: Request):
    """Handle Pub/Sub push message for NER processing."""

    envelope = await request.json()
    pubsub_message = envelope.get("message", {})

    data = base64.b64decode(pubsub_message.get("data", "")).decode("utf-8")
    message = json.loads(data)

    job_id = message.get("job_id")
    worker_type = message.get("worker_type", "fast")
    config = message.get("config", {})

    # Skip if this is meant for fast worker
    if worker_type != "ner":
        return {"status": "skipped", "reason": "Message for fast worker"}

    job_ref = db.collection("jobs").document(job_id)
    job_ref.update({
        "status": "processing",
        "progress": 0,
        "worker": "ner",
    })

    def update_progress(progress: int):
        job_ref.update({"progress": progress})

    try:
        stats = process_csv_with_ner(job_id, config, update_progress)

        job_ref.update({
            "status": "completed",
            "progress": 100,
            "completed_at": datetime.utcnow().isoformat(),
            "stats": stats,
        })

        return {"status": "completed", "job_id": job_id}

    except Exception as e:
        job_ref.update({
            "status": "failed",
            "message": str(e),
        })
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy", "worker": "ner", "spacy_model": "en_core_web_lg"}
```

Deploy NER Worker:
```bash
cd worker-ner

# Build (takes longer due to spaCy model download)
gcloud builds submit --tag gcr.io/$PROJECT_ID/pi-worker-ner --timeout=1200

# Deploy with more memory for spaCy
gcloud run deploy pi-worker-ner \
    --image gcr.io/$PROJECT_ID/pi-worker-ner \
    --platform managed \
    --region $REGION \
    --memory 4Gi \
    --cpu 2 \
    --timeout 900 \
    --concurrency 1 \
    --max-instances 5 \
    --no-allow-unauthenticated \
    --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID
```

### Step 7: Configure Pub/Sub Subscriptions

```bash
# Get service URLs
FAST_WORKER_URL=$(gcloud run services describe pi-worker-fast --region=$REGION --format='value(status.url)')
NER_WORKER_URL=$(gcloud run services describe pi-worker-ner --region=$REGION --format='value(status.url)')

# Create service account for Pub/Sub
gcloud iam service-accounts create pubsub-invoker \
    --display-name "Pub/Sub Cloud Run Invoker"

# Grant invoker permission
gcloud run services add-iam-policy-binding pi-worker-fast \
    --region=$REGION \
    --member=serviceAccount:pubsub-invoker@$PROJECT_ID.iam.gserviceaccount.com \
    --role=roles/run.invoker

gcloud run services add-iam-policy-binding pi-worker-ner \
    --region=$REGION \
    --member=serviceAccount:pubsub-invoker@$PROJECT_ID.iam.gserviceaccount.com \
    --role=roles/run.invoker

# Create subscriptions
gcloud pubsub subscriptions create pi-jobs-fast-sub \
    --topic=pi-removal-jobs \
    --push-endpoint=$FAST_WORKER_URL/process \
    --push-auth-service-account=pubsub-invoker@$PROJECT_ID.iam.gserviceaccount.com \
    --ack-deadline=600

gcloud pubsub subscriptions create pi-jobs-ner-sub \
    --topic=pi-removal-jobs \
    --push-endpoint=$NER_WORKER_URL/process \
    --push-auth-service-account=pubsub-invoker@$PROJECT_ID.iam.gserviceaccount.com \
    --ack-deadline=600
```

### Step 8: Deploy Frontend

Create `frontend/src/App.tsx`:
```tsx
import React, { useState } from 'react';
import './App.css';

interface JobStatus {
  job_id: string;
  status: string;
  progress: number;
  download_url?: string;
  message?: string;
}

const API_URL = process.env.REACT_APP_API_URL || 'https://pi-remover-api-xxx.run.app';

const PI_TYPES = [
  { key: 'emails', label: 'Emails', default: true },
  { key: 'phones', label: 'Phone Numbers', default: true },
  { key: 'emp_ids', label: 'Employee IDs', default: true },
  { key: 'names', label: 'Names', default: true },
  { key: 'ips', label: 'IP Addresses', default: true },
  { key: 'urls', label: 'URLs', default: true },
  { key: 'credentials', label: 'Credentials/Passwords', default: true },
  { key: 'asset_ids', label: 'Asset IDs', default: true },
  { key: 'hostnames', label: 'Hostnames', default: true },
];

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [enableNer, setEnableNer] = useState(false);
  const [piTypes, setPiTypes] = useState<Record<string, boolean>>(
    Object.fromEntries(PI_TYPES.map(pt => [pt.key, pt.default]))
  );
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'upload' | 'configure' | 'processing' | 'done'>('upload');

  const handleUpload = async () => {
    if (!file) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();

      setJobId(data.job_id);
      setColumns(data.columns);
      setStep('configure');
    } catch (error) {
      alert('Upload failed: ' + error);
    }
    setLoading(false);
  };

  const handleProcess = async () => {
    if (!jobId || selectedColumns.length === 0) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: jobId,
          columns: selectedColumns,
          enable_ner: enableNer,
          pi_types: piTypes,
        }),
      });

      if (response.ok) {
        setStep('processing');
        pollStatus();
      }
    } catch (error) {
      alert('Processing failed: ' + error);
    }
    setLoading(false);
  };

  const pollStatus = async () => {
    if (!jobId) return;

    const poll = async () => {
      const response = await fetch(`${API_URL}/status/${jobId}`);
      const data: JobStatus = await response.json();
      setStatus(data);

      if (data.status === 'completed') {
        setStep('done');
      } else if (data.status === 'failed') {
        alert('Processing failed: ' + data.message);
      } else {
        setTimeout(poll, 2000);
      }
    };
    poll();
  };

  return (
    <div className="App">
      <header>
        <h1>PI Remover Service</h1>
        <p>Remove Personal Information from CSV files</p>
      </header>

      <main>
        {step === 'upload' && (
          <section className="upload-section">
            <h2>Step 1: Upload CSV File</h2>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <button onClick={handleUpload} disabled={!file || loading}>
              {loading ? 'Uploading...' : 'Upload'}
            </button>
          </section>
        )}

        {step === 'configure' && (
          <section className="configure-section">
            <h2>Step 2: Configure Processing</h2>

            <div className="config-group">
              <h3>Select Columns to Clean</h3>
              {columns.map(col => (
                <label key={col}>
                  <input
                    type="checkbox"
                    checked={selectedColumns.includes(col)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedColumns([...selectedColumns, col]);
                      } else {
                        setSelectedColumns(selectedColumns.filter(c => c !== col));
                      }
                    }}
                  />
                  {col}
                </label>
              ))}
            </div>

            <div className="config-group">
              <h3>Processing Mode</h3>
              <label className="ner-toggle">
                <input
                  type="checkbox"
                  checked={enableNer}
                  onChange={(e) => setEnableNer(e.target.checked)}
                />
                Enable NER (spaCy) - Better name detection, slower processing
              </label>
              <p className="hint">
                {enableNer
                  ? '~500-1000 rows/sec - Uses AI for better name detection'
                  : '~10,000 rows/sec - Fast regex + dictionary based'}
              </p>
            </div>

            <div className="config-group">
              <h3>Select PI Types to Redact</h3>
              {PI_TYPES.map(pt => (
                <label key={pt.key}>
                  <input
                    type="checkbox"
                    checked={piTypes[pt.key]}
                    onChange={(e) => setPiTypes({...piTypes, [pt.key]: e.target.checked})}
                  />
                  {pt.label}
                </label>
              ))}
            </div>

            <button
              onClick={handleProcess}
              disabled={selectedColumns.length === 0 || loading}
            >
              Start Processing
            </button>
          </section>
        )}

        {step === 'processing' && status && (
          <section className="processing-section">
            <h2>Step 3: Processing</h2>
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{width: `${status.progress}%`}}
              />
            </div>
            <p>{status.progress}% complete</p>
            <p>Status: {status.status}</p>
          </section>
        )}

        {step === 'done' && status?.download_url && (
          <section className="done-section">
            <h2>Processing Complete!</h2>
            <a
              href={status.download_url}
              className="download-button"
              download
            >
              Download Cleaned CSV
            </a>
            <button onClick={() => {
              setStep('upload');
              setFile(null);
              setJobId(null);
              setColumns([]);
              setSelectedColumns([]);
              setStatus(null);
            }}>
              Process Another File
            </button>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
```

Create `frontend/Dockerfile`:
```dockerfile
# Build stage
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

Deploy Frontend:
```bash
cd frontend

# Get API URL
API_URL=$(gcloud run services describe pi-remover-api --region=$REGION --format='value(status.url)')

# Build with API URL
gcloud builds submit \
    --tag gcr.io/$PROJECT_ID/pi-remover-frontend \
    --build-arg REACT_APP_API_URL=$API_URL

# Deploy
gcloud run deploy pi-remover-frontend \
    --image gcr.io/$PROJECT_ID/pi-remover-frontend \
    --platform managed \
    --region $REGION \
    --memory 256Mi \
    --allow-unauthenticated
```

---

## Terraform Deployment (Optional)

For infrastructure-as-code deployment, create `terraform/main.tf`:

```hcl
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "storage.googleapis.com",
    "pubsub.googleapis.com",
    "firestore.googleapis.com",
    "artifactregistry.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# Storage buckets
resource "google_storage_bucket" "uploads" {
  name     = "${var.project_id}-pi-uploads"
  location = var.region

  lifecycle_rule {
    condition {
      age = 2
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "processed" {
  name     = "${var.project_id}-pi-processed"
  location = var.region

  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}

# Pub/Sub topic
resource "google_pubsub_topic" "jobs" {
  name = "pi-removal-jobs"
}

# Firestore database
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}

# Service account for Pub/Sub
resource "google_service_account" "pubsub_invoker" {
  account_id   = "pubsub-invoker"
  display_name = "Pub/Sub Cloud Run Invoker"
}

# Output
output "uploads_bucket" {
  value = google_storage_bucket.uploads.name
}

output "processed_bucket" {
  value = google_storage_bucket.processed.name
}

output "pubsub_topic" {
  value = google_pubsub_topic.jobs.name
}
```

Deploy with Terraform:
```bash
cd terraform
terraform init
terraform plan -var="project_id=$PROJECT_ID"
terraform apply -var="project_id=$PROJECT_ID"
```

---

## Security Best Practices

### 1. Authentication & Authorization

```bash
# Restrict API access with IAP (Identity-Aware Proxy)
gcloud run services update pi-remover-api \
    --ingress=internal-and-cloud-load-balancing

# Create OAuth consent screen and IAP
# (Configure in Cloud Console)
```

### 2. CORS Configuration

Update `api/main.py` for production:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.run.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

### 3. Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/upload")
@limiter.limit("10/minute")
async def upload_file(request: Request, file: UploadFile = File(...)):
    ...
```

### 4. File Size Limits

```python
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Check file size
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large. Max 500MB allowed.")
```

---

## Monitoring & Logging

### Cloud Monitoring Dashboard

```bash
# Create custom dashboard
gcloud monitoring dashboards create --config-from-file=dashboard.json
```

### Key Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `run.googleapis.com/request_count` | Total requests | N/A |
| `run.googleapis.com/request_latencies` | Response time | > 30s |
| `run.googleapis.com/container/cpu/utilizations` | CPU usage | > 80% |
| `run.googleapis.com/container/memory/utilizations` | Memory usage | > 90% |
| `pubsub.googleapis.com/subscription/num_undelivered_messages` | Queue depth | > 100 |

### Logging

```python
import logging
from google.cloud import logging as cloud_logging

# Setup Cloud Logging
client = cloud_logging.Client()
client.setup_logging()

logger = logging.getLogger(__name__)

# Log processing events
logger.info(f"Processing job {job_id}", extra={
    "job_id": job_id,
    "rows": total_rows,
    "ner_enabled": config.get("enable_ner"),
})
```

---

## Cost Optimization Tips

### 1. Use Committed Use Discounts
- For predictable workloads, commit to 1 or 3 year usage for 20-50% savings

### 2. Regional vs Multi-Regional Storage
- Use regional storage (us-central1) instead of multi-regional for 50% savings

### 3. Optimize Worker Configuration

| Workload | Recommended Config |
|----------|-------------------|
| Small files (<10MB) | 512Mi RAM, 1 CPU |
| Medium files (10-100MB) | 1Gi RAM, 1 CPU |
| Large files (>100MB) | 2Gi RAM, 2 CPU |
| NER processing | 4Gi RAM, 2 CPU |

### 4. Auto-Cleanup Policies

```json
{
  "lifecycle_rules": [
    {"age": 1, "action": "SetStorageClass", "storage_class": "NEARLINE"},
    {"age": 7, "action": "Delete"}
  ]
}
```

### 5. Batch Processing for High Volume

For enterprise use, consider:
- Cloud Dataflow for parallel processing
- Batch API for scheduled jobs
- Preemptible/Spot instances for 60-90% cost reduction

---

## API Reference

### POST /upload
Upload a CSV file.

**Request:**
```bash
curl -X POST \
  -F "file=@data.csv" \
  https://api.example.com/upload
```

**Response:**
```json
{
  "job_id": "abc123",
  "filename": "data.csv",
  "file_size": 1048576,
  "columns": ["name", "email", "description"]
}
```

### POST /process
Start processing a job.

**Request:**
```json
{
  "job_id": "abc123",
  "columns": ["email", "description"],
  "enable_ner": false,
  "pi_types": {
    "emails": true,
    "phones": true,
    "names": true
  }
}
```

### GET /status/{job_id}
Get job status.

**Response:**
```json
{
  "job_id": "abc123",
  "status": "completed",
  "progress": 100,
  "download_url": "https://storage.googleapis.com/...",
  "stats": {
    "total_rows": 10000,
    "columns_cleaned": ["email", "description"]
  }
}
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Memory limit exceeded" | Large file or NER model | Increase Cloud Run memory |
| "Request timeout" | Large file processing | Increase timeout, use async |
| "Permission denied" | Missing IAM roles | Grant storage/pubsub roles |
| "Cold start slow" | NER model loading | Use min-instances=1 |

### Debug Commands

```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=pi-remover-api" --limit=100

# Check Pub/Sub messages
gcloud pubsub subscriptions pull pi-jobs-fast-sub --auto-ack --limit=10

# View Firestore jobs
gcloud firestore documents list jobs --limit=10
```

---

## Summary

This deployment provides:

| Feature | Implementation |
|---------|---------------|
| **Scalability** | Auto-scaling Cloud Run (0 to 1000s of instances) |
| **Cost Efficiency** | Pay-per-use, scales to zero when idle |
| **NER Toggle** | User choice between fast (regex) and accurate (NER) |
| **Column Selection** | Users pick which columns to clean |
| **PI Type Selection** | Granular control over what to redact |
| **Async Processing** | Pub/Sub queue for large files |
| **Progress Tracking** | Real-time progress via Firestore |
| **Security** | IAM, signed URLs, CORS, rate limiting |

**Estimated monthly cost for medium usage (100 files, 100MB avg):** **$5-15**

---

## References

- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Cloud Storage Pricing](https://cloud.google.com/storage/pricing)
- [Pub/Sub Pricing](https://cloud.google.com/pubsub/pricing)
- [Cloud Run Best Practices](https://cloud.google.com/run/docs/tips)
- [spaCy on Cloud Run](https://github.com/explosion/spaCy/issues/4617)

---

*Last Updated: 2025-12-12*
*Version: 2.0*
