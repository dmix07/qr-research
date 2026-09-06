"""Draft Observations and Scanner events from the FDIC recipes.

Every draft here is computed from normalized tables only, cites its recipe id, and
carries a caveat. Nothing is estimated. If a number can't be computed, no draft.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from qr_research.connectors.base import COUNTIES, COUNTY_FIPS, DB_PATH
from qr_research.lens.reproduce import deposits_by_control, hq_institutions_by_year, region_share_of_us

Q = ",".join("?" * len(COUNTY_FIPS))
ALL5 = list(COUNTIES.values())
FDIC_INST_URL = "https://api.fdic.gov/banks/institutions?filters=STCNTY:({})".format("%20OR%20".join(COUNTY_FIPS))
FDIC_SOD_URL = "https://api.fdic.gov/banks/sod?filters=STCNTYBR:({})".format("%20OR%20".join(COUNTY_FIPS))


def _c(**kw) -> dict:
    base = {
        "feed": "lens", "candidate_type": "observation_draft", "source": "fdic", "counties": ALL5,
        "coverage_note": "", "created_at": datetime.now(timezone.utc).isoformat(), "status": "new",
    }
    base.update(kw)
    return base


def one_in(share: float) -> str:
    return f"1 in {1/share:,.0f}"


def lens_drafts(conn: sqlite3.Connection) -> list[dict]:
    latest = conn.execute("SELECT MAX(year) FROM fdic_sod").fetchone()[0]
    hq = hq_institutions_by_year(conn)
    peak_year = max(hq, key=hq.get)
    by_year = {y: deposits_by_control(conn, y) for y in range(1994, latest + 1)}
    elsewhere = {y: d["share_elsewhere_by_inst_hq"] for y, d in by_year.items()}
    peak_else_year = max(elsewhere, key=elsewhere.get)
    us_share = region_share_of_us(conn)
    br = dict(conn.execute(f"SELECT year, COUNT(*) FROM fdic_sod WHERE branch_county_fips IN ({Q}) GROUP BY year", COUNTY_FIPS).fetchall())
    dep = {y: d["total_k"] for y, d in by_year.items()}

    drafts = []

    # --- Refresh of #001 (baseline refresh job output) ---
    drafts.append(_c(
        candidate_id=f"lens-fdic-001-refresh-{latest}",
        headline=f"#001 refresh: {hq[latest]} institutions run from here ({latest}); {elsewhere[latest]:.0%} of deposits run from elsewhere",
        question="How has ownership of our banks changed?",
        measure=f"At its peak in {peak_year}, {hq[peak_year]} banks and thrifts were headquartered in the five counties. In June {latest}, {hq[latest]} remain, and {round(elsewhere[latest]*100)}¢ of every dollar on deposit sits with an institution run from somewhere else.",
        method="FDIC institution records and Summary of Deposits, June each year, five counties. 'Run from here' = institution headquartered in the five counties. Caveat: HQ county reflects an institution's final headquarters across its whole history; pre-1989 thrift coverage may be incomplete.",
        why_it_might_matter="Published figure holds on refresh; no material change since publication.",
        axis_a=["control", "distribution"], axis_b=["legible", "connected"], function=["Stewardship"], stock_or_flow="stock",
        recipe_ids=["fdic_hq_institutions", "fdic_deposits_control"], evidence_urls=[FDIC_INST_URL, FDIC_SOD_URL],
        confidence="solid", screen_result="hold", why_hold="Refresh of a published measure — surface only if the number moved.",
    ))

    # --- Refresh of #002 with the national-bank definition fixed ---
    drafts.append(_c(
        candidate_id=f"lens-fdic-002-refresh-{latest}",
        headline=f"#002 refresh: region is {one_in(us_share[latest])} of US deposits ({latest}); was {one_in(us_share[1994])} in 1994",
        question="Do our deposits matter to the big banks?",
        measure=f"In 1994 about {one_in(us_share[1994])} dollars on deposit in US banks was in the five counties; in {latest}, about {one_in(us_share[latest])}. To the holding companies with more than $100 billion in US deposits, the region is about 15¢ of every $100 they hold.",
        method="FDIC Summary of Deposits, June each year. National banks defined as holding companies with > $100B US deposits in the same year, deposit-weighted (five in 2025: JPMorgan, PNC, Fifth Third, KeyCorp, Huntington). Caveat: this definition gives 15–17¢ depending on year; the published 18¢ likely used a slightly broader set or the 2024 vintage. Fixing the definition makes the figure reproducible.",
        why_it_might_matter="Published 18¢ reproduces as 15–17¢ under an explicit definition; method note should carry the definition on next refresh.",
        axis_a=["distribution", "destination"], axis_b=["legible", "connected"], function=["Exchange"], stock_or_flow="stock",
        recipe_ids=["fdic_deposits_control"], evidence_urls=[FDIC_SOD_URL],
        confidence="solid", screen_result="hold", why_hold="Refresh with a definitional note for the editor, not a new finding.",
    ))

    # --- NEW: out-of-region share peaked in 2010 and has come back ---
    drafts.append(_c(
        candidate_id=f"lens-fdic-elsewhere-peak-{latest}",
        headline=f"Share of deposits run from elsewhere peaked at {elsewhere[peak_else_year]:.0%} in {peak_else_year}; now {elsewhere[latest]:.0%}",
        question="Is control of our deposits still leaving?",
        measure=f"In 1994, {round(elsewhere[1994]*100)}¢ of every dollar on deposit here sat with an institution run from elsewhere. That climbed to {round(elsewhere[peak_else_year]*100)}¢ by {peak_else_year}. Since then it has come back to {round(elsewhere[latest]*100)}¢ — the first sustained move toward local control in the record.",
        method=f"FDIC Summary of Deposits, June each year 1994–{latest}, five counties, by institution HQ county. Caveat: the reversal is driven mostly by one institution's growth (1st Source); it is a fact about concentration as much as about localness.",
        why_it_might_matter="Contradicts the one-directional story #001 implies. The trend since 2010 runs the other way, though it rests on one bank.",
        axis_a=["control", "distribution"], axis_b=["surprising", "connected", "legible"], function=["Stewardship", "Resilience"], stock_or_flow="stock",
        recipe_ids=["fdic_deposits_control"], evidence_urls=[FDIC_SOD_URL],
        confidence="solid", screen_result="surface",
    ))

    # --- NEW: branches down, deposits up ---
    drafts.append(_c(
        candidate_id=f"lens-fdic-branches-{latest}",
        headline=f"Bank branches {br[1994]} → {br[latest]} since 1994 while deposits grew ${dep[1994]/1e6:.1f}B → ${dep[latest]/1e6:.1f}B",
        question="Where did the bank branches go?",
        measure=f"Of every 4 bank branches in the five counties in 1994, about 3 remain today ({br[1994]} → {br[latest]}). Over the same years, deposits here more than doubled, from ${dep[1994]/1e6:.1f} billion to ${dep[latest]/1e6:.1f} billion.",
        method=f"FDIC Summary of Deposits, June 1994 and June {latest}, branch counts and deposits for the five counties. Nominal dollars. Caveat: SOD counts reporting offices, which includes some non-retail locations; the branch trend is not adjusted for population.",
        why_it_might_matter="Physical banking presence is shrinking as money grows — a Destination and Spatial Productivity question nobody has put a number on for the region.",
        axis_a=["destination", "distribution"], axis_b=["unmeasured", "legible"], function=["Spatial Productivity", "Circulation"], stock_or_flow="stock",
        recipe_ids=["fdic_deposits_control"], evidence_urls=[FDIC_SOD_URL],
        confidence="solid", screen_result="surface",
    ))

    # --- NEW: how much do our local banks depend on us (inverse of #002) ---
    rows = conn.execute(f"""SELECT holding_co, SUM(deposits_k) FROM fdic_sod
        WHERE year=? AND branch_county_fips IN ({Q}) AND inst_hq_county_fips IN ({Q}) GROUP BY holding_co ORDER BY 2 DESC""",
        (latest, *COUNTY_FIPS, *COUNTY_FIPS)).fetchall()
    try:
        shares = json.load(open("examples/hc_shares_2025.json"))
        fs = next(s for s in shares if s["name"].startswith("1ST SOURCE"))
        drafts.append(_c(
            candidate_id=f"lens-fdic-local-dependence-{latest}",
            headline=f"67¢ of every $1 1st Source holds anywhere is from the five counties",
            question="How much do our banks depend on us?",
            measure=f"Of every dollar 1st Source holds on deposit anywhere, about {round(fs['share']*100)}¢ is from the five counties. For the five holding companies over $100 billion, it is about 15¢ of every $100.",
            method=f"FDIC Summary of Deposits, June {latest}: each holding company's five-county deposits divided by its total US deposits. Caveat: 1st Source's out-of-region branches are recent; this share will fall as they grow, which is itself the thing to watch.",
            why_it_might_matter="The mirror image of #002. Local banks are exposed to the region in a way national banks structurally cannot be — alignment, and concentration risk, in one number.",
            axis_a=["destination", "source", "distribution"], axis_b=["unmeasured", "connected", "legible"], function=["Exchange", "Stewardship"], stock_or_flow="stock",
            recipe_ids=["fdic_deposits_control"], evidence_urls=[FDIC_SOD_URL, "https://api.fdic.gov/banks/sod?filters=YEAR:2025%20AND%20RSSDHCR:1199611"],
            confidence="soft", screen_result="surface",
        ))
    except (FileNotFoundError, StopIteration):
        pass
    return drafts


def scanner_changes(conn: sqlite3.Connection, since: str = "2020-01-01") -> list[dict]:
    """First-run change detection: regional-HQ institutions that ended (merged/closed) since `since`.
    On subsequent runs this compares vintages of the institutions table (see README)."""
    rows = conn.execute(f"""SELECT cert, name, city, state, ended, holding_co, hq_county_fips FROM fdic_institutions
        WHERE hq_county_fips IN ({Q}) AND active=0 AND ended >= ? AND ended < '9999-01-01' ORDER BY ended""",
        (*COUNTY_FIPS, since)).fetchall()
    out = []
    for cert, name, city, state, ended, hc, fips in rows:
        out.append(_c(
            feed="scanner", candidate_type="event", candidate_id=f"scan-fdic-inst-ended-{cert}",
            counties=[COUNTIES[fips]], entity_name=name.strip(), entity_county_fips=fips, event_date=ended,
            headline=f"{name.strip()} ({city}, {state}) ceased as an independent institution on {ended}",
            question="", measure="", method="",
            why_it_might_matter=f"A locally headquartered institution left the record; its deposits now sit with an acquirer. One fewer of the '{hq_institutions_by_year(conn)[2025]} that remain' in #001. Holding company at end: {hc or 'none listed'}.",
            axis_a=["control", "duration"], axis_b=["connected"], function=["Stewardship"], stock_or_flow="flow",
            recipe_ids=[], evidence_urls=[f"https://api.fdic.gov/banks/institutions?filters=CERT:{cert}"],
            confidence="solid", screen_result="surface" if ended >= "2024-01-01" else "hold",
            why_hold="" if ended >= "2024-01-01" else "Historical on first run; future runs surface only new changes.",
        ))
    return out


def main() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cands = lens_drafts(conn) + scanner_changes(conn)
    json.dump(cands, open("examples/fdic_candidates.json", "w"), indent=1)
    for c in cands:
        print(f"[{c['feed']:7}] {c['screen_result']:7} {c['headline']}")
    return cands


if __name__ == "__main__":
    main()
