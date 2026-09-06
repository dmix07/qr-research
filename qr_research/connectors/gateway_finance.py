"""Indiana Gateway (DLGF/SBOA) connector — local government finance: budgets and debt.

Same form-post mechanism as gateway.py's PARCEL download, different report picker:
  https://gateway.ifionline.org/public/download.aspx
    RadComboBox1=Budget Data                          -> form4b_<year>.txt, every unit, every fund
    RadComboBox1=Annual Financial Reports, RadComboBox2=Debt, UnitType=All -> afr_debt_<year>.txt

Both files are statewide; we stream-filter to the three Indiana counties as we read (never
hold the full file in memory — RadComboBox2 must still be a valid option string even when
downloading Budget Data, which ignores it, or the post 500s).

No bulk "TIF district report" exists on this site (TIFviewer/ is a JS map app with no bulk
download this connector could find). TIF is captured instead as a keyword tag on budget fund
names and debt descriptions (e.g. "Northeast Corridor TIF", "ECONOMIC DEVELOPMENT IN TIF
AREA") — real government filings that mention TIF, not a separate dataset. See DECISIONS.md.
"""
from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from typing import Any, Iterator

import requests

from .base import Connector, RawRecord, db, record_health
from .gateway import IN_COUNTIES, norm_name

URL = "https://gateway.ifionline.org/public/download.aspx"
UA = {"User-Agent": f"qr-research (contact: {os.environ.get('CONTACT_EMAIL', 'unset')})"}
CNTY_CODES = set(IN_COUNTIES)  # Gateway 2-digit codes: "71","20","50"

TIF_RE = re.compile(r"\bTIF\b|REDEVELOPMENT|ECONOMIC DEVELOPMENT", re.I)


def _hid(html: str, name: str) -> str:
    m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), html)
    return m.group(1) if m else ""


def _viewstate(session: requests.Session) -> tuple[dict, list[str]]:
    html = session.get(URL, timeout=60).text
    state = {"__VIEWSTATE": _hid(html, "__VIEWSTATE"), "__VIEWSTATEGENERATOR": _hid(html, "__VIEWSTATEGENERATOR"),
             "__EVENTVALIDATION": _hid(html, "__EVENTVALIDATION")}
    years = re.findall(r'<select name="ctl00\$ContentPlaceHolder1\$DropDownListYear".*?</select>', html, re.S)[0]
    year_opts = sorted((y for y in re.findall(r'value="(\d{4})"', years)), reverse=True)
    return state, year_opts


def _download_lines(session: requests.Session, state: dict, cat1: str, cat2: str, unit_type: str, year: str) -> Iterator[str]:
    """Stream the response line by line; never materialize the whole file."""
    data = {**state, "ctl00$ContentPlaceHolder1$RadComboBox1": cat1, "ctl00$ContentPlaceHolder1$RadComboBox2": cat2,
            "ctl00$ContentPlaceHolder1$DropDownListUnitType": unit_type, "ctl00$ContentPlaceHolder1$DropDownListYear": year,
            "ctl00$ContentPlaceHolder1$button_download1": "Download"}
    r = session.post(URL, data=data, timeout=300, stream=True)
    r.raise_for_status()
    if "attachment" not in r.headers.get("Content-Disposition", ""):
        raise RuntimeError(f"Gateway finance returned no attachment for {cat1}/{cat2}/{unit_type}/{year}: {r.status_code}")
    first = True
    for raw in r.iter_lines(decode_unicode=False):
        line = raw.decode("latin-1")
        if first:  # header row
            first = False
            continue
        if line:
            yield line


