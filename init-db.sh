#!/bin/bash
#
# SCRIPT FOR DATABASE INITIALIZATION WITH IMPROVED LOCK HANDLING
#
set -e

echo "=== [INIT JOB] Starting database initialization check... ==="
echo "Host: ${PGHOST}, User: ${PGUSER}, DB: ${PGDATABASE}"
echo "========================================================"

# Increase lock timeout for this session
export PGOPTIONS="-c lock_timeout=300000 -c statement_timeout=300000"

# Query to check if a core Odoo table exists.
TABLE_EXISTS_QUERY="SELECT 1 FROM information_schema.tables WHERE table_name='ir_module_module' LIMIT 1"

# Check if database is already initialized
if ! PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "${TABLE_EXISTS_QUERY}" 2>/dev/null | grep -q 1; then
    echo "=== [INIT JOB] Database is new. Installing modules... ==="
    echo "=== Using increased lock timeout (5 minutes) ==="
    
    # Run Odoo initialization with increased timeouts
    # FIXED: Removed --db_maxconn=1 to allow multiple connections
    odoo \
        --db_host="${PGHOST}" \
        --db_port="${PGPORT:-5432}" \
        --db_user="${PGUSER}" \
        --db_password="${PGPASSWORD}" \
        --database="${PGDATABASE}" \
        --db_sslmode="${PGSSLMODE:-disable}" \
        --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
        -i base,account,GMailer \
        --stop-after-init \
        --without-demo=all \
        --workers=0
    
    echo "=== [INIT JOB] Database initialization successful! ==="
    echo "=== Installed modules: base, account, GMailer ==="
    
    # Set admin password
    echo "=== Setting admin password... ==="
    PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c \
        "UPDATE res_users SET password='admin' WHERE login='admin';" 2>/dev/null || echo "Password already set"
    
    echo "=== Default login: admin / admin ==="
else
    echo "=== [INIT JOB] Database already initialized. Checking modules... ==="
    
    # Check if GMailer is installed
    GMAILER_CHECK="SELECT 1 FROM ir_module_module WHERE name='GMailer' AND state='installed' LIMIT 1"
    
    if ! PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "${GMAILER_CHECK}" 2>/dev/null | grep -q 1; then
        echo "=== [INIT JOB] Installing GMailer... ==="
        odoo \
            --db_host="${PGHOST}" \
            --db_port="${PGPORT:-5432}" \
            --db_user="${PGUSER}" \
            --db_password="${PGPASSWORD}" \
            --database="${PGDATABASE}" \
            --db_sslmode="${PGSSLMODE:-disable}" \
            --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
            -i GMailer \
            --stop-after-init \
            --workers=0
        echo "=== [INIT JOB] GMailer installation successful! ==="
    else
        echo "=== [INIT JOB] All modules already installed. ==="
    fi
fi

echo "=== [INIT JOB] Finished successfully. ==="
echo "=== Login with: admin / admin ==="
exit 0
