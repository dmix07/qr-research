"""SEC EDGAR Form D connector — regional private securities offerings.

National Form D volume (hundreds/day) is too high to scan via the daily index, so discovery
uses EDGAR's full-text search (efts.sec.gov) instead: one query per region city/ZIP, form
type D, over the backfill window. Full-text search only narrows candidates — it matches
anywhere in the filing, including a related person's home address, not just the issuer's own
(confirmed live: a Southfield, MI company surfaced because a director lives in Harbert, MI).
So every hit is re-verified against the filing's own primary_doc.xml `primaryIssuer/
issuerAddress` — the only field that actually answers "is the issuer regional." Free, no key.

Region definition: Indiana cities/ZIPs come from `gateway_parcels` (already fetched by
in_gateway_parcels); Michigan ZIPs (Berrien 26021, Cass 26027) are hardcoded from the Census
Bureau's 2020 ZCTA-to-county relationship file (tab20_zcta520_county20_natl.txt) since no
Michigan parcel source exists yet to derive them from.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree

import requests

from .base import Connector, RawRecord, db, record_health

UA = {"User-Agent": f"qr-research (contact: {os.environ.get('CONTACT_EMAIL', 'unset')})"}
EFTS = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
BACKFILL_DAYS = 730  # ~24 months

# zip -> county FIPS (Berrien 26021, Cass 26027); some ZCTAs straddle both, hence tuples.
MI_ZIP_COUNTY: dict[str, tuple[str, ...]] = {
    "49022": ("26021",), "49038": ("26021",), "49084": ("26021",), "49085": ("26021",),
    "49098": ("26021",), "49101": ("26021",), "49103": ("26021",), "49104": ("26021",),
    "49106": ("26021",), "49107": ("26021",), "49113": ("26021",), "49115": ("26021",),
    "49116": ("26021",), "49117": ("26021",), "49119": ("26021",), "49125": ("26021",),
    "49126": ("26021",), "49127": ("26021",), "49128": ("26021",), "49129": ("26021",),
    "49031": ("26027",), "49042": ("26027",), "49045": ("26027",), "49061": ("26027",),
    "49067": ("26027",), "49093": ("26027",), "49095": ("26027",), "49099": ("26027",),
    "49112": ("26027",), "49130": ("26027",),
    "49047": ("26021", "26027"), "49102": ("26021", "26027"), "49111": ("26021", "26027"), "49120": ("26021", "26027"),
}
MI_ZIPS = set(MI_ZIP_COUNTY)


def _region_in_lists() -> tuple[set[str], dict[str, str]]:
    """IN cities and a ZIP -> county_fips map for the three counties, from Gateway parcel
    data already on hand (ZIP is more precise than city for county assignment)."""
    conn = db()
    try:
        cities = {r[0].upper() for r in conn.execute("SELECT DISTINCT prop_city FROM gateway_parcels WHERE prop_city != ''").fetchall()}
        zip_county = {r[0]: r[1] for r in conn.execute(
            "SELECT prop_zip5, county_fips FROM gateway_parcels WHERE prop_zip5 != '' GROUP BY prop_zip5").fetchall()}
    except Exception:
        cities, zip_county = set(), {}
    finally:
        conn.close()
    return cities, zip_county


def _get(url: str, params: dict | None = None) -> requests.Response:
    r = requests.get(url, headers=UA, params=params, timeout=60)
    time.sleep(0.34)  # ~3 req/s, well under SEC's stated 10 req/s cap
    return r


def _search(term: str, start_date: str, end_date: str) -> list[dict]:
    hits, frm = [], 0
    while frm < 100:  # a single city/ZIP pulling >100 regional Form Ds in 24mo would be extraordinary
        r = _get(EFTS, {"q": f'"{term}"', "forms": "D", "startdt": start_date, "enddt": end_date, "from": frm})
        if r.status_code != 200:
            break
        page = r.json().get("hits", {}).get("hits", [])
        hits.extend(page)
        if len(page) < 10:
            break
        frm += 10
    return hits


def _issuer_address(cik: str, accession: str) -> dict | None:
    """Fetch primary_doc.xml and return the issuer's own address fields — ground truth,
    unlike full-text search which matches anywhere in the document."""
    acc_nodash = accession.replace("-", "")
    r = _get(f"{ARCHIVES}/{int(cik)}/{acc_nodash}/primary_doc.xml")
    if r.status_code != 200:
        return None
    try:
        root = ElementTree.fromstring(r.content)
    except ElementTree.ParseError:
        return None
    addr = root.find(".//primaryIssuer/issuerAddress")
    if addr is None:
        return None
    def text(tag):
        el = addr.find(tag)
        return (el.text or "").strip() if el is not None else ""
    return {"city": text("city").upper(), "state": text("stateOrCountry"), "zip5": text("zipCode")[:5]}


class SECFormDConnector(Connector):
    source_id = "sec_form_d"
    tier = 1
    cadence = "daily"

    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=BACKFILL_DAYS)
        in_cities, in_zip_county = _region_in_lists()
        in_zips = set(in_zip_county)
        region_zips = in_zips | MI_ZIPS
        terms = list(in_cities) + list(in_zips) + list(MI_ZIPS)

        candidates: dict[str, dict] = {}
        for term in terms:
            for hit in _search(term, start.isoformat(), end.isoformat()):
                src = hit.get("_source", {})
                acc = src.get("adsh") or hit["_id"].split(":")[0]
                if acc in candidates:
                    continue
                candidates[acc] = {"cik": (src.get("ciks") or [""])[0], "issuer_name": (src.get("display_names") or [""])[0],
                                    "file_date": src.get("file_date", ""), "items": ",".join(src.get("items") or [])}

        recs: list[RawRecord] = []
        for acc, meta in candidates.items():
            addr = _issuer_address(meta["cik"], acc)
            if not addr or addr["state"] not in ("IN", "MI"):
                continue
            if addr["city"] not in in_cities and addr["zip5"] not in region_zips:
                continue  # issuer's own address isn't actually regional (see module docstring)
            if addr["state"] == "IN":
                county_fips = in_zip_county.get(addr["zip5"], "")
            else:
                county_fips = ",".join(MI_ZIP_COUNTY.get(addr["zip5"], ()))
            recs.append(RawRecord(self.source_id, f"formd:{acc}", {**meta, **addr, "county_fips": county_fips},
                url=f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={meta['cik']}&type=D"))
        return recs

    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        p = raw.payload
        return [{
            "table": "sec_form_d", "accession": raw.key.split(":", 1)[1], "cik": p["cik"], "issuer_name": p["issuer_name"],
            "state": p["state"], "city": p["city"], "zip5": p["zip5"], "county_fips": p.get("county_fips", ""),
            "file_date": p["file_date"], "items": p["items"],
        }]

    def expected_volume(self) -> tuple[int, int]:
        return (0, 60)  # rare by design ("every one surfaces") — zero hits in a run is not a failure here

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


DDL = """CREATE TABLE IF NOT EXISTS sec_form_d (
    accession TEXT PRIMARY KEY, cik TEXT, issuer_name TEXT, state TEXT, city TEXT, zip5 TEXT,
    county_fips TEXT, file_date TEXT, items TEXT)"""


def load(c: Connector, recs: list[RawRecord]) -> None:
    conn = db(); conn.execute(DDL)
    cols = "accession,cik,issuer_name,state,city,zip5,county_fips,file_date,items"
    for r in recs:
        for row in c.normalize(r):
            row.pop("table")
            conn.execute(f"REPLACE INTO sec_form_d ({cols}) VALUES ({','.join('?' * 9)})", list(row.values()))
    conn.commit(); conn.close()


if __name__ == "__main__":
    print(SECFormDConnector().run())
