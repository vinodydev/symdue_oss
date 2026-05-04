#!/bin/bash
# setup-mac.sh - macOS-specific setup script for GraphMind Orchestrator

set -e

echo "========================================="
echo "GraphMind Orchestrator - macOS Setup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${RED}✗${NC} This script is designed for macOS only"
    echo "For Linux setup, use: ./setup-env.sh, ./setup-db.sh, ./setup-dood.sh"
    exit 1
fi

# Function to check command exists
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "${RED}✗${NC} $1 is not installed"
        return 1
    fi
}

# Function to check version
check_version() {
    local cmd=$1
    local min_version=$2
    local current_version=$3
    
    if [ "$(printf '%s\n' "$min_version" "$current_version" | sort -V | head -n1)" = "$min_version" ]; then
        echo -e "${GREEN}✓${NC} $cmd version $current_version (>= $min_version)"
        return 0
    else
        echo -e "${RED}✗${NC} $cmd version $current_version is below minimum $min_version"
        return 1
    fi
}

echo "Checking prerequisites..."
echo ""

# Check Homebrew
if check_command brew; then
    BREW_OK=0
else
    echo -e "${YELLOW}⚠${NC} Homebrew not found"
    echo "  Install Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    BREW_OK=1
fi

# Check Python
if check_command python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    check_version "python3" "3.11.0" "$PYTHON_VERSION"
    PYTHON_OK=$?
else
    PYTHON_OK=1
    if [ $BREW_OK -eq 0 ]; then
        echo -e "${BLUE}ℹ${NC} Install Python 3.11+: brew install python@3.11"
    fi
fi

# Check Node.js
if check_command node; then
    NODE_VERSION=$(node --version | cut -d'v' -f2)
    check_version "node" "18.0.0" "$NODE_VERSION"
    NODE_OK=$?
else
    NODE_OK=1
    if [ $BREW_OK -eq 0 ]; then
        echo -e "${BLUE}ℹ${NC} Install Node.js: brew install node"
    fi
fi

# Check Docker
if check_command docker; then
    DOCKER_OK=0
    # Check if Docker Desktop is running
    if docker info > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Docker daemon is running"
    else
        echo -e "${YELLOW}⚠${NC} Docker is installed but daemon is not running"
        echo "  Start Docker Desktop from Applications or run: open -a Docker"
        DOCKER_OK=1
    fi
else
    DOCKER_OK=1
    if [ $BREW_OK -eq 0 ]; then
        echo -e "${BLUE}ℹ${NC} Install Docker Desktop: brew install --cask docker"
        echo "  Or download from: https://www.docker.com/products/docker-desktop"
    fi
fi

# Check Docker Compose
if docker compose version &> /dev/null; then
    echo -e "${GREEN}✓${NC} docker compose is available"
    COMPOSE_OK=0
elif command -v docker-compose &> /dev/null; then
    echo -e "${GREEN}✓${NC} docker-compose is available"
    COMPOSE_OK=0
else
    echo -e "${RED}✗${NC} docker-compose is not available"
    COMPOSE_OK=1
fi

# Check PostgreSQL (optional, can use Docker)
if check_command psql; then
    POSTGRES_OK=0
    # Check if PostgreSQL service is running
    if brew services list 2>/dev/null | grep -q "postgresql.*started"; then
        echo -e "${GREEN}✓${NC} PostgreSQL service is running"
    else
        echo -e "${YELLOW}⚠${NC} PostgreSQL is installed but not running"
        echo "  Start with: brew services start postgresql@15"
        echo "  Or use Docker PostgreSQL (recommended): docker-compose up -d postgres"
    fi
else
    echo -e "${YELLOW}⚠${NC} psql not found (will use Docker PostgreSQL)"
    POSTGRES_OK=0
    if [ $BREW_OK -eq 0 ]; then
        echo -e "${BLUE}ℹ${NC} Install PostgreSQL: brew install postgresql@15"
    fi
fi

# Check Redis (optional, can use Docker)
if check_command redis-cli; then
    REDIS_OK=0
    # Check if Redis service is running
    if brew services list 2>/dev/null | grep -q "redis.*started"; then
        echo -e "${GREEN}✓${NC} Redis service is running"
    else
        echo -e "${YELLOW}⚠${NC} Redis is installed but not running"
        echo "  Start with: brew services start redis"
        echo "  Or use Docker Redis (recommended): docker-compose up -d redis"
    fi
