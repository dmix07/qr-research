"""Pick at most 5 candidates a week for Dustin, out of everything the generators produced.

Every generator re-emits its full history each run (USAspending alone is ~670), and nobody can
review that. The full lists stay in examples/*_candidates.json and the SQLite DB for accumulation
and Lens work; only this pick goes to Airtable.

Rank (first wins):
  0. observation drafts tagged surface
  1. accumulations (one entity in >=2 sources)
  2. observation drafts tagged hold
  3. single-source events, at most one per source, in SOURCE_ORDER
Anything already delivered in an earlier week is skipped. The shortlist is screened (rubric.py)
in rank order until WEEKLY_CAP survive, so the LLM sees ~5-15 candidates a week, not ~800.

`python -m qr_research.screen.weekly_pick`                  -> writes examples/weekly_pick.json
`python -m qr_research.screen.weekly_pick --mark-delivered` -> run after a successful deliver
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timezone

from qr_research.connectors.base import db
from qr_research.screen import rubric

WEEKLY_CAP = 5
SHORTLIST = 15
OUT = "examples/weekly_pick.json"
# Rarer, more specific signals first; high-volume award feeds last.
SOURCE_ORDER = ["sec_form_d", "bankruptcy", "in_gateway_finance", "fdic", "irs_990", "usaspending"]


def _delivered() -> set[str]:
    conn = db()
    conn.execute("CREATE TABLE IF NOT EXISTS delivered (candidate_id TEXT PRIMARY KEY, delivered_at TEXT)")
    ids = {r[0] for r in conn.execute("SELECT candidate_id FROM delivered")}
    conn.close()
    return ids


def rank(cands: list[dict], already: set[str]) -> list[dict]:
    pool = [c for c in cands if c["candidate_id"] not in already and c.get("screen_result") != "kill"]
    drafts = [c for c in pool if c.get("candidate_type") == "observation_draft"]
    tiers = [
        [c for c in drafts if c.get("screen_result") == "surface"],
        [c for c in pool if c.get("candidate_type") == "accumulation"],
        [c for c in drafts if c.get("screen_result") == "hold"],
    ]
    events = [c for c in pool if c.get("candidate_type") == "event"]
    order = SOURCE_ORDER + sorted({c["source"] for c in events} - set(SOURCE_ORDER))
    first = {}
    for c in events:
        first.setdefault(c["source"], c)  # generators already sort by magnitude
    tiers.append([first[s] for s in order if s in first])
    seen, out = set(), []
    for tier in tiers:
        for c in tier:
            if c["candidate_id"] not in seen:
                seen.add(c["candidate_id"])
                out.append(c)
    return out


def pick(cands: list[dict], already: set[str], screen=rubric.screen) -> list[dict]:
    kept = []
    for c in rank(cands, already)[:SHORTLIST]:
        s = screen(c)
        if s.get("screen_result") != "kill":
            kept.append(s)
        if len(kept) == WEEKLY_CAP:
            break
    return kept


def mark_delivered() -> int:
    ids = [c["candidate_id"] for c in json.load(open(OUT))]
    _delivered()  # ensures table
    conn = db()
    now = datetime.now(timezone.utc).isoformat()
    conn.executemany("INSERT OR IGNORE INTO delivered VALUES (?, ?)", [(i, now) for i in ids])
    conn.commit()
    conn.close()
    return len(ids)


def main() -> list[dict]:
    cands = [c for f in sorted(glob.glob("examples/*_candidates.json")) for c in json.load(open(f))]
    out = pick(cands, _delivered())
    json.dump(out, open(OUT, "w"), indent=1)
    print(f"{len(cands)} candidates generated; this week's pick ({len(out)}):")
    for c in out:
        print(f"  [{c['screen_result']:7}] {c['source']:16} {c['headline']}")
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["--mark-delivered"]:
        print(f"marked {mark_delivered()} candidates delivered")
    else:
        main()
