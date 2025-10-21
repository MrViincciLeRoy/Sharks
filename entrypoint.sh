#!/bin/bash
set -e

# Debug: Print environment variables
echo "=== Environment Variables Debug ==="
echo "PGHOST: ${PGHOST:-NOT SET}"
echo "PGPORT: ${PGPORT:-NOT SET}"
echo "PGUSER: ${PGUSER:-NOT SET}"
echo "PGDATABASE: ${PGDATABASE:-NOT SET}"
echo "DATABASE_URL: ${DATABASE_URL:-NOT SET}"
echo "==================================="

# Parse DATABASE_URL if it exists
if [ -n "$DATABASE_URL" ]; then
    echo "Parsing DATABASE_URL..."
    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PASS=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
    
    export PGHOST="${DB_HOST}"
    export PGPORT="${DB_PORT}"
    export PGUSER="${DB_USER}"
    export PGPASSWORD="${DB_PASS}"
    export PGDATABASE="${DB_NAME}"
fi

# Fallback to individual PG variables
if [ -z "$PGHOST" ] && [ -n "$POSTGRES_HOST" ]; then
    export PGHOST="$POSTGRES_HOST"
fi

if [ -z "$PGPORT" ] && [ -n "$POSTGRES_PORT" ]; then
    export PGPORT="$POSTGRES_PORT"
fi

if [ -z "$PGUSER" ] && [ -n "$POSTGRES_USER" ]; then
    export PGUSER="$POSTGRES_USER"
fi

if [ -z "$PGPASSWORD" ] && [ -n "$POSTGRES_PASSWORD" ]; then
    export PGPASSWORD="$POSTGRES_PASSWORD"
fi

if [ -z "$PGDATABASE" ] && [ -n "$POSTGRES_DB" ]; then
    export PGDATABASE="$POSTGRES_DB"
fi

echo "=== Using Database Configuration ==="
echo "Host: ${PGHOST}"
echo "Port: ${PGPORT}"
echo "User: ${PGUSER}"
echo "Database: ${PGDATABASE}"
echo "===================================="

# CRITICAL: Set SSL mode to 'require' for Render PostgreSQL
# Render databases require SSL connections
export PGSSLMODE=require

# Start Odoo with explicit SSL mode parameter
exec odoo \
    --db_host="${PGHOST}" \
    --db_port="${PGPORT:-5432}" \
    --db_user="${PGUSER}" \
    --db_password="${PGPASSWORD}" \
    --db_sslmode=require \
    --http-port=8069 \
    "$@"
