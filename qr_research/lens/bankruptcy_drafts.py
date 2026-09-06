"""Scanner events from CourtListener — new business bankruptcy filings in the region.

County tagging here is text-search-derived, not address-verified (see connectors/bankruptcy.py
docstring) — every candidate's coverage_note says so.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from qr_research.connectors.base import COUNTIES, DB_PATH

CHAPTER_LABEL = {"7": "Chapter 7 (liquidation)", "11": "Chapter 11 (reorganization)", "12": "Chapter 12 (family farmer/fisherman)"}


def _c(**kw) -> dict:
    base = {
        "feed": "scanner", "candidate_type": "event", "source": "bankruptcy",
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "new", "recipe_ids": [],
    }
    base.update(kw)
    return base


def main() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT docket_id, case_name, chapter, court_id, county_fips, date_filed, docket_number, url FROM bankruptcy_filings ORDER BY date_filed DESC").fetchall()
    out = []
    for docket_id, name, chapter, court_id, county_fips, date_filed, docket_number, url in rows:
        fips_list = [f for f in (county_fips or "").split(",") if f in COUNTIES]
        counties = [COUNTIES[f] for f in fips_list] or (["St. Joseph IN", "Elkhart IN", "Marshall IN"] if court_id == "innb" else ["Berrien MI", "Cass MI"])
        coverage = "County match is text-search-derived (no verified debtor address without a CourtListener API key — see QUESTIONS.md)."
        out.append(_c(
            candidate_id=f"scan-bk-{docket_id}",
            counties=counties, coverage_note=coverage,
            headline=f"{name} filed {CHAPTER_LABEL.get(chapter, 'Chapter ' + chapter)}, {date_filed}",
            why_it_might_matter=f"A business bankruptcy filing ({docket_number}, {'N.D. Indiana' if court_id == 'innb' else 'W.D. Michigan'}) with a debtor name/location matching the region. Chapter {chapter} filings are a leading indicator of local business distress — worth checking who the entity is, what it owes, and whether it's connected to any other candidate on file.",
            axis_a=["control", "duration"], axis_b=["unmeasured"], function=["Resilience"], stock_or_flow="flow",
            evidence_urls=[url], confidence="soft", screen_result="surface",
        ))
    json.dump(out, open("examples/bankruptcy_candidates.json", "w"), indent=1)
    for c in out:
        print(f"[{c['screen_result']:7}] {c['headline']}")
    return out


if __name__ == "__main__":
    main()
