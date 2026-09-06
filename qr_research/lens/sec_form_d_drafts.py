"""Scanner events from SEC Form D — every regional private offering surfaces (rare by design)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from qr_research.connectors.base import COUNTIES, DB_PATH


def _c(**kw) -> dict:
    base = {
        "feed": "scanner", "candidate_type": "event", "source": "sec_form_d",
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "new", "recipe_ids": [],
    }
    base.update(kw)
    return base


def main() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT accession, cik, issuer_name, state, city, zip5, county_fips, file_date, items FROM sec_form_d ORDER BY file_date DESC").fetchall()
    out = []
    for accession, cik, name, state, city, zip5, county_fips, file_date, items in rows:
        name = name.split("  (CIK")[0].strip()
        fips_list = [f for f in (county_fips or "").split(",") if f in COUNTIES]
        counties = [COUNTIES[f] for f in fips_list] or (["St. Joseph IN", "Elkhart IN", "Marshall IN"] if state == "IN" else ["Berrien MI", "Cass MI"])
        coverage = "Indiana counties only" if state == "IN" else "Michigan counties only (Berrien/Cass)"
        out.append(_c(
            candidate_id=f"scan-formd-{accession}",
            counties=counties,
            coverage_note=coverage,
            headline=f"{name} filed a Form D ({city}, {state}), {file_date}",
            why_it_might_matter=f"A private securities offering registered with an issuer address in {city}, {state} — new capital being raised by an entity based in the region. Filing items: {items or 'none listed'}. Worth a look at who's behind it and what the raise is for; Form D itself doesn't disclose amount reliably (issuers often decline to specify).",
            axis_a=["source", "type"], axis_b=["unmeasured"], function=["Circulation"], stock_or_flow="flow",
            evidence_urls=[f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=D"],
            confidence="solid", screen_result="surface",
        ))
    json.dump(out, open("examples/sec_form_d_candidates.json", "w"), indent=1)
    for c in out:
        print(f"[{c['screen_result']:7}] {c['headline']}")
    return out


if __name__ == "__main__":
    main()
