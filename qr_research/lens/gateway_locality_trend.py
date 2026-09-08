"""County x class x year trend: count-local% and value-local%, 2020 pay 2021 through 2025 pay
2026 — the only six vintages Gateway's Real Property download actually has (DECISIONS.md #75).

Loops the existing, unmodified `value_coverage()` and `count_vs_value_local_share()` from
gateway_commercial_industrial_locality.py per year and pivots into county x class rows with
one column per year. Does not read or import anything acreage-related — see DECISIONS.md #90.

NOT wired into run.py/Makefile: a one-off trend read, not a recurring build.
"""
from __future__ import annotations

import sqlite3

from qr_research.connectors.base import COUNTIES, DB_PATH
from qr_research.lens.gateway_commercial_industrial_locality import (
    CLASSES, COUNTY_FIPS_ORDER, count_vs_value_local_share, value_coverage,
)

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
ROW_KEYS = [(fips, cls) for cls in CLASSES for fips in COUNTY_FIPS_ORDER]


def build_trend(conn: sqlite3.Connection, years: list[int] = YEARS) -> dict:
    by_year_coverage = {y: {(r["county"], r["class"]): r for r in value_coverage(conn, y)} for y in years}
    by_year_shares = {y: {(r["county"], r["class"]): r for r in count_vs_value_local_share(conn, y)} for y in years}
    return {"coverage": by_year_coverage, "shares": by_year_shares}


def print_pivot(title: str, data: dict, field: str, fmt: str, years: list[int] = YEARS) -> None:
    print(f"\n{title}")
    hdr = f"{'county':14} {'class':11}" + "".join(f"{y:>9}" for y in years)
    print(hdr); print("-" * len(hdr))
    for fips, cls in ROW_KEYS:
        county = COUNTIES[fips]
        cells = []
        for y in years:
            row = data[y].get((county, cls))
            v = row[field] if row else None
            cells.append(fmt.format(v) if v is not None else "n/a")
        print(f"{county:14} {cls:11}" + "".join(f"{c:>9}" for c in cells))


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    trend = build_trend(conn)
    print_pivot("COUNT-LOCAL % (share of parcels owned locally)", trend["shares"], "count_local_pct", "{:.1%}")
    print_pivot("VALUE-LOCAL % (share of assessed value owned locally)", trend["shares"], "value_local_pct", "{:.1%}")
    print_pivot("VALUE-FIELD COVERAGE % (av_total populated & > 0)", trend["coverage"], "value_coverage_pct", "{:.1%}")
