"""Commercial + industrial local-ownership share, by county, acreage-weighted vs
value-weighted, current assessment year only (2025 pay 2026).

One-off analysis answering a specific question (DECISIONS.md #84-onward): does the
"locals own the dirt, outsiders own the value" story hold for commercial/industrial
property? NOT wired into run.py/Makefile — this is a research question, not a Scanner/Lens
candidate generator yet. If the gap is real, the next build is the 2020-2025 time series;
if it isn't, this was the whole build.

Reuses classify()/num() from lens/gateway_drafts.py — same locality definition as the
published gateway_parcel_ownership recipe ('local' = home + nearby, i.e. owner mailing ZIP
falls within the three counties' own property-ZIP set). Not reinvented here.

Value-weighted uses av_total (total assessed value = land + improvements), not av_land or
av_improvements alone — see DECISIONS.md for why.
"""
from __future__ import annotations

import sqlite3

from qr_research.connectors.base import COUNTIES, DB_PATH
from qr_research.lens.gateway_drafts import classify

CLASSES = {"industrial": ("300", "399"), "commercial": ("400", "499")}
COUNTY_FIPS_ORDER = ["18141", "18039", "18099"]  # St. Joseph, Elkhart, Marshall


def _region_zips(conn: sqlite3.Connection, year: int) -> set[str]:
    return {z for (z,) in conn.execute(
        "SELECT DISTINCT prop_zip5 FROM gateway_parcels WHERE prop_zip5 != '' AND assessment_year=?",
        (year,)).fetchall()}


def run(conn: sqlite3.Connection, year: int) -> list[dict]:
    zips = _region_zips(conn, year)
    out = []
    for cls_name, (lo, hi) in CLASSES.items():
        for fips in COUNTY_FIPS_ORDER:
            rows = conn.execute(
                """SELECT prop_address, prop_zip5, owner_address, owner_zip5, owner_state, acres, av_total
                   FROM gateway_parcels
                   WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?""",
                (year, fips, lo, hi)).fetchall()
            n = len(rows)
            total_acres = sum(r[5] or 0 for r in rows)
            total_av = sum(r[6] or 0 for r in rows)
            acre_rows = [(pa, pz, oa, oz, st, acres) for pa, pz, oa, oz, st, acres, av in rows]
            av_rows = [(pa, pz, oa, oz, st, av) for pa, pz, oa, oz, st, acres, av in rows]
            acre_shares = classify(acre_rows, zips)
            av_shares = classify(av_rows, zips)
            acre_local = (acre_shares["home"] + acre_shares["nearby"]) if acre_shares else None
            av_local = (av_shares["home"] + av_shares["nearby"]) if av_shares else None
            gap = (acre_local - av_local) if (acre_local is not None and av_local is not None) else None
            acres_populated = sum(1 for r in rows if (r[5] or 0) > 0)
            out.append({
                "county": COUNTIES[fips], "class": cls_name, "parcel_count": n,
                "parcels_with_acreage": acres_populated,
                "total_acres": round(total_acres, 1), "total_assessed_value": total_av,
                "acreage_local_share": round(acre_local, 4) if acre_local is not None else None,
                "value_local_share": round(av_local, 4) if av_local is not None else None,
                "gap_acreage_minus_value": round(gap, 4) if gap is not None else None,
            })
    return out


def value_coverage(conn: sqlite3.Connection, year: int) -> list[dict]:
    """Check 1: what share of parcels have a populated, non-zero av_total?"""
    out = []
    for cls_name, (lo, hi) in CLASSES.items():
        for fips in COUNTY_FIPS_ORDER:
            rows = conn.execute(
                "SELECT av_total FROM gateway_parcels WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?",
                (year, fips, lo, hi)).fetchall()
            n = len(rows)
            populated = sum(1 for (av,) in rows if av is not None and av > 0)
            out.append({
                "county": COUNTIES[fips], "class": cls_name, "parcel_count": n,
                "value_populated": populated, "value_coverage_pct": round(populated / n, 4) if n else None,
                "publishable": (populated / n >= 0.95) if n else False,
            })
    return out


