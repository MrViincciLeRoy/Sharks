#!/bin/bash
set -e

echo "=== Installing Forecaster ==="

odoo \
    --db_host="${PGHOST}" \
    --db_port="${PGPORT:-5432}" \
    --db_user="${PGUSER}" \
    --db_password="${PGPASSWORD}" \
    --database="${PGDATABASE}" \
    --db_sslmode="${PGSSLMODE:-disable}" \
    --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
    -i Forecaster \
    --stop-after-init \
    --workers=0

echo "✅ Forecaster module installed!"
exit 0
