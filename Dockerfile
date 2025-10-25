FROM odoo:17.0

USER root

# Install PostgreSQL client for database checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN pip install cryptography==42.0.4 pyopenssl==24.1.0 urllib3==2.2.1

# Install Python dependencies for GMailer addon + PDF parsing
RUN pip3 install --no-cache-dir \
    google-auth \
    google-auth-oauthlib \
    google-auth-httplib2 \
    google-api-python-client \
    beautifulsoup4 \
    requests \
    PyPDF2 \
    pdfplumber

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

# Copy custom addons to the container
COPY --chown=odoo:odoo custom-addons /mnt/extra-addons

USER odoo

EXPOSE 8069

# The default command for the container is to start the web service.
# Render's "job" service will override this to run the init script instead.
ENTRYPOINT ["/entrypoint.sh"]
