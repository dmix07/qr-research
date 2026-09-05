"""Census Bureau connector.

Three datasets, two access paths:
  cbp  — County Business Patterns, county × NAICS × size band. Bulk zip, no key.
  bds  — Business Dynamics Statistics, county time series 1978–latest. Bulk CSV, no key.
  acs  — American Community Survey 5-year, county (and place) tables. API, needs
         CENSUS_API_KEY (free: https://api.census.gov/data/key_signup.html). Skipped
         cleanly when the key is absent; health notes it.
"""
from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from datetime import datetime
from typing import Any

import requests

from .base import COUNTY_FIPS, Connector, RawRecord, db, record_health

UA = {"User-Agent": f"qr-research (contact: {os.environ.get('CONTACT_EMAIL', 'unset')})"}
FTP = "https://www2.census.gov/programs-surveys"
API = "https://api.census.gov/data"

# (state, county) pairs as they appear in Census files
PAIRS = {(f[:2], f[2:]) for f in COUNTY_FIPS}

ACS_VARS = {  # used by #005 and #006; extend as recipes need
    "B25077_001E": "median_home_value", "B25064_001E": "median_gross_rent",
    "B25003_001E": "occupied_units", "B25003_002E": "owner_occupied", "B25003_003E": "renter_occupied",
    "B01003_001E": "population",
}


def _latest_year(index_url: str, pattern: str) -> int:
    html = requests.get(index_url, headers=UA, timeout=60).text
    years = [int(y) for y in re.findall(pattern, html)]
    return max(years)


class CensusConnector(Connector):
    source_id = "census"
    tier = 1
    cadence = "quarterly"  # CBP/BDS land annually; quarterly check is cheap
    _acs_skipped = False

    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        recs: list[RawRecord] = []
        recs += self._fetch_cbp()
        recs += self._fetch_bds()
        recs += self._fetch_acs()
        return recs

    # --- CBP -----------------------------------------------------------
    def _fetch_cbp(self) -> list[RawRecord]:
        year = _latest_year(f"{FTP}/cbp/datasets/", r'href="(20\d\d)/"')
        yy = str(year)[2:]
        url = f"{FTP}/cbp/datasets/{year}/cbp{yy}co.zip"
        z = zipfile.ZipFile(io.BytesIO(requests.get(url, headers=UA, timeout=300).content))
        name = next(n for n in z.namelist() if n.endswith(".txt") or n.endswith(".csv"))
        out = []
        for row in csv.DictReader(io.TextIOWrapper(z.open(name), encoding="latin-1")):
            if (row["fipstate"], row["fipscty"]) in PAIRS:
                row["year"] = year
                out.append(RawRecord(self.source_id, f"cbp:{year}:{row['fipstate']}{row['fipscty']}:{row['naics']}", row, url=url))
        return out

    # --- BDS -----------------------------------------------------------
    def _fetch_bds(self) -> list[RawRecord]:
        year = _latest_year(f"{FTP}/bds/tables/time-series/", r'href="(20\d\d)/"')
        url = f"{FTP}/bds/tables/time-series/{year}/bds{year}_st_cty.csv"
        text = requests.get(url, headers=UA, timeout=300).text
        out = []
        for row in csv.DictReader(io.StringIO(text)):
            if (row["st"].zfill(2), row["cty"].zfill(3)) in PAIRS:
                out.append(RawRecord(self.source_id, f"bds:{row['year']}:{row['st'].zfill(2)}{row['cty'].zfill(3)}", row, url=url))
        return out

    # --- ACS -----------------------------------------------------------
    def _fetch_acs(self) -> list[RawRecord]:
        key = os.environ.get("CENSUS_API_KEY")
        if not key:
            self._acs_skipped = True
            return []
        out = []
        year = _latest_year(f"{API}/", r'"c_vintage":\s*(20\d\d)') if False else datetime.now().year - 2  # ACS 5-yr lags ~2 years
        for st in ("18", "26"):
            cty = ",".join(c for s, c in PAIRS if s == st)
            r = requests.get(f"{API}/{year}/acs/acs5", params={"get": "NAME," + ",".join(ACS_VARS), "for": f"county:{cty}", "in": f"state:{st}", "key": key}, headers=UA, timeout=60)
            r.raise_for_status()
            rows = r.json()
            hdr = rows[0]
            for vals in rows[1:]:
                row = dict(zip(hdr, vals)); row["year"] = year
                out.append(RawRecord(self.source_id, f"acs:{year}:{row['state']}{row['county']}", row, url=r.url.split("&key=")[0]))
        return out

    # --- normalize -----------------------------------------------------
    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        p = raw.payload
        if raw.key.startswith("cbp:"):
            def n(k):
                v = p.get(k); return int(v) if v not in (None, "", "N", "S", "D") else None
            return [{"table": "census_cbp", "year": p["year"], "county_fips": p["fipstate"] + p["fipscty"], "naics": p["naics"],
                     "estab": n("est"), "emp": n("emp"), "payroll_k": n("ap"),
                     "n_lt5": n("n<5"), "n5_9": n("n5_9"), "n10_19": n("n10_19"), "n20_49": n("n20_49"),
                     "n50_99": n("n50_99"), "n100_249": n("n100_249"), "n250_499": n("n250_499"), "n500_999": n("n500_999"), "n1000": n("n1000")}]
        if raw.key.startswith("bds:"):
            def f(k):
                v = p.get(k); return float(v) if v not in (None, "", "(D)", "(S)", "(X)") else None
            return [{"table": "census_bds", "year": int(p["year"]), "county_fips": p["st"].zfill(2) + p["cty"].zfill(3),
                     "firms": f("firms"), "estabs": f("estabs"), "emp": f("emp"), "estabs_entry": f("estabs_entry"), "estabs_exit": f("estabs_exit"),
                     "job_creation": f("job_creation"), "job_destruction": f("job_destruction"), "net_job_creation_rate": f("net_job_creation_rate"),
                     "reallocation_rate": f("reallocation_rate"), "firmdeath_firms": f("firmdeath_firms"), "firmdeath_emp": f("firmdeath_emp")}]
        if raw.key.startswith("acs:"):
            row = {"table": "census_acs", "year": p["year"], "county_fips": p["state"] + p["county"], "name": p.get("NAME")}
            for var, col in ACS_VARS.items():
                v = p.get(var); row[col] = int(v) if v not in (None, "", "-666666666") else None
            return [row]
        return []

    def expected_volume(self) -> tuple[int, int]:
        # CBP: 5 counties × ~500–900 NAICS rows; BDS: 5 × ~46 years; ACS: 5 (if keyed)
        return (2500, 6000)

    def run(self) -> dict:
        ok, note = True, ""
        try:
            recs = self.fetch()
        except Exception as e:  # noqa: BLE001
            recs, ok, note = [], False, repr(e)
        if self._acs_skipped:
            note = (note + " | ACS skipped: CENSUS_API_KEY not set").strip(" |")
        path = self.store_raw(recs) if recs else None
        if recs:
            load(self, recs)
        health = record_health(self.source_id, len(recs), self.expected_volume(), self.schema_hash(recs) if recs else "", ok, note)
        return {"source": self.source_id, "records": len(recs), "raw_path": str(path), "health": health, "note": note}


