#!/bin/bash
# setup-dood.sh - Setup directories and permissions for Docker-out-of-Docker (DooD)

set -e

echo "========================================="
echo "GraphMind Orchestrator - DooD Setup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the project root (graph_execution directory)
# From setup/ directory, go up to code/, then up to graph_execution/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
GRAPH_MIND_DIR="$PROJECT_ROOT/graph_mind"

# Directories to create (relative to project root)
WORKSPACE_DIR="$GRAPH_MIND_DIR/workspaces"
CACHE_DIR="$GRAPH_MIND_DIR/cache"
STORAGE_DIR="$GRAPH_MIND_DIR/storage"

echo "Creating workspace and cache directories in project folder..."
echo "Project root: $PROJECT_ROOT"
echo "GraphMind directory: $GRAPH_MIND_DIR"
echo ""

# Create graph_mind base directory
if [ ! -d "$GRAPH_MIND_DIR" ]; then
    mkdir -p "$GRAPH_MIND_DIR"
    echo -e "${GREEN}✓${NC} Created $GRAPH_MIND_DIR"
else
    echo -e "${GREEN}✓${NC} $GRAPH_MIND_DIR already exists"
fi

# Create workspace directory
if [ ! -d "$WORKSPACE_DIR" ]; then
    mkdir -p "$WORKSPACE_DIR"
    echo -e "${GREEN}✓${NC} Created $WORKSPACE_DIR"
else
    echo -e "${GREEN}✓${NC} $WORKSPACE_DIR already exists"
fi

# Create cache directory
if [ ! -d "$CACHE_DIR" ]; then
    mkdir -p "$CACHE_DIR"
    echo -e "${GREEN}✓${NC} Created $CACHE_DIR"
else
    echo -e "${GREEN}✓${NC} $CACHE_DIR already exists"
fi

# Create storage directory
if [ ! -d "$STORAGE_DIR" ]; then
    mkdir -p "$STORAGE_DIR"
    echo -e "${GREEN}✓${NC} Created $STORAGE_DIR"
else
    echo -e "${GREEN}✓${NC} $STORAGE_DIR already exists"
fi

# Set permissions (containers need to write here)
echo ""
echo "Setting permissions..."
chmod -R 755 "$GRAPH_MIND_DIR"
chmod -R 777 "$WORKSPACE_DIR"
chmod -R 777 "$CACHE_DIR"
chmod -R 777 "$STORAGE_DIR"
echo -e "${GREEN}✓${NC} Permissions set"

# Verify Docker socket is accessible
echo ""
echo "Checking Docker socket..."
if [ -S /var/run/docker.sock ]; then
    echo -e "${GREEN}✓${NC} Docker socket found at /var/run/docker.sock"
    
    # Check if user is in docker group
    if groups | grep -q docker; then
        echo -e "${GREEN}✓${NC} User is in docker group"
    else
        echo -e "${YELLOW}⚠${NC} User is not in docker group"
        echo "  To add user to docker group, run:"
        echo "    sudo usermod -aG docker $USER"
        echo "  Then log out and back in for changes to take effect"
    fi
else
    echo -e "${RED}✗${NC} Docker socket not found at /var/run/docker.sock"
    echo "  Make sure Docker is installed and running"
    exit 1
fi

# Verify Docker daemon is running
if docker info > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker daemon is running"
else
    echo -e "${RED}✗${NC} Cannot connect to Docker daemon"
    echo "  Make sure Docker is running: sudo systemctl start docker (Linux)"
    exit 1
fi

echo ""
echo "========================================="
echo -e "${GREEN}DooD setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Run: docker-compose up -d"
echo "2. Verify services: docker-compose ps"
echo "3. Check logs: docker-compose logs backend"
echo "4. Access Temporal UI: http://localhost:8088"
echo ""

