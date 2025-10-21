FROM odoo:17.0

USER root

# Create directories
RUN mkdir -p /mnt/extra-addons && \
    chown -R odoo:odoo /mnt/extra-addons && \
    chown -R odoo:odoo /var/lib/odoo

# Create a startup script that uses environment variables
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Start Odoo with database configuration from environment variables\n\
exec odoo \\\n\
    --db_host="${DB_HOST:-db}" \\\n\
    --db_port="${DB_PORT:-5432}" \\\n\
    --db_user="${DB_USER:-odoo}" \\\n\
    --db_password="${DB_PASSWORD}" \\\n\
    --http-port=8069 \\\n\
    "$@"' > /usr/local/bin/start-odoo.sh && \
    chmod +x /usr/local/bin/start-odoo.sh

USER odoo

EXPOSE 8069

ENTRYPOINT ["/usr/local/bin/start-odoo.sh"]
