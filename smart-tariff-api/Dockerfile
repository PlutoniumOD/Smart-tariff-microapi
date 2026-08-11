FROM ghcr.io/home-assistant/base:latest

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

# Copy application source
COPY app /app/app
RUN echo "=== VERIFYING COPIED MAIN.PY ===" \
    && grep -n "BUILD_MARKER: ENERGY_CLASSES_2026_08_11_V2" /app/app/main.py \
    && grep -n -A 12 -B 2 "smart_tariff_elec_cost_today" /app/app/main.py \
    && grep -n -A 12 -B 2 "smart_tariff_gas_cost_today" /app/app/main.py \
    && sha256sum /app/app/main.py \
    && /app/venv/bin/python -m py_compile /app/app/main.py \
    && echo "=== MAIN.PY SYNTAX OK ==="
COPY run.sh /run.sh
RUN chmod +x /run.sh

# Expose port
EXPOSE 8787

# Start using venv
ENV PATH="/app/venv/bin:$PATH"

CMD ["/run.sh"]
