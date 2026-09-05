#!/usr/bin/env bash
# Runs after every service run. If the run failed (health != ok or any step errored), email Dustin.
# Uses ALERT_EMAIL + a local sendmail, or ALERT_WEBHOOK_URL if set. Silent on success by design.
set -u
[ "${SERVICE_RESULT:-}" = "success" ] && exit 0
MSG="qr-research run failed on $(hostname) at $(date -Is). Result: ${SERVICE_RESULT:-unknown}. Last log lines:
$(journalctl -u qr-research -n 30 --no-pager 2>/dev/null)"
if [ -n "${ALERT_WEBHOOK_URL:-}" ]; then
  curl -sS -X POST -H 'Content-Type: application/json' -d "$(python3 -c 'import json,sys;print(json.dumps({"text":sys.stdin.read()}))' <<<"$MSG")" "$ALERT_WEBHOOK_URL" || true
fi
if [ -n "${ALERT_EMAIL:-}" ] && command -v sendmail >/dev/null; then
  printf 'Subject: [qr-research] feed run failed\n\n%s\n' "$MSG" | sendmail "$ALERT_EMAIL" || true
fi
