# STATUS.md — what the system is, right now (Sept 6, 2026, post Scanner Phase 2)

This is the build ledger. Read it as: which parts of the spec exist, which are stubs, which aren't started.

## The system in one diagram

    [connectors] ──raw snapshots──▶ [normalized SQLite] ──▶ [recipes] ──▶ Lens skill ──▶ draft Observations ─┐
         │                                │                                                                   ├──▶ screener ──▶ Airtable queue
         └──────── vintage diff ──────────┴──────────────────────────────▶ Scanner events ────────────────────┘
    every connector ends in a health check; the workflow fails if any source isn't "ok"

## Layer by layer

| Layer | Spec ref | State | Notes |
|---|---|---|---|
| Connector interface | II §1 | **built, proven on 3 sources** | `connectors/base.py`. FDIC (Tier 1 API), Census (Tier 1 bulk), Gateway (Tier 2 form post) all implement it unchanged. |
| Raw storage (immutable snapshots) | II §1 | built | JSONL per run under `data/raw/<source>/<date>/` |
| Normalized store | II §1 | built | SQLite. 8 tables, ~250k rows. |
| Health checks | II §1 | built | per-source volume band, schema hash, last success; `make health` exits non-zero on anything but ok |
| Scheduling | II §1 | built, not deployed | systemd timer on a VM (`deploy/`); GitHub Actions for tests only |
| Scanner change detection | I §6 | **built (generic)**, plus source-specific event drafts for every Scanner source | `scanner/diff.py` diffs any source's last two snapshots |
| Entities table | I §6.2 | **built** | ~23k organizational owners from Gateway parcels + government units (Gateway finance) + nonprofits (IRS 990), business/nonprofit/government/bank types. Persons never enter it. |
| Screener — rules stage | I §6.4 | built | geography, evidence, recipe-required-for-Lens |
| Screener — LLM stage | I §6.4 | **built and proven live** | needs `SCREENER_API_KEY`; now falls back to dry mode per-candidate on any API failure instead of crashing the batch (found live — see DECISIONS.md #72) |
| Rubric | I §7 | v1 in `rubric_prompt_v1.md` | |
| Recipe catalog | II §4 | 6 recipes | fdic ×2, census ×3, gateway ×1 |
| Lens skill | I §5 | **built** as `skills/qr-lens/SKILL.md` | three inputs, recipe-only rule, house format, kill rules |
| Lens baseline refresh | I §5.5 | partial | `lens/reproduce.py` recomputes #001/#002; not yet generalized to "every published measure" |
| Airtable delivery | II §1 | **built and proven live** (REST) | Base `appBVtPxGG9DJpnxL`; 1,206 candidates delivered in the Sept 6 overnight run |
| Sources | II §3 | 8 of ~25 | fdic, census, in_gateway_parcels, in_gateway_finance, sec_form_d, bankruptcy, usaspending, irs_990 |
| Accumulation | I §6.3 | **built** | `scanner/accumulate.py`; 2 real cross-source matches found live (irs_990 + usaspending) — see OVERNIGHT_REPORT.md |

## Sources: built / next / blocked

- **Built:** FDIC institutions + SOD (1934–/1994–). Census CBP (2023), BDS (1978–2023). Indiana Gateway PARCEL files (3 IN counties, 236k parcels, 2025 assessment) — reproduces #006. Indiana Gateway local finance (`in_gateway_finance`). SEC EDGAR Form D (`sec_form_d`). CourtListener bankruptcy (`bankruptcy`). USASpending (`usaspending`). IRS 990 (`irs_990`).
- **Dropped, terms/access blocked:** IEDC transparency portal (bot-management-blocked API, no bulk CSV). Michigan Treasury local-unit finance (403 on a plain request; stretch goal, not pursued further).
- **Next in order:** SBA 7(a)/504 + PPP, FFIEC CRA, DOL Form 5500, Fed data.
- **Needs a free key:** Census ACS (`CENSUS_API_KEY`, have it). CourtListener (`COURTLISTENER_API_KEY`, would upgrade bankruptcy's text-search-derived county matching to address-verified).
- **Terms check before building:** public-notice aggregators, IN/MI SOS portals, BS&A county portals.

## Scanner Phase 2 (overnight build, Sept 5–6 2026) — done

Built the event sources per Dustin's overnight brief, in order, committing after each passed `make test` + a local fetch, then deployed and verified live on the server. Full account in OVERNIGHT_REPORT.md.

| # | Source | State | Candidates delivered (live server run) |
|---|---|---|---|
| 1 | Indiana Gateway local finance (Budget + AFR Debt) | **built** — `in_gateway_finance` | 4 |
| 2 | SEC EDGAR Form D | **built** — `sec_form_d` | 59 |
| 3 | Bankruptcy (CourtListener RECAP) | **built** — `bankruptcy` | 6 — county tagging is text-search-derived, not address-verified (no API key; see QUESTIONS.md) |
| 4 | IEDC transparency portal | **dropped** | Real data API found (`POST /contract/search`) but blocked by bot management (405 on every POST); no bulk CSV on the site. Terms-of-use not locatable either. See QUESTIONS.md #8. |
| 5 | USASpending | **built** — `usaspending` | 669 ($250k+ floor, 24mo, grants+contracts; 0 loans) — high volume (AM General, Notre Dame, Honeywell, MDOT formula grants); flagged as a screening-cost/review-load thing to watch |
| 6 | IRS 990 (ProPublica + IRS bulk EO file) | **built** — `irs_990` | 444 (>25% YoY asset change); adds `nonprofit` entities |
| 7 | Michigan Treasury local-unit finance (stretch) | **not built** | `michigan.gov` returned 403 to a plain identified request (no bulk file located before hitting that wall) — stretch goal, recorded rather than pursued given required sources 1–6 and accumulation |
| — | Accumulation candidates | **built** — `qr_research/scanner/accumulate.py` | 2 — real cross-source matches (irs_990 + usaspending), same two nonprofits, both regional social-service agencies |
| — | FDIC / Gateway parcels (already-built sources, re-delivered this run) | — | 6 + 16 |

**Total delivered:** 1,206 candidates. **Screening:** the Anthropic account ran out of credits partway through (444 IRS-990 candidates is a lot of LLM calls) — `accumulation`, `bankruptcy`, `fdic`, `in_gateway_finance`, and `in_gateway_parcels` (34 candidates) got real rubric screening (surface/hold/kill, real `why_hold`); `irs_990`, `sec_form_d`, and `usaspending` (1,172 candidates) are rules-screened only and kept their generator's `surface` tag. See QUESTIONS.md #5 — this is the single most important thing to act on.

## Needs Dustin (see QUESTIONS.md)
Add Anthropic credits (urgent, blocks real screening for 1,172 candidates) · optional CourtListener key · optional terms check on IEDC/MI Treasury.
