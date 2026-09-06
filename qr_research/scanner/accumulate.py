"""Accumulation candidates (spec Part I §6.3): >=2 Scanner events from >=2 sources hitting the
same entity within 24 months -> one candidate_type=accumulation candidate linking them.

Matches by normalized name (gateway.norm_name) + county, not a shared ID — no single ID type
(EIN, CIK, docket number, Gateway parcel owner) exists across every source, so name+county is
the common ground, and the candidate says so as a caveat rather than implying certainty.

Persons are never entities: every source feeding this already excludes them at generation time
(bankruptcy's BUSINESS_RE filter, IRS 990/Gateway-finance being government or nonprofit filers,
Form D issuer names, FDIC institution names) — this module does no person/business judgment of
its own, it only matches names sources have already vetted as non-individual.

Reads every examples/*_candidates.json a drafts module wrote — each scanner event candidate
carries entity_name/entity_county_fips/event_date for exactly this purpose.
"""
from __future__ import annotations

import glob
import json
from datetime import datetime, timezone
from itertools import combinations

from qr_research.connectors.base import COUNTIES
from qr_research.connectors.gateway import norm_name

WINDOW_DAYS = 730  # 24 months


def _load_events() -> list[dict]:
    out = []
    for path in glob.glob("examples/*_candidates.json"):
        try:
            cands = json.load(open(path))
        except (json.JSONDecodeError, FileNotFoundError):
            continue
        for c in cands:
            if c.get("feed") == "scanner" and c.get("candidate_type") == "event" and c.get("entity_name"):
                out.append(c)
    return out


def _fips_for(c: dict) -> str:
    fips = c.get("entity_county_fips") or ""
    if fips:
        return fips
    for name in c.get("counties", []):
        for f, n in COUNTIES.items():
            if n == name:
                return f
    return ""


def _parse_date(s: str):
    try:
        return datetime.strptime((s or "")[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def find_accumulations() -> list[dict]:
    events = _load_events()
    groups: dict[tuple[str, str], list[dict]] = {}
    for c in events:
        nn = norm_name(c["entity_name"])
        fips = _fips_for(c)
        if not nn or not fips:
            continue
        groups.setdefault((nn, fips), []).append(c)

    out = []
    for (nn, fips), members in groups.items():
        sources = {m["source"] for m in members}
        if len(members) < 2 or len(sources) < 2:
            continue
        dated = [(m, _parse_date(m.get("event_date", ""))) for m in members]
        dated = [(m, d) for m, d in dated if d]
        if len(dated) < 2:
            continue
        dated.sort(key=lambda md: md[1])
        within_window = any(abs((d2 - d1).days) <= WINDOW_DAYS for (_, d1), (_, d2) in combinations(dated, 2))
        if not within_window:
            continue

        display_name = members[0]["entity_name"]
        related_ids = [m["candidate_id"] for m in members]
        source_list = sorted(sources)
        detail_lines = "; ".join(f"{m['source']}: {m['headline']}" for m in members)
        out.append({
            "feed": "scanner", "candidate_type": "accumulation",
            "candidate_id": f"accum-{fips}-{nn.replace(' ', '')[:40]}",
            "source": "+".join(source_list), "counties": [COUNTIES.get(fips, fips)],
            "coverage_note": "Entity match by normalized name + county across independently built sources — a name match, not a shared legal ID (no EIN/CIK/docket number common to every source).",
            "headline": f"{display_name} shows up in {len(source_list)} sources within 24 months: {', '.join(source_list)}",
            "why_it_might_matter": f"Related candidates: {', '.join(related_ids)}. {detail_lines}",
            "axis_a": ["control", "distribution"], "axis_b": ["connected", "large"], "function": ["Stewardship"],
            "evidence_urls": sorted({u for m in members for u in m.get("evidence_urls", [])}),
            "recipe_ids": [], "related_candidates": related_ids,
            "confidence": "soft", "screen_result": "surface",
            "created_at": datetime.now(timezone.utc).isoformat(), "status": "new",
        })
    return out


def main() -> list[dict]:
    out = find_accumulations()
    json.dump(out, open("examples/accumulation_candidates.json", "w"), indent=1)
    for c in out:
        print(f"[{c['screen_result']:7}] {c['headline']}")
    return out


if __name__ == "__main__":
    main()
