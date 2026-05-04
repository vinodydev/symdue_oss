#!/bin/bash
# setup-db.sh - Database initialization

set -e

echo "========================================="
echo "GraphMind Orchestrator - Database Setup"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables from server/.env if it exists
if [ -f "../server/.env" ]; then
    export $(cat ../server/.env | grep -v '^#' | xargs)
fi

# Default values
DB_USER=${POSTGRES_USER:-graphmind}
DB_PASSWORD=${POSTGRES_PASSWORD:-your_password}
DB_NAME=${POSTGRES_DB:-graphmind_db}
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}

echo "Database configuration:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  User: $DB_USER"
echo "  Database: $DB_NAME"
echo ""

# Check if PostgreSQL is accessible
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} psql not found. Skipping database setup."
    echo "You can use Docker PostgreSQL instead (see docker-compose.yml)"
    exit 0
fi

# Check if we can connect to PostgreSQL
if ! PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c '\q' 2>/dev/null; then
    echo -e "${YELLOW}⚠${NC} Cannot connect to PostgreSQL as $DB_USER@$DB_HOST:$DB_PORT"
    echo "This script requires PostgreSQL to be running and accessible."
    echo ""
    echo "Options:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "1. Start PostgreSQL: brew services start postgresql@15"
        echo "2. Use Docker PostgreSQL: docker-compose up -d postgres"
        echo "3. Create user manually: psql postgres"
    else
        echo "1. Start PostgreSQL: sudo systemctl start postgresql"
        echo "2. Use Docker PostgreSQL: docker-compose up -d postgres"
        echo "3. Create user manually: sudo -u postgres psql"
    fi
    exit 1
fi

echo -e "${GREEN}✓${NC} Connected to PostgreSQL"
echo ""

# Check if database exists
if PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
    echo -e "${GREEN}✓${NC} Database '$DB_NAME' already exists"
else
    echo "Creating database '$DB_NAME'..."
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "CREATE DATABASE $DB_NAME;"
    echo -e "${GREEN}✓${NC} Database created"
fi

echo ""
echo "========================================="
echo "Database setup complete!"
echo ""
echo "Next steps:"
echo "1. Run Alembic migrations: cd ../server && alembic upgrade head"
echo "2. Or use Docker: docker-compose up -d postgres"
echo ""

