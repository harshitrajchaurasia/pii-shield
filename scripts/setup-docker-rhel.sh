#!/bin/bash
# =============================================================================
# PI Remover - Docker Engine Installation for RHEL 8/9
# =============================================================================
#
# This script installs Docker Engine (free for commercial use) on RHEL.
# Alternatively, it can set up Podman (pre-installed on RHEL) as a Docker replacement.
#
# Usage:
#   chmod +x setup-docker-rhel.sh
#   sudo ./setup-docker-rhel.sh [--podman]
#
# Options:
#   --podman    Use Podman instead of Docker CE (native RHEL, no extra repos)
#
# Requirements:
#   - RHEL 8 or RHEL 9
#   - Internet connection
#   - Root or sudo access
#
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse arguments
USE_PODMAN=false
if [[ "$1" == "--podman" ]]; then
    USE_PODMAN=true
fi

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
if $USE_PODMAN; then
    echo -e "${CYAN}║     PI REMOVER - Podman Setup for RHEL                        ║${NC}"
else
    echo -e "${CYAN}║     PI REMOVER - Docker Engine Setup for RHEL                 ║${NC}"
fi
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}[WARNING] Not running as root. Will use sudo for commands.${NC}"
    SUDO="sudo"
else
    SUDO=""
fi

# Check RHEL version
if [ -f /etc/redhat-release ]; then
    RHEL_VERSION=$(cat /etc/redhat-release)
    echo -e "${GREEN}[INFO] Detected: $RHEL_VERSION${NC}"
    
    # Extract major version
    if [[ $RHEL_VERSION =~ "release 8" ]]; then
        RHEL_MAJOR=8
    elif [[ $RHEL_VERSION =~ "release 9" ]]; then
        RHEL_MAJOR=9
    else
        echo -e "${YELLOW}[WARNING] Unsupported RHEL version. Continuing anyway...${NC}"
        RHEL_MAJOR=8
    fi
else
    echo -e "${RED}[ERROR] This script is designed for RHEL. Exiting.${NC}"
    exit 1
fi

# =============================================================================
# PODMAN Installation (Native RHEL)
# =============================================================================
if $USE_PODMAN; then
    echo ""
    echo -e "${CYAN}Installing Podman (Docker-compatible, native to RHEL)...${NC}"
    
    # Remove old Docker if present
    echo ""
    echo -e "${CYAN}[STEP 1/4] Removing old Docker installations...${NC}"
    $SUDO dnf remove -y docker docker-client docker-client-latest docker-common \
        docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null || true
    echo -e "${GREEN}  ✓ Old packages removed${NC}"
    
    # Install Podman
    echo ""
    echo -e "${CYAN}[STEP 2/4] Installing Podman...${NC}"
    $SUDO dnf install -y podman podman-compose
    echo -e "${GREEN}  ✓ Podman installed${NC}"
    
    # Enable Podman socket (Docker API compatibility)
    echo ""
    echo -e "${CYAN}[STEP 3/4] Enabling Podman socket...${NC}"
    systemctl --user enable --now podman.socket 2>/dev/null || \
        $SUDO systemctl enable --now podman.socket 2>/dev/null || true
    echo -e "${GREEN}  ✓ Podman socket enabled${NC}"
    
    # Create Docker aliases
    echo ""
    echo -e "${CYAN}[STEP 4/4] Creating Docker compatibility aliases...${NC}"
    
    if ! grep -q "alias docker=podman" ~/.bashrc 2>/dev/null; then
        echo "" >> ~/.bashrc
        echo "# Podman as Docker replacement" >> ~/.bashrc
        echo "alias docker='podman'" >> ~/.bashrc
        echo "alias docker-compose='podman-compose'" >> ~/.bashrc
    fi
    echo -e "${GREEN}  ✓ Aliases created${NC}"
    
    # Verify
    echo ""
    echo -e "${CYAN}Verifying installation...${NC}"
    echo ""
    echo "Podman version:"
    podman --version
    echo ""
    echo "Podman Compose version:"
    podman-compose --version 2>/dev/null || echo "podman-compose installed"
    
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              PODMAN INSTALLATION COMPLETE                     ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}NOTE: Use 'podman' and 'podman-compose' commands, or use aliases:${NC}"
    echo -e "  ${CYAN}source ~/.bashrc${NC}  # Then 'docker' will work as alias"
    echo ""
    echo -e "${CYAN}Next Steps:${NC}"
    echo -e "  1. Deploy DEV: ${CYAN}podman-compose -f docker/docker-compose.dev.yml up -d${NC}"
    echo -e "  2. Access: ${CYAN}http://localhost:8080${NC} (API) or ${CYAN}http://localhost:8082${NC} (Web UI)"
    echo ""
    exit 0
