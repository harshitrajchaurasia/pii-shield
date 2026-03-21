#!/bin/bash
# =============================================================================
# PI Remover - Google Cloud Platform Deployment Script
# =============================================================================
#
# This script deploys PI Remover to Google Cloud Run.
#
# Usage:
#   chmod +x deploy-gcp.sh
#   ./deploy-gcp.sh [--env dev|prod] [--build] [--setup]
#
# Options:
#   --env dev|prod    Deploy to DEV or PROD environment (default: dev)
#   --build           Build and push Docker images before deploying
#   --setup           Run initial GCP setup (APIs, secrets, etc.)
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Docker installed (for building images)
#   - GCP project with billing enabled
#
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="dev"
BUILD_IMAGES=false
RUN_SETUP=false
REGION="us-central1"
VERSION="v2.9.0"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --build)
            BUILD_IMAGES=true
            shift
            ;;
        --setup)
            RUN_SETUP=true
            shift
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--env dev|prod] [--build] [--setup] [--region REGION] [--version VERSION]"
            echo ""
            echo "Options:"
            echo "  --env dev|prod    Deploy to DEV or PROD environment (default: dev)"
            echo "  --build           Build and push Docker images before deploying"
            echo "  --setup           Run initial GCP setup (APIs, secrets, etc.)"
            echo "  --region REGION   GCP region (default: us-central1)"
            echo "  --version VERSION Image version tag (default: v2.9.0)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     PI REMOVER - Google Cloud Platform Deployment            ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# Check Prerequisites
# =============================================================================
echo -e "${CYAN}[PREFLIGHT] Checking prerequisites...${NC}"

# Check gcloud
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}  ✗ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ gcloud CLI found${NC}"

# Check authentication
if ! gcloud auth print-identity-token &> /dev/null; then
    echo -e "${YELLOW}  ⚠ Not authenticated. Running 'gcloud auth login'...${NC}"
    gcloud auth login
fi
echo -e "${GREEN}  ✓ Authenticated with GCP${NC}"

