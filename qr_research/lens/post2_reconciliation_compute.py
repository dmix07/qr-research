"""Verification recompute for LinkedIn Post 2 — same bar as post1_reconciliation_compute.py,
extended across every available assessment year (2020-2025) plus a named-parcel decomposition
of the St. Joseph industrial value-local% move (the "Razor5" worked example).

Same three code paths as Post 1, now parametrized by year:
  A. RECIPE     — classify() from gateway_drafts.py (what's published).
  B. ZIP-SET    — pure SQL, owner_zip5 IN the region's own property-ZIP set for that year.
  C. CITY/STATE — pure SQL, owner_city (normalized) IN the region's own property-city set for
                  that year, AND owner_state='IN'.

Read-only. Not wired into run.py/Makefile. Prints one JSON blob to stdout.
"""
from __future__ import annotations

import json
import sqlite3

from qr_research.connectors.base import COUNTIES, DB_PATH
from qr_research.connectors.gateway import BUSINESS_RE, norm_name
from qr_research.lens.gateway_commercial_industrial_locality import CLASSES, count_vs_value_local_share

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
COUNTY_FIPS = {"St. Joseph IN": "18141", "Elkhart IN": "18039", "Marshall IN": "18099"}
ALL_FIPS = list(COUNTY_FIPS.values())
ALL_CELLS = [(county, cls) for cls in CLASSES for county in COUNTY_FIPS]


def method_a_recipe(conn: sqlite3.Connection, year: int) -> dict:
    return {(r["county"], r["class"]): r for r in count_vs_value_local_share(conn, year)}


def _zips_sql(year: int) -> str:
    return f"""(SELECT DISTINCT prop_zip5 FROM gateway_parcels
                WHERE assessment_year={year} AND prop_zip5 != '' AND county_fips IN ({','.join('?' * len(ALL_FIPS))}))"""


def _cities_sql(year: int) -> str:
    return f"""(SELECT DISTINCT UPPER(TRIM(prop_city)) FROM gateway_parcels
                WHERE assessment_year={year} AND prop_city != '' AND county_fips IN ({','.join('?' * len(ALL_FIPS))}))"""


def method_b_zipset(conn: sqlite3.Connection, year: int) -> dict:
    out = {}
    zsql = _zips_sql(year)
    for county, cls in ALL_CELLS:
        fips = COUNTY_FIPS[county]
        lo, hi = CLASSES[cls]
        q = f"""SELECT COUNT(*) n,
                       SUM(CASE WHEN owner_zip5 IN {zsql} THEN 1 ELSE 0 END) local_n,
                       SUM(COALESCE(av_total,0)) total_av,
                       SUM(CASE WHEN owner_zip5 IN {zsql} THEN COALESCE(av_total,0) ELSE 0 END) local_av
                FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?"""
        params = (*ALL_FIPS, *ALL_FIPS, year, fips, lo, hi)
        n, local_n, total_av, local_av = conn.execute(q, params).fetchone()
        out[(county, cls)] = {
            "n": n, "count_local_pct": local_n / n if n else None,
            "value_local_pct": local_av / total_av if total_av else None,
            "total_av": total_av, "local_av": local_av,
        }
    return out


def method_c_city_state(conn: sqlite3.Connection, year: int) -> dict:
    out = {}
    csql = _cities_sql(year)
    for county, cls in ALL_CELLS:
        fips = COUNTY_FIPS[county]
        lo, hi = CLASSES[cls]
        q = f"""SELECT COUNT(*) n,
                       SUM(CASE WHEN UPPER(TRIM(owner_city)) IN {csql} AND UPPER(TRIM(owner_state))='IN' THEN 1 ELSE 0 END) local_n,
                       SUM(COALESCE(av_total,0)) total_av,
                       SUM(CASE WHEN UPPER(TRIM(owner_city)) IN {csql} AND UPPER(TRIM(owner_state))='IN' THEN COALESCE(av_total,0) ELSE 0 END) local_av
                FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?"""
        params = (*ALL_FIPS, *ALL_FIPS, year, fips, lo, hi)
        n, local_n, total_av, local_av = conn.execute(q, params).fetchone()
        out[(county, cls)] = {
            "n": n, "count_local_pct": local_n / n if n else None,
            "value_local_pct": local_av / total_av if total_av else None,
        }
    return out


