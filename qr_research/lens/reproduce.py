"""Recompute published Observations #001 and #002 from raw FDIC pulls.

This is the Phase 0 acceptance test. It prints the figures and the published ones
side by side; any disagreement is written up in reference/reproduction_notes.md.
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict

from qr_research.connectors.base import COUNTY_FIPS, DB_PATH

REGION = tuple(COUNTY_FIPS)
Q = ",".join("?" * len(REGION))


def hq_institutions_by_year(conn: sqlite3.Connection) -> dict[int, int]:
    """Count institutions headquartered in the region active on June 30 of each year."""
    rows = conn.execute(
        f"SELECT established, ended, active FROM fdic_institutions WHERE hq_county_fips IN ({Q})", REGION
    ).fetchall()
    out = {}
    for year in range(1934, 2026):
        asof = f"{year}-06-30"
        n = 0
        for est, end, active in rows:
            if est and est <= asof and (active or not end or end > asof):
                n += 1
        out[year] = n
    return out


def deposits_by_control(conn: sqlite3.Connection, year: int) -> dict:
    """Regional deposits split by whether the institution is run from inside the region.

    'Run from here' = institution headquartered in one of the five counties. Holding-company
    HQ is reported alongside as a second, stricter reading (an institution HQ'd here but
    owned by a holding company elsewhere is 'here' on the first reading, 'elsewhere' on the second).
    """
    rows = conn.execute(
        f"""SELECT deposits_k, inst_hq_county_fips, holding_co_state, holding_co_city, holding_co
            FROM fdic_sod WHERE year=? AND branch_county_fips IN ({Q})""",
        (year, *REGION),
    ).fetchall()
    total = sum(r[0] for r in rows)
    local_inst = sum(r[0] for r in rows if r[1] in REGION)
    return {"year": year, "total_k": total, "local_inst_k": local_inst,
            "share_elsewhere_by_inst_hq": 1 - local_inst / total if total else None}


def region_share_of_us(conn: sqlite3.Connection) -> dict[int, float]:
    us = dict(conn.execute("SELECT year, us_deposits_k FROM fdic_us_deposits").fetchall())
    reg = dict(conn.execute(
        f"SELECT year, SUM(deposits_k) FROM fdic_sod WHERE branch_county_fips IN ({Q}) GROUP BY year", REGION
    ).fetchall())
    return {y: reg[y] / us[y] for y in sorted(reg) if y in us and us[y]}


def national_bank_share(conn: sqlite3.Connection, year: int, min_us_share: float = 0.0) -> dict:
    """For each holding company with branches in the region: what share of ITS total US deposits
    sit in our five counties. Weighted average across the large (national) ones."""
    reg = conn.execute(
        f"""SELECT holding_co_rssd, holding_co, SUM(deposits_k) FROM fdic_sod
            WHERE year=? AND branch_county_fips IN ({Q}) AND holding_co_rssd IS NOT NULL AND holding_co_rssd != 0
            GROUP BY holding_co_rssd""", (year, *REGION)).fetchall()
    return {"year": year, "holding_companies_present": len(reg), "note": "per-HC national totals need one extra SOD aggregate pull per RSSDHCR; see reproduction_notes.md"}


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    hq = hq_institutions_by_year(conn)
    peak_year = max(hq, key=hq.get)
    latest_year = conn.execute("SELECT MAX(year) FROM fdic_sod").fetchone()[0]

    print("== Observation 001: How has ownership of our banks changed? ==")
    print(f"  Institutions headquartered in the five counties, peak: {hq[peak_year]} in {peak_year}   (published: 47, ~50 years ago)")
    print(f"  Today (June {latest_year}): {hq[latest_year]}   (published: 4)")
    for y in (1975, 1985, 1994, 2005, 2015, latest_year):
        print(f"    {y}: {hq[y]}")
    d = deposits_by_control(conn, latest_year)
    print(f"  Share of regional deposits at institutions run from elsewhere ({latest_year}): {d['share_elsewhere_by_inst_hq']:.0%}   (published: 59¢ of every $1)")

    print("\n== Observation 002: Do our deposits matter to the big banks? ==")
    sh = region_share_of_us(conn)
    first, last = min(sh), max(sh)
    print(f"  Region's share of US deposits, {first}: 1 in {1/sh[first]:,.0f}   (published: about 1 in 500)")
    print(f"  Region's share of US deposits, {last}: 1 in {1/sh[last]:,.0f}   (published: about 1 in 1,300)")
    print(f"  National-bank 18¢-per-$100 figure: {national_bank_share(conn, latest_year)['note']}")


if __name__ == "__main__":
    main()
