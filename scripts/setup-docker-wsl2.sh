#!/bin/bash
# =============================================================================
# PI Remover - Docker Engine Installation for WSL2 Ubuntu
# =============================================================================
#
# This script installs Docker Engine (free for commercial use) in WSL2 Ubuntu.
# It does NOT require Docker Desktop.
#
# Usage:
#   chmod +x setup-docker-wsl2.sh
#   ./setup-docker-wsl2.sh
#
# Requirements:
#   - WSL2 with Ubuntu 20.04, 22.04, or 24.04
#   - Internet connection
#   - sudo access
#
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     PI REMOVER - Docker Engine Setup for WSL2                 ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running in WSL
if ! grep -qi microsoft /proc/version 2>/dev/null; then
    echo -e "${YELLOW}[WARNING] This doesn't appear to be WSL2. Continuing anyway...${NC}"
fi

# Check Ubuntu version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo -e "${GREEN}[INFO] Detected: $NAME $VERSION${NC}"
else
    echo -e "${YELLOW}[WARNING] Could not detect OS version${NC}"
fi

# =============================================================================
# Step 1: Remove old Docker installations
# =============================================================================
echo ""
echo -e "${CYAN}[STEP 1/6] Removing old Docker installations...${NC}"

for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
    sudo apt-get remove -y $pkg 2>/dev/null || true
done

echo -e "${GREEN}  ✓ Old packages removed${NC}"

# =============================================================================
# Step 2: Install prerequisites
# =============================================================================
echo ""
echo -e "${CYAN}[STEP 2/6] Installing prerequisites...${NC}"

sudo apt-get update
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

echo -e "${GREEN}  ✓ Prerequisites installed${NC}"

# =============================================================================
# Step 3: Add Docker's official GPG key
# =============================================================================
echo ""
echo -e "${CYAN}[STEP 3/6] Adding Docker GPG key...${NC}"

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo -e "${GREEN}  ✓ GPG key added${NC}"

# =============================================================================
# Step 4: Add Docker repository
# =============================================================================
echo ""
echo -e "${CYAN}[STEP 4/6] Adding Docker repository...${NC}"

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo -e "${GREEN}  ✓ Repository added${NC}"

# =============================================================================
# Step 5: Install Docker Engine
# =============================================================================
echo ""
echo -e "${CYAN}[STEP 5/6] Installing Docker Engine...${NC}"

sudo apt-get update
sudo apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

echo -e "${GREEN}  ✓ Docker Engine installed${NC}"

# =============================================================================
# Step 6: Configure Docker
# =============================================================================
echo ""
echo -e "${CYAN}[STEP 6/6] Configuring Docker...${NC}"

# Add current user to docker group
sudo usermod -aG docker $USER

# Start Docker service
sudo service docker start

# Enable Docker to start on WSL launch (add to .bashrc if not already there)
if ! grep -q "sudo service docker start" ~/.bashrc 2>/dev/null; then
    echo "" >> ~/.bashrc
    echo "# Start Docker on WSL launch" >> ~/.bashrc
    echo "if service docker status 2>&1 | grep -q 'is not running'; then" >> ~/.bashrc
    echo "    sudo service docker start >/dev/null 2>&1" >> ~/.bashrc
    echo "fi" >> ~/.bashrc
    echo -e "${GREEN}  ✓ Added Docker auto-start to .bashrc${NC}"
fi

# Configure sudo for passwordless docker service start (optional)
SUDOERS_DOCKER="/etc/sudoers.d/docker-service"
if [ ! -f "$SUDOERS_DOCKER" ]; then
    echo "$USER ALL=(ALL) NOPASSWD: /usr/sbin/service docker start, /usr/sbin/service docker stop, /usr/sbin/service docker status" | sudo tee $SUDOERS_DOCKER > /dev/null
    sudo chmod 440 $SUDOERS_DOCKER
    echo -e "${GREEN}  ✓ Configured passwordless Docker service control${NC}"
fi

echo -e "${GREEN}  ✓ Docker configured${NC}"

# =============================================================================
# Verify Installation
# =============================================================================
echo ""
echo -e "${CYAN}Verifying installation...${NC}"

echo ""
echo -e "Docker version:"
docker --version

echo ""
echo -e "Docker Compose version:"
docker compose version

echo ""
echo -e "Docker service status:"
sudo service docker status

# Test Docker
echo ""
echo -e "${CYAN}Testing Docker with hello-world...${NC}"
sudo docker run --rm hello-world 2>/dev/null && echo -e "${GREEN}  ✓ Docker is working!${NC}" || echo -e "${RED}  ✗ Docker test failed${NC}"

# =============================================================================
# Done
# =============================================================================
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              DOCKER ENGINE INSTALLATION COMPLETE              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}IMPORTANT: To use Docker without sudo, either:${NC}"
echo -e "  1. Log out and log back into WSL2, or"
echo -e "  2. Run: ${CYAN}newgrp docker${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo -e "  1. Navigate to project: ${CYAN}cd /mnt/c/Users/YourUser/Downloads/PI_Removal${NC}"
echo -e "  2. Deploy DEV: ${CYAN}./scripts/deploy-dev.sh${NC}"
echo -e "  3. Access: ${CYAN}http://localhost:8080${NC} (API) or ${CYAN}http://localhost:8082${NC} (Web UI)"
echo ""
