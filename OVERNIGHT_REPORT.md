# OVERNIGHT_REPORT.md — Scanner Phase 2, Sept 5–6 2026

## What got built

Six required event sources, in the order given, each with a connector + health check + tests +
draft-candidate generator, wired into `run.py`/`Makefile`, plus accumulation matching across all
of them. Deployed to the server, run for real, delivered to Airtable. Full decision log in
`DECISIONS.md` (#47–73); source-by-source detail in `STATUS.md`.

| Source | Built? | Delivered (live) |
|---|---|---|
| Indiana Gateway local finance (budgets + debt) | yes — `in_gateway_finance` | 4 |
| SEC EDGAR Form D | yes — `sec_form_d` | 59 |
| Bankruptcy (CourtListener) | yes — `bankruptcy` | 6 |
| IEDC transparency portal | **dropped** — bot-blocked API, no bulk file | — |
| USASpending | yes — `usaspending` | 669 |
| IRS 990 | yes — `irs_990` | 444 |
| Michigan Treasury (stretch) | **not attempted** — `michigan.gov` 403'd immediately | — |
| Accumulation (cross-source entity matching) | yes — `scanner/accumulate.py` | 2 |
| *(re-delivered: fdic, gateway parcels)* | already existed | 6 + 16 |

**Total: 1,206 candidates**, all `status=new` in Airtable base `appBVtPxGG9DJpnxL`, health `ok` on
all 8 sources.

**Screening gap — the one thing to act on first:** the Anthropic account ran out of credits
partway through (444 IRS-990 candidates is a lot of LLM calls). 34 candidates got real rubric
screening; **1,172 (irs_990, sec_form_d, usaspending) are rules-screened only** and sit in the
Inbox tagged `surface` by their generator, not by the rubric. I fixed the code so this can't
crash the pipeline again, but the actual screening still needs credits — see `QUESTIONS.md` #5.
Everything else in this report is read from the *unscreened* data, so treat "surface" loosely.

## Three candidates worth a look first

1. **The accumulation mechanism found something real on its first live run.** Center for the
   Homeless and Oaklawn Psychiatric Center — both regional social-service nonprofits — each show
   up in both `irs_990` and `usaspending` within 24 months (candidate `accum-*`, source
   `irs_990+usaspending`). This is exactly what accumulation is for: two independently-built
   sources agreeing that the same entity had two kinds of activity. Worth checking what the
   federal money was for.
2. **New TIF-tagged budget lines in Goshen and Plymouth for FY2026**, alongside an Elkhart County
   bond explicitly named "Northeast Corridor TIF" already on the books — this is the original
   question behind the whole project, and it's now a live feed instead of a one-time #006-style
   pull.
3. **A cluster of same-family Form D filings**: "Sterling Self Storage Fund VII," "Sterling Real
   Estate Development Fund II," and two "Sterling Self Storage" feeder funds, all out of
   Mishawaka within about six weeks of each other; separately, two "Solyco Portfolio SPV" entities
   out of Rochester, MI. Same-source repeats like this don't qualify for accumulation (needs
   ≥2 *sources*), but an editor's eye would probably connect them faster than any of my code will.

## What I'm least sure about

- **USASpending's volume (669) and IRS-990's volume (444) are both much higher than I guessed
  before running them** — real, not a bug (AM General, Notre Dame, Honeywell, and Michigan DOT
  formula grants all genuinely clear the $250k floor; the region has more nonprofits than I
  expected). But 1,113 candidates from two sources in one run is a lot for a weekly cadence, and
  I don't know if that's a "this is what unmeasured actually looks like" fact about the region or
  a floor/cadence choice that needs revisiting once Dustin sees the kept-rate.
- **Bankruptcy and Form D county-tagging is text-search-derived, not address-verified** — no
  anonymous API gives a debtor's actual address for bankruptcy, so a match means "the region's
  name/ZIP appeared in this filing," not "the debtor is definitely there." A free CourtListener
  key would close that gap for bankruptcy; Form D's tagging *is* address-verified (I found and
  fixed a real false-positive there — see `DECISIONS.md` #53 — so that one I trust more).
- **Accumulation matches by name + county, not a shared ID** — it will occasionally over-match
  (two unrelated entities with genuinely similar names in the same county) or under-match (real
  name variants that don't normalize to the same string). The two matches tonight look right by
  inspection, but I haven't watched it run for months the way you'd need to trust its precision.
- **"Year over year" on IRS 990 sometimes spans more than a year** when a filer has gaps in
  electronic filing coverage — the headline always shows both years explicitly so it's visible,
  not hidden, but it means a few of the 444 aren't quite what the label implies at a glance.
