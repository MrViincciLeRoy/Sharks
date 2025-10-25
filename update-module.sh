#!/bin/bash
#
# SCRIPT TO UPDATE GMAILER MODULE
#
set -e

echo "=== [UPDATE] Updating GMailer module... ==="
echo "Host: ${PGHOST}, DB: ${PGDATABASE}"
echo "==========================================="

# Update the GMailer module
odoo \
    --db_host="${PGHOST}" \
    --db_port="${PGPORT:-5432}" \
    --db_user="${PGUSER}" \
    --db_password="${PGPASSWORD}" \
    --database="${PGDATABASE}" \
    --db_sslmode="${PGSSLMODE:-disable}" \
    --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
    -u GMailer \
    --stop-after-init \
    --workers=0

echo "=== [UPDATE] GMailer module updated successfully! ==="
exit 0