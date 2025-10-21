set -e

# Debug: Print environment variables
echo "=== Environment Variables Debug ==="
echo "PGHOST: ${PGHOST:-NOT SET}"
echo "PGPORT: ${PGPORT:-NOT SET}"
echo "PGUSER: ${PGUSER:-NOT SET}"
echo "PGDATABASE: ${PGDATABASE:-NOT SET}"
echo "DATABASE_URL: ${DATABASE_URL:-NOT SET}"
echo "==================================="

# Parse DATABASE_URL if it exists
if [ -n "$DATABASE_URL" ]; then
    echo "Parsing DATABASE_URL..."
    # Extract database connection details from URL
    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PASS=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
    
    export PGHOST="${DB_HOST}"
    export PGPORT="${DB_PORT}"
    export PGUSER="${DB_USER}"
    export PGPASSWORD="${DB_PASS}"
    export PGDATABASE="${DB_NAME}"
fi

# Fallback to individual PG variables if DATABASE_URL not provided
if [ -z "$PGHOST" ] && [ -n "$POSTGRES_HOST" ]; then
    export PGHOST="$POSTGRES_HOST"
fi

if [ -z "$PGPORT" ] && [ -n "$POSTGRES_PORT" ]; then
    export PGPORT="$POSTGRES_PORT"
fi

if [ -z "$PGUSER" ] && [ -n "$POSTGRES_USER" ]; then
    export PGUSER="$POSTGRES_USER"
fi

if [ -z "$PGPASSWORD" ] && [ -n "$POSTGRES_PASSWORD" ]; then
    export PGPASSWORD="$POSTGRES_PASSWORD"
fi

if [ -z "$PGDATABASE" ] && [ -n "$POSTGRES_DB" ]; then
    export PGDATABASE="$POSTGRES_DB"
fi

# Set defaults if still not set
PGPORT="${PGPORT:-5432}"
PGDATABASE="${PGDATABASE:-defaultdb}"

echo "=== Using Database Configuration ==="
echo "Host: ${PGHOST}"
echo "Port: ${PGPORT}"
echo "User: ${PGUSER}"
echo "Database: ${PGDATABASE}"
echo "===================================="

# Set SSL mode to 'require' for Aiven PostgreSQL
export PGSSLMODE=require

# Wait for database to be ready
echo "=== Waiting for Database ==="
max_attempts=30
attempt=0
until PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -c "SELECT 1" >/dev/null 2>&1 || [ $attempt -eq $max_attempts ]; do
    attempt=$((attempt + 1))
    echo "Waiting for database... attempt $attempt/$max_attempts"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "ERROR: Could not connect to database after $max_attempts attempts"
    exit 1
fi

echo "=== Database Connection Successful ==="

# Check if database needs initialization
echo "=== Checking Database State ==="
DB_INITIALIZED=$(PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='ir_module_module';" 2>/dev/null || echo "0")

if [ "$DB_INITIALIZED" = "0" ]; then
    echo "=== Database Not Initialized ==="
    echo "=== Starting Odoo with initialization in background ==="
    
    # Start Odoo server first to keep port open
    odoo \
        --db_host="${PGHOST}" \
        --db_port="${PGPORT}" \
        --db_user="${PGUSER}" \
        --db_password="${PGPASSWORD}" \
        --database="${PGDATABASE}" \
        --db_sslmode=require \
        --db-filter="^${PGDATABASE}$" \
        --http-port=8069 \
        --log-level=info \
        --init=base \
        --without-demo=all \
        "$@"
else
    echo "=== Database Already Initialized ==="
    echo "=== Starting Odoo Server ==="
    
    # Start Odoo normally
    exec odoo \
        --db_host="${PGHOST}" \
        --db_port="${PGPORT}" \
        --db_user="${PGUSER}" \
        --db_password="${PGPASSWORD}" \
        --database="${PGDATABASE}" \
        --db_sslmode=require \
        --db-filter="^${PGDATABASE}$" \
        --http-port=8069 \
        --log-level=info \
        "$@"
fi
