"""One-off historical backfill of Gateway Real Property PARCEL files, three IN counties, for
every assessment year actually available (2020 pay 2021 through 2025 pay 2026 — confirmed
live, DECISIONS.md #75; there is no earlier vintage to reach for).

Feeds the count-local%/value-local% time series (DECISIONS.md). Reuses `GatewayConnector`'s
own download mechanics (`_form_state`/`_download`/`_lines`), `LAYOUT`, and `normalize()`/
`load()` unchanged — does not modify gateway.py, does not duplicate its parsing. The only
difference from the production connector's `fetch()` is looping over an explicit year list
instead of auto-detecting "latest only."

NOT wired into run.py/Makefile: this is a one-time backfill for a specific analysis, not a
recurring fetch — the weekly production connector still only pulls the latest year.

Deliberately does NOT call build_entities(): that aggregates owner_name by county_fips across
every row in gateway_parcels with no year filter, so running it after a 5-extra-year backfill
would silently change first_seen/parcel/av_total figures for every existing entity record.
Out of scope for this analysis; left untouched.
"""
from __future__ import annotations

import time

from qr_research.connectors.base import RawRecord
from qr_research.connectors.gateway import IN_COUNTIES, LAYOUT, URL, GatewayConnector, _slice, load

YEARS = ["2020", "2021", "2022", "2023", "2024", "2025"]


def backfill(years: list[str] = YEARS) -> dict[str, int]:
    gw = GatewayConnector()
    counts: dict[str, int] = {}
    for year in years:
        state, _latest = gw._form_state()  # fresh viewstate per year; ignore the auto-detected "latest"
        for code, fips in IN_COUNTIES.items():
            blob = gw._download(state, year, code)
            recs = []
            for line in gw._lines(blob):
                if line.startswith("PARCEL") or line.startswith("TRAILER"):
                    continue
                row = {name: _slice(line, s, e) for name, s, e in LAYOUT}
                row["assessment_year"] = int(year)
                row["county_fips"] = fips
                recs.append(RawRecord(gw.source_id, f"parcel:{year}:{fips}:{row['parcel_number']}", row, url=URL))
            load(gw, recs)
            counts[f"{year}:{fips}"] = len(recs)
            print(f"{year} county_fips={fips}: {len(recs)} parcels loaded")
            time.sleep(1.5)  # be a polite, identified scraper across 18 back-to-back downloads
    return counts


if __name__ == "__main__":
    print(backfill())
