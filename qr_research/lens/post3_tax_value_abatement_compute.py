"""Post 3: tax vs. value + abatement, top-10 St. Joseph industrial owners.

Data-availability finding (logged DECISIONS.md): for St. Joseph County, the Real Property
(PARCEL) file is available through 2025 pay 2026, but the Tax Bill (TAXDATA) file is only
available through 2024 pay 2025, and the Adjustments (ADJMENTS) file -- which carries the
abatement/ERA deduction line -- is only available through 2023 pay 2024. Since Part A of
this task requires abatement detail, this script uses 2023 pay 2024, the most recent year
for which PARCEL + TAXDATA + ADJMENTS are ALL available for St. Joseph. This is NOT the same
ownership snapshot as post2_parent_rollup (2025) -- notably Razor5's parcels had not yet
transferred as of the Jan 1, 2023 assessment date, so Razor5 will not appear as an owner in
this book. The FAMILY GROUPING DEFINITIONS are reused unchanged; the actual top-10 outcome is
computed fresh against 2023's owner set, not copied from post2_parent_rollup's output.

Fetches TAXDATA + ADJMENTS directly from Gateway (same form mechanics as GatewayConnector,
parameterized for DropDownList1=3 and =4). Joins to the already-loaded gateway_parcels table
on parcel_number. Read-only against gateway_parcels; does not write anything.

Not wired into run.py/Makefile. Prints one JSON blob to stdout.
"""
from __future__ import annotations

import io
import json
import re
import sqlite3
import zipfile

import requests

from qr_research.connectors.base import DB_PATH
from qr_research.connectors.gateway import norm_name

URL = "https://gateway.ifionline.org/public/download.aspx"
YEAR = "2023"  # 2023 pay 2024 -- see module docstring
FIPS = "18141"
COUNTY_CODE = "71"
CLASS_LO, CLASS_HI = "300", "399"

TAXDATA_LAYOUT = [
    ("parcel_number", 1, 25), ("taxpayer_name", 52, 131),
    ("av_land_3pct_cap", 605, 616), ("av_impr_3pct_cap", 617, 628),
    ("gross_av", 665, 676), ("net_av", 677, 688),
    ("tax_rate", 689, 694),  # format 2.4 -- implied 4 decimals
    ("gross_tax_due", 695, 708),  # format 12.2
    ("local_tax_relief", 709, 722),  # format 12.2
    ("property_tax_cap", 723, 736),  # format 12.2 -- circuit-breaker credit $
    ("total_property_tax_due", 737, 750),  # format 12.2 -- net tax billed
    ("total_other_charges", 751, 764),  # format 12.2
]

ADJMENTS_LAYOUT = [
    ("parcel_number", 1, 25), ("adj_instance", 26, 28), ("adj_type_code", 29, 29),
    ("adjustment_code", 30, 31), ("total_adjustment_amount", 32, 45),  # format 12.2
]

ABATEMENT_CODE = "16"  # Code List 37: REHABILITATION OR REDEVELOPMENT OF REAL PROPERTY IN
                        # ECONOMIC REVITALIZATION AREAS ABATEMENT (6-1.1-12.1)

FAMILIES = [
    ("Razor5", ["RAZOR5"]),
    ("Great Lakes Capital / Portage Prairie", [
        "GLC PORTAGE PRAIRIE", "GLC PORTAGE PRAIRIE II", "GLC PORTAGE PRAIRIE III", "GLC PORTAGE PRAIRIE IV"]),
    ("I/N Tek / I/N Kote / Inland Steel (Cleveland-Cliffs / Nippon Steel JV, per public record)", [
        "I/N TEK", "I/N KOTE % TAX DEPT 8-299", "I/N TEK TAX DIVISION", "INLAND STEEL",
        "INLAND STEEL % KEN WALKER 8-229"]),
    ("Unnamed South Bend real-estate cluster (3454 Douglas Rd)", [
        "3300 SAMPLE STREET ASSOCIATES", "AMERIPLEX SUPERIOR PARTNERS", "HP OLD CLEVELAND PARTNERS",
        "HURON PARTNERS", "KOCSIS FAMILY PARTNERSHIP", "OLIVE ENTERPRISE PARTNERS",
        "OLIVER PLOW PARTNERS", "ONTARIO PARTNERS"]),
    ("Mullen Indiana Real Estate", ["MULLEN INDIANA REAL ESTATE"]),
    ("JVE Investments (Tire Rack real estate)", [
        "JVE INVESTMENTS", "JVE INVESTMENTS % TIRE RACK", "BW BUSINESS PARK % TIRE RACK"]),
]