def count_vs_value_local_share(conn: sqlite3.Connection, year: int) -> list[dict]:
    """Check 2: share of PARCEL COUNT owned locally vs. share of assessed VALUE owned locally."""
    zips = _region_zips(conn, year)
    out = []
    for cls_name, (lo, hi) in CLASSES.items():
        for fips in COUNTY_FIPS_ORDER:
            rows = conn.execute(
                """SELECT prop_address, prop_zip5, owner_address, owner_zip5, owner_state, av_total
                   FROM gateway_parcels
                   WHERE assessment_year=? AND county_fips=? AND property_class BETWEEN ? AND ?""",
                (year, fips, lo, hi)).fetchall()
            n = len(rows)
            count_rows = [(pa, pz, oa, oz, st, 1) for pa, pz, oa, oz, st, av in rows]
            av_rows = [(pa, pz, oa, oz, st, av) for pa, pz, oa, oz, st, av in rows]
            count_shares = classify(count_rows, zips)
            av_shares = classify(av_rows, zips)
            count_local = (count_shares["home"] + count_shares["nearby"]) if count_shares else None
            val_local = (av_shares["home"] + av_shares["nearby"]) if av_shares else None
            diff = (count_local - val_local) if (count_local is not None and val_local is not None) else None
            out.append({
                "county": COUNTIES[fips], "class": cls_name, "parcel_count": n,
                "count_local_pct": round(count_local, 4) if count_local is not None else None,
                "value_local_pct": round(val_local, 4) if val_local is not None else None,
                "diff_count_minus_value": round(diff, 4) if diff is not None else None,
            })
    return out


def print_value_coverage(rows: list[dict]) -> None:
    hdr = f"{'county':14} {'class':11} {'n':>6} {'populated':>10} {'coverage':>9} {'publishable':>12}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        cov = f"{r['value_coverage_pct']:.1%}" if r["value_coverage_pct"] is not None else "n/a"
        print(f"{r['county']:14} {r['class']:11} {r['parcel_count']:>6} {r['value_populated']:>10} {cov:>9} {str(r['publishable']):>12}")


def print_count_vs_value(rows: list[dict]) -> None:
    hdr = f"{'county':14} {'class':11} {'n':>6} {'count-local%':>13} {'value-local%':>13} {'diff':>8}"
    print(hdr); print("-" * len(hdr))
    for r in rows:
        c = f"{r['count_local_pct']:.1%}" if r["count_local_pct"] is not None else "n/a"
        v = f"{r['value_local_pct']:.1%}" if r["value_local_pct"] is not None else "n/a"
        d = f"{r['diff_count_minus_value']:+.1%}" if r["diff_count_minus_value"] is not None else "n/a"
        print(f"{r['county']:14} {r['class']:11} {r['parcel_count']:>6} {c:>13} {v:>13} {d:>8}")


def print_table(rows: list[dict]) -> None:
    hdr = f"{'county':14} {'class':11} {'n':>6} {'acres':>10} {'av_total':>15} {'acre%':>7} {'val%':>7} {'gap':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        acre_pct = f"{r['acreage_local_share']:.1%}" if r["acreage_local_share"] is not None else "n/a"
        val_pct = f"{r['value_local_share']:.1%}" if r["value_local_share"] is not None else "n/a"
        gap_pct = f"{r['gap_acreage_minus_value']:+.1%}" if r["gap_acreage_minus_value"] is not None else "n/a"
        print(f"{r['county']:14} {r['class']:11} {r['parcel_count']:>6} {r['total_acres']:>10,.1f} {r['total_assessed_value']:>15,} {acre_pct:>7} {val_pct:>7} {gap_pct:>7}")


def main_checks() -> None:
    """Check 1 (value-field coverage) and Check 2 (count-local% vs value-local%) — no chart,
    no draft, no time series; just the two tables. See DECISIONS.md."""
    conn = sqlite3.connect(DB_PATH)
    year = conn.execute("SELECT MAX(assessment_year) FROM gateway_parcels").fetchone()[0]
    print(f"assessment_year = {year}\n")
    print("CHECK 1 — value-field coverage")
    print_value_coverage(value_coverage(conn, year))
    print("\nCHECK 2 — parcel-count local share vs value local share")
    print_count_vs_value(count_vs_value_local_share(conn, year))


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    year = conn.execute("SELECT MAX(assessment_year) FROM gateway_parcels").fetchone()[0]
    print(f"assessment_year = {year}\n")
    rows = run(conn, year)
    print_table(rows)
    for r in rows:
        cov = r["parcels_with_acreage"] / r["parcel_count"] if r["parcel_count"] else 0
        print(f"  [coverage] {r['county']} {r['class']}: {r['parcels_with_acreage']}/{r['parcel_count']} parcels ({cov:.0%}) have acreage > 0")
