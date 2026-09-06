"""CourtListener RECAP connector — new business bankruptcy filings in the region.

Courts: innb (Bankr. N.D. Indiana), miwb (Bankr. W.D. Michigan) — both districts cover far
more counties than our five, so geography still needs narrowing the same way sec_form_d.py
does it: one full-text query per region city/ZIP (`/api/rest/v4/search/?type=r`), chapter and
"is this a business, not a person" filtered client-side.

Anonymous access only gets the search index, not a per-case debtor address — the `dockets`
and `parties` endpoints that would give one require an API key (confirmed: 401 without one).
So unlike sec_form_d.py, there is no authoritative per-filing address to re-verify a hit
against; county tagging here is text-search-derived, not address-verified, and every
candidate says so. A free CourtListener account would upgrade this — see QUESTIONS.md.

Chapter 13 is individual-only and is excluded outright. Chapters 7/11/12 can be either; a
case name matching organizational patterns (BUSINESS_RE, same as gateway.py) is required
before anything counts as a business filing — this is the hard "never individuals" rule.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .base import Connector, RawRecord, db, record_health
from .gateway import BUSINESS_RE
from .sec_form_d import MI_ZIP_COUNTY, _region_in_lists

UA = {"User-Agent": f"qr-research (contact: {os.environ.get('CONTACT_EMAIL', 'unset')})"}
SEARCH = "https://www.courtlistener.com/api/rest/v4/search/"
BACKFILL_DAYS = 365
COURTS = {"innb": "IN", "miwb": "MI"}
BUSINESS_CHAPTERS = {"7", "11", "12"}


def _get(params: dict) -> requests.Response:
    r = requests.get(SEARCH, headers=UA, params=params, timeout=60)
    time.sleep(0.5)  # polite; CourtListener has no published RECAP-search rate limit like SEC's
    return r


def _search(court: str, term: str, after: str, before: str) -> list[dict]:
    hits, page = [], 1
    while page <= 10:  # a single city/ZIP pulling >100 regional business filings in 12mo would be extraordinary
        r = _get({"type": "r", "court": court, "q": f'"{term}"', "filed_after": after, "filed_before": before, "page": page})
        if r.status_code != 200:
            break
        j = r.json()
        results = j.get("results", [])
        hits.extend(results)
        if not j.get("next"):
            break
        page += 1
    return hits


class BankruptcyConnector(Connector):
    source_id = "bankruptcy"
    tier = 1.5
    cadence = "daily"

    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=BACKFILL_DAYS)
        after, before = start.strftime("%m/%d/%Y"), end.strftime("%m/%d/%Y")

        in_cities, in_zip_county = _region_in_lists()
        in_terms = list(in_cities) + list(in_zip_county)
        mi_terms = list(MI_ZIP_COUNTY)

        recs: list[RawRecord] = []
        seen: set[int] = set()
        for court, terms in (("innb", in_terms), ("miwb", mi_terms)):
            for term in terms:
                for hit in _search(court, term, after, before):
                    docket_id = hit.get("docket_id")
                    if not docket_id or docket_id in seen:
                        continue
                    chapter = (hit.get("chapter") or "").strip()
                    case_name = hit.get("caseName") or ""
                    if chapter not in BUSINESS_CHAPTERS or not BUSINESS_RE.search(case_name):
                        continue
                    seen.add(docket_id)
                    county_fips = "" if court == "innb" else ",".join(MI_ZIP_COUNTY.get(term, ())) if term in MI_ZIP_COUNTY else ""
                    if court == "innb" and term in in_zip_county:
                        county_fips = in_zip_county[term]
                    recs.append(RawRecord(self.source_id, f"bk:{docket_id}", {
                        "docket_id": docket_id, "case_name": case_name, "chapter": chapter, "court_id": court,
                        "county_fips": county_fips, "date_filed": hit.get("dateFiled") or "",
                        "docket_number": hit.get("docketNumber") or "",
                    }, url=f"https://www.courtlistener.com{hit.get('docket_absolute_url', '')}"))
        return recs

    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        p = raw.payload
        return [{
            "table": "bankruptcy_filings", "docket_id": p["docket_id"], "case_name": p["case_name"], "chapter": p["chapter"],
            "court_id": p["court_id"], "county_fips": p["county_fips"], "date_filed": p["date_filed"],
            "docket_number": p["docket_number"], "url": raw.url,
        }]

    def expected_volume(self) -> tuple[int, int]:
        return (0, 50)  # business filings across five counties in 12 months should be a small count

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


DDL = """CREATE TABLE IF NOT EXISTS bankruptcy_filings (
    docket_id INTEGER PRIMARY KEY, case_name TEXT, chapter TEXT, court_id TEXT, county_fips TEXT,
    date_filed TEXT, docket_number TEXT, url TEXT)"""


def load(c: Connector, recs: list[RawRecord]) -> None:
    conn = db(); conn.execute(DDL)
    cols = "docket_id,case_name,chapter,court_id,county_fips,date_filed,docket_number,url"
    for r in recs:
        for row in c.normalize(r):
            row.pop("table")
            conn.execute(f"REPLACE INTO bankruptcy_filings ({cols}) VALUES ({','.join('?' * 8)})", list(row.values()))
    conn.commit(); conn.close()


if __name__ == "__main__":
    print(BankruptcyConnector().run())
