"""Verification recompute for LinkedIn Post 1 — independent of gateway_parcel_ownership's
code path (classify()/num() in lens/gateway_drafts.py), on purpose: the point is that a bug
in that shared function can't validate itself.

Three independent-ish computations of "local," all against gateway_parcels directly:
  A. RECIPE   — classify() from gateway_drafts.py (home+nearby by owner ZIP; what's published).
  B. ZIP-SET  — pure SQL, owner_zip5 IN (the region's own property-ZIP set). Mathematically
                equivalent to A's home+nearby definition (every "home" case is a "nearby" case
                too, since a matching prop_zip is trivially in the region ZIP set) but computed
                by SQL set membership, not a Python loop with address-number regex matching —
                a genuinely different code path, not a restatement of the same one.
  C. CITY/STATE — pure SQL, owner_city (normalized) IN (the region's own property-city set)
                AND owner_state='IN'. Independent of ZIP codes entirely.

Part 1 output: A vs B, per cell (the "recipe vs. independent recompute" table).
Part 2 output: C vs B, per cell (the "two-way denominator cross-check").
Part 3 output: Marshall industrial value-coverage bias check.

Read-only. Not wired into run.py/Makefile. Prints one JSON blob to stdout.
"""
from __future__ import annotations

import json
import re
import sqlite3

from qr_research.connectors.base import COUNTIES, DB_PATH
from qr_research.connectors.gateway import BUSINESS_RE
from qr_research.lens.gateway_commercial_industrial_locality import count_vs_value_local_share

YEAR = 2025
CLASSES = {"commercial": ("400", "499"), "industrial": ("300", "399")}
COUNTY_FIPS = {"St. Joseph IN": "18141", "Elkhart IN": "18039", "Marshall IN": "18099"}
ALL_FIPS = list(COUNTY_FIPS.values())

CELLS = [
    ("St. Joseph IN", "commercial"), ("Elkhart IN", "commercial"), ("Marshall IN", "commercial"),
    ("St. Joseph IN", "industrial"), ("Elkhart IN", "industrial"),
]


def method_a_recipe(conn: sqlite3.Connection) -> dict:
    rows = count_vs_value_local_share(conn, YEAR)
    return {(r["county"], r["class"]): r for r in rows}


def _region_zips_sql() -> str:
    return f"""(SELECT DISTINCT prop_zip5 FROM gateway_parcels
                WHERE assessment_year={YEAR} AND prop_zip5 != '' AND county_fips IN ({','.join('?' * len(ALL_FIPS))}))"""


def _region_cities_sql() -> str:
    return f"""(SELECT DISTINCT UPPER(TRIM(prop_city)) FROM gateway_parcels
                WHERE assessment_year={YEAR} AND prop_city != '' AND county_fips IN ({','.join('?' * len(ALL_FIPS))}))"""


def method_b_zipset(conn: sqlite3.Connection) -> dict:
    out = {}
    zips_sql = _region_zips_sql()
    for county, cls in CELLS:
        fips = COUNTY_FIPS[county]
        lo, hi = CLASSES[cls]
        q = f"""SELECT COUNT(*) n,
                       SUM(CASE WHEN owner_zip5 IN {zips_sql} THEN 1 ELSE 0 END) local_n,
                       SUM(COALESCE(av_total,0)) total_av,
                       SUM(CASE WHEN owner_zip5 IN {zips_sql} THEN COALESCE(av_total,0) ELSE 0 END) local_av
                FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?"""
        params = (*ALL_FIPS, *ALL_FIPS, YEAR, fips, lo, hi)
        n, local_n, total_av, local_av = conn.execute(q, params).fetchone()
        out[(county, cls)] = {
            "n": n, "count_local_pct": local_n / n if n else None,
            "value_local_pct": local_av / total_av if total_av else None,
            "total_av": total_av, "local_av": local_av,
        }
    return out


