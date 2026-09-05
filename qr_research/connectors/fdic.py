"""FDIC BankFind Suite connector.

Two datasets from https://api.fdic.gov/banks/ :
  institutions — every FDIC-insured institution ever, with HQ county (STCNTY) and
                 established/ended dates. Used for "banks headquartered here" over time.
  sod          — Summary of Deposits, June each year from 1994, one row per branch,
                 with deposits (thousands) and the holding company. Used for
                 "whose institutions hold our deposits" and "our share of US deposits".

Free, no key, documented at https://api.fdic.gov/banks/docs/
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import requests

from .base import COUNTY_FIPS, Connector, RawRecord, db, record_health

BASE = "https://api.fdic.gov/banks"
UA = {"User-Agent": f"qr-research (contact: {os.environ.get('CONTACT_EMAIL', 'unset')})"}

INST_FIELDS = "CERT,NAME,CITY,STALP,COUNTY,STCNTY,ACTIVE,ESTYMD,ENDEFYMD,BKCLASS,CHARTER,RSSDHCR,NAMEHCR,STALPHCR,CITYHCR"
SOD_FIELDS = "YEAR,CERT,BRNUM,NAMEFULL,STCNTYBR,DEPSUMBR,STCNTY,CITY,STALP,RSSDHCR,NAMEHCR,CITYHCR,STALPHCR,BKCLASS"

SOD_FIRST_YEAR = 1994


def _get(path: str, params: dict[str, Any], retries: int = 3) -> dict:
    for attempt in range(retries):
        r = requests.get(f"{BASE}/{path}", params={**params, "format": "json"}, headers=UA, timeout=60)
        if r.status_code == 200:
            return r.json()
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()
    return {}


def _page(path: str, filters: str, fields: str, limit: int = 10000) -> list[dict]:
    out, offset = [], 0
    while True:
        j = _get(path, {"filters": filters, "fields": fields, "limit": limit, "offset": offset})
        rows = [d["data"] for d in j.get("data", [])]
        out.extend(rows)
        if len(rows) < limit:
            break
        offset += limit
    return out


def county_filter(field: str) -> str:
    return f"{field}:({' OR '.join(COUNTY_FIPS)})"


class FDICConnector(Connector):
    source_id = "fdic"
    tier = 1
    cadence = "weekly"  # institutions change year-round; SOD lands annually (June data, published ~Oct)

    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        recs: list[RawRecord] = []

        # 1. Every institution ever headquartered in the five counties.
        inst = _page("institutions", county_filter("STCNTY"), INST_FIELDS)
        for row in inst:
            recs.append(RawRecord(self.source_id, f"inst:{row['CERT']}", row, url=f"{BASE}/institutions?filters=CERT:{row['CERT']}"))

        # 2. SOD branch rows in the five counties, all years.
        latest = self._latest_sod_year()
        for year in range(SOD_FIRST_YEAR, latest + 1):
            rows = _page("sod", f"{county_filter('STCNTYBR')} AND YEAR:{year}", SOD_FIELDS)
            for row in rows:
                recs.append(RawRecord(self.source_id, f"sod:{row['YEAR']}:{row['CERT']}:{row['BRNUM']}", row))

        # 3. National deposit totals by year (one aggregate row per year).
        for year in range(SOD_FIRST_YEAR, latest + 1):
            j = _get("sod", {"filters": f"YEAR:{year}", "agg_by": "YEAR", "agg_sum_fields": "DEPSUMBR"})
            tot = j.get("totals", {})
            recs.append(RawRecord(self.source_id, f"sod_us:{year}", {"YEAR": year, "US_DEPSUMBR": tot.get("sum_DEPSUMBR"), "US_BRANCHES": tot.get("count")}))
        return recs

    def _latest_sod_year(self) -> int:
        j = _get("sod", {"filters": "STCNTYBR:18141", "fields": "YEAR", "sort_by": "YEAR", "sort_order": "DESC", "limit": 1})
        return int(j["data"][0]["data"]["YEAR"])

    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        p = raw.payload
        if raw.key.startswith("inst:"):
            return [{
                "table": "fdic_institutions",
                "cert": p["CERT"], "name": p.get("NAME"), "city": p.get("CITY"), "state": p.get("STALP"),
                "hq_county_fips": str(p.get("STCNTY")), "active": int(p.get("ACTIVE") or 0),
                "established": _iso(p.get("ESTYMD")), "ended": _iso(p.get("ENDEFYMD")),
                "bkclass": p.get("BKCLASS"), "holding_co": p.get("NAMEHCR"), "holding_co_state": p.get("STALPHCR"),
            }]
        if raw.key.startswith("sod_us:"):
            return [{"table": "fdic_us_deposits", "year": p["YEAR"], "us_deposits_k": p["US_DEPSUMBR"], "us_branches": p["US_BRANCHES"]}]
        if raw.key.startswith("sod:"):
            return [{
                "table": "fdic_sod",
                "year": p["YEAR"], "cert": p["CERT"], "brnum": p["BRNUM"], "name": p.get("NAMEFULL"),
                "branch_county_fips": str(p.get("STCNTYBR")), "deposits_k": p.get("DEPSUMBR") or 0,
                "inst_hq_county_fips": str(p.get("STCNTY")), "inst_hq_state": p.get("STALP"),
                "holding_co_rssd": p.get("RSSDHCR"), "holding_co": p.get("NAMEHCR"),
                "holding_co_city": p.get("CITYHCR"), "holding_co_state": p.get("STALPHCR"), "bkclass": p.get("BKCLASS"),
            }]
        return []

    def expected_volume(self) -> tuple[int, int]:
        # ~150–250 institutions ever HQ'd here; ~150–250 branch rows/yr × ~31 yrs; 31 US rows
        return (4000, 10000)

    def run(self) -> dict:
        ok, note = True, ""
        try:
            recs = self.fetch()
        except Exception as e:  # noqa: BLE001
            recs, ok, note = [], False, repr(e)
        path = self.store_raw(recs) if recs else None
        if recs:
            load_normalized(self, recs)
        health = record_health(self.source_id, len(recs), self.expected_volume(), self.schema_hash(recs) if recs else "", ok, note)
        return {"source": self.source_id, "records": len(recs), "raw_path": str(path), "health": health, "note": note}


def _iso(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return s


DDL = {
    "fdic_institutions": """CREATE TABLE IF NOT EXISTS fdic_institutions (
        cert INTEGER PRIMARY KEY, name TEXT, city TEXT, state TEXT, hq_county_fips TEXT, active INTEGER,
        established TEXT, ended TEXT, bkclass TEXT, holding_co TEXT, holding_co_state TEXT)""",
    "fdic_sod": """CREATE TABLE IF NOT EXISTS fdic_sod (
        year INTEGER, cert INTEGER, brnum INTEGER, name TEXT, branch_county_fips TEXT, deposits_k INTEGER,
        inst_hq_county_fips TEXT, inst_hq_state TEXT, holding_co_rssd INTEGER, holding_co TEXT,
        holding_co_city TEXT, holding_co_state TEXT, bkclass TEXT, PRIMARY KEY (year, cert, brnum))""",
    "fdic_us_deposits": """CREATE TABLE IF NOT EXISTS fdic_us_deposits (
        year INTEGER PRIMARY KEY, us_deposits_k INTEGER, us_branches INTEGER)""",
}


def load_normalized(conn_obj: Connector, recs: list[RawRecord]) -> None:
    conn = db()
    for ddl in DDL.values():
        conn.execute(ddl)
    for r in recs:
        for row in conn_obj.normalize(r):
            table = row.pop("table")
            cols = ",".join(row)
            qs = ",".join("?" * len(row))
            conn.execute(f"REPLACE INTO {table} ({cols}) VALUES ({qs})", list(row.values()))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    print(FDICConnector().run())
