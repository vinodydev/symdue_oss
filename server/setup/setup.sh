#!/bin/bash
# setup.sh - Server (Backend) setup script

set -e

echo "========================================="
echo "GraphMind Orchestrator - Server Setup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the server directory (parent of setup/)
SERVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SERVER_DIR"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗${NC} Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION found"

# Create virtual environment
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    echo ""
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment already exists"
fi

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    source .venv/bin/activate
fi

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null
echo -e "${GREEN}✓${NC} pip upgraded"

# Install production dependencies
if [ -f "requirements.txt" ]; then
    echo ""
    echo "Installing production dependencies..."
    pip install -r requirements.txt
    echo -e "${GREEN}✓${NC} Production dependencies installed"
else
    echo -e "${YELLOW}⚠${NC} requirements.txt not found, skipping production dependencies"
fi

# Install development dependencies
if [ -f "requirements-dev.txt" ]; then
    echo ""
    echo "Installing development dependencies..."
    pip install -r requirements-dev.txt
    echo -e "${GREEN}✓${NC} Development dependencies installed"
else
    echo -e "${YELLOW}⚠${NC} requirements-dev.txt not found, skipping development dependencies"
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

# Run Alembic migrations if available
if command -v alembic &> /dev/null; then
    if [ -d "alembic" ]; then
        echo ""
        echo "Running database migrations..."
        alembic upgrade head || echo -e "${YELLOW}⚠${NC} Migrations failed (database may not be ready)"
    fi
fi

echo ""
echo "========================================="
echo -e "${GREEN}Server setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Update .env with your configuration"
echo "2. Run: source venv/bin/activate (to activate virtual environment)"
echo "3. Run: python main.py (to start the server)"
echo ""

