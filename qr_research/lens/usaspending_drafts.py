"""Scanner events from USASpending — new federal grants/loans/contracts >= $250k in the region."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from qr_research.connectors.base import COUNTIES, DB_PATH

GROUP_LABEL = {"grants": "grant", "loans": "loan", "contracts": "contract"}


def _c(**kw) -> dict:
    base = {
        "feed": "scanner", "candidate_type": "event", "source": "usaspending",
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "new", "recipe_ids": [],
        "coverage_note": "Awards >= $250,000 only (a volume floor Dustin chose to keep this source's volume sane; see DECISIONS.md).",
    }
    base.update(kw)
    return base


def main() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""SELECT key, award_id, recipient_name, amount, awarding_agency, award_type, start_date,
        description, county_fips, award_group, url FROM usaspending_awards ORDER BY amount DESC""").fetchall()
    out = []
    for key, award_id, recipient, amount, agency, award_type, start_date, desc, fips, group, url in rows:
        label = GROUP_LABEL.get(group, group)
        out.append(_c(
            candidate_id=f"scan-usas-{key.split(':', 2)[-1].replace(' ', '_')[:60]}",
            counties=[COUNTIES.get(fips, fips)],
            headline=f"{recipient.title()} received a ${amount:,.0f} federal {label} ({agency})",
            why_it_might_matter=f"A federal {label} of ${amount:,.0f} to {recipient.title()} for work performed in {COUNTIES.get(fips, fips)}, from {agency}{' (' + award_type + ')' if award_type else ''}. {desc or 'No description on file.'} Worth checking whether this is new capacity, a research grant, or infrastructure work — and whether the recipient shows up elsewhere (Form D, bankruptcy, Gateway ownership).",
            axis_a=["source", "destination"], axis_b=["large" if amount >= 5_000_000 else "unmeasured"],
            function=["Circulation"], stock_or_flow="flow",
            evidence_urls=[url], confidence="solid", screen_result="surface",
        ))
    json.dump(out, open("examples/usaspending_candidates.json", "w"), indent=1)
    for c in out[:20]:
        print(f"[{c['screen_result']:7}] {c['headline']}")
    if len(out) > 20:
        print(f"... and {len(out) - 20} more")
    return out


if __name__ == "__main__":
    main()
