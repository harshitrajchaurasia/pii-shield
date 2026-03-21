#!/bin/bash
# =============================================================================
# PI Remover - Promote DEV to PRODUCTION on Google Cloud Platform
# =============================================================================
#
# This script promotes the DEV Cloud Run service to PRODUCTION on GCP.
# It includes pre-flight checks, testing, traffic migration, and rollback support.
#
# Usage:
#   chmod +x promote-to-prod-gcp.sh
#   ./promote-to-prod-gcp.sh [--skip-tests] [--skip-confirmation] [--rollback]
#
# Options:
#   --skip-tests          Skip running pytest (not recommended)
#   --skip-confirmation   Skip production deployment confirmation
#   --rollback            Rollback PROD to previous revision
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - DEV environment deployed to Cloud Run
#   - PROD secrets configured in Secret Manager
#
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
REGION="us-central1"
PROJECT_ID=""
VERSION="v2.9.0"

# Service names (must match deploy-gcp.sh)
API_SERVICE_DEV="pi-gateway-dev"
API_SERVICE_PROD="pi-gateway-prod"
WEB_SERVICE_DEV="pi-web-dev"
WEB_SERVICE_PROD="pi-web-prod"

# Default values
SKIP_TESTS=false
SKIP_CONFIRMATION=false
ROLLBACK=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-confirmation)
            SKIP_CONFIRMATION=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        --project)
            PROJECT_ID="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --skip-tests          Skip running pytest (not recommended)"
            echo "  --skip-confirmation   Skip production deployment confirmation"
            echo "  --rollback            Rollback PROD to previous revision"
            echo "  --project PROJECT_ID  GCP Project ID (default: current project)"
            echo "  --region REGION       GCP Region (default: us-central1)"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Step tracking
CURRENT_STEP=0
TOTAL_STEPS=7

print_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo ""
    echo -e "${GREEN}[$CURRENT_STEP/$TOTAL_STEPS] $1${NC}"
    echo "------------------------------------------------------------"
}

# Banner
echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      PI REMOVER - GCP PROMOTION: DEV → PROD                   ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# Handle Rollback
# =============================================================================
if $ROLLBACK; then
    echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                    ROLLBACK MODE                              ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Get project if not set
    if [ -z "$PROJECT_ID" ]; then
        PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    fi
    
    echo -e "${CYAN}Rolling back PROD services to previous revision...${NC}"
    echo ""
    
    # List recent revisions for API
    echo -e "${CYAN}API Service Revisions:${NC}"
    gcloud run revisions list --service=$API_SERVICE_PROD --region=$REGION --limit=5 \
        --format="table(name,active,creationTimestamp)"
    
    echo ""
    read -p "Enter API revision to rollback to (or press Enter to skip): " api_revision
    
    if [ -n "$api_revision" ]; then
        echo -e "${CYAN}Rolling back API to $api_revision...${NC}"
        gcloud run services update-traffic $API_SERVICE_PROD \
            --region=$REGION \
            --to-revisions=$api_revision=100
        echo -e "${GREEN}  ✓ API rolled back to $api_revision${NC}"
    fi
    
    echo ""
    echo -e "${CYAN}Web Service Revisions:${NC}"
    gcloud run revisions list --service=$WEB_SERVICE_PROD --region=$REGION --limit=5 \
        --format="table(name,active,creationTimestamp)"
    
    echo ""
    read -p "Enter Web revision to rollback to (or press Enter to skip): " web_revision
    
    if [ -n "$web_revision" ]; then
        echo -e "${CYAN}Rolling back Web to $web_revision...${NC}"
        gcloud run services update-traffic $WEB_SERVICE_PROD \
            --region=$REGION \
            --to-revisions=$web_revision=100
        echo -e "${GREEN}  ✓ Web rolled back to $web_revision${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}Rollback complete.${NC}"
    exit 0
fi

# =============================================================================
# STEP 1: Pre-flight Checks
# =============================================================================
print_step "Pre-flight Checks"

