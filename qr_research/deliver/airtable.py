"""Deliver candidates to Airtable (one-way) — or to CSV when no token is configured.

Env: AIRTABLE_TOKEN (scopes: data.records:read/write, schema.bases:read/write),
     AIRTABLE_BASE_ID (optional; created on first run if blank and AIRTABLE_WORKSPACE_ID is set).
"""
from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import requests

SCHEMA = json.load(open(Path(__file__).resolve().parents[2] / "candidate_schema.json"))
API = "https://api.airtable.com/v0"
LIST_FIELDS = {"counties", "axis_a", "axis_b", "function", "evidence_urls", "recipe_ids"}
TEXT_LIST_FIELDS = {"evidence_urls", "recipe_ids"}  # stored as newline text in Airtable


def _h() -> dict:
    tok = os.environ.get("AIRTABLE_TOKEN")
    if not tok:
        raise RuntimeError("AIRTABLE_TOKEN not set")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _airtable_field(f: dict) -> dict | None:
    t = f["type"]
    if t in ("singleLineText", "multilineText", "dateTime", "number"):
        out = {"name": f["name"], "type": t}
        if t == "dateTime":
            out["options"] = {"dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}, "timeZone": "America/Indiana/Indianapolis"}
        if t == "number":
            out["options"] = {"precision": 0}
        return out
    if t in ("singleSelect", "multipleSelects"):
        return {"name": f["name"], "type": t, "options": {"choices": [{"name": o} for o in f["options"]]}}
    return None  # linked records added after tables exist


def create_base(workspace_id: str) -> str:
    tables = []
    for tname, tdef in SCHEMA["tables"].items():
        fields = [af for f in tdef["fields"] if (af := _airtable_field(f))]
        tables.append({"name": tname, "fields": fields})
    r = requests.post(f"{API}/meta/bases", headers=_h(), json={"name": SCHEMA["base_name"], "workspaceId": workspace_id, "tables": tables}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def to_fields(c: dict) -> dict:
    keep = {f["name"] for f in SCHEMA["tables"]["candidates"]["fields"]} - {"entity", "related_candidates"}
    out = {}
    for k, v in c.items():
        if k not in keep or v in (None, "", []):
            continue
        if k in TEXT_LIST_FIELDS:
            out[k] = "\n".join(v)
        else:
            out[k] = v
    return out


def upsert(base_id: str, candidates: list[dict], table: str = "candidates") -> int:
    n = 0
    for i in range(0, len(candidates), 10):
        batch = [{"fields": to_fields(c)} for c in candidates[i:i + 10]]
        r = requests.patch(f"{API}/{base_id}/{table}", headers=_h(), json={"performUpsert": {"fieldsToMergeOn": ["candidate_id"]}, "records": batch, "typecast": True}, timeout=60)
        if r.status_code >= 400:
            print(r.text, file=sys.stderr)
        r.raise_for_status()
        n += len(batch)
    return n


def to_csv(candidates: list[dict], path: str) -> str:
    cols = [f["name"] for f in SCHEMA["tables"]["candidates"]["fields"] if f["name"] not in ("entity", "related_candidates")]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for c in candidates:
            row = dict(c)
            for k in LIST_FIELDS:
                if isinstance(row.get(k), list):
                    row[k] = "\n".join(row[k]) if k in TEXT_LIST_FIELDS else ", ".join(row[k])
            w.writerow(row)
    return path


def deliver(candidates: list[dict]) -> str:
    if not os.environ.get("AIRTABLE_TOKEN"):
        p = to_csv(candidates, "examples/candidates_for_airtable.csv")
        return f"no AIRTABLE_TOKEN — wrote {len(candidates)} candidates to {p} (import into Airtable manually)"
    base = os.environ.get("AIRTABLE_BASE_ID", "appBVtPxGG9DJpnxL") or create_base(os.environ["AIRTABLE_WORKSPACE_ID"])
    n = upsert(base, candidates)
    return f"upserted {n} candidates to Airtable base {base}"


if __name__ == "__main__":
    cands = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "examples/fdic_candidates.json"))
    print(deliver(cands))
