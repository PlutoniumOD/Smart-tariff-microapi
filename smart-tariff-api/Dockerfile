ARG BUILD_FROM
FROM $BUILD_FROM

# Add tzdata if needed; HA images already include bashio and s6
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install needed Alpine packages
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv \
    ca-certificates \
    tzdata \
    curl

# Create application directory
WORKDIR /app

# Create and activate virtual environment
RUN python3 -m venv /app/venv

# Ensure pip inside venv is upgradable
RUN /app/venv/bin/pip install --upgrade pip setuptools wheel --break-system-packages

# Install Python requirements inside virtualenv only
COPY requirements.txt /app/
RUN /app/venv/bin/pip install -r /app/requirements.txt --break-system-packages

# --- Solar poller dependency ---
RUN pip install --no-cache-dir requests==2.31.0

# Copy application source
COPY app /app/app
COPY run.sh /run.sh
RUN chmod +x /run.sh

# Expose port
EXPOSE 8787

# Start using venv
ENV PATH="/app/venv/bin:$PATH"

CMD ["/run.sh"]
