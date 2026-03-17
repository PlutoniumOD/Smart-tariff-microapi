ARG BUILD_FROM
FROM $BUILD_FROM

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# Install dependencies
RUN apk add --no-cache \
    ca-certificates \
    tzdata \
    curl \
    python3 \
    py3-pip

WORKDIR /app

COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY app /app/app
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8787
CMD ["/run.sh"]
