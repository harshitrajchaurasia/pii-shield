#!/bin/bash
# =============================================================================
# PI Remover - DEV Environment Deployment Script (Linux/WSL2)
# =============================================================================
#
# This script deploys PI Remover services to the DEVELOPMENT environment.
# Uses Docker Engine (free for commercial use).
#
# Usage:
#   chmod +x deploy-dev.sh
#   ./deploy-dev.sh [--build] [--follow]
#
# Options:
#   --build     Force rebuild of Docker images
#   --follow    Follow container logs after starting
#
# Prerequisites:
#   - Docker Engine installed (run setup-docker-wsl2.sh or setup-docker-rhel.sh)
#   - Docker Compose plugin installed
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
BUILD_FLAG=""
FOLLOW_LOGS=false

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
        -h|--help)
            echo "Usage: $0 [--build] [--follow]"
            echo ""
            echo "Options:"
            echo "  --build     Force rebuild of Docker images"
            echo "  --follow    Follow container logs after starting"
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
COMPOSE_FILE="${DOCKER_DIR}/docker-compose.dev.yml"
ENV_FILE="${DOCKER_DIR}/.env.dev"

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║           PI REMOVER - DEVELOPMENT DEPLOYMENT                 ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
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

# Create logs directory
LOGS_DIR="${PROJECT_ROOT}/logs/dev"
if [ ! -d "$LOGS_DIR" ]; then
    mkdir -p "$LOGS_DIR"
    echo -e "${GREEN}  ✓ Created logs directory: $LOGS_DIR${NC}"
fi

echo ""

# =============================================================================
# Stop Existing Containers
# =============================================================================
echo -e "${CYAN}[STEP 1/3] Stopping existing containers...${NC}"

cd "$PROJECT_ROOT"

COMPOSE_ARGS="-f $COMPOSE_FILE"
if [ -f "$ENV_FILE" ]; then
    COMPOSE_ARGS="$COMPOSE_ARGS --env-file $ENV_FILE"
    echo -e "${YELLOW}  Using environment file: $ENV_FILE${NC}"
fi

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
    sleep 5
    
    # Show container status
    echo ""
    docker compose $COMPOSE_ARGS ps
    
    # Health checks
    echo ""
    echo -e "${CYAN}Running health checks...${NC}"
    
    # Check API Gateway
    if curl -s --fail http://localhost:8080/dev/health > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ API Gateway (port 8080) is healthy${NC}"
    else
        echo -e "${YELLOW}  ⚠ API Gateway health check failed (may still be starting)${NC}"
    fi
    
    # Check Web Service
    if curl -s --fail http://localhost:8082/health > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Web Service (port 8082) is healthy${NC}"
    else
        echo -e "${YELLOW}  ⚠ Web Service health check failed (may still be starting)${NC}"
    fi
    
    # =============================================================================
    # Done
    # =============================================================================
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              DEV DEPLOYMENT COMPLETE                          ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Services available at:${NC}"
    echo -e "  API Gateway:    ${YELLOW}http://localhost:8080${NC}"
    echo -e "  Web UI:         ${YELLOW}http://localhost:8082${NC}"
    echo -e "  API Docs:       ${YELLOW}http://localhost:8080/docs${NC}"
    echo ""
    echo -e "${CYAN}DEV Credentials:${NC}"
    echo -e "  Client ID:      pi-dev-client"
    echo -e "  Client Secret:  YOUR_DEV_CLIENT_SECRET_HERE"
    echo ""
    echo -e "${CYAN}API Endpoints:${NC}"
    echo -e "  Auth:    POST http://localhost:8080/dev/auth/token"
    echo -e "  Redact:  POST http://localhost:8080/dev/v1/redact"
    echo -e "  Health:  GET  http://localhost:8080/dev/health"
    echo ""
    echo -e "${CYAN}Quick Test:${NC}"
    echo -e "  curl -X POST http://localhost:8080/dev/auth/token \\"
    echo -e "    -H 'Content-Type: application/json' \\"
    echo -e "    -d '{\"client_id\":\"pi-dev-client\",\"client_secret\":\"YOUR_DEV_CLIENT_SECRET_HERE\"}'"
    echo ""
    echo -e "${CYAN}View Logs:${NC}"
    echo -e "  docker compose -f docker/docker-compose.dev.yml logs -f"
    echo ""
fi
