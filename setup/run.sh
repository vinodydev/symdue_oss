#!/bin/bash
# run.sh - Execution script for Symdue (legacy)
#
# DEPRECATED: please use ./setup/symdue.sh instead. run.sh is kept for
# backwards compatibility through v0.2 and will be removed afterwards.

set -e

# Yellow without depending on tput (works in any terminal).
_YELLOW='\033[1;33m'
_NC='\033[0m'

echo -e "${_YELLOW}⚠  run.sh is deprecated.${_NC} Use ./setup/symdue.sh instead:"
echo "    ./setup/symdue.sh init      # first-time setup (generates .env)"
echo "    ./setup/symdue.sh start     # launch the stack"
echo "    ./setup/symdue.sh help      # full subcommand list"
echo ""
echo "Continuing with run.sh in 3 seconds (Ctrl-C to abort)..."
sleep 3
echo ""

echo "========================================="
echo "Symdue - Execution Script (legacy run.sh)"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect host's docker group GID so the in-container non-root user can
# write to the bind-mounted /var/run/docker.sock. Falls back to 999 (the
# Debian default) if `getent` isn't available (e.g. macOS Docker Desktop).
if [ -z "${DOCKER_GID:-}" ]; then
    if command -v getent >/dev/null 2>&1; then
        export DOCKER_GID="$(getent group docker | cut -d: -f3)"
    fi
    export DOCKER_GID="${DOCKER_GID:-999}"
fi

# Bootstrap: generate a fresh ../server/.env on first run with random
# secrets so the stack starts without requiring manual edits. The
# substrate refuses to start if any secret is left at its placeholder
# value (see flowgraph_oss/server/config/settings.py::assert_real_secrets).
if [ ! -f "../server/.env" ]; then
    echo -e "${BLUE}Generating ../server/.env with random secrets…${NC}"
    if ! command -v openssl >/dev/null 2>&1; then
        echo -e "${RED}openssl not found — install it (apt install openssl) and re-run.${NC}"
        exit 1
    fi

    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '\n=' | tr '/+' '_-' | cut -c1-32)
    SECRET_KEY=$(openssl rand -hex 32)
    MINIO_ROOT_USER="admin-$(openssl rand -hex 4)"
    MINIO_ROOT_PASSWORD=$(openssl rand -base64 32 | tr -d '\n=' | tr '/+' '_-' | cut -c1-32)

    # macOS sed needs '' after -i; GNU sed does not. Branch on $OSTYPE.
    if [[ "$OSTYPE" == "darwin"* ]]; then
        SED_INPLACE=(sed -i '')
    else
        SED_INPLACE=(sed -i)
    fi

    cp ../server/.env.example ../server/.env
    "${SED_INPLACE[@]}" "s|<set-via-setup-or-environment>|${POSTGRES_PASSWORD}|g" ../server/.env
    "${SED_INPLACE[@]}" "s|<run: openssl rand -hex 32>|${SECRET_KEY}|g" ../server/.env
    "${SED_INPLACE[@]}" "s|^MINIO_ROOT_USER=.*|MINIO_ROOT_USER=${MINIO_ROOT_USER}|g" ../server/.env
    "${SED_INPLACE[@]}" "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}|g" ../server/.env

    # Mode 644 (not 600): backend container runs as UID 1001 (flowgraph) but
    # the bind-mounted .env is owned by host UID; mode 600 makes it unreadable
    # across the bind-mount boundary. 644 is fine for locally-generated dev
    # secrets — server/.env lives under home-directory permissions already.
    chmod 644 ../server/.env
    echo -e "${GREEN}✓ Generated ../server/.env (mode 644)${NC}"
fi

# Export the just-generated (or pre-existing) values so docker compose can
# substitute them into the compose file. The `:?` guards in compose require
# them to be in the environment, not just in .env on disk.
set -a
source ../server/.env
set +a

# Parse arguments
MODE="docker"
BACKEND_ONLY=false
FRONTEND_ONLY=false
STOP=false
LOGS=false
RESTART=false

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --docker, -d          Start using Docker Compose (default)"
    echo "  --local, -l           Start backend and frontend locally"
    echo "  --backend-only, -b    Start only backend (local mode)"
    echo "  --frontend-only, -f   Start only frontend (local mode)"
    echo "  --stop, -s            Stop all services"
    echo "  --restart, -r         Restart all services"
    echo "  --logs                Show logs from Docker services"
    echo "  --help, -h            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start with Docker (default)"
    echo "  $0 --local            # Start backend and frontend locally"
    echo "  $0 --backend-only     # Start only backend locally"
    echo "  $0 --stop             # Stop all Docker services"
    echo "  $0 --logs             # Show Docker logs"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --docker|-d)
            MODE="docker"
            shift
            ;;
        --local|-l)
            MODE="local"
            shift
            ;;
        --backend-only|-b)
            MODE="local"
            BACKEND_ONLY=true
            shift
            ;;
        --frontend-only|-f)
            MODE="local"
            FRONTEND_ONLY=true
            shift
            ;;
        --stop|-s)
            STOP=true
            shift
            ;;
        --restart|-r)
            RESTART=true
            shift
            ;;
        --logs)
            LOGS=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Stop services
if [ "$STOP" = true ]; then
    echo "Stopping services..."
    
    # Stop Docker services
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        docker compose down
        echo -e "${GREEN}✓${NC} Docker services stopped"
    else
        echo -e "${YELLOW}⚠${NC} No Docker services running"
    fi
    
    # Stop local processes (if any)
    if pgrep -f "uvicorn.*main:app" > /dev/null; then
        pkill -f "uvicorn.*main:app"
        echo -e "${GREEN}✓${NC} Backend process stopped"
    fi
    
    if pgrep -f "vite" > /dev/null; then
        pkill -f "vite"
        echo -e "${GREEN}✓${NC} Frontend process stopped"
    fi
    
    exit 0