def value_coverage(conn: sqlite3.Connection, year: int) -> dict:
    out = {}
    for county, cls in ALL_CELLS:
        fips = COUNTY_FIPS[county]
        lo, hi = CLASSES[cls]
        n, populated = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN av_total IS NOT NULL AND av_total>0 THEN 1 ELSE 0 END) "
            "FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?",
            (year, fips, lo, hi)).fetchone()
        out[(county, cls)] = {"n": n, "populated": populated, "coverage_pct": populated / n if n else None}
    return out


def razor5_by_year(conn: sqlite3.Connection) -> dict:
    fips = COUNTY_FIPS["St. Joseph IN"]
    lo, hi = CLASSES["industrial"]
    zips_by_year = {y: {z for (z,) in conn.execute(
        f"SELECT DISTINCT prop_zip5 FROM gateway_parcels WHERE assessment_year={y} AND prop_zip5!='' AND county_fips IN ({','.join('?' * len(ALL_FIPS))})",
        ALL_FIPS)} for y in YEARS}

    out = {}
    for y in YEARS:
        rows = conn.execute(
            """SELECT parcel_number, owner_name, owner_address, owner_city, owner_state, owner_zip5, av_total, property_class
               FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?""",
            (y, fips, lo, hi)).fetchall()
        total_av = sum(r[6] or 0 for r in rows)
        razor5_rows = [r for r in rows if "RAZOR5" in (r[1] or "").upper()]
        razor5_av = sum(r[6] or 0 for r in razor5_rows)
        razor5_local = all(r[5] in zips_by_year[y] for r in razor5_rows) if razor5_rows else None

        # value-local% with vs without Razor5 (Razor5, when present, is non-local -> only ever
        # subtracts from the denominator, never the numerator)
        local_av_with = sum(r[6] or 0 for r in rows if r[5] in zips_by_year[y])
        value_local_with = local_av_with / total_av if total_av else None
        total_av_without = total_av - razor5_av
        local_av_without = local_av_with - sum(r[6] or 0 for r in razor5_rows if r[5] in zips_by_year[y])
        value_local_without = local_av_without / total_av_without if total_av_without else None

        # who else is big: aggregate by normalized owner name, find the single largest owner's
        # total share of this year's St. Joseph industrial value
        owner_totals: dict[str, float] = {}
        owner_display: dict[str, str] = {}
        owner_local: dict[str, bool] = {}
        for r in rows:
            nn = norm_name(r[1] or "") or (r[1] or "").strip().upper()
            owner_totals[nn] = owner_totals.get(nn, 0) + (r[6] or 0)
            owner_display.setdefault(nn, r[1])
            owner_local.setdefault(nn, r[5] in zips_by_year[y])
        top_owners = sorted(owner_totals.items(), key=lambda kv: -kv[1])[:5]
        top_owners_out = [{"owner": owner_display[nn], "total_av": v, "share_of_total": v / total_av if total_av else None,
                            "local": owner_local[nn]} for nn, v in top_owners]

        out[y] = {
            "total_industrial_av": total_av,
            "razor5_parcel_count": len(razor5_rows),
            "razor5_total_av": razor5_av,
            "razor5_share_of_total": razor5_av / total_av if total_av and razor5_rows else 0.0,
            "razor5_local": razor5_local,
            "razor5_parcels": [{"parcel": r[0], "owner_name": r[1], "owner_address": r[2], "owner_city": r[3],
                                 "owner_state": r[4], "owner_zip5": r[5], "av_total": r[6], "property_class": r[7]} for r in razor5_rows],
            "value_local_pct_with_razor5": value_local_with,
            "value_local_pct_without_razor5": value_local_without,
            "top_5_owners_by_value": top_owners_out,
        }
    return out


def _key_to_str(d: dict) -> dict:
    return {f"{k[0]}|{k[1]}": v for k, v in d.items()}


def main() -> dict:
    conn = sqlite3.connect(DB_PATH)
    by_year = {}
    for y in YEARS:
        by_year[y] = {
            "method_a_recipe": _key_to_str(method_a_recipe(conn, y)),
            "method_b_zipset": _key_to_str(method_b_zipset(conn, y)),
            "method_c_city_state": _key_to_str(method_c_city_state(conn, y)),
            "value_coverage": _key_to_str(value_coverage(conn, y)),
        }
    return {"years": YEARS, "by_year": by_year, "razor5_by_year": razor5_by_year(conn)}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
