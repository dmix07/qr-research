# Brief: Q&R Research Feeds

**For:** a coding agent starting from zero context.
**From:** Dustin Mix, Quarterline & Rock (Q&R), South Bend, Indiana.
**Date:** September 5, 2026.

Read this file first, then `reference/published_observations.md`, then `SPEC_v0.3.md` in full. The framework PDF in `reference/` is background for the rubric's vocabulary; skim it. Then build — all of it — without waiting for anyone.

---

## 1. Who we are and what this is

Quarterline & Rock is a small capital platform in a five-county region of northern Indiana and southwest Michigan — **St. Joseph, Elkhart, and Marshall counties (IN); Berrien and Cass counties (MI)**. We invest in and write about how capital moves through small cities: who owns things, who controls them, whether wealth generated here stays here.

One of our public outputs is a series called **Observations**. Each Observation answers one question about capital in our region with a single measure drawn from public data — for example, "Of every 100 single-family houses, 82 are the owner's home." Six have been published. They are in `reference/published_observations.md`. Read them; they define what "good" looks like.

Today Dustin produces Observations by hand: he thinks of a question, goes looking for public data that can answer it for our five counties, computes one number, and writes a method note that states the data's bias honestly. It works. It is slow.

**We are building the machine that does the looking, so a human only has to do the judging.**

## 2. What the system is

Two internal systems feeding one review queue. Nothing publishes automatically. A human (Dustin) reviews every candidate and decides what becomes an Observation.

- **Scanner** — watches public records in the five counties for changes (filings, disclosures, awards, government actions) and surfaces the ones that matter to our stance. A pipeline: scheduled jobs.
- **Lens** — generates and answers *questions* about capital in the region from public datasets, producing draft Observations in the house format. A skill you invoke, plus an annual refresh of published numbers.

Both write **candidates** to an **Airtable base**. The full design is in `SPEC_v0.3.md`. Key decisions already made (do not re-open): free data sources only, no purchases; no size floors before screening; Airtable is the queue, in its own base; one reviewer; the rubric in Spec Part I §7 is final for v1.

## 3. The stance (this is the rubric's soul)

Every Observation asks, in some form: **where does control over this region's capital actually sit — here, or somewhere else — and which way is it moving?** Banks headquartered elsewhere. Deposits that don't matter to the banks holding them. Houses still mostly locally owned — for now. Businesses whose owners are retiring with no local buyer.

The rubric formalizes this on two axes. **Axis A** — what dimension of capital the finding is about: source, ownership, control, destination, duration, distribution, transformation, type. **Axis B** — why it earns a human's time: unmeasured, surprising, large (relative to the region), connected, legible. A candidate needs one tag on each axis. `unmeasured` — "knowable from public data but nobody has computed it for this region" — is the most important tag; it's the whole point.

## 4. How this build works

**Build the whole thing. Do not stop at a phase boundary to ask permission.** Dustin will not be watching. He will read your decision log and your final report when you are done, and he is judging one thing above all: whether you made good calls on his behalf without needing him.

Work through the phases in `SPEC_v0.3.md` Part II §5 in order. Each phase has acceptance checks below. Run them yourself. If a check fails, fix it before moving on. If it cannot pass, write down why and move on — a documented, honest failure is acceptable; a silent one is not.

### Making decisions on Dustin's behalf

You will hit hundreds of small decisions the spec does not settle. Make them. The rule: **choose the option that keeps the system smaller, more honest, and easier for one non-engineer to maintain with an AI assistant.** When two options are equal on that, pick the boring one.

Record every non-trivial decision in `DECISIONS.md` as one line: what you chose, what you rejected, why. This file is how Dustin will judge your judgment. Keep it terse and complete.

**Stop and ask only for these** — and when you do, write the question to `QUESTIONS.md`, make a reasonable provisional choice, note it, and keep building:
- You need a secret you don't have (Airtable token/base ID, an API key, a contact email for User-Agent). Use environment variables; document exactly which are needed in the README.
- A data source's terms of use appear to forbid automated access. Do not scrape it. Record it as dropped, with the terms quoted, and continue.
- You would be spending money. There is no budget. Free sources only.
- Something in the spec is contradictory or impossible as written. Choose the interpretation most consistent with the stance in §3 and the published Observations, record it, continue.

Everything else you decide.

### What you may not do regardless of judgment

- Fabricate a number, a source, a URL, or a county-level equivalent that doesn't exist. If a Lens question has no recipe, the answer is "no county-level equivalent exists."
- Publish anything, anywhere. The Airtable base is the only output.
- Build orchestration infrastructure — daemons, agent pools, dispatch. Cron and invoked skills. (Fan-out inside a single Lens run is allowed from Phase 1.)
- Purchase data or circumvent an access restriction.
- Add a source the spec doesn't list without recording why in `DECISIONS.md`.

