"""Connector interface shared by every source.

A connector does three things and nothing else: fetch raw records from one public
source, store them immutably, and normalize them into typed rows. Screening and
delivery live elsewhere.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("QR_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "qr_research.sqlite"

COUNTIES = {
    "18141": "St. Joseph IN",
    "18039": "Elkhart IN",
    "18099": "Marshall IN",
    "26021": "Berrien MI",
    "26027": "Cass MI",
}
COUNTY_FIPS = list(COUNTIES)


@dataclass
class RawRecord:
    source_id: str
    key: str
    payload: dict[str, Any]
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    url: str = ""


class Connector:
    source_id: str = "base"
    tier: int = 1
    cadence: str = "weekly"
    counties: list[str] = COUNTY_FIPS

    # --- to implement -------------------------------------------------
    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        raise NotImplementedError

    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        raise NotImplementedError

    def expected_volume(self) -> tuple[int, int]:
        raise NotImplementedError

    # --- shared -------------------------------------------------------
    def store_raw(self, records: Iterable[RawRecord]) -> Path:
        """Write one JSONL file per run under data/raw/<source>/<date>/. Immutable."""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_dir = RAW_DIR / self.source_id / day
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%H%M%S")
        path = out_dir / f"{self.source_id}_{stamp}.jsonl"
        n = 0
        with path.open("w") as f:
            for r in records:
                f.write(json.dumps(r.__dict__, default=str) + "\n")
                n += 1
        return path

    def schema_hash(self, records: list[RawRecord]) -> str:
        keys = sorted({k for r in records[:200] for k in r.payload})
        return hashlib.sha1(",".join(keys).encode()).hexdigest()[:12]


def db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS source_health (
            source_id TEXT PRIMARY KEY, last_success TEXT, last_volume INTEGER,
            expected_min INTEGER, expected_max INTEGER, schema_hash TEXT, health TEXT, note TEXT)"""
    )
    return conn


def record_health(source_id: str, volume: int, expected: tuple[int, int], schema: str, ok: bool, note: str = "") -> str:
    lo, hi = expected
    if not ok:
        health = "error"
    elif volume < lo or volume > hi:
        health = "volume_out_of_band"
    else:
        health = "ok"
    conn = db()
    prev = conn.execute("SELECT schema_hash FROM source_health WHERE source_id=?", (source_id,)).fetchone()
    if prev and prev[0] and prev[0] != schema and health == "ok":
        health = "schema_drift"
    conn.execute(
        "REPLACE INTO source_health VALUES (?,?,?,?,?,?,?,?)",
        (source_id, datetime.now(timezone.utc).isoformat(), volume, lo, hi, schema, health, note),
    )
    conn.commit()
    conn.close()
    return health