fi

# Show logs
if [ "$LOGS" = true ]; then
    echo "Showing Docker logs..."
    docker compose logs -f
    exit 0
fi

# Restart services
if [ "$RESTART" = true ]; then
    echo "Restarting services..."
    docker compose restart
    echo -e "${GREEN}✓${NC} Services restarted"
    exit 0
fi

# Docker mode
if [ "$MODE" = "docker" ]; then
    echo "Starting services with Docker Compose..."
    echo ""
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}✗${NC} Docker is not running"
        echo "  Please start Docker Desktop and try again"
        exit 1
    fi
    
    # Check if docker-compose.yml exists
    if [ ! -f "docker-compose.yml" ]; then
        echo -e "${RED}✗${NC} docker-compose.yml not found"
        exit 1
    fi
    
    # Start services
    docker compose up -d
    
    echo ""
    echo -e "${GREEN}✓${NC} Services started"
    echo ""
    echo "Services:"
    echo "  - Backend API: http://localhost:8000"
    echo "  - Frontend: http://localhost:3000"
    echo "  - Temporal UI: http://localhost:8089"
    echo ""
    echo "Useful commands:"
    echo "  ./run.sh --logs        # View logs"
    echo "  ./run.sh --stop        # Stop services"
    echo "  docker compose ps      # Check service status"
    echo "  docker compose logs -f # Follow logs"
    echo ""
    
    exit 0
fi

# Local mode
if [ "$MODE" = "local" ]; then
    echo "Starting services locally..."
    echo ""
    
    # Start backend
    if [ "$FRONTEND_ONLY" = false ]; then
        echo "Starting backend..."
        cd ../server
        
        # Check for virtual environment
        if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
            echo -e "${YELLOW}⚠${NC} Virtual environment not found"
            echo "Creating virtual environment..."
            python3 -m venv venv
            source venv/bin/activate
            pip install -r requirements.txt
        else
            if [ -d "venv" ]; then
                source venv/bin/activate
            else
                source .venv/bin/activate
            fi
        fi
        
        # Check if .env exists
        if [ ! -f ".env" ]; then
            echo -e "${YELLOW}⚠${NC} .env file not found"
            if [ -f ".env.example" ]; then
                cp .env.example .env
                echo -e "${GREEN}✓${NC} Created .env from .env.example"
                echo -e "${YELLOW}⚠${NC} Please update .env with your configuration"
            fi
        fi
        
        # Run database migrations
        if command -v alembic &> /dev/null; then
            echo "Running database migrations..."
            alembic upgrade head
        fi
        
        # Start backend in background
        echo -e "${GREEN}✓${NC} Starting backend server..."
        uvicorn main:app --reload --host 0.0.0.0 --port 8000 > /tmp/graphmind-backend.log 2>&1 &
        BACKEND_PID=$!
        echo "Backend PID: $BACKEND_PID"
        echo "Backend logs: /tmp/graphmind-backend.log"
        
        cd "$SCRIPT_DIR"
        echo ""
    fi
    
    # Start frontend
    if [ "$BACKEND_ONLY" = false ]; then
        echo "Starting frontend..."
        cd ../client
        
        # Check for node_modules
        if [ ! -d "node_modules" ]; then
            echo -e "${YELLOW}⚠${NC} Node modules not found"
            echo "Installing dependencies..."
            yarn install
        fi
        
        # Check if .env exists
        if [ ! -f ".env" ]; then
            echo -e "${YELLOW}⚠${NC} .env file not found"
            if [ -f ".env.example" ]; then
                cp .env.example .env
                echo -e "${GREEN}✓${NC} Created .env from .env.example"
                echo -e "${YELLOW}⚠${NC} Please update .env with your configuration"
            fi
        fi
        
        # Start frontend in background
        echo -e "${GREEN}✓${NC} Starting frontend server..."
        yarn dev > /tmp/graphmind-frontend.log 2>&1 &
        FRONTEND_PID=$!
        echo "Frontend PID: $FRONTEND_PID"
        echo "Frontend logs: /tmp/graphmind-frontend.log"
        
        cd "$SCRIPT_DIR"
        echo ""
    fi
    
    echo "========================================="
    echo -e "${GREEN}Services started!${NC}"
    echo ""
    if [ "$FRONTEND_ONLY" = false ]; then
        echo "Backend API: http://localhost:8000"
        echo "  - API Docs: http://localhost:8000/docs"
        echo "  - Health: http://localhost:8000/health"
    fi
    if [ "$BACKEND_ONLY" = false ]; then
        echo "Frontend: http://localhost:5173"
    fi
    echo ""
    echo "Logs:"
    if [ "$FRONTEND_ONLY" = false ]; then
        echo "  Backend: tail -f /tmp/graphmind-backend.log"
    fi
    if [ "$BACKEND_ONLY" = false ]; then
        echo "  Frontend: tail -f /tmp/graphmind-frontend.log"
    fi
    echo ""
    echo "To stop services:"
    if [ "$FRONTEND_ONLY" = false ]; then
        echo "  kill $BACKEND_PID  # Backend"
    fi
    if [ "$BACKEND_ONLY" = false ]; then
        echo "  kill $FRONTEND_PID  # Frontend"
    fi
    echo "  Or use: ./run.sh --stop"
    echo ""
    
    exit 0
fi

