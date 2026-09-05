---
name: qr-lens
description: Q&R Research Lens — generate and answer questions about capital in the five-county region (St. Joseph, Elkhart, Marshall IN; Berrien, Cass MI) from cataloged public-data recipes, producing draft Observations in the house format. Trigger on "run the lens", "lens on [capital type]", "is it different here", "what does [national report] say about us", "what dataset accidentally measures [X] here", "run the grid on [farmland / deposits / housing / ...]", or when Dustin hands over a national report, dataset, or proxy idea and wants the five-county cut. Internal only — produces candidates for review, never publishes.
---

# Q&R Lens

You produce **draft Observations**: one question about capital in the region, one measure, a method note that states the bias. You do not publish. You write candidates to the research queue for Dustin to judge.

## Read first, every run
1. `reference/published_observations.md` — the house format and the six published pieces. Match the form exactly.
2. `qr_research/lens/recipes/*.yaml` — the **only** data you may compute from. If no recipe covers a question, the answer is "no county-level equivalent exists" and you stop. Never approximate, never estimate, never invent a proxy that isn't cataloged.
3. `rubric_prompt_v1.md` — the two axes and the function label.

## Three inputs — identify which one you've been given
- **Grid slice** ("run the grid on farmland"): enumerate capital type × dimension (source · ownership · control · destination · duration · distribution · transformation · type). For each cell, check the recipe catalog. Cells without a recipe die silently. Prioritize cells that would give a first indicator to Conversion, Resilience, or Spatial Productivity. Try to produce stock/flow pairs.
- **External report** (a national report or dataset): identify the metric, find the recipe that supports the same metric at county level, compute the five-county cut, state how the region compares — or state that no county equivalent exists.
- **Proxy idea** (a dataset that accidentally measures something): translate the analogy into "what cataloged dataset here has a side-channel that reads on capital, control, or flow?" Propose candidates; only compute the ones with a recipe. Uncataloged proxy ideas go to the queue as `hold` with `recipe_ids` empty and a note "needs recipe" — that's how the catalog grows.

## Computing
Run `make fetch` if the normalized DB is stale (check `make health`). Query `data/qr_research.sqlite` — tables are named in each recipe. Use `qr_research/lens/reproduce.py` as the pattern. Render measures as everyday ratios (82 of 100; 18¢ of every $100), region and vintage named.

## Baselines — per question, not system-wide
Comparison is one question shape of six. When comparing: own history first; national total (share-of-whole); national norm; peer set only when "unusual" is the claim, chosen per sub-economy (Elkhart / South Bend metro / Berrien–Cass lakeshore / rural Marshall), and named in the method note.

## Output — one candidate per finding, in this shape
```
candidate_id, feed=lens, candidate_type=observation_draft, source, counties, coverage_note,
headline (≤120 chars), question, measure, method (source · vintage · geography · cut · caveat),
why_it_might_matter (one sentence against the stance), axis_a[], axis_b[], function[],
stock_or_flow, recipe_ids[], evidence_urls[], confidence (solid|soft|speculative),
screen_result (surface|hold)
```
Write them to `examples/lens_<slug>.json` then `python -m qr_research.deliver.airtable examples/lens_<slug>.json`.

## Kill rules
- Caveat would swallow the finding → no candidate; say so in one line.
- Only one county has the data → `coverage_note` says which, or kill if the question is regional.
- A refresh of a published measure that hasn't moved → `hold`, not `surface`.

## Never
Estimate. Invent a URL. Use metaphor vocabulary in candidates. Publish. Skip the caveat.
