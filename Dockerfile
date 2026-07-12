# Cloakwell DLP — single image shared by the proxy, dashboard, and demo client
# services (see docker-compose.yml). Python 3.10 because mitmproxy 10.4.0 pins to it.
FROM python:3.10-slim

# curl: dashboard/proxy healthchecks. mitmproxy ships wheels, so no build toolchain needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for layer caching.
COPY proxy/requirements.txt /app/proxy/requirements.txt
RUN pip install --no-cache-dir -r /app/proxy/requirements.txt

# App code (dashboard static assets live at /app/dashboard, which api.py mounts
# as ../dashboard relative to its /app/proxy working dir).
COPY . /app

ENV PYTHONUNBUFFERED=1
WORKDIR /app/proxy
