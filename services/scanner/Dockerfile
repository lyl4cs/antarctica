FROM python:3.12-slim

# Node + Chromium for Lighthouse
RUN apt-get update && apt-get install -y --no-install-recommends \
      nodejs npm chromium fonts-liberation ca-certificates \
    && npm install -g lighthouse@12 \
    && rm -rf /var/lib/apt/lists/*
ENV CHROME_PATH=/usr/bin/chromium

WORKDIR /app
COPY pyproject.toml .
COPY services ./services
COPY core ./core
RUN pip install --no-cache-dir .

CMD ["python", "-m", "services.scanner.worker"]
