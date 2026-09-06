"""USASpending.gov connector — federal grants/loans/contracts by place of performance,
five counties, above a $250k floor (a per-source volume floor Dustin chose to keep this
source's volume sane; recorded here and in DECISIONS.md).

Free, no key: https://api.usaspending.gov/api/v2/search/spending_by_award/. The API rejects
mixed award-type groups in one call (confirmed live: 422 "must only contain types from one
group"), so each county is queried once per group (grants, loans, contracts).

`time_period` filters on award *activity* (any transaction, including modifications to old
awards), not the award's own start date — confirmed live: a 2004 grant surfaced under a
2024-2026 time_period filter because of continued funding activity. So every hit is also
checked client-side against its own Period of Performance Start Date before counting as a
"new award" for this backfill window.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .base import COUNTIES, COUNTY_FIPS, Connector, RawRecord, db, record_health

UA = {"User-Agent": f"qr-research (contact: {os.environ.get('CONTACT_EMAIL', 'unset')})"}
SEARCH = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
BACKFILL_DAYS = 730  # ~24 months
AMOUNT_FLOOR = 250_000
STATE_ABBR = {"18": "IN", "26": "MI"}
AWARD_GROUPS = {"grants": ["02", "03", "04", "05"], "loans": ["07", "08"], "contracts": ["A", "B", "C", "D"]}
FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Award Type", "Start Date", "Description"]


def _get(fips: str, group: str, type_codes: list[str], start: str, end: str) -> list[dict]:
    state, county = STATE_ABBR[fips[:2]], fips[2:]
    hits, page = [], 1
    while page <= 20:  # 2,000 awards per county/group over 24mo would be extraordinary at this floor
        body = {
            "filters": {
                "award_type_codes": type_codes,
                "time_period": [{"start_date": start, "end_date": end}],
                "place_of_performance_locations": [{"country": "USA", "state": state, "county": county}],
                "award_amounts": [{"lower_bound": AMOUNT_FLOOR}],
            },
            "fields": FIELDS, "page": page, "limit": 100, "sort": "Start Date", "order": "desc",
        }
        r = requests.post(SEARCH, headers={**UA, "Content-Type": "application/json"}, json=body, timeout=60)
        time.sleep(0.2)
        if r.status_code != 200:
            break
        j = r.json()
        results = j.get("results", [])
        for row in results:
            row["_group"] = group
            row["_county_fips"] = fips
        hits.extend(results)
        if len(results) < 100:
            break
        page += 1
    return hits


class USASpendingConnector(Connector):
    source_id = "usaspending"
    tier = 1
    cadence = "monthly"

    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=BACKFILL_DAYS)
        start_s, end_s = start.isoformat(), end.isoformat()

        recs: list[RawRecord] = []
        for fips in COUNTY_FIPS:
            for group, codes in AWARD_GROUPS.items():
                for row in _get(fips, group, codes, start_s, end_s):
                    award_start = row.get("Start Date") or ""
                    if award_start and award_start < start_s:
                        continue  # activity in-window, but the award itself predates the backfill — not "new"
                    aid = row.get("Award ID") or ""
                    key = f"award:{row['_county_fips']}:{row['_group']}:{aid}"
                    recs.append(RawRecord(self.source_id, key, row,
                        url=f"https://www.usaspending.gov/award/{row.get('generated_internal_id', '')}"))
        return recs

    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        p = raw.payload
        return [{
            "table": "usaspending_awards", "key": raw.key, "award_id": p.get("Award ID", ""),
            "recipient_name": p.get("Recipient Name", ""), "amount": p.get("Award Amount"),
            "awarding_agency": p.get("Awarding Agency", ""), "award_type": p.get("Award Type", ""),
            "start_date": p.get("Start Date", ""), "description": (p.get("Description") or "")[:500],
            "county_fips": p["_county_fips"], "award_group": p["_group"], "url": raw.url,
        }]

    def expected_volume(self) -> tuple[int, int]:
        return (0, 1200)  # widened after a real first run returned 669 (AM General, Notre Dame, MDOT formula
        # grants, Honeywell all clear $250k here) — the original 500 ceiling was a guess made before any data existed

    def run(self) -> dict:
        ok, note = True, ""
        try:
            recs = self.fetch()
        except Exception as e:  # noqa: BLE001
            recs, ok, note = [], False, repr(e)
        path = self.store_raw(recs) if recs else None
        if recs:
            load(self, recs)
        health = record_health(self.source_id, len(recs), self.expected_volume(), self.schema_hash(recs) if recs else "", ok, note)
        return {"source": self.source_id, "records": len(recs), "raw_path": str(path), "health": health, "note": note}


DDL = """CREATE TABLE IF NOT EXISTS usaspending_awards (
    key TEXT PRIMARY KEY, award_id TEXT, recipient_name TEXT, amount REAL, awarding_agency TEXT,
    award_type TEXT, start_date TEXT, description TEXT, county_fips TEXT, award_group TEXT, url TEXT)"""


def load(c: Connector, recs: list[RawRecord]) -> None:
    conn = db(); conn.execute(DDL)
    cols = "key,award_id,recipient_name,amount,awarding_agency,award_type,start_date,description,county_fips,award_group,url"
    for r in recs:
        for row in c.normalize(r):
            row.pop("table")
            conn.execute(f"REPLACE INTO usaspending_awards ({cols}) VALUES ({','.join('?' * 11)})", list(row.values()))
    conn.commit(); conn.close()


if __name__ == "__main__":
    print(USASpendingConnector().run())