fi

# =============================================================================
# DOCKER CE Installation
# =============================================================================

# Step 1: Remove old packages
echo ""
echo -e "${CYAN}[STEP 1/6] Removing old Docker installations...${NC}"

$SUDO dnf remove -y docker docker-client docker-client-latest docker-common \
    docker-latest docker-latest-logrotate docker-logrotate docker-engine \
    podman runc 2>/dev/null || true

echo -e "${GREEN}  ✓ Old packages removed${NC}"

# Step 2: Install prerequisites
echo ""
echo -e "${CYAN}[STEP 2/6] Installing prerequisites...${NC}"

$SUDO dnf install -y yum-utils

echo -e "${GREEN}  ✓ Prerequisites installed${NC}"

# Step 3: Add Docker repository
echo ""
echo -e "${CYAN}[STEP 3/6] Adding Docker repository...${NC}"

# For RHEL, we use CentOS repo which is compatible
if [ $RHEL_MAJOR -eq 9 ]; then
    $SUDO dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
else
    $SUDO dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
fi

echo -e "${GREEN}  ✓ Repository added${NC}"

# Step 4: Install Docker Engine
echo ""
echo -e "${CYAN}[STEP 4/6] Installing Docker Engine...${NC}"

$SUDO dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo -e "${GREEN}  ✓ Docker Engine installed${NC}"

# Step 5: Start and enable Docker
echo ""
echo -e "${CYAN}[STEP 5/6] Starting Docker service...${NC}"

$SUDO systemctl start docker
$SUDO systemctl enable docker

echo -e "${GREEN}  ✓ Docker service started and enabled${NC}"

# Step 6: Add user to docker group
echo ""
echo -e "${CYAN}[STEP 6/6] Configuring user permissions...${NC}"

# Get the actual user (not root if using sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
$SUDO usermod -aG docker $ACTUAL_USER

echo -e "${GREEN}  ✓ User '$ACTUAL_USER' added to docker group${NC}"

# =============================================================================
# Verify Installation
# =============================================================================
echo ""
echo -e "${CYAN}Verifying installation...${NC}"

echo ""
echo "Docker version:"
docker --version

echo ""
echo "Docker Compose version:"
docker compose version

echo ""
echo "Docker service status:"
$SUDO systemctl status docker --no-pager | head -5

# Test Docker
echo ""
echo -e "${CYAN}Testing Docker with hello-world...${NC}"
$SUDO docker run --rm hello-world 2>/dev/null && echo -e "${GREEN}  ✓ Docker is working!${NC}" || echo -e "${RED}  ✗ Docker test failed${NC}"

# =============================================================================
# Configure Firewall
# =============================================================================
echo ""
echo -e "${CYAN}Configuring firewall for PI Remover ports...${NC}"

# Check if firewalld is running
if systemctl is-active --quiet firewalld; then
    $SUDO firewall-cmd --permanent --add-port=8080/tcp  # DEV API
    $SUDO firewall-cmd --permanent --add-port=8082/tcp  # DEV Web
    $SUDO firewall-cmd --permanent --add-port=9080/tcp  # PROD API
    $SUDO firewall-cmd --permanent --add-port=9082/tcp  # PROD Web
    $SUDO firewall-cmd --reload
    echo -e "${GREEN}  ✓ Firewall configured (ports 8080, 8082, 9080, 9082)${NC}"
else
    echo -e "${YELLOW}  ⚠ firewalld not running. Skipping firewall configuration.${NC}"
fi

# =============================================================================
# Done
# =============================================================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              DOCKER ENGINE INSTALLATION COMPLETE              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: To use Docker without sudo, either:${NC}"
echo -e "  1. Log out and log back in, or"
echo -e "  2. Run: ${CYAN}newgrp docker${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo -e "  1. Navigate to project: ${CYAN}cd /opt/PI_Removal${NC}"
echo -e "  2. Deploy DEV: ${CYAN}./scripts/deploy-dev.sh${NC}"
echo -e "  3. Deploy PROD: ${CYAN}./scripts/deploy-prod.sh${NC}"
echo -e "  4. Access: ${CYAN}http://YOUR_IP:8080${NC} (DEV API) or ${CYAN}http://YOUR_IP:8082${NC} (DEV Web UI)"
echo ""
