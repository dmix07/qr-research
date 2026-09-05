# Q&R Research Feeds — working rules for this repo

You are building the system described in BRIEF.md and SPEC_v0.3.md for Quarterline & Rock.
Dustin is not an engineer and will not be watching. Build all of it. Do not stop at phase
boundaries to ask permission.

## Read in this order, once, at the start
1. BRIEF.md
2. reference/published_observations.md
3. SPEC_v0.3.md (all of it)
4. rubric_prompt_v1.md and candidate_schema.json
5. reference/Thriving_City_Framework_Aug_12_2026.pdf — skim for vocabulary only

## Decision rule
Choose the option that keeps the system smaller, more honest, and easier for one
non-engineer to maintain with an AI assistant. When tied, pick the boring one.
Log every non-trivial choice in DECISIONS.md: chose / rejected / why. One line each.

## Ask only for: a missing secret, a terms-of-use restriction, spending money, a spec
contradiction. Write it to QUESTIONS.md, make a provisional call, keep building.

## Never
- Fabricate a number, source, URL, or county-level equivalent. Say "no county-level
  equivalent exists" instead.
- Publish anything. Airtable is the only output.
- Build daemons, agent pools, or dispatch. Cron + invoked skills. (Fan-out inside one
  Lens run is fine from Phase 1.)
- Purchase data or work around an access restriction.
- Use metaphor vocabulary (metabolism, hemorrhage) in code or prompts. Use dimension names.
- Commit .env or any secret. Read config from environment only.

## Conventions
- Python 3.11+, plain dependencies, `requirements.txt`. No frameworks needing explanation.
- Every connector implements the interface in SPEC Part II §1 and ships with a health check.
- Raw payloads immutable under data/raw/<source>/<date>/. Normalized in SQLite/DuckDB.
- Tests: `make test`. Reproduction: `make reproduce`. Health: `make health`.
- Commit often with plain messages. Push to origin when a phase's checks pass.

## Done
Phases 0–2 pass their checks in BRIEF.md §6; Phase 3 as far as terms allow; DECISIONS.md,
QUESTIONS.md, FINAL_REPORT.md exist and are honest. Then stop.
