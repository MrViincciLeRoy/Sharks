FROM odoo:17.0

USER root

# Install CA certificates for SSL connections
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    postgresql-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create directories
RUN mkdir -p /mnt/extra-addons && \
    chown -R odoo:odoo /mnt/extra-addons && \
    chown -R odoo:odoo /var/lib/odoo

USER odoo

EXPOSE 8069

ENTRYPOINT ["/entrypoint.sh"]