class GatewayFinanceConnector(Connector):
    source_id = "in_gateway_finance"
    tier = 1
    cadence = "quarterly"  # budgets/debt reports update through the fiscal year
    counties = list(IN_COUNTIES.values())

    def fetch(self, since: datetime | None = None) -> list[RawRecord]:
        session = requests.Session()
        session.headers.update(UA)
        state, years = _viewstate(session)
        latest, prior = years[0], years[1]
        recs: list[RawRecord] = []

        # Budget Data (form4b) — latest year and prior year, for year-over-year revenue change.
        for year in (latest, prior):
            state2, _ = _viewstate(session)
            for line in _download_lines(session, state2, "Budget Data", "Capital Assets", "All", year):
                f = line.split("|")
                if len(f) < 27 or f[1] not in CNTY_CODES:
                    continue
                recs.append(RawRecord(self.source_id, f"budget:{f[0]}:{f[1]}:{f[4]}:{f[7]}", dict(zip(BUDGET_COLS, f)), url=URL))

        # Annual Financial Report — Debt, all unit types. AFRs trail budgets by a year (the
        # current fiscal year's AFR isn't filed yet), so walk backward from `prior` until a
        # year actually has data instead of assuming which one does.
        for year in years[years.index(prior):]:
            state3, _ = _viewstate(session)
            lines = list(_download_lines(session, state3, "Annual Financial Reports", "Debt", "All", year))
            if lines and lines[0].startswith("Data Not Available"):
                continue
            for line in lines:
                f = line.split("|")
                if len(f) < 17 or f[2] not in CNTY_CODES:
                    continue
                desc_hash = hashlib.sha1(f[14].encode()).hexdigest()[:10]
                recs.append(RawRecord(self.source_id, f"debt:{f[0]}:{f[2]}:{f[4]}:{f[9]}:{f[12]}:{desc_hash}", dict(zip(DEBT_COLS, f)), url=URL))
            break
        return recs

    def normalize(self, raw: RawRecord) -> list[dict[str, Any]]:
        p = raw.payload
        if raw.key.startswith("budget:"):
            fips = IN_COUNTIES[p["cnty_cd"]]
            def num(k):
                v = p.get(k, "").strip()
                try:
                    return float(v)
                except ValueError:
                    return None
            return [{
                "table": "gateway_budget", "year": int(p["year"]), "county_fips": fips,
                "unit_code": p["unit_code"], "unit_name": p["unit_name"].strip(), "fund_cd": p["fund_cd"],
                "fund_description": p["fund_description"].strip(),
                "net_av": num("Net Assessed Valuation"),
                "taxes_to_be_collected_adopted": num("Taxes to be collected_adopted"),
                "total_budget_adopted": num("Total budget estimate_adopted"),
                "is_tif_related": 1 if TIF_RE.search(p["fund_description"] + " " + p["unit_name"]) else 0,
            }]
        if raw.key.startswith("debt:"):
            fips = IN_COUNTIES[p["county_cd_fk"]]
            def num(k):
                v = p.get(k, "").strip()
                try:
                    return float(v)
                except ValueError:
                    return None
            return [{
                "table": "gateway_debt", "year": int(p["year"]), "county_fips": fips,
                "unit_code": p["unit_code"], "unit_name": p["unit_name"].strip(),
                "ent_id": p.get("ent_id") or "", "ent_name": (p.get("ent_name") or "").strip(),
                "debt_class_code": p["debt_class_code"], "debt_class_name": p["debt_class_name"].strip(),
                "debt_description": p["debt_description"].strip(),
                "end_principal_bal": num("end_principal_bal"), "principal_amt_due_1yr": num("principal_amt_due_1yr"),
                "is_tif_related": 1 if TIF_RE.search(p["debt_description"] + " " + p["unit_name"]) else 0,
            }]
        return []

    def expected_volume(self) -> tuple[int, int]:
        # ~950 budget rows/yr * 2 years + ~300 debt rows, three counties, all unit types
        return (1200, 4000)

    def run(self) -> dict:
        ok, note = True, ""
        try:
            recs = self.fetch()
        except Exception as e:  # noqa: BLE001
            recs, ok, note = [], False, repr(e)
        path = self.store_raw(recs) if recs else None
        if recs:
            load(self, recs)
            build_gov_entities()
        health = record_health(self.source_id, len(recs), self.expected_volume(), self.schema_hash(recs) if recs else "", ok, note)
        return {"source": self.source_id, "records": len(recs), "raw_path": str(path), "health": health, "note": note}


