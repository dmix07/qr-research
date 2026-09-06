"""Scanner events from Indiana Gateway local finance (budgets, debt) — TIF-district and
debt-issuance activity in the three IN counties.

Within-run (year-over-year, both years already loaded by the connector):
  - new TIF-tagged fund this year that wasn't in last year's budget -> "new TIF district"
  - TIF-tagged fund's tax levy or total budget moved >20% year over year -> "TIF/redevelopment
    revenue change"
Across-run (via the generic vintage diff in scanner/diff.py, same as every other source):
  - a debt row that's new since the last scheduled run -> "new debt issuance"
First run therefore surfaces TIF-fund events (two years of budget data exist immediately) but
no debt events (debt is only fetched for one year; "new" needs a prior run to compare against).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from qr_research.connectors.base import COUNTIES
from qr_research.scanner.diff import detect_changes

URL = "https://gateway.ifionline.org/public/download.aspx"
THRESHOLD = 0.20


def _c(**kw) -> dict:
    base = {
        "feed": "scanner", "candidate_type": "event", "source": "in_gateway_finance",
        "coverage_note": "Indiana counties only (Berrien, Cass not covered — Michigan Treasury local-unit finance is a separate, unbuilt source)",
        "created_at": datetime.now(timezone.utc).isoformat(), "status": "new",
        "evidence_urls": [URL], "recipe_ids": [],
    }
    base.update(kw)
    return base


def _pct_change(new: float | None, old: float | None) -> float | None:
    if not old:
        return None
    if new is None:
        return None
    return (new - old) / old


def tif_fund_events(conn: sqlite3.Connection) -> list[dict]:
    years = [y for (y,) in conn.execute("SELECT DISTINCT year FROM gateway_budget ORDER BY year DESC").fetchall()]
    if len(years) < 2:
        return []
    latest, prior = years[0], years[1]
    cur = {(fips, unit, fund): (name, taxes, total) for fips, unit, name, fund, taxes, total in conn.execute(
        "SELECT county_fips, unit_code, unit_name, fund_cd, taxes_to_be_collected_adopted, total_budget_adopted "
        "FROM gateway_budget WHERE year=? AND is_tif_related=1", (latest,)).fetchall()}
    prev = {(fips, unit, fund): (taxes, total) for fips, unit, fund, taxes, total in conn.execute(
        "SELECT county_fips, unit_code, fund_cd, taxes_to_be_collected_adopted, total_budget_adopted "
        "FROM gateway_budget WHERE year=? AND is_tif_related=1", (prior,)).fetchall()}
    out = []
    for (fips, unit, fund), (name, taxes, total) in cur.items():
        if (fips, unit, fund) not in prev:
            out.append(_c(
                candidate_id=f"scan-gwf-newtif-{fips}-{unit}-{fund}-{latest}",
                counties=[COUNTIES[fips]], entity_name=name.strip(), entity_county_fips=fips, event_date=f"{latest}-01-01",
                headline=f"New TIF/redevelopment budget line: {name.strip()} ({latest})",
                why_it_might_matter=f"A TIF- or redevelopment-tagged fund appears in {latest}'s budget for {name.strip()} that wasn't in {prior}'s — either a new TIF district or a new fund inside an existing one. Adopted budget: ${total or 0:,.0f}; tax levy: ${taxes or 0:,.0f}. Worth confirming against the unit's TIF district records (not available as a separate Gateway dataset — see DECISIONS.md).",
                axis_a=["destination", "type"], axis_b=["unmeasured"], function=["Regeneration"], stock_or_flow="flow",
                confidence="soft", screen_result="surface",
            ))
            continue
        p_taxes, p_total = prev[(fips, unit, fund)]
        for label, n, o in (("tax levy", taxes, p_taxes), ("total budget", total, p_total)):
            chg = _pct_change(n, o)
            if chg is not None and abs(chg) >= THRESHOLD:
                out.append(_c(
                    candidate_id=f"scan-gwf-tifchange-{fips}-{unit}-{fund}-{label.replace(' ', '')}-{latest}",
                    counties=[COUNTIES[fips]], entity_name=name.strip(), entity_county_fips=fips, event_date=f"{latest}-01-01",
                    headline=f"{name.strip()} {label} {'up' if chg > 0 else 'down'} {abs(chg):.0%} ({prior}→{latest})",
                    why_it_might_matter=f"TIF/redevelopment fund '{name.strip()}' {label} moved {chg:+.0%} year over year (${o:,.0f} → ${n:,.0f}). A swing this size in a redevelopment fund usually means a new project, a bond draw, or a district winding down.",
                    axis_a=["destination", "distribution"], axis_b=["large" if abs(chg) >= 0.5 else "unmeasured"],
                    function=["Regeneration"], stock_or_flow="flow", confidence="soft", screen_result="surface",
                ))
    return out


def debt_events(conn: sqlite3.Connection) -> list[dict]:
    diff = detect_changes("in_gateway_finance")
    if diff["status"] != "diffed":
        return []
    rows = conn.execute("SELECT source_id, key, before, after FROM changes WHERE source_id='in_gateway_finance' AND key LIKE 'debt:%' AND change='added' ORDER BY seen_at DESC").fetchall()
    out = []
    for _, key, _, after in rows:
        p = json.loads(after)
        fips = {"20": "18039", "50": "18099", "71": "18141"}[p["county_cd_fk"]]
        desc = p["debt_description"].strip()
        out.append(_c(
            candidate_id=f"scan-gwf-newdebt-{key.split(':', 1)[1]}",
            counties=[COUNTIES[fips]], entity_name=p['unit_name'].strip(), entity_county_fips=fips, event_date=f"{p['year']}-01-01",
            headline=f"New debt on record: {p['unit_name'].strip()} — {desc}",
            why_it_might_matter=f"{p['unit_name'].strip()} reported a debt instrument not present in the prior Annual Financial Report: {desc}. Outstanding balance ${float(p.get('end_principal_bal') or 0):,.0f}.",
            axis_a=["source", "type"], axis_b=["connected"] if "TIF" in desc.upper() or "REDEVELOPMENT" in desc.upper() else ["unmeasured"],
            function=["Regeneration"] if "TIF" in desc.upper() or "REDEVELOPMENT" in desc.upper() else ["Stewardship"],
            stock_or_flow="flow", confidence="solid", screen_result="surface",
        ))
    return out


def main() -> list[dict]:
    from qr_research.connectors.base import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    out = tif_fund_events(conn) + debt_events(conn)
    json.dump(out, open("examples/gateway_finance_candidates.json", "w"), indent=1)
    for c in out:
        print(f"[{c['screen_result']:7}] {c['headline']}")
    return out


if __name__ == "__main__":
    main()
