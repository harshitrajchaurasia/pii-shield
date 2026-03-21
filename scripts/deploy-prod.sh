#!/bin/bash
# =============================================================================
# PI Remover - PROD Environment Deployment Script (Linux/WSL2)
# =============================================================================
#
# This script deploys PI Remover services to the PRODUCTION environment.
# Uses Docker Engine (free for commercial use).
#
# Usage:
#   chmod +x deploy-prod.sh
#   ./deploy-prod.sh [--build] [--follow] [--skip-confirmation]
#
# Options:
#   --build               Force rebuild of Docker images
#   --follow              Follow container logs after starting
#   --skip-confirmation   Skip production deployment confirmation prompt
#
# Prerequisites:
#   - Docker Engine installed (run setup-docker-wsl2.sh or setup-docker-rhel.sh)
#   - Docker Compose plugin installed
#   - Production environment file configured (docker/.env.prod)
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
BUILD_FLAG=""
FOLLOW_LOGS=false
SKIP_CONFIRMATION=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD_FLAG="--build"
            shift
            ;;
        --follow)
            FOLLOW_LOGS=true
            shift
            ;;
        --skip-confirmation)
            SKIP_CONFIRMATION=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--build] [--follow] [--skip-confirmation]"
            echo ""
            echo "Options:"
            echo "  --build               Force rebuild of Docker images"
            echo "  --follow              Follow container logs after starting"
            echo "  --skip-confirmation   Skip production deployment confirmation prompt"
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
COMPOSE_FILE="${DOCKER_DIR}/docker-compose.prod.yml"
ENV_FILE="${DOCKER_DIR}/.env.prod"
ENV_TEMPLATE="${DOCKER_DIR}/.env.prod.template"

echo ""
echo -e "${MAGENTA}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║           PI REMOVER - PRODUCTION DEPLOYMENT                  ║${NC}"
echo -e "${MAGENTA}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# Preflight Checks
# =============================================================================
echo -e "${CYAN}[PREFLIGHT] Checking prerequisites...${NC}"

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
    echo -e "${RED}  ✗ Docker Compose not found. Install docker-compose-plugin.${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Docker Compose found${NC}"

# Check compose file
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}  ✗ Compose file not found: $COMPOSE_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Compose file found${NC}"

# Check environment file
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                    MISSING CONFIGURATION                      ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Production environment file not found: $ENV_FILE${NC}"
    echo ""
    echo -e "${CYAN}To fix this:${NC}"
    if [ -f "$ENV_TEMPLATE" ]; then
        echo -e "  1. Copy the template:  ${YELLOW}cp $ENV_TEMPLATE $ENV_FILE${NC}"
    else
        echo -e "  1. Create the file:    ${YELLOW}touch $ENV_FILE${NC}"
    fi
    echo -e "  2. Edit .env.prod and set production secrets"
    echo -e "  3. Re-run this script"
    echo ""
    exit 1
fi
echo -e "${GREEN}  ✓ Environment file found${NC}"

# Check for unconfigured secrets
if grep -q "REPLACE_WITH" "$ENV_FILE" 2>/dev/null; then
    echo -e "${RED}  ✗ Environment file contains unconfigured secrets${NC}"
    echo -e "${YELLOW}    Please update all 'REPLACE_WITH...' placeholders in $ENV_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Environment secrets configured${NC}"

# Create logs directory
LOGS_DIR="${PROJECT_ROOT}/logs/prod"
if [ ! -d "$LOGS_DIR" ]; then
    mkdir -p "$LOGS_DIR"
    echo -e "${GREEN}  ✓ Created logs directory: $LOGS_DIR${NC}"
fi

echo ""

