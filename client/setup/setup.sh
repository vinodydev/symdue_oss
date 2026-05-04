#!/bin/bash
# setup.sh - Client (Frontend) setup script

set -e

echo "========================================="
echo "GraphMind Orchestrator - Client Setup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the client directory (parent of setup/)
CLIENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CLIENT_DIR"

# Check Node.js version
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗${NC} Node.js is not installed"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2)
echo -e "${GREEN}✓${NC} Node.js $NODE_VERSION found"

# Check for yarn
if ! command -v yarn &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} yarn not found, installing..."
    npm install -g yarn
fi

YARN_VERSION=$(yarn --version)
echo -e "${GREEN}✓${NC} yarn $YARN_VERSION found"

# Install dependencies
if [ -f "package.json" ]; then
    echo ""
    echo "Installing dependencies with yarn..."
    yarn install
    echo -e "${GREEN}✓${NC} Dependencies installed"
else
    echo -e "${RED}✗${NC} package.json not found"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo ""
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo -e "${GREEN}✓${NC} .env file created"
        echo -e "${YELLOW}⚠${NC} Please update .env with your configuration"
    else
        echo -e "${YELLOW}⚠${NC} .env.example not found, please create .env manually"
    fi
fi

echo ""
echo "========================================="
echo -e "${GREEN}Client setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Update .env with your configuration"
echo "2. Run: yarn dev (to start development server)"
echo "3. Run: yarn build (to build for production)"
echo ""

