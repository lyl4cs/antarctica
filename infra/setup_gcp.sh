#!/usr/bin/env bash
# One-time GCP setup for Antarctica. YOU run this (agents must not).
# Usage: PROJECT_ID=antarctica-xxxx REGION=us-central1 ./infra/setup_gcp.sh
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"

gcloud config set project "$PROJECT_ID"

echo "== Enabling APIs"
gcloud services enable \
  run.googleapis.com \
  pubsub.googleapis.com \
  sqladmin.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com

echo "== Artifact Registry"
gcloud artifacts repositories create antarctica \
  --repository-format=docker --location="$REGION" || true

echo "== Pub/Sub: topic, dead-letter topic, worker subscription"
gcloud pubsub topics create scans || true
gcloud pubsub topics create scans-dlq || true
gcloud pubsub subscriptions create scans-worker \
  --topic=scans \
  --ack-deadline=180 \
  --dead-letter-topic=scans-dlq \
  --max-delivery-attempts=5 || true

echo "== Cloud SQL (smallest tier; STOP it when not in use to save money)"
echo "   Run manually when ready (costs money while running):"
echo "   gcloud sql instances create antarctica-db --database-version=POSTGRES_16 \\"
echo "     --tier=db-f1-micro --region=$REGION --edition=ENTERPRISE"
echo "   gcloud sql databases create antarctica --instance=antarctica-db"

echo
echo "Done. Next: set a budget alert in Console -> Billing -> Budgets & alerts (\$20, alerts at 50/90/100%)."