# =============================================================================
# Production Confirmation
# =============================================================================
if ! $SKIP_CONFIRMATION; then
    echo -e "${YELLOW}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║                    ⚠️  PRODUCTION DEPLOYMENT                   ║${NC}"
    echo -e "${YELLOW}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}You are about to deploy to PRODUCTION.${NC}"
    echo ""
    echo -e "${CYAN}This will:${NC}"
    echo -e "  • Stop existing production containers"
    echo -e "  • Build new images (if --build specified)"
    echo -e "  • Start production services on ports 9080/9082"
    echo ""
    
    read -p "Type 'DEPLOY' to confirm production deployment: " confirmation
    if [ "$confirmation" != "DEPLOY" ]; then
        echo ""
        echo -e "${YELLOW}Deployment cancelled.${NC}"
        exit 0
    fi
    echo ""
fi

# =============================================================================
# Stop Existing Containers
# =============================================================================
echo -e "${CYAN}[STEP 1/3] Stopping existing containers...${NC}"

cd "$PROJECT_ROOT"

COMPOSE_ARGS="-f $COMPOSE_FILE --env-file $ENV_FILE"

docker compose $COMPOSE_ARGS down --remove-orphans 2>/dev/null || true
echo -e "${GREEN}  ✓ Existing containers stopped${NC}"

# =============================================================================
# Build and Start Services
# =============================================================================
echo ""
echo -e "${CYAN}[STEP 2/3] Building and starting services...${NC}"

if $FOLLOW_LOGS; then
    # Run in foreground with logs
    docker compose $COMPOSE_ARGS up $BUILD_FLAG
else
    # Run in detached mode
    docker compose $COMPOSE_ARGS up -d $BUILD_FLAG
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}  ✗ Docker Compose failed${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ Services started${NC}"
fi

# =============================================================================
# Verify Deployment
# =============================================================================
if ! $FOLLOW_LOGS; then
    echo ""
    echo -e "${CYAN}[STEP 3/3] Verifying deployment...${NC}"
    
    # Wait for services to start
    echo -e "  Waiting for services to initialize..."
    sleep 8
    
    # Show container status
    echo ""
    docker compose $COMPOSE_ARGS ps
    
    # Health checks
    echo ""
    echo -e "${CYAN}Running health checks...${NC}"
    
    # Check API Gateway
    if curl -s --fail http://localhost:9080/prod/health > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ API Gateway (port 9080) is healthy${NC}"
    else
        echo -e "${YELLOW}  ⚠ API Gateway health check failed (may still be starting)${NC}"
    fi
    
    # Check Web Service
    if curl -s --fail http://localhost:9082/health > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Web Service (port 9082) is healthy${NC}"
    else
        echo -e "${YELLOW}  ⚠ Web Service health check failed (may still be starting)${NC}"
    fi
    
    # =============================================================================
    # Done
    # =============================================================================
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              PROD DEPLOYMENT COMPLETE                         ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Services available at:${NC}"
    echo -e "  API Gateway:    ${YELLOW}http://localhost:9080${NC}"
    echo -e "  Web UI:         ${YELLOW}http://localhost:9082${NC}"
    echo ""
    echo -e "${CYAN}PROD Credentials:${NC}"
    echo -e "  See: config/clients.yaml (uncomment pi-prod-client section)"
    echo -e "  ${YELLOW}⚠️  Generate a unique secret for production!${NC}"
    echo -e "    python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    echo ""
    echo -e "${CYAN}API Endpoints:${NC}"
    echo -e "  Auth:    POST http://localhost:9080/prod/auth/token"
    echo -e "  Redact:  POST http://localhost:9080/prod/v1/redact"
    echo -e "  Health:  GET  http://localhost:9080/prod/health"
    echo ""
    echo -e "${CYAN}Quick Test (replace with your configured credentials):${NC}"
    echo -e "  curl -X POST http://localhost:9080/prod/auth/token \\"
    echo -e "    -H 'Content-Type: application/json' \\"
    echo -e "    -d '{\"client_id\":\"pi-prod-client\",\"client_secret\":\"YOUR_PROD_SECRET\"}'"
    echo ""
    echo -e "${CYAN}View Logs:${NC}"
    echo -e "  docker compose -f docker/docker-compose.prod.yml logs -f"
    echo ""
    echo -e "${MAGENTA}NOTE: Swagger UI is disabled in production for security.${NC}"
    echo ""
fi
