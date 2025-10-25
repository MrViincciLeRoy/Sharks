#!/bin/bash
set -e

echo "=== Installing GMailer-ERPNext Bridge ==="

odoo \
    --db_host="${PGHOST}" \
    --db_port="${PGPORT:-5432}" \
    --db_user="${PGUSER}" \
    --db_password="${PGPASSWORD}" \
    --database="${PGDATABASE}" \
    --db_sslmode="${PGSSLMODE:-disable}" \
    --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
    -i gmail_erpnext_bridge \
    --stop-after-init \
    --workers=0

echo "✅ Bridge module installed!"
exit 0
