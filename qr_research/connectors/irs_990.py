"""IRS 990 connector — nonprofits in the five counties, year-over-year asset change.

Two steps, both free/no key:
  1. IRS's own bulk Exempt Organization Business Master File, one CSV per state
     (irs.gov/pub/irs-soi/eo_<st>.csv) — stream-filtered to the region's ZIPs (same region
     definition as sec_form_d.py: IN ZIPs from gateway_parcels, MI ZIPs hardcoded from the
     Census ZCTA-county crosswalk). This is the discovery step; ProPublica's own search API
     has no city/ZIP filter (confirmed live: `city=` is silently ignored, and a full-text `q=`
     match on org name misses/over-matches — the same problem sec_form_d.py solved differently).
  2. ProPublica's Nonprofit Explorer per-organization API (one call per matched EIN — a small,
     already-regional list, not all 44k+ Indiana filers) for the filing history needed to
     compute year-over-year change in total assets.

Grants paid isn't computed: that field only exists on Form 990-PF (private foundations);
most filers here use Form 990/990-EZ, which don't report it in a common field. Total assets
(the brief's other named metric) is universal across filing types, so that's what's used.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Any

import requests

from .base import Connector, RawRecord, db, record_health
from .gateway import norm_name
from .sec_form_d import MI_ZIP_COUNTY, _region_in_lists

UA = {"User-Agent": f"qr-research (contact: {os.environ.get('CONTACT_EMAIL', 'unset')})"}
EO_BMF = "https://www.irs.gov/pub/irs-soi/eo_{st}.csv"
PP_ORG = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
CHANGE_THRESHOLD = 0.25


def _region_zip_county() -> dict[str, str]:
    _, in_zip_county = _region_in_lists()
    out = dict(in_zip_county)
    for z, fips in MI_ZIP_COUNTY.items():
        out[z] = fips[0]  # first county when a ZCTA straddles both
    return out


def _stream_state_csv(state_abbr: str, region_zips: dict[str, str]) -> list[dict]:
    """Stream the state's EO bulk file line-by-line; never materialize the whole CSV."""
    r = requests.get(EO_BMF.format(st=state_abbr.lower()), headers=UA, timeout=180, stream=True)
    r.raise_for_status()
    matches = []
    for row in csv.DictReader(_lines(r)):
        zip5 = (row.get("ZIP") or "")[:5]
        if zip5 in region_zips:
            row["_county_fips"] = region_zips[zip5]
            matches.append(row)
    return matches


def _lines(r: requests.Response):
    for raw in r.iter_lines(decode_unicode=True):
        if raw:
            yield raw


def _latest_two_years(ein: str) -> tuple[dict, dict] | None:
    r = requests.get(PP_ORG.format(ein=int(ein)), headers=UA, timeout=60)
    if r.status_code != 200:
        return None
    filings = sorted(r.json().get("filings_with_data", []), key=lambda f: f.get("tax_prd_yr") or 0, reverse=True)
    if len(filings) < 1:
        return None
    return filings[0], (filings[1] if len(filings) > 1 else None)


class IRS990Connector(Connector):
    source_id = "irs_990"
    tier = 1
    cadence = "annual"

    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        region_zips = _region_zip_county()
        recs: list[RawRecord] = []
        for state_abbr in ("IN", "MI"):
            for row in _stream_state_csv(state_abbr, region_zips):
                ein = row["EIN"].lstrip("0") or "0"
                latest_pair = _latest_two_years(ein)
                latest, prior = (latest_pair or (None, None))
                pct_change = None
                if latest and prior and prior.get("totassetsend"):
                    pct_change = (latest.get("totassetsend", 0) - prior["totassetsend"]) / prior["totassetsend"]
                recs.append(RawRecord(self.source_id, f"990:{ein}", {
                    "ein": ein, "name": row["NAME"].strip(), "city": row["CITY"].strip(), "zip5": row["ZIP"][:5],
                    "county_fips": row["_county_fips"], "ntee_code": row.get("NTEE_CD") or "",
                    "latest_year": (latest or {}).get("tax_prd_yr"), "latest_assets": (latest or {}).get("totassetsend"),
                    "prior_year": (prior or {}).get("tax_prd_yr"), "prior_assets": (prior or {}).get("totassetsend"),
                    "pct_change": pct_change,
                }, url=f"https://projects.propublica.org/nonprofits/organizations/{ein}"))
        return recs

    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        p = raw.payload
        return [{
            "table": "irs_990", "ein": p["ein"], "name": p["name"], "city": p["city"], "zip5": p["zip5"],
            "county_fips": p["county_fips"], "ntee_code": p["ntee_code"], "latest_year": p["latest_year"],
            "latest_assets": p["latest_assets"], "prior_year": p["prior_year"], "prior_assets": p["prior_assets"],
            "pct_change": p["pct_change"],
        }]

    def expected_volume(self) -> tuple[int, int]:
        return (20, 4000)  # a real run against Berrien+Cass alone (no IN data on this laptop)
        # already returned 1282; widened with headroom for the three IN counties on the server

    def run(self) -> dict:
        ok, note = True, ""
        try:
            recs = self.fetch()
        except Exception as e:  # noqa: BLE001
            recs, ok, note = [], False, repr(e)
        path = self.store_raw(recs) if recs else None
        if recs:
            load(self, recs)
            build_nonprofit_entities()
        health = record_health(self.source_id, len(recs), self.expected_volume(), self.schema_hash(recs) if recs else "", ok, note)
        return {"source": self.source_id, "records": len(recs), "raw_path": str(path), "health": health, "note": note}


DDL = """CREATE TABLE IF NOT EXISTS irs_990 (
    ein TEXT PRIMARY KEY, name TEXT, city TEXT, zip5 TEXT, county_fips TEXT, ntee_code TEXT,
    latest_year INTEGER, latest_assets REAL, prior_year INTEGER, prior_assets REAL, pct_change REAL)"""


def load(c: Connector, recs: list[RawRecord]) -> None:
    conn = db(); conn.execute(DDL)
    cols = "ein,name,city,zip5,county_fips,ntee_code,latest_year,latest_assets,prior_year,prior_assets,pct_change"
    for r in recs:
        for row in c.normalize(r):
            row.pop("table")
            conn.execute(f"REPLACE INTO irs_990 ({cols}) VALUES ({','.join('?' * 11)})", list(row.values()))
    conn.commit(); conn.close()


def build_nonprofit_entities() -> int:
    conn = db(); conn.execute("""CREATE TABLE IF NOT EXISTS entities (
        entity_id TEXT PRIMARY KEY, name TEXT, name_norm TEXT, entity_type TEXT, county_fips TEXT,
        owner_state TEXT, owner_city TEXT, first_seen TEXT, source TEXT, parcels INTEGER, av_total INTEGER)""")
    rows = conn.execute("SELECT ein, name, city, county_fips FROM irs_990").fetchall()
    n = 0
    for ein, name, city, fips in rows:
        nn = norm_name(name)
        if not nn:
            continue
        eid = f"990:{ein}"
        conn.execute("""INSERT OR REPLACE INTO entities (entity_id, name, name_norm, entity_type, county_fips, owner_city, source)
            VALUES (?,?,?,?,?,?,?)""", (eid, name, nn, "nonprofit", fips, city, "irs_990"))
        n += 1
    conn.commit(); conn.close()
    return n


if __name__ == "__main__":
    print(IRS990Connector().run())
