FROM odoo:17.0

USER root

# Install PostgreSQL client for database checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy both scripts into the container
COPY init-db.sh /init-db.sh
COPY entrypoint.sh /entrypoint.sh

# Make both scripts executable
RUN chmod +x /init-db.sh /entrypoint.sh

# Create directories and set ownership for the odoo user
RUN mkdir -p /mnt/extra-addons && \
    chown -R odoo:odoo /mnt/extra-addons && \
    mkdir -p /var/lib/odoo && \
    chown -R odoo:odoo /var/lib/odoo

USER odoo

EXPOSE 8069

# The default command for the container is to start the web service.
# Render's "job" service will override this to run the init script instead.
ENTRYPOINT ["/entrypoint.sh"]

