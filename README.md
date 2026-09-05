# qr-research

Internal candidate-generating feeds for Q&R Research. See BRIEF.md and SPEC_v0.3.md.

## Run locally
    pip install -r requirements.txt
    cp .env.example .env   # fill in; then `set -a; source .env; set +a`
    make fetch             # pull FDIC into data/
    make reproduce         # recompute Observations #001 and #002
    make candidates        # write examples/fdic_candidates.json
    make screen            # rules + LLM rubric pass (dry mode without SCREENER_API_KEY)
    make deliver           # Airtable upsert, or CSV if no token
    make health            # exits 1 if any source isn't ok
    make test

## Adding a source
1. `qr_research/connectors/<source>.py` — subclass `Connector`; implement `fetch`, `normalize`, `expected_volume`; add a `run()` like fdic's.
2. If it feeds Lens, add `qr_research/lens/recipes/<id>.yaml` with a caveat. Lens may only compute from recipes.
3. Drafts/events in `qr_research/lens/<source>_drafts.py`; every candidate needs `evidence_urls` and, for Lens, `recipe_ids`.
4. Add a workflow (copy `.github/workflows/fdic.yml`) ending in `make health`.
5. Add a test that breaks the endpoint and asserts health == "error".

## Layout
    qr_research/connectors/   acquisition + normalization (base.py = interface)
    qr_research/lens/         recipes/, reproduce.py, *_drafts.py
    qr_research/screen/       rubric.py (rules + LLM)
    qr_research/deliver/      airtable.py
    data/raw/                 immutable payloads (gitignored)
    data/qr_research.sqlite   normalized tables + source_health (gitignored; cached in Actions)
    examples/                 candidates and reference outputs
    reference/                published Observations, framework, reproduction notes