## 5. Constraints

- Python. Plain dependencies. No framework you'd have to explain to a non-engineer.
- Free public sources only. Respect rate limits and robots.txt. Identify scrapers in User-Agent with a contact email from env.
- Store full payloads for government records. For anything copyrighted (news), store links only.
- Every candidate carries at least one primary-record URL. Lens candidates also carry recipe IDs.
- Secrets via environment variables. Nothing in the repo.
- Keep the analogy language in the framework PDF (metabolism, hemorrhage) out of prompts and code. Use the dimension names.
- Every connector implements the interface in Spec Part II §1 and ships with a health check. No exceptions, including the first one.

## 6. Acceptance checks per phase

**Phase 0 — FDIC end to end** (institution records + Summary of Deposits; five-county FIPS: 18141, 18039, 18099, 26021, 26027)
1. `make reproduce` recomputes Observations #001 and #002 from raw pulls and prints the figures. Match the published numbers (47 / 4 / 59¢; ~1 in 500 → ~1 in 1,300; ~18¢ per $100) within rounding, **or** write `reference/reproduction_notes.md` explaining the discrepancy. Unexplained disagreement is a failure.
2. Two recipes exist, versioned, each with an honest caveat field.
3. A draft Observation in the house format is produced from each recipe by the Lens path and written to Airtable with all rubric fields populated by the screener.
4. The connector runs via GitHub Actions on schedule and its health check fails loudly when pointed at a broken endpoint. Test this deliberately and keep the test.
5. At least one Scanner *change* candidate (new charter, merger, HQ move, branch closure) is produced from a diff between two vintages and written to Airtable.

**Phase 1 — Lens**
1. Recipe catalog covers every Tier 1 dataset in Spec Part II §3 that supports county-level cuts. Each recipe has a caveat.
2. The grid is enumerated (capital type × dimension) and stored, with function priority and stock/flow pairing.
3. The on-demand Lens skill runs in three modes — grid slice, external report, proxy idea — and returns draft Observations or explicit misses. Demonstrate each mode once and commit the outputs under `examples/`.
4. Run the grid on the three functions with no published indicators (Conversion, Resilience, Spatial Productivity). Surface whatever clears the screener to Airtable. Record how many cells died at the data check and why.
5. Annual baseline-refresh job exists for every published measure.

**Phase 2 — Scanner Tier 1/1.5**
1. Every Tier 1 and 1.5 Scanner source in Spec Part II §3 has a connector, a health check, and at least one candidate in Airtable — or a `DECISIONS.md` entry explaining why it was dropped.
2. Entities table live; at least one accumulation candidate produced from two sources on one entity.
3. The `sources` table in Airtable reflects live health for every connector.

**Phase 3 — Scanner Tier 2/3**
1. For each source: terms checked and quoted in `DECISIONS.md`; built narrowly, or dropped.
2. Council/RDC agenda survey completed for the ~15–20 bodies; the ones with a structured feed (e.g. Legistar) built first; the rest listed with a per-body effort estimate.
3. Michigan coverage stated honestly in the README: which counties, which sources, what's missing.

**Finished means:** Phases 0–2 pass; Phase 3 is as far as terms and effort allow, with every remaining source listed as built, dropped, or deferred with a reason; `DECISIONS.md`, `QUESTIONS.md`, and a `FINAL_REPORT.md` exist. The final report is one page: what's running, what it produced (candidate counts by source, surface/hold/kill rates), what you dropped and why, what you'd do next, and what you're least sure about.

## 7. Package contents

```
BRIEF.md                                  ← this file
SPEC_v0.3.md                              ← full product spec and build plan
candidate_schema.json                     ← Airtable field definitions
rubric_prompt_v1.md                       ← screening prompt, versioned
reference/published_observations.md       ← the six Observations, tagged (few-shot set)
reference/Thriving_City_Framework_Aug_12_2026.pdf  ← source of the Axis A vocabulary
```

## 8. What we'll judge

In order: whether anything anywhere was made up; whether the published numbers were reproduced honestly; how many times you actually needed Dustin versus how many times you made a sound call yourself (`DECISIONS.md` vs `QUESTIONS.md`); whether the system is small enough for one non-engineer to keep alive with an AI assistant; and whether the final report tells the truth about what isn't working.

A build that finishes fewer sources with an honest ledger beats one that finishes more with a quiet gap.
