FROM odoo:17.0

USER root

# Create directories
RUN mkdir -p /mnt/extra-addons && \
    chown -R odoo:odoo /mnt/extra-addons && \
    chown -R odoo:odoo /var/lib/odoo

USER odoo

EXPOSE 8069

# Use environment variables directly with CMD
CMD ["odoo", "--db_host=${DB_HOST}", "--db_port=${DB_PORT}", "--db_user=${DB_USER}", "--db_password=${DB_PASSWORD}"]
