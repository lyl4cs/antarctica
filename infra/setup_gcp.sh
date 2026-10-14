#!/usr/bin/env bash
# One-time GCP setup. YOU run this; agents must not.
# Prereqs: gcloud installed + `gcloud auth login`, a project with billing, a $20 budget alert.
# Usage: PROJECT_ID=my-antarctica REGION=us-central1 ./infra/setup_gcp.sh
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"

gcloud config set project "$PROJECT_ID"

echo "== Enable APIs"
gcloud services enable run.googleapis.com pubsub.googleapis.com aiplatform.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

echo "== Artifact Registry (container images)"
gcloud artifacts repositories create antarctica --repository-format=docker \
  --location="$REGION" 2>/dev/null || echo "   (exists)"

echo "== Service accounts (least privilege: each service only gets what it needs)"
gcloud iam service-accounts create antarctica-api 2>/dev/null || true
gcloud iam service-accounts create antarctica-scanner 2>/dev/null || true
gcloud iam service-accounts create antarctica-pusher 2>/dev/null || true
API_SA="antarctica-api@${PROJECT_ID}.iam.gserviceaccount.com"
SCAN_SA="antarctica-scanner@${PROJECT_ID}.iam.gserviceaccount.com"
PUSH_SA="antarctica-pusher@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$API_SA" \
  --role=roles/pubsub.publisher --condition=None >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$API_SA" \
  --role=roles/aiplatform.user --condition=None >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$API_SA" \
  --role=roles/secretmanager.secretAccessor --condition=None >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member="serviceAccount:$SCAN_SA" \
  --role=roles/secretmanager.secretAccessor --condition=None >/dev/null

echo "== Pub/Sub topics"
gcloud pubsub topics create scans 2>/dev/null || echo "   (scans exists)"
gcloud pubsub topics create scans-dlq 2>/dev/null || echo "   (scans-dlq exists)"
gcloud pubsub subscriptions create scans-dlq-sub --topic=scans-dlq 2>/dev/null || true

echo "== Database URL secret (Neon connection string, never in the repo)"
if ! gcloud secrets describe database-url >/dev/null 2>&1; then
  read -r -s -p "Paste your Neon DATABASE_URL: " DBURL; echo
  printf '%s' "$DBURL" | gcloud secrets create database-url --data-file=-
fi

echo
echo "Next: ./infra/deploy.sh  (builds images, deploys both services, wires the push subscription)"
