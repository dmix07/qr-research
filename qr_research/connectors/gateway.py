"""Indiana Gateway (DLGF) connector — Real Property PARCEL files.

Source: https://gateway.ifionline.org/public/download.aspx (ASP.NET form; Tier 2).
Layout: 50 IAC 26-20-4(b), positional. https://regulations.justia.com/states/indiana/title-50/article-26/rule-20/section-4
Covers the three Indiana counties only (St. Joseph 71, Elkhart 20, Marshall 50). Michigan parcels
come from BS&A county portals — separate connector, terms permitting.

This is the source behind Observation #006 and the first entity-level source in the system:
owner names that are businesses/trusts/institutions are extracted into the `entities` table.
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from datetime import datetime
from typing import Any, Iterator

import requests

from .base import Connector, RawRecord, db, record_health

URL = "https://gateway.ifionline.org/public/download.aspx"
UA = {"User-Agent": f"qr-research (contact: {os.environ.get('CONTACT_EMAIL', 'unset')})"}
IN_COUNTIES = {"71": "18141", "20": "18039", "50": "18099"}  # Gateway code -> FIPS

# (name, start, end) — 1-indexed inclusive, per 50 IAC 26-20-4(b). Only the fields we normalize.
LAYOUT = [
    ("parcel_number", 1, 25), ("township_no", 51, 54), ("state_district_no", 58, 60),
    ("prop_address", 94, 153), ("prop_city", 154, 183), ("prop_zip", 184, 193),
    ("property_class", 194, 196),
    ("owner_name", 224, 303), ("owner_address", 304, 363), ("owner_city", 364, 393),
    ("owner_state", 394, 423), ("owner_zip", 424, 433), ("owner_country", 434, 436),
    ("transfer_date", 437, 446),
    ("av_land", 469, 480), ("av_improvements", 481, 492), ("av_total", 493, 504),
    ("acreage_x10000", 697, 708),
]

BUSINESS_RE = re.compile(r"\b(LLC|L\.L\.C|INC|INCORPORATED|CORP|CORPORATION|CO\b|COMPANY|LP\b|L\.P\.|LLP|LTD|LIMITED|TRUST|TR\b|TRUSTEE|PARTNERSHIP|PARTNERS|HOLDINGS|PROPERTIES|REALTY|INVESTMENTS?|ENTERPRISES|GROUP|ASSOC|ASSOCIATION|CHURCH|FOUNDATION|UNIVERSITY|COLLEGE|SCHOOL|HOSPITAL|BANK|CITY OF|COUNTY OF|TOWN OF|STATE OF|UNITED STATES|USA\b|HOUSING AUTHORITY|REDEVELOPMENT|AUTHORITY)\b", re.I)


def _slice(line: str, start: int, end: int) -> str:
    return line[start - 1:end].strip()


def _int(s: str) -> int | None:
    s = s.strip()
    if not s or s in ("-",):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _date(s: str) -> str | None:
    s = s.strip()
    try:
        return datetime.strptime(s, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


class GatewayConnector(Connector):
    source_id = "in_gateway_parcels"
    tier = 2
    cadence = "annual"  # assessment files land each spring for the prior assessment year
    counties = list(IN_COUNTIES.values())

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(UA)

    # --- form mechanics ------------------------------------------------
    def _form_state(self) -> tuple[dict, str]:
        t = self._session.get(URL, timeout=60).text
        def hid(n):
            m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(n), t)
            return m.group(1) if m else ""
        years = re.findall(r'<select name="ctl00\$ContentPlaceHolder1\$DropDownList2".*?</select>', t, re.S)[0]
        latest = max(re.findall(r'value="(\d{4})"', years))
        return {"__VIEWSTATE": hid("__VIEWSTATE"), "__VIEWSTATEGENERATOR": hid("__VIEWSTATEGENERATOR"), "__EVENTVALIDATION": hid("__EVENTVALIDATION")}, latest

    def _download(self, state: dict, year: str, county_code: str) -> bytes:
        data = {**state, "ctl00$ContentPlaceHolder1$DropDownList1": "5", "ctl00$ContentPlaceHolder1$DropDownList2": year,
                "ctl00$ContentPlaceHolder1$DropDownList3": county_code, "ctl00$ContentPlaceHolder1$button2": "Download"}
        r = self._session.post(URL, data=data, timeout=600)
        r.raise_for_status()
        if "zip" not in (r.headers.get("Content-Disposition", "") + r.headers.get("Content-Type", "")).lower():
            raise RuntimeError(f"Gateway returned non-zip for {county_code}/{year}: {r.headers.get('Content-Type')}")
        return r.content

    # --- connector interface -------------------------------------------
    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        state, year = self._form_state()
        recs: list[RawRecord] = []
        for code, fips in IN_COUNTIES.items():
            blob = self._download(state, year, code)
            for line in self._lines(blob):
                if line.startswith("PARCEL") or line.startswith("TRAILER"):
                    continue
                row = {name: _slice(line, s, e) for name, s, e in LAYOUT}
                row["assessment_year"] = int(year); row["county_fips"] = fips
                recs.append(RawRecord(self.source_id, f"parcel:{year}:{fips}:{row['parcel_number']}", row, url=URL))
        return recs

    @staticmethod
    def _lines(blob: bytes) -> Iterator[str]:
        z = zipfile.ZipFile(io.BytesIO(blob))
        name = z.namelist()[0]
        with z.open(name) as f:
            for raw in io.TextIOWrapper(f, encoding="latin-1", newline=""):
                yield raw.rstrip("\r\n")

    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        p = raw.payload
        return [{
            "table": "gateway_parcels", "assessment_year": p["assessment_year"], "county_fips": p["county_fips"],
            "parcel_number": p["parcel_number"], "township_no": p["township_no"], "state_district_no": p["state_district_no"],
            "prop_address": p["prop_address"], "prop_city": p["prop_city"].title(), "prop_zip5": p["prop_zip"][:5],
            "property_class": p["property_class"],
            "owner_name": p["owner_name"], "owner_address": p["owner_address"], "owner_city": p["owner_city"].title(),
            "owner_state": p["owner_state"][:2].upper(), "owner_zip5": p["owner_zip"][:5], "owner_country": p["owner_country"],
            "transfer_date": _date(p["transfer_date"]),
            "av_land": _int(p["av_land"]), "av_improvements": _int(p["av_improvements"]), "av_total": _int(p["av_total"]),
            "acres": (_int(p["acreage_x10000"]) or 0) / 10000,
            "owner_is_entity": 1 if BUSINESS_RE.search(p["owner_name"]) else 0,
        }]

    def expected_volume(self) -> tuple[int, int]:
        # St. Joseph ~118k, Elkhart ~85k, Marshall ~25k parcels
        return (180000, 300000)

    def run(self) -> dict:
        ok, note = True, ""
        try:
            recs = self.fetch()
        except Exception as e:  # noqa: BLE001
            recs, ok, note = [], False, repr(e)
        path = self.store_raw(recs) if recs else None
        if recs:
            load(self, recs)
            build_entities()
        health = record_health(self.source_id, len(recs), self.expected_volume(), self.schema_hash(recs) if recs else "", ok, note)
        return {"source": self.source_id, "records": len(recs), "raw_path": str(path), "health": health, "note": note}


DDL = """CREATE TABLE IF NOT EXISTS gateway_parcels (
    assessment_year INTEGER, county_fips TEXT, parcel_number TEXT, township_no TEXT, state_district_no TEXT,
    prop_address TEXT, prop_city TEXT, prop_zip5 TEXT, property_class TEXT,
    owner_name TEXT, owner_address TEXT, owner_city TEXT, owner_state TEXT, owner_zip5 TEXT, owner_country TEXT,
    transfer_date TEXT, av_land INTEGER, av_improvements INTEGER, av_total INTEGER, acres REAL, owner_is_entity INTEGER,
    PRIMARY KEY (assessment_year, county_fips, parcel_number))"""

ENT_DDL = """CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY, name TEXT, name_norm TEXT, entity_type TEXT, county_fips TEXT,
    owner_state TEXT, owner_city TEXT, first_seen TEXT, source TEXT, parcels INTEGER, av_total INTEGER)"""


def load(c: Connector, recs: list[RawRecord]) -> None:
    conn = db(); conn.execute(DDL)
    conn.execute("PRAGMA synchronous=OFF")
    rows = []
    for r in recs:
        for row in c.normalize(r):
            row.pop("table"); rows.append(list(row.values()))
    cols = "assessment_year,county_fips,parcel_number,township_no,state_district_no,prop_address,prop_city,prop_zip5,property_class,owner_name,owner_address,owner_city,owner_state,owner_zip5,owner_country,transfer_date,av_land,av_improvements,av_total,acres,owner_is_entity"
    conn.executemany(f"REPLACE INTO gateway_parcels ({cols}) VALUES ({','.join('?'*21)})", rows)
    conn.commit(); conn.close()


def norm_name(s: str) -> str:
    s = re.sub(r"[.,'&]", " ", s.upper())
    s = re.sub(r"\b(THE|L L C|LLC|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LP|LLP|LTD|LIMITED)\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def build_entities() -> int:
    """Owner names that look like organizations → entities table (aggregated across parcels)."""
    conn = db(); conn.execute(ENT_DDL)
    rows = conn.execute("""SELECT owner_name, county_fips, owner_state, owner_city, MIN(transfer_date), COUNT(*), SUM(COALESCE(av_total,0))
                           FROM gateway_parcels WHERE owner_is_entity=1 GROUP BY owner_name, county_fips""").fetchall()
    n = 0
    for name, fips, st, city, first, cnt, av in rows:
        nn = norm_name(name)
        if not nn:
            continue
        etype = "government" if re.search(r"\b(CITY OF|COUNTY OF|TOWN OF|STATE OF|UNITED STATES|AUTHORITY|REDEVELOPMENT|SCHOOL)\b", name, re.I) else \
                "nonprofit" if re.search(r"\b(CHURCH|FOUNDATION|UNIVERSITY|COLLEGE|HOSPITAL|ASSOC|ASSOCIATION)\b", name, re.I) else \
                "bank" if re.search(r"\bBANK\b", name, re.I) else "business"
        eid = f"gw:{fips}:{re.sub(r'[^A-Z0-9]', '', nn)[:40]}"
        conn.execute("REPLACE INTO entities VALUES (?,?,?,?,?,?,?,?,?,?,?)", (eid, name, nn, etype, fips, st, city, first, "in_gateway_parcels", cnt, av))
        n += 1
    conn.commit(); conn.close()
    return n


if __name__ == "__main__":
    print(GatewayConnector().run())
