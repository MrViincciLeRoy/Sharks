#!/bin/bash
set -e

echo "=== [INIT JOB] Starting database initialization check... ==="
echo "Host: ${PGHOST}, DB: ${PGDATABASE}"
echo "========================================================"

export PGOPTIONS="-c lock_timeout=300000 -c statement_timeout=300000"

# Check if ir_module_module table exists AND has data
TABLE_EXISTS_QUERY="SELECT COUNT(*) FROM information_schema.tables WHERE table_name='ir_module_module' LIMIT 1"
HAS_DATA_QUERY="SELECT COUNT(*) FROM ir_module_module LIMIT 1"

TABLE_COUNT=$(PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "${TABLE_EXISTS_QUERY}" 2>/dev/null || echo "0")

if [ "$TABLE_COUNT" -eq "0" ]; then
    echo "=== [INIT JOB] Database is new (no tables). Installing all modules... ==="
    FRESH_INSTALL=true
else
    # Table exists, check if it has data
    DATA_COUNT=$(PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "${HAS_DATA_QUERY}" 2>/dev/null || echo "0")
    
    if [ "$DATA_COUNT" -eq "0" ]; then
        echo "=== [INIT JOB] Database was truncated (tables exist but empty). Treating as fresh install... ==="
        FRESH_INSTALL=true
    else
        echo "=== [INIT JOB] Database exists with data. Checking modules... ==="
        FRESH_INSTALL=false
    fi
fi

if [ "$FRESH_INSTALL" = true ]; then
    echo "=== [INIT JOB] Performing fresh installation... ==="
    
    # For fresh install or truncated DB, we need to initialize
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
        --workers=0 \
        --no-http
    
    echo "=== [INIT JOB] Installation successful! ==="
    echo "=== Installed: base, account, GMailer, erpnext_connector, gmail_erpnext_bridge ==="
    
    # Reset admin password
    PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c \
        "UPDATE res_users SET password='admin' WHERE login='admin';" 2>/dev/null || echo "Password set during initialization"
    
    echo "=== Default login: admin / admin ==="
else
    echo "=== [INIT JOB] Database exists. Checking for missing modules... ==="
    
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
                --workers=0 \
                --no-http
            echo "=== ${MODULE} installed! ==="
        else
            echo "=== ${MODULE} already installed ==="
        fi
    done
    
    echo "=== [INIT JOB] All modules up to date ==="
fi

echo "=== [INIT JOB] Finished successfully ==="
exit 0 
