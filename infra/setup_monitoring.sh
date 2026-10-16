#!/usr/bin/env bash
# Find out the site is down before a user does. YOU run this; agents must not.
#
# WHY THIS EXISTS
# The scanner failed on every request for about an hour and nothing said so. It
# was noticed by trying to use the site. Logs had the answer the whole time; no
# one was looking, because nothing asked anyone to look.
#
# This sets up the smallest thing that fixes that:
#   1. An uptime check that calls /health on the API and the scanner every minute
#      from several regions, so it tests the path a real user takes rather than
#      something inside the project.
#   2. An alert that emails you when either check fails from more than one region
#      for 5 minutes. More than one region, so a single flaky prober stays quiet.
#   3. A log-based alert for scans that are failing to save, which is the shape of
#      failure that leaves no 5xx on the API because it happens in the scanner,
#      behind Pub/Sub. That is exactly what went unnoticed.
#   4. A budget with alerts at 50/90/100 percent, because Cloud Run plus Gemini
#      plus Neon with nothing watching is how a runaway loop becomes an invoice.
#
# Usage:
#   PROJECT_ID=antarctica-ls ALERT_EMAIL=you@example.com bash infra/setup_monitoring.sh
# Optional:
#   REGION=us-central1            Cloud Run region (default us-central1)
#   BUDGET_USD=25                 monthly budget ceiling (default 25)
#   BILLING_ACCOUNT=XXXXXX-...    needed only for the budget; auto-detected if unset
#
# Safe to re-run: every resource is created only if it is not already there.

set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
: "${ALERT_EMAIL:?set ALERT_EMAIL (where the alerts go)}"
REGION="${REGION:-us-central1}"
BUDGET_USD="${BUDGET_USD:-25}"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "== Enable the APIs this needs"
gcloud services enable monitoring.googleapis.com logging.googleapis.com \
  cloudbilling.googleapis.com billingbudgets.googleapis.com >/dev/null

api_host() { gcloud run services describe "$1" --region="$REGION" \
  --format='value(status.url)' 2>/dev/null | sed -e 's|^https://||' -e 's|/$||'; }

API_HOST="$(api_host antarctica-api)"
SCAN_HOST="$(api_host antarctica-scanner)"
[[ -n "$API_HOST" ]] || { echo "antarctica-api not found in $REGION. Deploy first." >&2; exit 1; }

echo "   api:     $API_HOST"
echo "   scanner: ${SCAN_HOST:-<not deployed>}"

# ------------------------------------------------------------ notifications --
echo "== Notification channel for $ALERT_EMAIL"
CHANNEL="$(gcloud alpha monitoring channels list \
  --filter="type=email AND labels.email_address=${ALERT_EMAIL}" \
  --format='value(name)' 2>/dev/null | head -1)"
if [[ -z "$CHANNEL" ]]; then
  CHANNEL="$(gcloud alpha monitoring channels create \
    --display-name="sn0wy alerts" --type=email \
    --channel-labels="email_address=${ALERT_EMAIL}" \
    --format='value(name)')"
  echo "   created $CHANNEL"
  echo "   NOTE: check your inbox and confirm the address, or nothing will be delivered."
else
  echo "   (exists)"
fi

# --------------------------------------------------------------- uptime ------
# /health is deliberately the target: it answers without touching the database,
# so this check reports "the service is up", and the log-based alert below
# reports "the service is working". Two different questions, two signals.
make_uptime() {
  local name="$1" host="$2"
  [[ -n "$host" ]] || return 0
  if gcloud monitoring uptime list-configs \
       --filter="displayName='${name}'" --format='value(name)' 2>/dev/null | grep -q .; then
    echo "   (${name} exists)"
    return 0
  fi
  gcloud monitoring uptime create "$name" \
    --resource-type=uptime-url \
    --resource-labels="host=${host},project_id=${PROJECT_ID}" \
    --path=/health --port=443 --protocol=https \
    --period=1 --timeout=10 >/dev/null
  echo "   created ${name}"
}

echo "== Uptime checks (every minute, several regions)"
make_uptime "sn0wy api health" "$API_HOST"
make_uptime "sn0wy scanner health" "$SCAN_HOST"

