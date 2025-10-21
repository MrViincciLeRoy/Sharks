#!/bin/bash
#
# SCRIPT FOR THE RENDER 'JOB'
# Its only purpose is to initialize the database if it's empty.
#
set -e

echo "=== [INIT JOB] Starting database initialization check... ==="
echo "Host: ${PGHOST}, User: ${PGUSER}, DB: ${PGDATABASE}"
echo "========================================================"

# Query to check if a core Odoo table exists.
TABLE_EXISTS_QUERY="SELECT 1 FROM information_schema.tables WHERE table_name='ir_module_module' LIMIT 1"

# If the psql command does NOT find the table, the 'if' condition becomes true.
if ! PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "${TABLE_EXISTS_QUERY}" | grep -q 1; then
    echo "=== [INIT JOB] Database is new. Installing 'base' module... (This may take several minutes) ==="
    odoo \
        --db_host="${PGHOST}" \
        --db_port="${PGPORT:-5432}" \
        --db_user="${PGUSER}" \
        --db_password="${PGPASSWORD}" \
        --database="${PGDATABASE}" \
        --db_sslmode="${PGSSLMODE:-disable}" \
        -i base,account,sale_management,crm,stock,purchase,account_accountant,payment,l10n_generic_coa \
        --stop-after-init \
        --without-demo=all
    echo "=== [INIT JOB] Database initialization successful! ==="
else
    echo "=== [INIT JOB] Database already initialized. Nothing to do. ==="
fi

echo "=== [INIT JOB] Finished. The web service can now start. ==="
exit 0

