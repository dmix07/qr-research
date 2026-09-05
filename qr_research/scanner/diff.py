"""Generic Scanner change detection: diff this run's raw snapshot against the previous one.

Works for every connector without source-specific code: keys that appeared, keys that
disappeared, and keys whose payload changed. Writes change rows to `changes`; source-specific
draft modules turn them into candidates with rubric context.
"""
from __future__ import annotations

import json
from pathlib import Path

from qr_research.connectors.base import RAW_DIR, db

DDL = """CREATE TABLE IF NOT EXISTS changes (source_id TEXT, key TEXT, change TEXT, seen_at TEXT, before TEXT, after TEXT, PRIMARY KEY (source_id, key, seen_at))"""


def _snapshots(source_id: str) -> list[Path]:
    return sorted((RAW_DIR / source_id).glob("*/*.jsonl")) if (RAW_DIR / source_id).exists() else []


def _load(p: Path) -> dict[str, dict]:
    out = {}
    with p.open() as f:
        for line in f:
            r = json.loads(line); out[r["key"]] = r["payload"]
    return out


def detect_changes(source_id: str) -> dict:
    snaps = _snapshots(source_id)
    if len(snaps) < 2:
        return {"status": "first_run", "changes": 0}
    prev, cur = _load(snaps[-2]), _load(snaps[-1])
    conn = db(); conn.execute(DDL)
    seen = cur and snaps[-1].stem
    n = 0
    for k in cur.keys() - prev.keys():
        conn.execute("INSERT OR IGNORE INTO changes VALUES (?,?,?,?,?,?)", (source_id, k, "added", seen, None, json.dumps(cur[k]))); n += 1
    for k in prev.keys() - cur.keys():
        conn.execute("INSERT OR IGNORE INTO changes VALUES (?,?,?,?,?,?)", (source_id, k, "removed", seen, json.dumps(prev[k]), None)); n += 1
    for k in cur.keys() & prev.keys():
        if cur[k] != prev[k]:
            conn.execute("INSERT OR IGNORE INTO changes VALUES (?,?,?,?,?,?)", (source_id, k, "modified", seen, json.dumps(prev[k]), json.dumps(cur[k]))); n += 1
    conn.commit(); conn.close()
    return {"status": "diffed", "changes": n, "prev": snaps[-2].name, "cur": snaps[-1].name}
