FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1     PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates tzdata curl &&     rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r requirements.txt

COPY app /app/app
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8787
CMD ["/run.sh"]