def _slice(line: str, start: int, end: int) -> str:
    return line[start - 1:end].strip()


def _implied(raw: str, decimals: int) -> float:
    """Parse a TAXDATA numeric field. Spec (50 IAC 26-21-2(6)) says these are raw digits with
    an implied decimal point (no literal '.'), but this vendor's export (WinTax, per the file
    header) writes a literal decimal point for at least the tax-rate field -- confirmed live
    against the downloaded file, not assumed. Handle both rather than guess which one applies
    to a given field."""
    s = raw.strip()
    if not s:
        return 0.0
    if "." in s:
        return float(s)
    neg = s.startswith("-")
    s = s.lstrip("-")
    n = int(s or "0")
    val = n / (10 ** decimals)
    return -val if neg else val


def _form_state(session: requests.Session) -> dict:
    t = session.get(URL, timeout=60).text
    def hid(n):
        m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(n), t)
        return m.group(1) if m else ""
    return {"__VIEWSTATE": hid("__VIEWSTATE"), "__VIEWSTATEGENERATOR": hid("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": hid("__EVENTVALIDATION")}


def _download(session: requests.Session, dataset: str, year: str, county_code: str) -> bytes:
    state = _form_state(session)
    data = {**state, "ctl00$ContentPlaceHolder1$DropDownList1": dataset,
            "ctl00$ContentPlaceHolder1$DropDownList2": year,
            "ctl00$ContentPlaceHolder1$DropDownList3": county_code,
            "ctl00$ContentPlaceHolder1$button2": "Download"}
    r = session.post(URL, data=data, timeout=600)
    r.raise_for_status()
    if "zip" not in (r.headers.get("Content-Disposition", "") + r.headers.get("Content-Type", "")).lower():
        raise RuntimeError(f"Gateway returned non-zip for dataset={dataset} {county_code}/{year} "
                            f"(status message usually 'Data not available.')")
    return r.content


def _lines(blob: bytes):
    z = zipfile.ZipFile(io.BytesIO(blob))
    name = z.namelist()[0]
    with z.open(name) as f:
        for raw in io.TextIOWrapper(f, encoding="latin-1", newline=""):
            yield raw.rstrip("\r\n")


def fetch_taxdata() -> dict[str, dict]:
    s = requests.Session()
    blob = _download(s, "3", YEAR, COUNTY_CODE)
    out = {}
    for line in _lines(blob):
        if line.startswith("TAXDATA") or line.startswith("TRAILER"):
            continue
        row = {name: _slice(line, a, b) for name, a, b in TAXDATA_LAYOUT}
        rec = {
            "parcel_number": row["parcel_number"],
            "taxpayer_name": row["taxpayer_name"],
            "gross_av": int(row["gross_av"] or 0),
            "net_av": int(row["net_av"] or 0),
            "tax_rate": _implied(row["tax_rate"], 4),
            "gross_tax_due": _implied(row["gross_tax_due"], 2),
            "local_tax_relief": _implied(row["local_tax_relief"], 2),
            "property_tax_cap": _implied(row["property_tax_cap"], 2),
            "total_property_tax_due": _implied(row["total_property_tax_due"], 2),
            "total_other_charges": _implied(row["total_other_charges"], 2),
        }
        out[rec["parcel_number"]] = rec
    return out


def fetch_adjments() -> dict[str, dict]:
    s = requests.Session()
    blob = _download(s, "4", YEAR, COUNTY_CODE)
    out: dict[str, dict] = {}
    for line in _lines(blob):
        if line.startswith("ADJMENTS") or line.startswith("TRAILER"):
            continue
        row = {name: _slice(line, a, b) for name, a, b in ADJMENTS_LAYOUT}
        pn = row["parcel_number"]
        amt = _implied(row["total_adjustment_amount"], 2)
        code = row["adjustment_code"].zfill(2) if row["adjustment_code"] else ""
        d = out.setdefault(pn, {"total_deductions": 0.0, "abatement": 0.0, "codes_seen": {}})
        d["total_deductions"] += amt
        if code == ABATEMENT_CODE:
            d["abatement"] += amt
        d["codes_seen"][code] = d["codes_seen"].get(code, 0.0) + amt
    return out


def region_zips(conn: sqlite3.Connection) -> set[str]:
    return {z for (z,) in conn.execute(
        "SELECT DISTINCT prop_zip5 FROM gateway_parcels WHERE assessment_year=? AND prop_zip5 != '' AND county_fips IN (?,?,?)",
        (int(YEAR), "18141", "18039", "18099")).fetchall()}


def family_for(owner_name: str) -> str | None:
    key = norm_name(owner_name or "")
    for fam_name, members in FAMILIES:
        for m in members:
            if norm_name(m) == key or norm_name(m) in key or key in norm_name(m):
                return fam_name
    return None


def main() -> dict:
    conn = sqlite3.connect(DB_PATH)
    zips = region_zips(conn)

    parcels = conn.execute(
        """SELECT parcel_number, owner_name, owner_city, owner_state, owner_zip5, av_total, property_class
           FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?""",
        (int(YEAR), FIPS, CLASS_LO, CLASS_HI)).fetchall()

    taxdata = fetch_taxdata()
    adjments = fetch_adjments()

    fetch_errors = []
    joined = []
    for pn, oname, ocity, ostate, ozip, av_total, cls in parcels:
        td = taxdata.get(pn)
        if td is None:
            fetch_errors.append({"parcel_number": pn, "issue": "no TAXDATA record"})
            continue
        adj = adjments.get(pn, {"total_deductions": 0.0, "abatement": 0.0, "codes_seen": {}})
        local = ozip in zips
        fam = family_for(oname)
        owner_key = fam or norm_name(oname or "") or (oname or "").strip().upper()
        joined.append({
            "parcel_number": pn, "owner_name": oname, "owner_key": owner_key, "family": fam,
            "local_by_zip": local, "av_total_parcel_file": av_total or 0,
            "gross_av": td["gross_av"], "net_av": td["net_av"], "tax_rate": td["tax_rate"],
            "gross_tax_due": td["gross_tax_due"], "local_tax_relief": td["local_tax_relief"],
            "property_tax_cap": td["property_tax_cap"], "net_tax_billed": td["total_property_tax_due"],
            "total_deductions": adj["total_deductions"], "abatement": adj["abatement"],
        })

    county_total_av = sum(r["gross_av"] for r in joined)
    county_total_tax = sum(r["net_tax_billed"] for r in joined)

    owners: dict[str, dict] = {}
    for r in joined:
        o = owners.setdefault(r["owner_key"], {
            "display_name": r["family"] or r["owner_name"], "is_family": bool(r["family"]),
            "parcel_count": 0, "gross_av": 0, "net_tax_billed": 0, "total_deductions": 0.0,
            "abatement": 0.0, "property_tax_cap": 0.0, "local_by_zip_any": False, "local_by_zip_all": True,
        })
        o["parcel_count"] += 1
        o["gross_av"] += r["gross_av"]
        o["net_tax_billed"] += r["net_tax_billed"]
        o["total_deductions"] += r["total_deductions"]
        o["abatement"] += r["abatement"]
        o["property_tax_cap"] += r["property_tax_cap"]
        o["local_by_zip_any"] = o["local_by_zip_any"] or r["local_by_zip"]
        o["local_by_zip_all"] = o["local_by_zip_all"] and r["local_by_zip"]

    owner_rows = []
    for key, o in owners.items():
        eff_rate = o["net_tax_billed"] / o["gross_av"] if o["gross_av"] else None
        gross_tax_if_no_cap_no_abate = None  # not computable per-owner without per-parcel gross_tax_due sum
        owner_rows.append({
            "owner_key": key, "display_name": o["display_name"], "is_family_rollup": o["is_family"],
            "parcel_count": o["parcel_count"], "gross_av": o["gross_av"],
            "value_share_pct": round(o["gross_av"] / county_total_av * 100, 4) if county_total_av else None,
            "net_tax_billed": round(o["net_tax_billed"], 2),
            "tax_share_pct": round(o["net_tax_billed"] / county_total_tax * 100, 4) if county_total_tax else None,
            "effective_rate_pct": round(eff_rate * 100, 4) if eff_rate is not None else None,
            "abatement": round(o["abatement"], 2), "total_deductions": round(o["total_deductions"], 2),
            "circuit_breaker_credit": round(o["property_tax_cap"], 2),
            "local_by_zip": "all" if o["local_by_zip_all"] else ("some" if o["local_by_zip_any"] else "none"),
        })
    owner_rows.sort(key=lambda r: -r["gross_av"])

    top10 = owner_rows[:10]
    for r in top10:
        r["gap_pp"] = round((r["value_share_pct"] or 0) - (r["tax_share_pct"] or 0), 4)
        gross_at_3pct = r["gross_av"] * 0.03
        r["at_3pct_cap"] = round(r["circuit_breaker_credit"], 2) > 0.01

    other_parcels = [r for r in joined if (r["family"] or norm_name(r["owner_name"] or "") or r["owner_name"]) not in {r2["owner_key"] for r2 in top10}]
    other_av = sum(r["gross_av"] for r in other_parcels)
    other_tax = sum(r["net_tax_billed"] for r in other_parcels)
    other_abate = sum(r["abatement"] for r in other_parcels)
    other_ded = sum(r["total_deductions"] for r in other_parcels)
    other_cb = sum(r["property_tax_cap"] for r in other_parcels)
    other_row = {
        "owner_key": "ALL OTHER OWNERS", "display_name": "All other owners", "parcel_count": len(other_parcels),
        "gross_av": other_av, "value_share_pct": round(other_av / county_total_av * 100, 4) if county_total_av else None,
        "net_tax_billed": round(other_tax, 2), "tax_share_pct": round(other_tax / county_total_tax * 100, 4) if county_total_tax else None,
        "effective_rate_pct": round(other_tax / other_av * 100, 4) if other_av else None,
        "abatement": round(other_abate, 2), "total_deductions": round(other_ded, 2),
        "circuit_breaker_credit": round(other_cb, 2),
    }
    total_row = {
        "owner_key": "TOTAL", "display_name": "TOTAL (industrial book)", "parcel_count": len(joined),
        "gross_av": county_total_av, "value_share_pct": 100.0, "net_tax_billed": round(county_total_tax, 2),
        "tax_share_pct": 100.0, "effective_rate_pct": round(county_total_tax / county_total_av * 100, 4) if county_total_av else None,
        "abatement": round(sum(r["abatement"] for r in joined), 2), "total_deductions": round(sum(r["total_deductions"] for r in joined), 2),
        "circuit_breaker_credit": round(sum(r["property_tax_cap"] for r in joined), 2),
    }

    local_rows = [r for r in joined if r["local_by_zip"]]
    nonlocal_rows = [r for r in joined if not r["local_by_zip"]]
    def side(rows):
        av = sum(r["gross_av"] for r in rows); tax = sum(r["net_tax_billed"] for r in rows)
        return {
            "parcel_count": len(rows), "gross_av": av,
            "value_share_pct": round(av / county_total_av * 100, 4) if county_total_av else None,
            "net_tax_billed": round(tax, 2), "tax_share_pct": round(tax / county_total_tax * 100, 4) if county_total_tax else None,
            "effective_rate_pct": round(tax / av * 100, 4) if av else None,
            "total_abatement": round(sum(r["abatement"] for r in rows), 2),
        }
    part_b = {"local": side(local_rows), "non_local": side(nonlocal_rows)}

    # --- verification ---
    recon_sum_tax = round(sum(r["net_tax_billed"] for r in joined), 2)

    max_delta = 0.0
    over_100 = []
    for r in joined:
        computed_gross = r["net_av"] / 100.0 * r["tax_rate"]
        computed_capped = min(computed_gross, r["gross_av"] * 0.03)
        computed_net = computed_capped - r["local_tax_relief"]
        delta = abs(computed_net - r["net_tax_billed"])
        max_delta = max(max_delta, delta)
        if delta > 100:
            over_100.append({
                "parcel_number": r["parcel_number"], "computed_net_tax": round(computed_net, 2),
                "reported_net_tax": r["net_tax_billed"], "delta": round(delta, 2),
                "note": "delta beyond formula inputs -- likely another ADJMENTS credit code not modeled here",
            })

    return {
        "year_used": f"{YEAR} pay {int(YEAR)+1}",
        "why_this_year": ("St. Joseph Real Property is available through 2025 pay 2026, TAXDATA through "
                           "2024 pay 2025, and ADJMENTS (abatement detail) only through 2023 pay 2024 -- "
                           "2023 is the most recent year all three exist together."),
        "county_totals": {"gross_av": county_total_av, "net_tax_billed": round(county_total_tax, 2), "parcels": len(joined)},
        "part_a_top10": top10,
        "part_a_all_other": other_row,
        "part_a_total": total_row,
        "part_b_local_vs_nonlocal": part_b,
        "verification": {
            "sum_per_parcel_net_tax_equals_county_total": recon_sum_tax,
            "max_computed_vs_reported_delta": round(max_delta, 2),
            "parcels_off_by_over_100": over_100,
            "taxdata_missing_for_n_parcels": len(fetch_errors),
            "taxdata_missing_examples": fetch_errors[:10],
        },
        "families_reused_definitions": [f[0] for f in FAMILIES],
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
