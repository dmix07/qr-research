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
| Sources | II §3 | 3 of ~25 | fdic, census, in_gateway_parcels |

## Sources: built / next / blocked

- **Built:** FDIC institutions + SOD (1934–/1994–). Census CBP (2023), BDS (1978–2023). Indiana Gateway PARCEL files (3 IN counties, 236k parcels, 2025 assessment) — reproduces #006.
- **Next in order:** Indiana Gateway local-finance files (budgets, debt, TIF), SEC Form D, SBA 7(a)/504 + PPP, FFIEC CRA, IRS 990 (ProPublica), bankruptcy RSS, USASpending, DOL Form 5500, Fed data.
- **Needs a free key:** Census ACS (`CENSUS_API_KEY`).
- **Terms check before building:** public-notice aggregators, IN/MI SOS portals, BS&A county portals.

## Needs Dustin (see QUESTIONS.md)
Create the DigitalOcean VM · Airtable token · optional free Census key. Then one Claude Code session deploys it. Nothing else.