# Get project ID
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}  ✗ No GCP project set. Run: gcloud config set project YOUR_PROJECT_ID${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Project: $PROJECT_ID${NC}"

# Check Docker (if building)
if $BUILD_IMAGES; then
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}  ✗ Docker not found. Required for --build option.${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ Docker found${NC}"
fi

# Registry path
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/pi-remover"

echo ""
echo -e "${CYAN}Configuration:${NC}"
echo -e "  Environment: ${YELLOW}${ENVIRONMENT^^}${NC}"
echo -e "  Project ID:  ${PROJECT_ID}"
echo -e "  Region:      ${REGION}"
echo -e "  Registry:    ${REGISTRY}"
echo -e "  Version:     ${VERSION}"
echo ""

# =============================================================================
# Initial Setup (if --setup)
# =============================================================================
if $RUN_SETUP; then
    echo -e "${CYAN}[SETUP] Running initial GCP setup...${NC}"
    echo ""
    
    # Enable APIs
    echo -e "${CYAN}[SETUP 1/4] Enabling required APIs...${NC}"
    gcloud services enable \
        cloudbuild.googleapis.com \
        run.googleapis.com \
        artifactregistry.googleapis.com \
        secretmanager.googleapis.com
    echo -e "${GREEN}  ✓ APIs enabled${NC}"
    
    # Create Artifact Registry repository
    echo ""
    echo -e "${CYAN}[SETUP 2/4] Creating Artifact Registry repository...${NC}"
    if gcloud artifacts repositories describe pi-remover --location=$REGION &> /dev/null; then
        echo -e "${YELLOW}  ⚠ Repository 'pi-remover' already exists${NC}"
    else
        gcloud artifacts repositories create pi-remover \
            --repository-format=docker \
            --location=$REGION \
            --description="PI Remover Docker images"
        echo -e "${GREEN}  ✓ Repository created${NC}"
    fi
    
    # Configure Docker authentication
    echo ""
    echo -e "${CYAN}[SETUP 3/4] Configuring Docker authentication...${NC}"
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
    echo -e "${GREEN}  ✓ Docker authentication configured${NC}"
    
    # Create secrets
    echo ""
    echo -e "${CYAN}[SETUP 4/4] Creating secrets...${NC}"
    
    # DEV JWT Secret
    if gcloud secrets describe pi-jwt-secret-dev &> /dev/null; then
        echo -e "${YELLOW}  ⚠ Secret 'pi-jwt-secret-dev' already exists${NC}"
    else
        echo -n "YOUR_DEV_JWT_SECRET_HERE" | \
            gcloud secrets create pi-jwt-secret-dev --data-file=-
        echo -e "${GREEN}  ✓ Created pi-jwt-secret-dev${NC}"
    fi
    
    # PROD JWT Secret
    if gcloud secrets describe pi-jwt-secret-prod &> /dev/null; then
        echo -e "${YELLOW}  ⚠ Secret 'pi-jwt-secret-prod' already exists${NC}"
    else
        echo -n "YOUR_PROD_JWT_SECRET_HERE" | \
            gcloud secrets create pi-jwt-secret-prod --data-file=-
        echo -e "${GREEN}  ✓ Created pi-jwt-secret-prod${NC}"
    fi
    
    # DEV Client Credentials
    if gcloud secrets describe pi-client-creds-dev &> /dev/null; then
        echo -e "${YELLOW}  ⚠ Secret 'pi-client-creds-dev' already exists${NC}"
    else
        echo -n "pi-dev-client:YOUR_DEV_CLIENT_SECRET_HERE:development" | \
            gcloud secrets create pi-client-creds-dev --data-file=-
        echo -e "${GREEN}  ✓ Created pi-client-creds-dev${NC}"
    fi
    
    # PROD Client Credentials
    if gcloud secrets describe pi-client-creds-prod &> /dev/null; then
        echo -e "${YELLOW}  ⚠ Secret 'pi-client-creds-prod' already exists${NC}"
    else
        echo -n "pi-prod-client:YOUR_PROD_CLIENT_SECRET_HERE:production" | \
            gcloud secrets create pi-client-creds-prod --data-file=-
        echo -e "${GREEN}  ✓ Created pi-client-creds-prod${NC}"
    fi
    
    # Grant Cloud Run access to secrets
    echo ""
    echo -e "${CYAN}Granting Cloud Run access to secrets...${NC}"
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    
    for secret in pi-jwt-secret-dev pi-jwt-secret-prod pi-client-creds-dev pi-client-creds-prod; do
        gcloud secrets add-iam-policy-binding $secret \
            --member="serviceAccount:${SERVICE_ACCOUNT}" \
            --role="roles/secretmanager.secretAccessor" \
            --quiet 2>/dev/null || true
    done
    echo -e "${GREEN}  ✓ Secret access granted${NC}"
    
    echo ""
    echo -e "${GREEN}[SETUP] Initial setup complete!${NC}"
    echo ""
fi

# =============================================================================
# Build and Push Images (if --build)
# =============================================================================
if $BUILD_IMAGES; then
    echo -e "${CYAN}[BUILD] Building and pushing Docker images...${NC}"
    echo ""
    
    cd "$PROJECT_ROOT"
    
    # Build API Gateway
    echo -e "${CYAN}[BUILD 1/2] Building API Gateway image...${NC}"
    docker build -t ${REGISTRY}/pi-gateway:${VERSION} -f api_service/Dockerfile .
    docker push ${REGISTRY}/pi-gateway:${VERSION}
    docker tag ${REGISTRY}/pi-gateway:${VERSION} ${REGISTRY}/pi-gateway:latest
    docker push ${REGISTRY}/pi-gateway:latest
    echo -e "${GREEN}  ✓ API Gateway image pushed${NC}"
    
    # Build Web Service
    echo ""
    echo -e "${CYAN}[BUILD 2/2] Building Web Service image...${NC}"
    docker build -t ${REGISTRY}/pi-web:${VERSION} -f web_service/Dockerfile .
    docker push ${REGISTRY}/pi-web:${VERSION}
    docker tag ${REGISTRY}/pi-web:${VERSION} ${REGISTRY}/pi-web:latest
    docker push ${REGISTRY}/pi-web:latest
    echo -e "${GREEN}  ✓ Web Service image pushed${NC}"
    
    echo ""
    echo -e "${GREEN}[BUILD] Images built and pushed successfully!${NC}"
    echo ""
fi

# =============================================================================
# Deploy to Cloud Run
# =============================================================================
echo -e "${CYAN}[DEPLOY] Deploying to Cloud Run (${ENVIRONMENT^^})...${NC}"
echo ""

if [ "$ENVIRONMENT" == "dev" ]; then
    # DEV Environment Configuration
    JWT_SECRET="pi-jwt-secret-dev"
    CLIENT_CREDS="pi-client-creds-dev"
    API_SERVICE="pi-gateway-dev"
    WEB_SERVICE="pi-web-dev"
    API_MEMORY="2Gi"
    API_CPU="2"
    WEB_MEMORY="1Gi"
    WEB_CPU="1"
    MIN_INSTANCES="0"
    MAX_INSTANCES="5"
    LOG_LEVEL="DEBUG"
    RATE_LIMIT="1000"
    CORS_ORIGINS="*"
else
    # PROD Environment Configuration
    JWT_SECRET="pi-jwt-secret-prod"
    CLIENT_CREDS="pi-client-creds-prod"
    API_SERVICE="pi-gateway-prod"
    WEB_SERVICE="pi-web-prod"
    API_MEMORY="4Gi"
    API_CPU="4"
    WEB_MEMORY="2Gi"
    WEB_CPU="2"
    MIN_INSTANCES="1"
    MAX_INSTANCES="10"
    LOG_LEVEL="WARNING"
    RATE_LIMIT="100"
    CORS_ORIGINS="https://your-domain.com"
fi

# Deploy API Gateway
echo -e "${CYAN}[DEPLOY 1/2] Deploying API Gateway (${API_SERVICE})...${NC}"
gcloud run deploy $API_SERVICE \
    --image=${REGISTRY}/pi-gateway:latest \
    --platform=managed \
    --region=$REGION \
    --memory=$API_MEMORY \
    --cpu=$API_CPU \
    --timeout=300 \
    --concurrency=80 \
    --min-instances=$MIN_INSTANCES \
    --max-instances=$MAX_INSTANCES \
    --allow-unauthenticated \
    --set-env-vars="ENVIRONMENT=${ENVIRONMENT}" \
    --set-env-vars="LOG_LEVEL=${LOG_LEVEL}" \
    --set-env-vars="ENABLE_NER=true" \
    --set-env-vars="RATE_LIMIT_REQUESTS=${RATE_LIMIT}" \
    --set-env-vars="CORS_ORIGINS=${CORS_ORIGINS}" \
    --set-secrets="JWT_SECRET_KEY=${JWT_SECRET}:latest" \
    --set-secrets="AUTH_CLIENTS=${CLIENT_CREDS}:latest" \
    --quiet

API_URL=$(gcloud run services describe $API_SERVICE --region=$REGION --format='value(status.url)')
echo -e "${GREEN}  ✓ API Gateway deployed: ${API_URL}${NC}"

# Deploy Web Service
echo ""
echo -e "${CYAN}[DEPLOY 2/2] Deploying Web Service (${WEB_SERVICE})...${NC}"
gcloud run deploy $WEB_SERVICE \
    --image=${REGISTRY}/pi-web:latest \
    --platform=managed \
    --region=$REGION \
    --memory=$WEB_MEMORY \
    --cpu=$WEB_CPU \
    --timeout=300 \
    --concurrency=80 \
    --min-instances=$MIN_INSTANCES \
    --max-instances=$MAX_INSTANCES \
    --allow-unauthenticated \
    --set-env-vars="ENVIRONMENT=${ENVIRONMENT}" \
    --set-env-vars="LOG_LEVEL=${LOG_LEVEL}" \
    --quiet

WEB_URL=$(gcloud run services describe $WEB_SERVICE --region=$REGION --format='value(status.url)')
echo -e "${GREEN}  ✓ Web Service deployed: ${WEB_URL}${NC}"

# =============================================================================
# Verify Deployment
# =============================================================================
echo ""
echo -e "${CYAN}[VERIFY] Testing deployed services...${NC}"

# Test API health
echo ""
echo -e "Testing API Gateway health..."
if [ "$ENVIRONMENT" == "dev" ]; then
    HEALTH_ENDPOINT="${API_URL}/dev/health"
else
    HEALTH_ENDPOINT="${API_URL}/prod/health"
fi

if curl -s --fail "$HEALTH_ENDPOINT" > /dev/null; then
    echo -e "${GREEN}  ✓ API Gateway is healthy${NC}"
else
    echo -e "${YELLOW}  ⚠ API Gateway health check failed (may need a moment to start)${NC}"
fi

# Test Web UI
echo ""
echo -e "Testing Web Service..."
if curl -s --fail "$WEB_URL" > /dev/null; then
    echo -e "${GREEN}  ✓ Web Service is healthy${NC}"
else
    echo -e "${YELLOW}  ⚠ Web Service health check failed (may need a moment to start)${NC}"
fi

# =============================================================================
# Done
# =============================================================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              GCP DEPLOYMENT COMPLETE                          ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Environment: ${ENVIRONMENT^^}${NC}"
echo ""
echo -e "${CYAN}Service URLs:${NC}"
echo -e "  API Gateway: ${YELLOW}${API_URL}${NC}"
echo -e "  Web UI:      ${YELLOW}${WEB_URL}${NC}"
echo ""
echo -e "${CYAN}API Endpoints:${NC}"
if [ "$ENVIRONMENT" == "dev" ]; then
    echo -e "  Auth:   ${API_URL}/dev/auth/token"
    echo -e "  Redact: ${API_URL}/dev/v1/redact"
    echo -e "  Health: ${API_URL}/dev/health"
else
    echo -e "  Auth:   ${API_URL}/prod/auth/token"
    echo -e "  Redact: ${API_URL}/prod/v1/redact"
    echo -e "  Health: ${API_URL}/prod/health"
fi
echo ""
echo -e "${CYAN}Test with:${NC}"
if [ "$ENVIRONMENT" == "dev" ]; then
    echo -e "  curl -X POST ${API_URL}/dev/auth/token \\"
    echo -e "    -H 'Content-Type: application/json' \\"
    echo -e "    -d '{\"client_id\":\"pi-dev-client\",\"client_secret\":\"YOUR_DEV_CLIENT_SECRET_HERE\"}'"
else
    echo -e "  curl -X POST ${API_URL}/prod/auth/token \\"
    echo -e "    -H 'Content-Type: application/json' \\"
    echo -e "    -d '{\"client_id\":\"pi-prod-client\",\"client_secret\":\"YOUR_PROD_CLIENT_SECRET_HERE\"}'"
fi
echo ""
