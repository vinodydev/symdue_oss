#!/bin/bash
# setup-env.sh - Environment validation and setup

set -e

echo "========================================="
echo "GraphMind Orchestrator - Environment Setup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Check Python
if check_command python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    check_version "python3" "3.11.0" "$PYTHON_VERSION"
    PYTHON_OK=$?
else
    PYTHON_OK=1
fi

# Check Node.js
if check_command node; then
    NODE_VERSION=$(node --version | cut -d'v' -f2)
    check_version "node" "18.0.0" "$NODE_VERSION"
    NODE_OK=$?
else
    NODE_OK=1
fi

# Check Docker
if check_command docker; then
    DOCKER_OK=0
else
    DOCKER_OK=1
fi

# Check Docker Compose
if check_command docker-compose || docker compose version &> /dev/null; then
    echo -e "${GREEN}✓${NC} docker-compose is available"
    COMPOSE_OK=0
else
    echo -e "${RED}✗${NC} docker-compose is not available"
    COMPOSE_OK=1
fi

# Check PostgreSQL (optional, can use Docker)
if check_command psql; then
    POSTGRES_OK=0
else
    echo -e "${YELLOW}⚠${NC} psql not found (will use Docker PostgreSQL)"
    POSTGRES_OK=0
fi

# Check Redis (optional, can use Docker)
if check_command redis-cli; then
    REDIS_OK=0
else
    echo -e "${YELLOW}⚠${NC} redis-cli not found (will use Docker Redis)"
    REDIS_OK=0
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
    
    echo ""
    echo "========================================="
    echo "Next steps:"
    echo "1. Update server/.env and client/.env with your configuration"
    echo "2. Run: ./setup-db.sh (if using local PostgreSQL)"
    echo "3. Run: ./setup-dood.sh (for Docker-out-of-Docker setup)"
    echo "4. Run: docker-compose up -d (to start services)"
    echo ""
    exit 0
else
    echo -e "${RED}Some prerequisites are missing!${NC}"
    echo ""
    echo "Please install:"
    [ $PYTHON_OK -ne 0 ] && echo "  - Python 3.11+"
    [ $NODE_OK -ne 0 ] && echo "  - Node.js 18+"
    [ $DOCKER_OK -ne 0 ] && echo "  - Docker"
    [ $COMPOSE_OK -ne 0 ] && echo "  - Docker Compose"
    echo ""
    exit 1
fi

