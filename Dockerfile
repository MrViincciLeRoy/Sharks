FROM odoo:17.0

# Install additional dependencies if needed
USER root

# Create directories
RUN mkdir -p /mnt/extra-addons && \
    chown -R odoo:odoo /mnt/extra-addons && \
    chown -R odoo:odoo /var/lib/odoo

# Switch back to odoo user
USER odoo

# Expose Odoo port
EXPOSE 8069

# Entry point
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
