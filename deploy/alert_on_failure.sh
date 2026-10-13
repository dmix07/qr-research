#!/usr/bin/env bash
# Runs after every service run. Always pushes health to the Airtable `sources` table; the
# "Source health alert" automation there emails Dustin when any row (incl. pipeline_run) leaves ok.
# ALERT_WEBHOOK_URL / ALERT_EMAIL+sendmail are optional extra channels on failure.
set -u
cd /opt/qr-research
journalctl -u qr-research -n 30 --no-pager 2>/dev/null | .venv/bin/python -m qr_research.deliver.health_to_airtable "${SERVICE_RESULT:-unknown}" || echo "health push to Airtable failed" >&2
[ "${SERVICE_RESULT:-}" = "success" ] && exit 0
MSG="qr-research run failed on $(hostname) at $(date -Is). Result: ${SERVICE_RESULT:-unknown}. Last log lines:
$(journalctl -u qr-research -n 30 --no-pager 2>/dev/null)"
if [ -n "${ALERT_WEBHOOK_URL:-}" ]; then
  curl -sS -X POST -H 'Content-Type: application/json' -d "$(python3 -c 'import json,sys;print(json.dumps({"text":sys.stdin.read()}))' <<<"$MSG")" "$ALERT_WEBHOOK_URL" || true
fi
if [ -n "${ALERT_EMAIL:-}" ] && command -v sendmail >/dev/null; then
  printf 'Subject: [qr-research] feed run failed\n\n%s\n' "$MSG" | sendmail "$ALERT_EMAIL" || true
fi