# ---------------------------------------------------------------- alerting ---
# Written to a file because the condition is a nested structure that does not
# survive being typed as flags.
POLICY_UPTIME="$(mktemp)"
cat > "$POLICY_UPTIME" <<'JSON'
{
  "displayName": "sn0wy: a service is down",
  "combiner": "OR",
  "conditions": [{
    "displayName": "uptime check failing",
    "conditionThreshold": {
      "filter": "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND resource.type=\"uptime_url\"",
      "aggregations": [{
        "alignmentPeriod": "300s",
        "perSeriesAligner": "ALIGN_NEXT_OLDER",
        "crossSeriesReducer": "REDUCE_COUNT_FALSE",
        "groupByFields": ["resource.label.host"]
      }],
      "comparison": "COMPARISON_GT",
      "thresholdValue": 1,
      "duration": "300s",
      "trigger": { "count": 1 }
    }
  }],
  "notificationChannels": ["__CHANNEL__"],
  "alertStrategy": { "autoClose": "1800s" }
}
JSON

# Scans that start and never finish. This is the signal that was missing: the API
# stayed healthy the whole time, so nothing based on 5xx would have fired.
POLICY_SCAN="$(mktemp)"
cat > "$POLICY_SCAN" <<'JSON'
{
  "displayName": "sn0wy: scans are failing",
  "combiner": "OR",
  "conditions": [{
    "displayName": "scanner logging errors",
    "conditionMatchedLog": {
      "filter": "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"antarctica-scanner\" AND severity>=ERROR"
    }
  }],
  "notificationChannels": ["__CHANNEL__"],
  "alertStrategy": {
    "notificationRateLimit": { "period": "900s" },
    "autoClose": "1800s"
  }
}
JSON

# A quoted heredoc keeps the JSON escapes intact, so the channel goes in after.
for f in "$POLICY_UPTIME" "$POLICY_SCAN"; do
  sed -i.bak "s|__CHANNEL__|${CHANNEL}|" "$f" && rm -f "${f}.bak"
done

create_policy() {
  local file="$1" name="$2"
  if gcloud alpha monitoring policies list \
       --filter="displayName='${name}'" --format='value(name)' 2>/dev/null | grep -q .; then
    echo "   (${name} exists)"
    return 0
  fi
  gcloud alpha monitoring policies create --policy-from-file="$file" >/dev/null
  echo "   created ${name}"
}

echo "== Alert policies"
create_policy "$POLICY_UPTIME" "sn0wy: a service is down"
create_policy "$POLICY_SCAN" "sn0wy: scans are failing"
rm -f "$POLICY_UPTIME" "$POLICY_SCAN"

# ------------------------------------------------------------------ budget ---
echo "== Budget: \$${BUDGET_USD}/month with alerts at 50/90/100%"
BILLING_ACCOUNT="${BILLING_ACCOUNT:-$(gcloud billing projects describe "$PROJECT_ID" \
  --format='value(billingAccountName)' 2>/dev/null | sed 's|billingAccounts/||')}"
if [[ -z "$BILLING_ACCOUNT" ]]; then
  echo "   could not detect the billing account; set BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX" >&2
elif gcloud billing budgets list --billing-account="$BILLING_ACCOUNT" \
       --filter="displayName='sn0wy monthly'" --format='value(name)' 2>/dev/null | grep -q .; then
  echo "   (exists)"
else
  gcloud billing budgets create --billing-account="$BILLING_ACCOUNT" \
    --display-name="sn0wy monthly" \
    --budget-amount="${BUDGET_USD}USD" \
    --threshold-rule=percent=0.5 \
    --threshold-rule=percent=0.9 \
    --threshold-rule=percent=1.0 \
    --filter-projects="projects/$(gcloud projects describe "$PROJECT_ID" \
      --format='value(projectNumber)')" >/dev/null
  echo "   created"
fi

cat <<DONE

Done. What you now have:

  - /health on both services checked every minute from several regions
  - an email when either is down from more than one region for 5 minutes
  - an email when the scanner logs an error, rate-limited to one per 15 min
  - a \$${BUDGET_USD}/month budget alerting at 50%, 90% and 100%

Two things only you can do:
  1. Confirm the address in your inbox. An unconfirmed channel delivers nothing.
  2. Test it. Take the scanner down on purpose and wait for the email. An alert
     you have never seen arrive is not monitoring, it is an intention.
DONE
