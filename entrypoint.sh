#!/bin/bash
#
# SCRIPT FOR THE RENDER 'WEB' SERVICE
# This script just starts the Odoo server. It assumes the DB is ready.
#
set -e

echo "=== [WEB SERVICE] Starting Odoo Server... ==="
echo "Host: ${PGHOST}, Port: ${PGPORT}, DB: ${PGDATABASE}"
echo "==============================================="

# Use 'exec' to replace this script's process with the Odoo process.
exec odoo \
    --db_host="${PGHOST}" \
    --db_port="${PGPORT:-5432}" \
    --db_user="${PGUSER}" \
    --db_password="${PGPASSWORD}" \
    --database="${PGDATABASE}" \
    --db_sslmode="${PGSSLMODE:-disable}" \
    --http-port=8069 \
    "$@"