else
    echo -e "${YELLOW}⚠${NC} redis-cli not found (will use Docker Redis)"
    REDIS_OK=0
    if [ $BREW_OK -eq 0 ]; then
        echo -e "${BLUE}ℹ${NC} Install Redis: brew install redis"
    fi
fi

echo ""
echo "========================================="

if [ $PYTHON_OK -eq 0 ] && [ $NODE_OK -eq 0 ] && [ $DOCKER_OK -eq 0 ] && [ $COMPOSE_OK -eq 0 ]; then
    echo -e "${GREEN}All required prerequisites are met!${NC}"
    echo ""
    
    # Create .env files from examples if they don't exist
    echo "Setting up environment files..."
    
    if [ ! -f "../server/.env" ]; then
        if [ -f "../server/.env.example" ]; then
            cp ../server/.env.example ../server/.env
            echo -e "${GREEN}✓${NC} Created server/.env from .env.example"
            echo -e "${YELLOW}⚠${NC} Please update server/.env with your configuration"
        else
            echo -e "${YELLOW}⚠${NC} server/.env.example not found, skipping"
        fi
    else
        echo -e "${GREEN}✓${NC} server/.env already exists"
    fi
    
    if [ ! -f "../client/.env" ]; then
        if [ -f "../client/.env.example" ]; then
            cp ../client/.env.example ../client/.env
            echo -e "${GREEN}✓${NC} Created client/.env from .env.example"
            echo -e "${YELLOW}⚠${NC} Please update client/.env with your configuration"
        else
            echo -e "${YELLOW}⚠${NC} client/.env.example not found, skipping"
        fi
    else
        echo -e "${GREEN}✓${NC} client/.env already exists"
    fi
    
    # Setup directories for Docker-out-of-Docker
    echo ""
    echo "Setting up workspace directories..."
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
    GRAPH_MIND_DIR="$PROJECT_ROOT/graph_mind"
    
    WORKSPACE_DIR="$GRAPH_MIND_DIR/workspaces"
    CACHE_DIR="$GRAPH_MIND_DIR/cache"
    STORAGE_DIR="$GRAPH_MIND_DIR/storage"
    
    # Create directories
    mkdir -p "$WORKSPACE_DIR" "$CACHE_DIR" "$STORAGE_DIR"
    chmod -R 755 "$GRAPH_MIND_DIR"
    chmod -R 777 "$WORKSPACE_DIR" "$CACHE_DIR" "$STORAGE_DIR"
    echo -e "${GREEN}✓${NC} Created workspace directories"
    
    # Verify Docker socket is accessible
    echo ""
    echo "Checking Docker socket..."
    if [ -S /var/run/docker.sock ]; then
        echo -e "${GREEN}✓${NC} Docker socket found at /var/run/docker.sock"
    else
        echo -e "${YELLOW}⚠${NC} Docker socket not found at /var/run/docker.sock"
        echo "  Make sure Docker Desktop is running"
    fi
    
    echo ""
    echo "========================================="
    echo "Next steps:"
    echo "1. Update server/.env and client/.env with your configuration"
    echo "2. Run: ./setup-db.sh (if using local PostgreSQL)"
    echo "3. Run: ./run.sh (to start the application)"
    echo "4. Or use Docker: docker-compose up -d"
    echo ""
    exit 0
else
    echo -e "${RED}Some prerequisites are missing!${NC}"
    echo ""
    echo "Please install:"
    [ $BREW_OK -ne 0 ] && echo "  - Homebrew: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    [ $PYTHON_OK -ne 0 ] && echo "  - Python 3.11+: brew install python@3.11"
    [ $NODE_OK -ne 0 ] && echo "  - Node.js 18+: brew install node"
    [ $DOCKER_OK -ne 0 ] && echo "  - Docker Desktop: brew install --cask docker"
    [ $COMPOSE_OK -ne 0 ] && echo "  - Docker Compose (included with Docker Desktop)"
    echo ""
    echo "Optional (can use Docker instead):"
    echo "  - PostgreSQL: brew install postgresql@15"
    echo "  - Redis: brew install redis"
    echo ""
    exit 1
fi