DDL = {
    "census_cbp": """CREATE TABLE IF NOT EXISTS census_cbp (year INTEGER, county_fips TEXT, naics TEXT, estab INTEGER, emp INTEGER, payroll_k INTEGER,
        n_lt5 INTEGER, n5_9 INTEGER, n10_19 INTEGER, n20_49 INTEGER, n50_99 INTEGER, n100_249 INTEGER, n250_499 INTEGER, n500_999 INTEGER, n1000 INTEGER,
        PRIMARY KEY (year, county_fips, naics))""",
    "census_bds": """CREATE TABLE IF NOT EXISTS census_bds (year INTEGER, county_fips TEXT, firms REAL, estabs REAL, emp REAL, estabs_entry REAL, estabs_exit REAL,
        job_creation REAL, job_destruction REAL, net_job_creation_rate REAL, reallocation_rate REAL, firmdeath_firms REAL, firmdeath_emp REAL,
        PRIMARY KEY (year, county_fips))""",
    "census_acs": """CREATE TABLE IF NOT EXISTS census_acs (year INTEGER, county_fips TEXT, name TEXT, median_home_value INTEGER, median_gross_rent INTEGER,
        occupied_units INTEGER, owner_occupied INTEGER, renter_occupied INTEGER, population INTEGER, PRIMARY KEY (year, county_fips))""",
}


def load(c: Connector, recs: list[RawRecord]) -> None:
    conn = db()
    for ddl in DDL.values():
        conn.execute(ddl)
    for r in recs:
        for row in c.normalize(r):
            t = row.pop("table")
            conn.execute(f"REPLACE INTO {t} ({','.join(row)}) VALUES ({','.join('?'*len(row))})", list(row.values()))
    conn.commit(); conn.close()


if __name__ == "__main__":
    print(CensusConnector().run())
