#!/bin/bash
set -e

echo "=== Installing ERPNext Connector ==="

odoo \
    --db_host="${PGHOST}" \
    --db_port="${PGPORT:-5432}" \
    --db_user="${PGUSER}" \
    --db_password="${PGPASSWORD}" \
    --database="${PGDATABASE}" \
    --db_sslmode="${PGSSLMODE:-disable}" \
    --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
    -i erpnext_connector \
    --stop-after-init \
    --workers=0

echo "✅ ERPNext Connector installed!"
exit 0