# Check gcloud
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}  ✗ gcloud CLI not found. Please install Google Cloud SDK.${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ gcloud CLI found${NC}"

# Check authentication
if ! gcloud auth print-identity-token &> /dev/null; then
    echo -e "${RED}  ✗ Not authenticated. Run: gcloud auth login${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ gcloud authenticated${NC}"

# Get project
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo -e "${RED}  ✗ No GCP project configured. Set with: gcloud config set project PROJECT_ID${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}  ✓ GCP Project: $PROJECT_ID${NC}"

# Check DEV services exist
echo -e "${CYAN}  Checking DEV services...${NC}"
if ! gcloud run services describe $API_SERVICE_DEV --region=$REGION --format="value(status.url)" &>/dev/null; then
    echo -e "${RED}  ✗ DEV API service not found: $API_SERVICE_DEV${NC}"
    echo -e "${YELLOW}    Deploy DEV first: ./deploy-gcp.sh --env dev${NC}"
    exit 1
fi
DEV_API_URL=$(gcloud run services describe $API_SERVICE_DEV --region=$REGION --format="value(status.url)")
echo -e "${GREEN}  ✓ DEV API Service: $DEV_API_URL${NC}"

if ! gcloud run services describe $WEB_SERVICE_DEV --region=$REGION --format="value(status.url)" &>/dev/null; then
    echo -e "${RED}  ✗ DEV Web service not found: $WEB_SERVICE_DEV${NC}"
    exit 1
fi
DEV_WEB_URL=$(gcloud run services describe $WEB_SERVICE_DEV --region=$REGION --format="value(status.url)")
echo -e "${GREEN}  ✓ DEV Web Service: $DEV_WEB_URL${NC}"

# Get DEV image tags
DEV_API_IMAGE=$(gcloud run services describe $API_SERVICE_DEV --region=$REGION --format="value(spec.template.spec.containers[0].image)")
DEV_WEB_IMAGE=$(gcloud run services describe $WEB_SERVICE_DEV --region=$REGION --format="value(spec.template.spec.containers[0].image)")
echo -e "${GREEN}  ✓ DEV API Image: $DEV_API_IMAGE${NC}"
echo -e "${GREEN}  ✓ DEV Web Image: $DEV_WEB_IMAGE${NC}"

# =============================================================================
# STEP 2: Run Tests
# =============================================================================
print_step "Running Tests"

if $SKIP_TESTS; then
    echo -e "${YELLOW}  ⚠ Tests skipped (not recommended for production)${NC}"
else
    echo -e "${CYAN}  Running pytest...${NC}"
    
    cd "$PROJECT_ROOT"
    
    if python -m pytest tests/ -v --tb=short; then
        echo -e "${GREEN}  ✓ All tests passed${NC}"
    else
        echo ""
        echo -e "${RED}  ✗ Tests failed!${NC}"
        echo -e "${YELLOW}    Fix the failing tests before promoting to production.${NC}"
        exit 1
    fi
fi

# =============================================================================
# STEP 3: Test DEV Health
# =============================================================================
print_step "Testing DEV Environment Health"

# Get auth token for authenticated requests
AUTH_TOKEN=$(gcloud auth print-identity-token)

echo -e "${CYAN}  Testing DEV API health...${NC}"
if curl -s --fail -H "Authorization: Bearer $AUTH_TOKEN" "${DEV_API_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ DEV API Gateway is healthy${NC}"
else
    echo -e "${YELLOW}  ⚠ DEV API health check failed (may require authentication)${NC}"
fi

echo -e "${CYAN}  Testing DEV Web health...${NC}"
if curl -s --fail "${DEV_WEB_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ DEV Web Service is healthy${NC}"
else
    echo -e "${YELLOW}  ⚠ DEV Web health check failed${NC}"
fi

# =============================================================================
# STEP 4: Check Current PROD Status
# =============================================================================
print_step "Checking Current PROD Status"

PROD_EXISTS=false
if gcloud run services describe $API_SERVICE_PROD --region=$REGION &>/dev/null; then
    PROD_EXISTS=true
    PROD_API_URL=$(gcloud run services describe $API_SERVICE_PROD --region=$REGION --format="value(status.url)")
    CURRENT_PROD_IMAGE=$(gcloud run services describe $API_SERVICE_PROD --region=$REGION --format="value(spec.template.spec.containers[0].image)")
    echo -e "${GREEN}  ✓ Current PROD API: $PROD_API_URL${NC}"
    echo -e "${CYAN}    Current image: $CURRENT_PROD_IMAGE${NC}"
else
    echo -e "${YELLOW}  ⚠ PROD API service does not exist (will be created)${NC}"
fi

if $PROD_EXISTS && gcloud run services describe $WEB_SERVICE_PROD --region=$REGION &>/dev/null; then
    PROD_WEB_URL=$(gcloud run services describe $WEB_SERVICE_PROD --region=$REGION --format="value(status.url)")
    echo -e "${GREEN}  ✓ Current PROD Web: $PROD_WEB_URL${NC}"
else
    echo -e "${YELLOW}  ⚠ PROD Web service does not exist (will be created)${NC}"
fi

# =============================================================================
# STEP 5: Confirmation
# =============================================================================
print_step "Confirmation"

echo ""
echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║               READY TO PROMOTE TO PRODUCTION                  ║${NC}"
echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Promotion Plan:${NC}"
echo -e "  • DEV API image → PROD API service"
echo -e "  • DEV Web image → PROD Web service"
echo ""
echo -e "${CYAN}Images to deploy:${NC}"
echo -e "  API: $DEV_API_IMAGE"
echo -e "  Web: $DEV_WEB_IMAGE"
echo ""

if $PROD_EXISTS; then
    echo -e "${CYAN}Rollback available:${NC}"
    echo -e "  Run: ./promote-to-prod-gcp.sh --rollback"
    echo ""
fi

if ! $SKIP_CONFIRMATION; then
    read -p "Type 'PROMOTE' to deploy to production: " confirmation
    if [ "$confirmation" != "PROMOTE" ]; then
        echo ""
        echo -e "${YELLOW}Promotion cancelled.${NC}"
        exit 0
    fi
fi

# =============================================================================
# STEP 6: Deploy to Production
# =============================================================================
print_step "Deploying to Production"

ARTIFACT_REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/pi-remover"

# Tag DEV images for PROD (or use same images with different service config)
echo -e "${CYAN}  Deploying API to PROD...${NC}"

# Deploy PROD API with production secrets
gcloud run deploy $API_SERVICE_PROD \
    --image=$DEV_API_IMAGE \
    --region=$REGION \
    --platform=managed \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=1 \
    --max-instances=10 \
    --timeout=300 \
    --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO" \
    --set-secrets="API_CLIENT_ID=pi-remover-prod-client-id:latest,API_CLIENT_SECRET=pi-remover-prod-client-secret:latest,JWT_SECRET_KEY=pi-remover-jwt-secret:latest" \
    --allow-unauthenticated \
    --quiet

PROD_API_URL=$(gcloud run services describe $API_SERVICE_PROD --region=$REGION --format="value(status.url)")
echo -e "${GREEN}  ✓ PROD API deployed: $PROD_API_URL${NC}"

echo -e "${CYAN}  Deploying Web to PROD...${NC}"

# Deploy PROD Web
gcloud run deploy $WEB_SERVICE_PROD \
    --image=$DEV_WEB_IMAGE \
    --region=$REGION \
    --platform=managed \
    --memory=512Mi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=5 \
    --timeout=60 \
    --set-env-vars="ENVIRONMENT=production,API_URL=${PROD_API_URL}" \
    --allow-unauthenticated \
    --quiet

PROD_WEB_URL=$(gcloud run services describe $WEB_SERVICE_PROD --region=$REGION --format="value(status.url)")
echo -e "${GREEN}  ✓ PROD Web deployed: $PROD_WEB_URL${NC}"

# =============================================================================
# STEP 7: Post-Deployment Verification
# =============================================================================
print_step "Post-Deployment Verification"

echo -e "${CYAN}  Waiting for services to stabilize...${NC}"
sleep 10

ALL_HEALTHY=true

# Test production endpoints
echo -e "${CYAN}  Testing PROD API health...${NC}"
if curl -s --fail "${PROD_API_URL}/prod/health" > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ PROD API Gateway: HEALTHY${NC}"
else
    # Try without /prod prefix
    if curl -s --fail "${PROD_API_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ PROD API Gateway: HEALTHY${NC}"
    else
        echo -e "${RED}  ✗ PROD API Gateway: UNHEALTHY${NC}"
        ALL_HEALTHY=false
    fi
fi

echo -e "${CYAN}  Testing PROD Web health...${NC}"
if curl -s --fail "${PROD_WEB_URL}/health" > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ PROD Web Service: HEALTHY${NC}"
else
    echo -e "${RED}  ✗ PROD Web Service: UNHEALTHY${NC}"
    ALL_HEALTHY=false
fi

# Final status
echo ""
if $ALL_HEALTHY; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              GCP PROMOTION SUCCESSFUL                         ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Production services are now live:${NC}"
    echo -e "  • API Gateway:  ${YELLOW}$PROD_API_URL${NC}"
    echo -e "  • Web Service:  ${YELLOW}$PROD_WEB_URL${NC}"
    echo ""
    echo -e "${CYAN}PROD Credentials:${NC}"
    echo -e "  Client ID:      pi-prod-client"
    echo -e "  Client Secret:  (stored in Secret Manager)"
    echo ""
    echo -e "${CYAN}Quick Test:${NC}"
    echo -e "  curl ${PROD_API_URL}/prod/health"
    echo ""
    echo -e "${MAGENTA}Rollback if needed:${NC}"
    echo -e "  ./promote-to-prod-gcp.sh --rollback"
else
    echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║       PROMOTION COMPLETE - SOME SERVICES NEED ATTENTION       ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Check Cloud Run logs for issues:${NC}"
    echo -e "  gcloud run services logs read $API_SERVICE_PROD --region=$REGION"
    echo ""
    echo -e "${MAGENTA}Rollback if needed:${NC}"
    echo -e "  ./promote-to-prod-gcp.sh --rollback"
fi
echo ""
