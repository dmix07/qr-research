"""Scanner events from IRS 990 filings — nonprofits whose total assets moved >25% year over year.

Only total assets is used (see connectors/irs_990.py docstring — grants paid isn't a common
field outside Form 990-PF filers). A candidate only exists when both years' data are on file
and the change clears the threshold; most matched nonprofits never produce one.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from qr_research.connectors.base import COUNTIES, DB_PATH

THRESHOLD = 0.25


def _c(**kw) -> dict:
    base = {
        "feed": "scanner", "candidate_type": "event", "source": "irs_990",
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "new", "recipe_ids": [],
    }
    base.update(kw)
    return base


def main() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""SELECT ein, name, city, county_fips, latest_year, latest_assets, prior_year, prior_assets, pct_change
        FROM irs_990 WHERE pct_change IS NOT NULL ORDER BY ABS(pct_change) DESC""").fetchall()
    out = []
    for ein, name, city, fips, ly, la, py, pa, chg in rows:
        if abs(chg) < THRESHOLD:
            continue
        small_base_caveat = " (small prior-year base — a large percentage here can still be a small dollar move)" if pa and pa < 50000 else ""
        out.append(_c(
            candidate_id=f"scan-990-{ein}",
            counties=[COUNTIES.get(fips, fips)],
            headline=f"{name.title()} total assets {'up' if chg > 0 else 'down'} {abs(chg):.0%} ({py}→{ly})",
            why_it_might_matter=f"{name.title()} ({city.title()}) reported total assets of ${la:,.0f} in its {ly} Form 990, versus ${pa:,.0f} in {py} — a {chg:+.0%} change{small_base_caveat}. Worth checking what drove it: a bequest, a capital campaign, a program wind-down, or a merger.",
            axis_a=["ownership", "distribution"], axis_b=["large" if abs(chg) >= 1.0 else "unmeasured"],
            function=["Stewardship"], stock_or_flow="stock",
            evidence_urls=[f"https://projects.propublica.org/nonprofits/organizations/{ein}"],
            confidence="soft", screen_result="surface",
        ))
    json.dump(out, open("examples/irs_990_candidates.json", "w"), indent=1)
    for c in out:
        print(f"[{c['screen_result']:7}] {c['headline']}")
    return out


if __name__ == "__main__":
    main()
