#!/bin/bash
set -e

# Use PostgreSQL environment variables from Render
if [ -n "$POSTGRES_HOST" ]; then
    export PGHOST="$POSTGRES_HOST"
fi

if [ -n "$POSTGRES_PORT" ]; then
    export PGPORT="$POSTGRES_PORT"
fi

if [ -n "$POSTGRES_USER" ]; then
    export PGUSER="$POSTGRES_USER"
fi

if [ -n "$POSTGRES_PASSWORD" ]; then
    export PGPASSWORD="$POSTGRES_PASSWORD"
fi

if [ -n "$POSTGRES_DB" ]; then
    export PGDATABASE="$POSTGRES_DB"
fi

# Start Odoo with explicit database parameters and SSL mode
exec odoo \
    --db_host="${PGHOST}" \
    --db_port="${PGPORT:-5432}" \
    --db_user="${PGUSER}" \
    --db_password="${PGPASSWORD}" \
    --db_sslmode=require \
    --http-port=8069 \
    "$@"