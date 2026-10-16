# Scanner: Python + headless Chromium + Lighthouse CLI, served as an HTTP push endpoint.
#
# BOTH HALVES OF THE ENGINE ARE PINNED, because a score is only comparable to
# another score measured the same way. Lighthouse computes the number, but Chromium
# produces the trace it computes it from, so a browser that changes underneath you
# moves scores exactly like a Lighthouse upgrade would. See ADR 022.
#
# This was learned the hard way. Lighthouse was pinned to 12.8.2 while `chromium`
# was installed unpinned, and the image had not been rebuilt in a while. The next
# rebuild therefore changed TWO things at once: the intended Lighthouse bump, and
# an unintended Chromium jump to whatever Debian shipped that day. The scanner then
# died on every request.
#
# `bookworm` is spelled out rather than riding the `slim` tag, so a Debian release
# change is a deliberate commit and not something that arrives on a Tuesday.
FROM python:3.12-slim-bookworm

# The exact Debian package version of Chromium, e.g. "120.0.6099.224-1~deb12u1".
# Empty means "whatever is current", which is the behaviour that caused the
# incident above; it stays the default only so this build cannot break while the
# known-good version is still being established.
#
# To pin it:
#   1. Find the version your last working image ran:
#        docker run --rm <last-good-image> chromium --version
#      or, from a revision that still works:
#        gcloud run revisions describe <REVISION> --region=us-central1
#   2. Build with it: --build-arg CHROMIUM_VERSION=<that version>
#      (add it to infra/cloudbuild.yaml substitutions to make it permanent)
# A pinned version that Debian has since removed fails the build loudly, which is
# the correct outcome: it is a prompt to choose the next version on purpose.
ARG CHROMIUM_VERSION=

RUN apt-get update && apt-get install -y --no-install-recommends \
      nodejs npm fonts-liberation ca-certificates \
    && if [ -n "$CHROMIUM_VERSION" ]; then \
         apt-get install -y --no-install-recommends "chromium=$CHROMIUM_VERSION"; \
       else \
         apt-get install -y --no-install-recommends chromium; \
       fi \
    && npm install -g lighthouse@12.8.2 \
    && rm -rf /var/lib/apt/lists/*

# Recorded at build time and printed in the build log, so the browser that shipped
# in this image is always knowable after the fact. Without this the only way to
# answer "what Chrome was that scan run on" is to still have the image.
RUN chromium --version && lighthouse --version \
    && chromium --version > /etc/scanner-chromium-version

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
