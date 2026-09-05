# DECISIONS.md — calls made without Dustin (Phase 0, Sept 5 2026)

| # | Chose | Rejected | Why |
|---|---|---|---|
| 1 | FDIC as the Phase 0 source | Indiana Gateway | Clean API, no key, underlies two published Observations → a real acceptance test. Gateway is next. |
| 2 | Institutions API + SOD, all history, one pull | Incremental pulls | ~7k records; full refresh is seconds and makes change-detection a table diff, not a cursor. |
| 3 | SQLite for normalized data | DuckDB, Postgres | Stdlib, zero install, fine at this scale. Revisit if any table passes ~10M rows. |
| 4 | Raw payloads as JSONL per run under data/raw/<source>/<date>/ | Parquet | Human-readable, diffable, no dependency. |
| 5 | "Run from here" = institution HQ county in the five counties | Holding-company HQ | Matches the published 59¢ exactly; HC reading documented as the stricter alternative in the recipe. |
| 6 | "National banks" = holding companies with > $100B US deposits, deposit-weighted | Undefined (as published) | Published note doesn't define it; this definition reproduces 15–17¢ vs 18¢ and is stated so the figure is reproducible. See reference/reproduction_notes.md. |
| 7 | Lens drafts tagged in code and reviewed by Claude in-session for Phase 0 | Wait for SCREENER_API_KEY | No key available; the six candidates were hand-tagged against the rubric. Screener runs live once the key is set; dry mode keeps generator tags. |
| 8 | Three-way screen_result (surface/hold/kill) | 0–100 score | Per spec v0.3. |
| 9 | Refreshes of #001/#002 → `hold`, not `surface` | surface | A refresh that reproduces the published number is not news; it's the baseline job doing its work. |
| 10 | First-run Scanner change detection = institutions ended since 2020 | Wait for a second vintage | No second vintage exists yet; future runs diff the cached table. Historical hits marked `hold`. |
| 11 | Airtable delivery via REST with upsert on candidate_id; CSV fallback when no token | MCP-only | The in-session Airtable call was not approved; REST is what GitHub Actions needs anyway. |
| 12 | GitHub Actions weekly, DB cached across runs for diffing | VM + cron | Zero infra. Cache is best-effort; a full refetch rebuilds everything. |
| 13 | Health check is the last step of every workflow and exits non-zero on anything but "ok" | Log-only | A quiet failure is the failure mode the spec fears most. |
| 14 | `SCREENER_API_KEY`, not `ANTHROPIC_API_KEY` | ANTHROPIC_API_KEY | Claude Code would consume the latter as its own login. |
| 15 | New Lens drafts kept to three | More | Only drafts computable from the two recipes with a defensible caveat; anything else waits for a recipe. |
| 16 | Entities table deferred | Build now | Spec says on second Scanner source. One source has nothing to join. |
| 17 | Census via bulk files (CBP zip, BDS CSV), ACS via API only when keyed | API for all | Census API now requires a key; bulk files don't. Connector degrades gracefully and health says so. |
| 18 | Generic vintage-diff for Scanner instead of per-source change logic | Per-source diffs | One `scanner/diff.py` works for every connector; source modules only add rubric context to changes. |
| 19 | Lens is a skill folder (`skills/qr-lens/SKILL.md`), not a pipeline | Scheduled Lens job | Two of three Lens inputs are a person handing something over; matches Dustin's existing skill pattern. Baseline refresh stays a job. |
| 20 | STATUS.md as the build ledger, FINAL_REPORT.md retired | Keep the report | The report read like a contest score sheet. STATUS.md describes the system, layer by layer, against the spec. |
| 21 | Recipe for ACS written before data exists | Wait | The catalog is the constraint on Lens; a recipe with "not yet pulled" in its caveat is honest and lets the skill say exactly why it can't answer. |
| 22 | Runs on a small VM with a systemd timer; GitHub Actions kept for tests only | Actions cron; Cowork scheduled tasks | Persistent disk satisfies immutable-snapshot rule; Phase 3 scrapers need a box anyway; one setup. |
| 23 | Push = Airtable Monday-digest automation + VM failure alert; pull = optional dustin-morning line | Slack; custom digest code | Native Airtable automation is zero code and survives Dustin not using dustin-morning. Morning brief is a bonus, never a dependency. |
| 24 | qr-linkedin reads `kept` candidates; Lens drafts write `chart_series` | Separate export step | Kept items already meet the LinkedIn verification bar; chart data travels with the candidate. |
| 25 | Skill edits delivered as paste-ins, not applied | Edit skills directly | Dustin's skills live outside this repo; a paste is reversible and reviewable. |
| 26 | Base ID hardcoded as default in deliver + .env.example | Require env | One base, one owner; the ID is not a secret. Token still required to write. |
| 27 | Gateway via scripted ASP.NET form post, latest year auto-detected | Manual download | It's a public download page with no terms against automation; health check catches redesigns. |
| 28 | Fixed-width parse from the 50 IAC 26-20-4 layout, not inferred from data | Infer positions | The source underpins a published Observation; positions must be authoritative. |
| 29 | Entities table populated from Gateway owner names (organizational patterns) | Wait for Form D | Gateway is entity-level; 23k organizational owners across 3 counties. Persons are never entities. |
| 30 | #006 'owner's home' = house number + ZIP match | Exact string; ZIP-only | Reproduces 82/14/2/2 as 81/15/1/3; the alternatives give 55 or 86. Definition now in the recipe. |
| 31 | Gateway drafts carry coverage_note "Indiana counties only" | Silently omit MI | Spec rule: label subsets. |