def method_c_city_state(conn: sqlite3.Connection) -> dict:
    out = {}
    cities_sql = _region_cities_sql()
    for county, cls in CELLS:
        fips = COUNTY_FIPS[county]
        lo, hi = CLASSES[cls]
        q = f"""SELECT COUNT(*) n,
                       SUM(CASE WHEN UPPER(TRIM(owner_city)) IN {cities_sql} AND UPPER(TRIM(owner_state))='IN' THEN 1 ELSE 0 END) local_n,
                       SUM(COALESCE(av_total,0)) total_av,
                       SUM(CASE WHEN UPPER(TRIM(owner_city)) IN {cities_sql} AND UPPER(TRIM(owner_state))='IN' THEN COALESCE(av_total,0) ELSE 0 END) local_av
                FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?"""
        params = (*ALL_FIPS, *ALL_FIPS, YEAR, fips, lo, hi)
        n, local_n, total_av, local_av = conn.execute(q, params).fetchone()
        out[(county, cls)] = {
            "n": n, "count_local_pct": local_n / n if n else None,
            "value_local_pct": local_av / total_av if total_av else None,
        }
    return out


def value_coverage(conn: sqlite3.Connection) -> dict:
    out = {}
    for county, cls in CELLS + [("Marshall IN", "industrial")]:
        fips = COUNTY_FIPS[county]
        lo, hi = CLASSES[cls]
        n, populated = conn.execute(
            "SELECT COUNT(*), SUM(CASE WHEN av_total IS NOT NULL AND av_total>0 THEN 1 ELSE 0 END) "
            "FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?",
            (YEAR, fips, lo, hi)).fetchone()
        out[(county, cls)] = {"n": n, "populated": populated, "coverage_pct": populated / n if n else None}
    return out


def marshall_industrial_bias(conn: sqlite3.Connection) -> dict:
    fips = COUNTY_FIPS["Marshall IN"]
    lo, hi = CLASSES["industrial"]
    rows = conn.execute(
        """SELECT parcel_number, property_class, owner_name, owner_zip5, prop_address, acres, av_total
           FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?""",
        (YEAR, fips, lo, hi)).fetchall()
    zips_row = conn.execute(f"SELECT * FROM {_region_zips_sql()}", (*ALL_FIPS,)).fetchall()
    region_zips = {z for (z,) in zips_row}

    missing = [r for r in rows if r[6] is None or r[6] == 0]
    present = [r for r in rows if r[6] is not None and r[6] > 0]

    def local_rate(group):
        n = len(group)
        loc = sum(1 for r in group if r[3] in region_zips)
        return loc / n if n else None

    def entity_rate(group):
        n = len(group)
        ent = sum(1 for r in group if BUSINESS_RE.search(r[2] or ""))
        return ent / n if n else None

    def class_dist(group):
        d: dict[str, int] = {}
        for r in group:
            d[r[1]] = d.get(r[1], 0) + 1
        return dict(sorted(d.items()))

    def acre_stats(group):
        vals = [r[5] for r in group if r[5]]
        return {"n_with_acreage": len(vals), "mean_acres": sum(vals) / len(vals) if vals else None}

    sample_missing = [{"parcel": r[0], "class": r[1], "owner_name": r[2], "owner_zip5": r[3], "prop_address": r[4]} for r in missing[:15]]

    return {
        "n_total": len(rows), "n_missing": len(missing), "n_present": len(present),
        "missing_local_rate": local_rate(missing), "present_local_rate": local_rate(present),
        "missing_entity_rate": entity_rate(missing), "present_entity_rate": entity_rate(present),
        "missing_class_distribution": class_dist(missing), "present_class_distribution": class_dist(present),
        "missing_acreage": acre_stats(missing), "present_acreage": acre_stats(present),
        "sample_missing_parcels": sample_missing,
    }


def _key_to_str(d: dict) -> dict:
    return {f"{k[0]}|{k[1]}": v for k, v in d.items()}


def main() -> dict:
    conn = sqlite3.connect(DB_PATH)
    a = method_a_recipe(conn)
    b = method_b_zipset(conn)
    c = method_c_city_state(conn)
    cov = value_coverage(conn)
    marshall = marshall_industrial_bias(conn)
    return {
        "year": YEAR,
        "method_a_recipe": _key_to_str({k: v for k, v in a.items() if k in CELLS}),
        "method_b_zipset": _key_to_str(b),
        "method_c_city_state": _key_to_str(c),
        "value_coverage": _key_to_str(cov),
        "marshall_industrial_bias": marshall,
    }


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
