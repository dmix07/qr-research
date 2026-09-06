# STATUS.md — what the system is, right now (Sept 5, 2026)

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
| Scanner change detection | I §6 | **built (generic)**, no source-specific event drafts yet beyond FDIC | `scanner/diff.py` diffs any source's last two snapshots |
| Entities table | I §6.2 | **built** | ~23k organizational owners from Gateway parcels (business / nonprofit / government / bank). Persons never enter it. |
| Screener — rules stage | I §6.4 | built | geography, evidence, recipe-required-for-Lens |
| Screener — LLM stage | I §6.4 | built, untested live | needs SCREENER_API_KEY |
| Rubric | I §7 | v1 in `rubric_prompt_v1.md` | |
| Recipe catalog | II §4 | 6 recipes | fdic ×2, census ×3, gateway ×1 |
| Lens skill | I §5 | **built** as `skills/qr-lens/SKILL.md` | three inputs, recipe-only rule, house format, kill rules |
| Lens baseline refresh | I §5.5 | partial | `lens/reproduce.py` recomputes #001/#002; not yet generalized to "every published measure" |
| Airtable delivery | II §1 | built (REST) | Base `appBVtPxGG9DJpnxL` created; record writes await token on the VM (or CSV import) |
| Sources | II §3 | 4 of ~25 | fdic, census, in_gateway_parcels, in_gateway_finance |
| Scanner Phase 2 (event sources) | overnight build, Sept 6 2026 | in progress — see below | |

## Sources: built / next / blocked

- **Built:** FDIC institutions + SOD (1934–/1994–). Census CBP (2023), BDS (1978–2023). Indiana Gateway PARCEL files (3 IN counties, 236k parcels, 2025 assessment) — reproduces #006. Indiana Gateway local finance — Budget Data + Annual Financial Report Debt (`in_gateway_finance`; Scanner only) — see Scanner Phase 2 below.
- **Next in order:** SEC Form D, bankruptcy (CourtListener), IEDC transparency, USASpending, IRS 990 (ProPublica), SBA 7(a)/504 + PPP, FFIEC CRA, DOL Form 5500, Fed data.
- **Needs a free key:** Census ACS (`CENSUS_API_KEY`).
- **Terms check before building:** public-notice aggregators, IN/MI SOS portals, BS&A county portals.

## Scanner Phase 2 (overnight build, Sept 6 2026)

Building the event sources per Dustin's overnight brief, in order, committing after each passes `make test` + a local fetch. Updated as each source finishes.

| # | Source | State | Candidates (local test fetch) |
|---|---|---|---|
| 1 | Indiana Gateway local finance (Budget + AFR Debt) | **built** — `in_gateway_finance` | 16 events (TIF-fund changes/new funds); debt events start on run 2 |
| 2 | SEC EDGAR Form D | **built** — `sec_form_d` | 7 events, all Michigan-side (Berrien/Cass) in local test — no IN Gateway parcel data available on this laptop to exercise the Indiana side, which will run for real on the server |
| 3 | Bankruptcy (CourtListener RECAP) | **built** — `bankruptcy` | 3 events (all MI-side locally, same laptop limitation as #2) — county tagging is text-search-derived, not address-verified (no API key; see QUESTIONS.md) |
| 4 | IEDC transparency portal | **dropped** | Real data API found (`POST /contract/search`) but blocked by bot management (405 on every POST); no bulk CSV on the site. Terms-of-use not locatable either. See QUESTIONS.md #8. |
| 5 | USASpending | **built** — `usaspending` | 669 events locally ($250k+ floor, 24mo, grants+contracts; 0 loans) — high volume (AM General, Notre Dame, Honeywell, MDOT formula grants); flagged as a screening-cost/review-load thing to watch |
| 6 | IRS 990 (ProPublica + IRS bulk EO file) | **built** — `irs_990` | 1,282 nonprofits matched (Berrien/Cass only, local test), 407 with 2 years of filing data, ~90 clearing the >25% asset-change threshold; adds `nonprofit` entities |
| 7 | Michigan Treasury local-unit finance (stretch) | **not built** | `michigan.gov` returned 403 to a plain identified request (no bulk file located before hitting that wall) — stretch goal, recorded rather than pursued further given required sources 1–6 and accumulation still ahead |
| — | Accumulation candidates (entity matching across sources 1–3) | **built** — `qr_research/scanner/accumulate.py` | 0 in local test (the six sources' local test data came from separate isolated runs with no real overlapping entities to find — logic verified with 3 synthetic unit tests instead; a real cross-source match is only likely once all sources run together against the same live data on the server) |

## Needs Dustin (see QUESTIONS.md)
Create the DigitalOcean VM · Airtable token · optional free Census key. Then one Claude Code session deploys it. Nothing else.
