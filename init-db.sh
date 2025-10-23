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
    echo "=== [INIT JOB] Database is new. Installing base, account, sale_management, and GMailer... ==="
    odoo \
        --db_host="${PGHOST}" \
        --db_port="${PGPORT:-5432}" \
        --db_user="${PGUSER}" \
        --db_password="${PGPASSWORD}" \
        --database="${PGDATABASE}" \
        --db_sslmode="${PGSSLMODE:-disable}" \
        --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
        -i base,account,sale_management,GMailer \
        --stop-after-init \
        --without-demo=all
    
    echo "=== [INIT JOB] Database initialization successful! ==="
    echo "=== Installed modules: base, account, sale_management, GMailer ==="
    echo "=== Default login: admin / admin ==="
    
    # Set admin password explicitly to 'admin'
    echo "=== Setting admin password... ==="
    PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c \
        "UPDATE res_users SET password='admin' WHERE login='admin';" || echo "Password already set"
    
    echo "=== Admin password confirmed: admin ==="
else
    echo "=== [INIT JOB] Database already initialized. Checking if GMailer needs installation... ==="
    
    # Check if GMailer is already installed
    GMAILER_CHECK="SELECT 1 FROM ir_module_module WHERE name='GMailer' AND state='installed' LIMIT 1"
    
    if ! PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "${GMAILER_CHECK}" | grep -q 1; then
        echo "=== [INIT JOB] GMailer not installed. Installing now... ==="
        odoo \
            --db_host="${PGHOST}" \
            --db_port="${PGPORT:-5432}" \
            --db_user="${PGUSER}" \
            --db_password="${PGPASSWORD}" \
            --database="${PGDATABASE}" \
            --db_sslmode="${PGSSLMODE:-disable}" \
            --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
            -i GMailer \
            --stop-after-init
        echo "=== [INIT JOB] GMailer installation successful! ==="
    else
        echo "=== [INIT JOB] GMailer already installed. Nothing to do. ==="
    fi
fi

echo "=== [INIT JOB] Finished. The web service can now start. ==="
echo "=== You can now login with: admin / admin ==="
exit 0