BUDGET_COLS = ["year", "cnty_cd", "cnty_description", "unit_type", "unit_code", "unit_name", "sboa_id", "fund_cd", "fund_description",
    "Net Assessed Valuation", "Total budget estimate_published", "Total budget estimate_adopted", "Necessary expenditures_published",
    "Necessary expenditures_adopted", "Additional appropriation_published", "Additional appropriation_adopted",
    "Outstanding temp loans to be paid_published", "Outstanding temp loans to be paid_adopted",
    "Outstanding temp loans not repaid_published", "Outstanding temp loans not repaid_adopted",
    "Total funds reqd_published", "Total funds reqd_adopted", "Actual cash balance_published", "Actual cash balance_adopted",
    "Taxes to be collected_published", "Taxes to be collected_adopted", "Misc revenue from Form 2 ColA_published",
    "Misc revenue from Form 2 ColA_adopted", "Misc revenue from Form 2 ColB_published", "Misc revenue from Form 2 ColB_adopted",
    "Total funds_published", "Total funds_adopted", "Net to be raised for expenses_published", "Net to be raised for expenses_adopted",
    "Operating balance_published", "Operating balance_adopted", "Amt to be raised taxLevy_published", "Amt to be raised taxLevy_adopted",
    "Prop Tax Repl Cred_published", "Prop Tax Repl Cred_adopted", "Operating LOIT_published", "Operating LOIT_adopted",
    "NET AMT TO BE RAISED BY TAX LEVY_published", "NET AMT TO BE RAISED BY TAX LEVY_adopted", "Levy Excess Fund_published",
    "Levy Excess Fund_adopted", "Net amount to be raised_published", "Net amount to be raised_adopted", "Net Tax Rate_published",
    "Net Tax Rate_adopted", "PropertyTaxCap_published", "PropertyTaxCap_adopted"]

DEBT_COLS = ["year", "cnty_description", "county_cd_fk", "budget_unit_type", "unit_code", "submit_status", "unit_name",
    "afr_unit_type", "sboa_id", "ent_id", "ent_description", "ent_name", "debt_class_code", "debt_class_name",
    "debt_description", "end_principal_bal", "principal_amt_due_1yr"]

BUDGET_DDL = """CREATE TABLE IF NOT EXISTS gateway_budget (
    year INTEGER, county_fips TEXT, unit_code TEXT, unit_name TEXT, fund_cd TEXT, fund_description TEXT,
    net_av REAL, taxes_to_be_collected_adopted REAL, total_budget_adopted REAL, is_tif_related INTEGER,
    PRIMARY KEY (year, county_fips, unit_code, fund_cd))"""

DEBT_DDL = """CREATE TABLE IF NOT EXISTS gateway_debt (
    year INTEGER, county_fips TEXT, unit_code TEXT, unit_name TEXT, ent_id TEXT, ent_name TEXT,
    debt_class_code TEXT, debt_class_name TEXT, debt_description TEXT, end_principal_bal REAL, principal_amt_due_1yr REAL,
    is_tif_related INTEGER, PRIMARY KEY (year, county_fips, unit_code, ent_id, debt_class_code, debt_description))"""


def load(c: Connector, recs: list[RawRecord]) -> None:
    conn = db(); conn.execute(BUDGET_DDL); conn.execute(DEBT_DDL)
    conn.execute("PRAGMA synchronous=OFF")
    b_cols = "year,county_fips,unit_code,unit_name,fund_cd,fund_description,net_av,taxes_to_be_collected_adopted,total_budget_adopted,is_tif_related"
    d_cols = "year,county_fips,unit_code,unit_name,ent_id,ent_name,debt_class_code,debt_class_name,debt_description,end_principal_bal,principal_amt_due_1yr,is_tif_related"
    for r in recs:
        for row in c.normalize(r):
            table = row.pop("table")
            cols = b_cols if table == "gateway_budget" else d_cols
            conn.execute(f"REPLACE INTO {table} ({cols}) VALUES ({','.join('?' * len(row))})", list(row.values()))
    conn.commit(); conn.close()


def build_gov_entities() -> int:
    """Local government units that filed a budget or debt report -> entities table (government type)."""
    conn = db(); conn.execute("""CREATE TABLE IF NOT EXISTS entities (
        entity_id TEXT PRIMARY KEY, name TEXT, name_norm TEXT, entity_type TEXT, county_fips TEXT,
        owner_state TEXT, owner_city TEXT, first_seen TEXT, source TEXT, parcels INTEGER, av_total INTEGER)""")
    rows = conn.execute("SELECT DISTINCT unit_name, county_fips FROM gateway_budget").fetchall()
    n = 0
    for name, fips in rows:
        nn = norm_name(name)
        if not nn:
            continue
        eid = f"gwf:{fips}:{re.sub(r'[^A-Z0-9]', '', nn)[:40]}"
        conn.execute("""INSERT OR IGNORE INTO entities (entity_id, name, name_norm, entity_type, county_fips, source)
            VALUES (?,?,?,?,?,?)""", (eid, name, nn, "government", fips, "in_gateway_finance"))
        n += 1
    conn.commit(); conn.close()
    return n


if __name__ == "__main__":
    print(GatewayFinanceConnector().run())
