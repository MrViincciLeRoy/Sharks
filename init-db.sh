#!/bin/bash
set -e

echo "=== [INIT JOB] Starting database initialization check... ==="
echo "Host: ${PGHOST}, DB: ${PGDATABASE}"
echo "========================================================"

export PGOPTIONS="-c lock_timeout=300000 -c statement_timeout=300000"

TABLE_EXISTS_QUERY="SELECT 1 FROM information_schema.tables WHERE table_name='ir_module_module' LIMIT 1"

if ! PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "${TABLE_EXISTS_QUERY}" 2>/dev/null | grep -q 1; then
    echo "=== [INIT JOB] Database is new. Installing all modules... ==="
    
    odoo \
        --db_host="${PGHOST}" \
        --db_port="${PGPORT:-5432}" \
        --db_user="${PGUSER}" \
        --db_password="${PGPASSWORD}" \
        --database="${PGDATABASE}" \
        --db_sslmode="${PGSSLMODE:-disable}" \
        --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
        -i base,account,GMailer,erpnext_connector,gmail_erpnext_bridge \
        --stop-after-init \
        --without-demo=all \
        --workers=0
    
    echo "=== [INIT JOB] Installation successful! ==="
    echo "=== Installed: base, account, GMailer, erpnext_connector, gmail_erpnext_bridge ==="
    
    PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c \
        "UPDATE res_users SET password='admin' WHERE login='admin';" 2>/dev/null || echo "Password already set"
    
    echo "=== Default login: admin / admin ==="
else
    echo "=== [INIT JOB] Database exists. Checking modules... ==="
    
    # Check and install missing modules
    for MODULE in GMailer erpnext_connector gmail_erpnext_bridge; do
        MODULE_CHECK="SELECT 1 FROM ir_module_module WHERE name='${MODULE}' AND state='installed' LIMIT 1"
        
        if ! PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "${MODULE_CHECK}" 2>/dev/null | grep -q 1; then
            echo "=== Installing ${MODULE}... ==="
            odoo \
                --db_host="${PGHOST}" \
                --db_port="${PGPORT:-5432}" \
                --db_user="${PGUSER}" \
                --db_password="${PGPASSWORD}" \
                --database="${PGDATABASE}" \
                --db_sslmode="${PGSSLMODE:-disable}" \
                --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
                -i ${MODULE} \
                --stop-after-init \
                --workers=0
            echo "=== ${MODULE} installed! ==="
        fi
    done
    
    echo "=== [INIT JOB] All modules up to date ==="
fi

echo "=== [INIT JOB] Finished successfully ==="
exit 0
