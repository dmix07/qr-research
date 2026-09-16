"""Post 2 follow-up #2: absolute dollars over time (dilution vs. decline) + per-parcel history
of the 8 Razor5 parcels, 2020-2024, using the already-loaded gateway_parcels table (no new
fetch -- all six confirmed-available vintages, DECISIONS.md #75, are already in the DB).

Read-only. Not wired into run.py/Makefile. Prints one JSON blob to stdout.
"""
from __future__ import annotations

import json
import sqlite3

from qr_research.connectors.base import DB_PATH

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
FIPS = "18141"
CLASS_LO, CLASS_HI = "300", "399"
RAZOR5_PARCELS = [
    "710601100002000017", "710601200002000017", "710601200003000017", "710601200005000017",
    "710612400001000017", "710706100001000017", "710706100002000017", "710707300001000017",
]


def region_zips(conn: sqlite3.Connection, year: int) -> set[str]:
    return {z for (z,) in conn.execute(
        "SELECT DISTINCT prop_zip5 FROM gateway_parcels WHERE assessment_year=? AND prop_zip5 != '' AND county_fips IN (?,?,?)",
        (year, "18141", "18039", "18099")).fetchall()}


def part_a_dollars(conn: sqlite3.Connection) -> dict:
    out = {}
    for y in YEARS:
        zips = region_zips(conn, y)
        rows = conn.execute(
            "SELECT owner_zip5, av_total FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?",
            (y, FIPS, CLASS_LO, CLASS_HI)).fetchall()
        total = sum(r[1] or 0 for r in rows)
        local = sum(r[1] or 0 for r in rows if r[0] in zips)
        non_local = total - local
        out[y] = {"total_av": total, "local_av": local, "non_local_av": non_local}
    return out


def razor5_totals_by_year(conn: sqlite3.Connection) -> dict:
    out = {}
    for y in YEARS:
        rows = conn.execute(
            f"SELECT av_total FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND parcel_number IN ({','.join('?' * len(RAZOR5_PARCELS))})",
            (y, FIPS, *RAZOR5_PARCELS)).fetchall()
        out[y] = sum(r[0] or 0 for r in rows)
    return out


def parcel_history(conn: sqlite3.Connection) -> dict:
    out = {}
    for parcel in RAZOR5_PARCELS:
        history = {}
        for y in YEARS:
            row = conn.execute(
                """SELECT property_class, av_land, av_improvements, av_total, owner_name, owner_address,
                          owner_city, owner_state, owner_zip5, transfer_date, prop_address, acres
                   FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND parcel_number=?""",
                (y, FIPS, parcel)).fetchone()
            if row is None:
                history[y] = None
                continue
            cls, av_land, av_impr, av_total, oname, oaddr, ocity, ostate, ozip, tdate, paddr, acres = row
            zips = region_zips(conn, y)
            history[y] = {
                "property_class": cls, "av_land": av_land, "av_improvements": av_impr, "av_total": av_total,
                "owner_name": oname, "owner_address": oaddr, "owner_city": ocity, "owner_state": ostate,
                "owner_zip5": ozip, "local_by_zip": ozip in zips, "transfer_date": tdate,
                "prop_address": paddr, "acres": acres,
            }
        out[parcel] = history
    return out


def main() -> dict:
    conn = sqlite3.connect(DB_PATH)
    dollars = part_a_dollars(conn)
    razor5_totals = razor5_totals_by_year(conn)
    for y in YEARS:
        dollars[y]["razor5_av"] = razor5_totals[y]
        dollars[y]["non_local_av_excl_razor5"] = dollars[y]["non_local_av"] - razor5_totals[y]

    history = parcel_history(conn)

    razor5_2025_land = sum((history[p][2025]["av_land"] or 0) for p in RAZOR5_PARCELS)
    razor5_2025_impr = sum((history[p][2025]["av_improvements"] or 0) for p in RAZOR5_PARCELS)
    razor5_2025_total = sum((history[p][2025]["av_total"] or 0) for p in RAZOR5_PARCELS)

    return {
        "years": YEARS,
        "part_a_dollars_by_year": {str(y): v for y, v in dollars.items()},
        "razor5_parcel_history": history,
        "razor5_2025_land_vs_improvement": {
            "av_land": razor5_2025_land, "av_improvements": razor5_2025_impr, "av_total": razor5_2025_total,
            "land_share_pct": round(razor5_2025_land / razor5_2025_total * 100, 2) if razor5_2025_total else None,
            "improvement_share_pct": round(razor5_2025_impr / razor5_2025_total * 100, 2) if razor5_2025_total else None,
        },
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
