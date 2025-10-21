#!/bin/bash
set -e

# Use PostgreSQL environment variables if set
if [ -n "$PGHOST" ]; then
    export HOST="$PGHOST"
fi

if [ -n "$PGPORT" ]; then
    export PORT="$PGPORT"
fi

if [ -n "$PGUSER" ]; then
    export USER="$PGUSER"
fi

if [ -n "$PGPASSWORD" ]; then
    export PASSWORD="$PGPASSWORD"
fi

# Start Odoo with explicit database parameters
exec odoo \
    --db_host="${PGHOST}" \
    --db_port="${PGPORT:-5432}" \
    --db_user="${PGUSER}" \
    --db_password="${PGPASSWORD}" \
    --http-port=8069 \
    "$@"