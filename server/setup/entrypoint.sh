#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h postgres -U graphmind -d graphmind_db -p 5432; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is ready - running migrations..."
cd /app
alembic upgrade head || {
    echo "Alembic upgrade failed (tables may already exist), stamping head..."
    alembic stamp head 2>/dev/null || true
}

echo "Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000