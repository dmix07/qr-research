"""Push source health, plus one row for the whole run, to the Airtable `sources` table.

The "Source health alert" automation in Airtable emails Dustin whenever a row there leaves `ok`,
so this is the failure alert. Called by deploy/alert_on_failure.sh after every run, with
systemd's $SERVICE_RESULT ("success" or a failure reason).

`python -m qr_research.deliver.health_to_airtable success`
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import requests

from qr_research.connectors.base import db
from qr_research.deliver.airtable import API, _h

RUN_ROW = "pipeline_run"


def rows(service_result: str, log_tail: str = "") -> list[dict]:
    out = []
    for sid, last, vol, lo, hi, schema, health, note in db().execute(
        "SELECT source_id, last_success, last_volume, expected_min, expected_max, schema_hash, health, note FROM source_health"
    ):
        out.append({"source_id": sid, "last_success": last, "last_volume": vol, "expected_min": lo, "expected_max": hi,
                    "schema_hash": schema, "health": health, "note": note or ""})
    ok = service_result == "success"
    out.append({"source_id": RUN_ROW, "last_success": datetime.now(timezone.utc).isoformat() if ok else None,
                "health": "ok" if ok else "error",
                "note": "" if ok else f"Weekly run failed ({service_result}). Last log lines:\n{log_tail}"[-20_000:]})
    return out


def push(records: list[dict]) -> int:
    base = os.environ.get("AIRTABLE_BASE_ID", "appBVtPxGG9DJpnxL")
    for i in range(0, len(records), 10):
        batch = [{"fields": {k: v for k, v in r.items() if v is not None}} for r in records[i:i + 10]]
        r = requests.patch(f"{API}/{base}/sources", headers=_h(), timeout=60,
                           json={"performUpsert": {"fieldsToMergeOn": ["source_id"]}, "records": batch, "typecast": True})
        if r.status_code >= 400:
            print(r.text, file=sys.stderr)
        r.raise_for_status()
    return len(records)


if __name__ == "__main__":
    result = sys.argv[1] if len(sys.argv) > 1 else "success"
    print(f"pushed {push(rows(result, sys.stdin.read() if not sys.stdin.isatty() else ''))} health rows to Airtable")
