#!/bin/bash
# =============================================================================
# PI Remover - Promote DEV to PRODUCTION (Linux/WSL2)
# =============================================================================
#
# This script guides through the promotion process from DEV to PROD.
# It includes pre-flight checks, testing, and safe deployment steps.
#
# Usage:
#   chmod +x promote-to-prod.sh
#   ./promote-to-prod.sh [--skip-tests] [--skip-confirmation]
#
# Options:
#   --skip-tests          Skip running pytest (not recommended)
#   --skip-confirmation   Skip production deployment confirmation
#
# Prerequisites:
#   - Docker Engine installed
#   - DEV environment tested
#   - Production environment file configured
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

# Default values
SKIP_TESTS=false
SKIP_CONFIRMATION=false

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
        -h|--help)
            echo "Usage: $0 [--skip-tests] [--skip-confirmation]"
            echo ""
            echo "Options:"
            echo "  --skip-tests          Skip running pytest (not recommended)"
            echo "  --skip-confirmation   Skip production deployment confirmation"
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
DOCKER_DIR="${PROJECT_ROOT}/docker"
PROD_ENV_FILE="${DOCKER_DIR}/.env.prod"

# Step tracking
CURRENT_STEP=0
TOTAL_STEPS=6

print_step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    echo ""
    echo -e "${GREEN}[$CURRENT_STEP/$TOTAL_STEPS] $1${NC}"
    echo "------------------------------------------------------------"
}

# Banner
echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║           PI REMOVER - PROMOTION: DEV → PROD                  ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# STEP 1: Pre-flight Checks
# =============================================================================
print_step "Pre-flight Checks"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}  ✗ Docker not found. Run setup-docker-wsl2.sh or setup-docker-rhel.sh first.${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Docker found${NC}"

# Check Docker daemon
if ! docker info &> /dev/null; then
    echo -e "${YELLOW}  ⚠ Docker daemon not running. Attempting to start...${NC}"
    if command -v systemctl &> /dev/null; then
        sudo systemctl start docker
    else
        sudo service docker start
    fi
    sleep 2
    if ! docker info &> /dev/null; then
        echo -e "${RED}  ✗ Could not start Docker daemon.${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}  ✓ Docker daemon running${NC}"

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}  ✗ Docker Compose not found.${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Docker Compose found${NC}"

# Check environment file
if [ ! -f "$PROD_ENV_FILE" ]; then
    echo -e "${RED}  ✗ Production environment file not found: $PROD_ENV_FILE${NC}"
    echo ""
    echo -e "${YELLOW}  To fix:${NC}"
    echo -e "    cp docker/.env.prod.template docker/.env.prod"
    echo -e "    # Then edit .env.prod with production secrets"
    exit 1
fi
echo -e "${GREEN}  ✓ Production environment file exists${NC}"

# Validate prod env file
if grep -q "REPLACE_WITH" "$PROD_ENV_FILE" 2>/dev/null; then
    echo -e "${RED}  ✗ Production environment file contains unconfigured secrets${NC}"
    echo -e "${YELLOW}    Please update all 'REPLACE_WITH...' placeholders in .env.prod${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Production secrets configured${NC}"

# Check if DEV is running
DEV_RUNNING=false
if docker ps --filter "label=environment=development" --format "{{.Names}}" 2>/dev/null | grep -q .; then
    DEV_RUNNING=true
    echo -e "${GREEN}  ✓ DEV environment is running${NC}"
else
    echo -e "${YELLOW}  ⚠ DEV environment is not running${NC}"
    echo -e "    Consider running deploy-dev.sh first to test changes"
fi

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
# STEP 3: Test DEV Health (if running)
# =============================================================================
print_step "Testing DEV Environment Health"

if $DEV_RUNNING; then
    # Test API Gateway
    echo -e "${CYAN}  Testing API Gateway (http://localhost:8080/dev/health)...${NC}"
    if curl -s --fail http://localhost:8080/dev/health > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ DEV API Gateway is healthy${NC}"
    else
        echo -e "${YELLOW}  ⚠ DEV API Gateway health check failed${NC}"
    fi
    
    # Test Web Service
    echo -e "${CYAN}  Testing Web Service (http://localhost:8082/health)...${NC}"
    if curl -s --fail http://localhost:8082/health > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ DEV Web Service is healthy${NC}"
    else
        echo -e "${YELLOW}  ⚠ DEV Web Service health check failed${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠ DEV not running - skipping health checks${NC}"
fi

# =============================================================================
# STEP 4: Confirmation
# =============================================================================
print_step "Confirmation"

echo ""
echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${YELLOW}║               READY TO PROMOTE TO PRODUCTION                  ║${NC}"
echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}This will:${NC}"
echo -e "  • Stop existing production containers (if any)"
echo -e "  • Build fresh Docker images"
echo -e "  • Deploy to production ports (9080/9082)"
echo -e "  • Run health checks"
echo ""

if ! $SKIP_CONFIRMATION; then
    read -p "Type 'PROMOTE' to deploy to production: " confirmation
    if [ "$confirmation" != "PROMOTE" ]; then
        echo ""
        echo -e "${YELLOW}Promotion cancelled.${NC}"
        exit 0
    fi
fi

# =============================================================================
# STEP 5: Deploy to Production
# =============================================================================
print_step "Deploying to Production"

# Run the production deployment script
"${SCRIPT_DIR}/deploy-prod.sh" --build --skip-confirmation

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}  ✗ Production deployment failed!${NC}"
    exit 1
fi

# =============================================================================
# STEP 6: Post-Deployment Verification
# =============================================================================
print_step "Post-Deployment Verification"

echo -e "${CYAN}  Waiting for services to stabilize...${NC}"
sleep 5

ALL_HEALTHY=true

# Test production endpoints
echo -e "${CYAN}  Testing PROD API Gateway (http://localhost:9080/prod/health)...${NC}"
if curl -s --fail http://localhost:9080/prod/health > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ PROD API Gateway: HEALTHY${NC}"
else
    echo -e "${RED}  ✗ PROD API Gateway: UNHEALTHY${NC}"
    ALL_HEALTHY=false
fi

echo -e "${CYAN}  Testing PROD Web Service (http://localhost:9082/health)...${NC}"
if curl -s --fail http://localhost:9082/health > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ PROD Web Service: HEALTHY${NC}"
else
    echo -e "${RED}  ✗ PROD Web Service: UNHEALTHY${NC}"
    ALL_HEALTHY=false
fi

# Final status
echo ""
if $ALL_HEALTHY; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              PROMOTION TO PRODUCTION SUCCESSFUL               ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Production services are now live:${NC}"
    echo -e "  • API Gateway:  ${YELLOW}http://localhost:9080${NC}"
    echo -e "  • Web Service:  ${YELLOW}http://localhost:9082${NC}"
    echo ""
    echo -e "${CYAN}PROD Credentials:${NC}"
    echo -e "  See: config/clients.yaml (uncomment pi-prod-client section)"
    echo -e "  ${YELLOW}⚠️  Generate a unique secret for production!${NC}"
else
    echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║       PROMOTION COMPLETE - SOME SERVICES NEED ATTENTION       ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Check container logs for issues:${NC}"
    echo -e "  docker compose -f docker/docker-compose.prod.yml logs"
fi
echo ""
