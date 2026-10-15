# Scanner: Python + headless Chromium + Lighthouse CLI, served as an HTTP push endpoint.
#
# Lighthouse is pinned EXACTLY, not to a major. Scores are only comparable across
# scans run by the same engine, so a floating version would silently shift every
# score on the next image rebuild and put an invisible break in every site's
# history chart. Bumping it is a deliberate commit; see ADR 022.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      nodejs npm chromium fonts-liberation ca-certificates \
    && npm install -g lighthouse@12.8.2 \
    && rm -rf /var/lib/apt/lists/*
ENV CHROME_PATH=/usr/bin/chromium \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml .
COPY services ./services
COPY core ./core
RUN pip install --no-cache-dir ".[ai]"

# Cloud Run sets $PORT. One request at a time per instance: Lighthouse is CPU-heavy
# and runs are noisy if two share a CPU (concurrency=1 is set at deploy time too).
CMD exec uvicorn services.scanner.worker:app --host 0.0.0.0 --port ${PORT:-8080}
