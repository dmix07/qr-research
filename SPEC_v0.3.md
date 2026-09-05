# Q&R Research Feeds — Product Spec & Build Plan

**Status:** Draft v0.3 · September 5, 2026 (supersedes v0.2)
**Owner:** Dustin Mix
**Scope:** Two internal candidate-generating systems — **Scanner** and **Lens** — feeding one editorial queue for Q&R Research. Nothing here publishes anything. Both exist to do at scale what Dustin already does by hand.

**What changed from v0.2 (decisions made Sept 5):** Rubric Axis A replaced with the eight capital dimensions from Scott's Thriving Cities Framework; the seven metabolic functions become an organizing label; stock/flow is required on Lens candidates. Axis B gains `unmeasured`; any one Axis B tag earns review. No size floors. No bulk-data purchases — free sources only, which moves UCC/entity sources to scrape-or-drop and widens the Michigan gap. Queue is a separate Airtable base. Dustin is sole reviewer. Dustin + Claude (Code and Cowork) build all of it.

**Decision log**

| Decision | Answer |
|---|---|
| Who builds | Dustin + Claude Code (Scanner codebase) + Claude Cowork (Lens skill, light Tier 1 sources, docs) |
| Queue | Airtable — its own base, separate from the pipeline base |
| Reviewer | Dustin only |
| Bulk data | None. Free sources only |
| Size floors | None. Rubric decides |
| Rubric | Axis A = Scott's dimensions; Axis B = five tags, any one; functions as label; stock/flow required (Lens) |

---

## Part I — Product Spec

### 1. What the Observations already are

Six published Observations define the product's target. Each: **one question about capital in the region → one measure → a method note that states the bias.** Topics so far: who owns the houses; investor attractiveness of housing; succession financing and buyer counts; whether the region's deposits matter to the banks that hold them; how bank ownership left the region.

The through-line is not a topic. It's a stance: **where does control over this region's capital actually sit — here, or somewhere else — and which way is it moving?** Succession is one instance of that stance, not the category.

Scott's Thriving Cities Framework (Aug 2026 draft) gives that stance a structure: a region has a *capital metabolism* with seven functions (Circulation · Conversion · Regeneration · Stewardship · Resilience · Exchange · Spatial Productivity), and capital has eight dimensions that determine whether those functions work. Read against it, each published Observation is an indicator for one function: #006 → Stewardship; #001, #002 → Stewardship and Exchange; #003, #004 → Regeneration; #005 → Exchange. Conversion, Resilience, and Spatial Productivity have no indicators yet. That is where the Lens grid looks first.

Both feeds exist to generate candidates that could become the seventh, eighth, fiftieth Observation — or that inform the essays, the Local Fund thesis, or LinkedIn. Publication is a separate human act.

### 2. Operating model (Effort News)

- Machines generate candidates. A human decides what's worth publishing. Nothing ships automatically.
- Feeds are allowed to miss. They are not allowed to fabricate. Every candidate links to a primary record and carries a reproducible method.
- If the machine can't write the method note, there is no candidate.

### 3. Two systems, one queue

| | **Scanner** | **Lens** |
|---|---|---|
| Question | *What just changed?* | *What is true about capital here that nobody has measured?* |
| Trigger | An event lands: filing, disclosure, award, agenda item | A question arrives — from the grid, a report, or a proxy idea |
| Nature | A pipeline (scheduled jobs) | A skill (invoked), plus an annual baseline refresh |
| Unit | An event about an entity or place; or an accumulation of events | A question answered with one measure |
| Output | Event candidate | Draft Observation in the house format |
| Hard part | Acquisition and normalization of messy local sources | Generating good questions and refusing to answer bad ones |

Both draw from **one acquisition layer**. The same parcel file that Scanner watches for ownership changes is the file Lens used for Observation #006. Two front-ends, one set of sources.

### 4. Geography

St. Joseph, Elkhart, Marshall (IN); Berrien, Cass (MI). Every candidate carries county tags. Lens labels any subset used ("IN counties only") in the headline, because the data often forces it.

### 5. Lens

**5.1 Three inspiration inputs**

1. **The grid** — systematic and boring by design. Capital type × dimension, steered by function. Capital types: deposits, bank ownership, business equity, business debt, housing, commercial real estate, farmland, philanthropic endowments, public/TIF money, retirement assets, insurance float, municipal debt. Dimensions (Scott's): *Source · Ownership · Control · Destination · Duration · Distribution · Transformation · Type* — each is a question ("who owns the farmland," "how long is the capital behind our commercial buildings committed"). Functions steer priority: cells that would give an indicator to Conversion, Resilience, or Spatial Productivity rank first because nothing measures them yet. The grid also tries to generate **stock/flow pairs** (#001 is a stock, #002 its flow; together they're stronger). Most cells die at the data check.
2. **External reports and analyses** — reactive. A national report or dataset arrives; the question is whether the region looks like the report says. The work is finding the county-level equivalent — or stating that none exists.
3. **Proxy inspiration** — associative. Something like the Strava-heatmap piece crosses the desk (data collected for one purpose accidentally measures another). The question becomes: *what dataset in the five counties accidentally measures capital, control, or flow?* Observation #006 is already a proxy (assessor mailing addresses → where housing control sits). Candidates in this mode: Form 5500 (where local employers' retirement assets are administered); PPP data by lender (who actually lent locally under stress); registered-agent addresses (local companies domiciled through firms elsewhere); branch closure filings; 990 board overlap (where local decision-making concentrates).

**5.2 The Lens process (same for all three inputs)**

```
question → data check → one measure → method note (with bias stated) → candidate
```

- **Data check:** the machine may only draw on cataloged recipes (§Part II 4). No recipe → it says "no county-level equivalent exists" and stops. This is the anti-fabrication rule for Lens.
- **One measure:** rendered the way the house does it — everyday ratios (18¢ of every $100; 82 of 100 houses), not decimals.
- **Method note:** source, vintage, geography, cut, and the honest caveat. If the caveat swallows the finding, no candidate.

**5.3 Baselines (per question, not system-wide)**

Comparison is one question shape of six. When a question is comparative, Lens chooses the baseline appropriate to it: the region's own history; the national total (share-of-whole); a national norm; or a peer set. Peer sets are chosen **per question and per sub-economy** — Elkhart (RV concentration), the South Bend metro, the Berrien/Cass lakeshore, and rural Marshall do not share peers. Every peer set used is named in the method note.

**5.4 Lens candidate = draft Observation**

```
Question:        one line
Measure:         one sentence, everyday ratio, region and vintage named
Stock or flow:   stock | flow            (required)
Dimension(s):    Axis A tags
Function:        which of the seven this informs
Interest:        Axis B tags (≥1)
Method:          source · vintage · geography · cut · caveat
Why it matters:  one sentence against the stance (§1)
Recipes used:    [ids]
Confidence:      solid | soft | speculative
```

**5.5 Two modes**

- **On demand (primary):** a Claude skill in the existing Q&R skill pattern. Dustin hands it a report, a proxy idea, or "run the grid on farmland." It returns draft Observations or explicit misses.
- **Baseline refresh (secondary, annual):** when a cataloged dataset publishes a new vintage, recompute the measures behind every published Observation and every kept Lens candidate. Surface only material changes. This is a maintenance job, not a feed.

### 6. Scanner

**6.1 What it watches:** the sources in Part II §3, filtered to the five counties, screened against the rubric.

**6.2 Entities are first-class.** An `entities` table (name, aliases, type, county, addresses) with candidates referencing `entity_id`. Manual alias table maintained by Dustin. This is what makes patterns visible.

**6.3 Two candidate types**

- **Event:** one record that clears the rubric on its own (a Form D from a regional issuer; an RDC bond authorization).
- **Accumulation:** a pattern across records or sources on one entity or place within a window (three UCC filings in six months; an abatement approval for an entity that just raised capital; a parcel changing hands twice in a year). Accumulations are where the interesting things are.

**6.4 Screening**

1. **Rules stage** — geography and disqualifiers only. No size floors (decision: the rubric judges scale via `large`). Deterministic; kills less volume than a floored version would, which raises screening cost and review load early. Floors may be added per source later, with kept-rate evidence, never by guess.
2. **Rubric stage** — LLM pass on survivors. Emits: `surface | hold | kill`, rubric tags, one-paragraph why-it-might-matter, evidence links. No numeric score.
3. **Cold start** — the few-shot set is seeded from the six published Observations, the essays, and whatever Dustin has flagged by hand. Kept/killed decisions extend it over time.

### 7. The rubric

Two axes plus a label. A candidate needs at least one tag on each axis.

**Axis A — the dimension (what the measure is about).** Scott's eight capital dimensions. Locality — here vs. elsewhere — is not a separate tag; it is the reading applied to Source, Ownership, and Control, as the published pieces already do.

| Tag | Question |
|---|---|
| `source` | Where did the capital originate? |
| `ownership` | Who holds the residual economic claim? |
| `control` | Who determines what happens to the asset? |
| `destination` | What is the capital financing? |
| `duration` | How long is it committed? |
| `distribution` | How concentrated or dispersed is it? |
| `transformation` | What new capacity does it create — or does it just change hands? |
| `type` | What kind of capital is it (debt, equity, deposit, grant, public)? |

**Axis B — why it earns review.** Any one suffices.

| Tag | Meaning | Published example |
|---|---|---|
| `unmeasured` | Knowable from public data; no one has put the number on it for this region | #006 — nobody had asked who owns the houses |
| `surprising` | Contradicts the intuitive answer or the public narrative | #005 — affordability and investor appeal are the same number |
| `large` | Big relative to the region, not in absolute dollars | #004 — $1.2B/yr changing hands across five counties |
| `connected` | Links to another candidate, a published Observation, or a live question | #002 is stronger because #001 exists |
| `legible` | Statable as one everyday ratio a reader will remember | 18¢ of every $100 |

`unmeasured` is the core of the product and the tag the Lens grid and proxy modes exist to find. Guard: at county scale nearly everything is technically unmeasured, so it never excuses a missing Axis A tag or a method note that fails its own caveat. The screener checks it cheaply — has this measure been published for these counties?

**Function label (organizing, not screening).** Which of the seven metabolic functions the candidate informs: Circulation · Conversion · Regeneration · Stewardship · Resilience · Exchange · Spatial Productivity. Used to see the shape of the body of work and steer the grid toward functions with no indicators. Never used to kill a candidate.

**Stock or flow** — required on Lens candidates; recorded on Scanner candidates where it applies. The grid tries to pair them.

**Disqualifiers (rules stage):** outside the five counties; individual-level records not tied to an entity. That is the whole list.

**Language rule:** the framework's analogy vocabulary (metabolism, hemorrhage, cholesterol) stays out of the machine. The screener sees `control` and `duration`, never the metaphor. The metaphor is for the writing, if at all.

### 8. Editorial workflow

1. Candidates land in one Airtable base — **its own base**, not a table in the pipeline base. Filtered views per feed, per source, per function; `analyze_table` gives kept-rate by source for free.
2. Weekly review: each → `kept` or `killed` with a one-line note. Kept Lens candidates are draft Observations; kept Scanner candidates are leads for Observations, essays, or the thesis.
3. Publication is separate, human, and holds to the existing verification bar.
4. Quarterly: rubric and few-shot refresh from kept/killed history; source demotion by kept-rate.

### 9. Non-goals

- No public output. No auto-publishing.
- No individual-level investigation.
- No orchestration *as infrastructure* — no dispatch daemon, no agents choosing their own work, nothing unattended. Fan-out **within a single Lens invocation** (one lead, workers per grid cell or proxy hypothesis, results ranked and summarized back as one short list) is permitted from Phase 1, once the recipe catalog exists to constrain what workers may compute from. Scanner stays cron.
- No real-time.
- **No pipeline watchlist.** Monitoring active deal counterparties is a sourcing product with its own name and rules; it does not live here.
- No sector research (that's `sector-competence`).

### 10. Instruments (not gates)

Candidates/week by source · kept rate by source · Lens misses vs. hits by input type · published pieces traceable to a candidate · feed health per source.

### 11. Decisions

All six made Sept 5, 2026 — see the decision log at the top. Remaining open items are operational, not structural: which source is Phase 0 (Gateway or FDIC SOD), and whether the public-notice aggregators' terms permit automated access.

---

## Part II — Build Plan

### 1. Architecture

```
[Acquisition] → [Normalization] → [Screening / Lens process] → [Airtable]
```

- **Storage at start:** raw payloads as files (Parquet/JSON, immutable); normalized records in SQLite or DuckDB; Airtable is the human-facing store. Postgres only when a concrete need appears.
- **Who runs what:** the Scanner codebase (connectors, entities, screening, health checks) is built in Claude Code with Dustin directing. The Lens skill, the recipe catalog, the rubric prompt, the source/terms survey, and the lightest Tier 1 Scanner pulls run in Claude Cowork — the latter as scheduled tasks writing to Airtable, which may mean some Tier 1 sources never need a repo at all.
- **Scheduling:** GitHub Actions cron. Move to a VM + Prefect only when a job outgrows it.
- **Language:** Python. One repo `qr-research/`: `connectors/`, `normalize/`, `entities/`, `screen/`, `lens/`, `deliver/`.
- **Airtable:** one-way write from the pipeline. Kept/killed is read on demand when refreshing the few-shot set. Field set mirrors the candidate objects in Part I §5.4 and §6.3.
- **Observability from the first source:** per-source last-success and volume band; schema-drift hash; alert when silent > 2× cadence.

**Connector interface**

```python
class Connector:
    source_id: str
    tier: int            # 1 clean API/bulk · 2 structured/portal/purchasable · 3 unstructured
    cadence: str
    counties: list[str]  # which of the five it can actually cover
    def fetch(self, since) -> list[RawRecord]: ...
    def normalize(self, raw) -> list[Record]: ...
    def expected_volume(self) -> tuple[int, int]: ...
```

### 2. Cross-cutting rules

- Store links, not content, for news and anything copyrighted. Store full payloads for government records.
- Rate-limit and identify every scraper. **No bulk purchases (decision).** Sources that a state sells but also exposes through a portal become scrape-or-drop, and are re-tiered to 3 below. Where a portal's terms forbid automated access, the source is dropped, not worked around.
- Every candidate carries ≥1 primary-record URL and, for Lens, ≥1 recipe id.
- **Indiana/Michigan asymmetry is real and must be labeled.** Indiana: Gateway (local finance, TIF, parcel files), DLGF sales disclosures, SOS bulk data. Michigan: Treasury local-unit financial data (F-65 and audit filings), BS&A county portals (some sell data), MI Dept. of State UCC bulk, LARA entities. Michigan will come online slower; candidates say which counties are covered.

### 3. Source map — shared acquisition layer

Tier 1 = clean API/bulk · 1.5 = clean but lagged or search-only · 2 = structured, portal or purchase · 3 = unstructured

| Source | Gives | Tier | Cadence | Serves | Notes |
|---|---|---|---|---|---|
| Indiana Gateway (DLGF/SBOA) — local finance, TIF, parcel files | Budgets, debt, TIF reports, annual financials, parcel ownership (IN) | 1 | annual/quarterly | Both | Already used in #006. Highest-value IN source |
| Indiana DLGF sales disclosures | Property transfers (IN) | 1 | quarterly | Both | Commercial parcels for Scanner; ownership shifts for Lens |
| FDIC institution records + Summary of Deposits | Bank HQ, ownership, deposits by branch | 1 | annual | Both | Already used in #001, #002 |
| Census CBP, BDS, ABS, Nonemployer, ACS | Firms, churn, owner age, housing, rent, values | 1 | annual | Lens | Already used in #003–#005 |
| BLS QCEW; BEA regional | Employment, wages, county GDP/income | 1 | quarterly/annual | Lens | |
| FFIEC CRA small-business lending; HMDA | Who lends locally, by lender and county | 1 | annual | Lens | |
| SBA 7(a)/504 FOIA; PPP loan data | Guaranteed lending by county and lender | 1 | quarterly / static | Both | PPP is a proxy source (who lent under stress) |
| DOL Form 5500 | Retirement plan assets and administrators for local employers | 1 | annual | Lens | Proxy: where retirement capital is managed |
| IRS 990 (ProPublica API; IRS bulk XML) | Foundation/nonprofit finances, grants, investments, boards | 1 | annual | Both | Endowment stock; board-overlap proxy |
| IRS SOI county data; migration | Income, in/out migration | 1 | annual | Lens | |
| CDFI Fund TLR | CDFI lending by county | 1 | annual | Lens | |
| SEC EDGAR Form D | Regional private raises | 1 | daily | Scanner | Low volume, high signal |
| Bankruptcy — N.D. Ind., W.D. Mich. (court RSS; CourtListener) | New business filings | 1.5 | daily | Scanner | PACER fees only on kept |
| MSRB EMMA | Muni issuance and disclosures | 1.5 | weekly | Both | Search by issuer state |
| USASpending | Federal $ into the counties | 1 | monthly | Both | |
| IEDC transparency portal | IN incentive awards | 1.5 | monthly | Scanner | |
| MEDC / Michigan Strategic Fund | MI incentive awards | 2 | monthly | Scanner | PDF parse |
| State legislatures (IGA data; MI Legislature; LegiScan) | Bills on TIF, abatements, banking, DAFs | 1.5 | weekly in session | Scanner | |
| Public notice aggregators (IN, MI) | Sheriff/tax sales, bond and zoning hearings, assumed names | 2 | daily | Scanner | Press-association-run; **check terms before scraping** — link, don't copy |
| Fed District 7 (Chicago Fed) publications; Fed SBCS | Regional commentary; credit access | 1 | 8×/yr; annual | Lens | District-level only; label as such |
| Michigan Treasury local-unit finance (F-65, audits) | Local government finance (MI) | 2 | annual | Both | MI counterpart to Gateway; thinner |
| IN SOS entities & UCC | New entities, dissolutions, secured lending | 3 | weekly | Scanner | Portal only (no purchase). Terms check first; scrape narrowly or drop |
| MI Dept. of State UCC; LARA entities | Same for MI | 3 | weekly | Scanner | Portal only. Same rule |
| County recorder/assessor (Berrien, Cass via BS&A; IN via Gateway/Beacon) | Deeds, mortgages, liens, parcels | 1 (IN) / 3 (MI) | weekly | Both | IN parcels are free via Gateway. MI depends on BS&A terms; otherwise dropped |
| Council / commission / RDC agendas & minutes | Abatements, TIF actions, bonds, zoning | 3 | weekly | Scanner | Survey ~15–20 bodies; some use Legistar (API). IN RDCs first |
| Local news RSS | Corroboration | 1.5 | daily | Scanner | Enrichment only, links only |

### 4. Lens recipe catalog

Each recipe: `id · dataset · metrics · geography level · five-county cut · vintages available · refresh · caveats · Observations that used it`. Recipes are the only thing Lens may compute from. Adding a recipe is a deliberate act with a written caveat; the catalog is versioned.

Initial catalog: the recipes behind the six published Observations, plus the Tier 1 datasets above that support county-level cuts.

### 5. Phases

No deadlines. Ordered by dependency. Each phase ends with something producing candidates.

**Phase 0 — One source end-to-end**
- Indiana Gateway (or FDIC SOD — both already proven in published work): connector → normalize → rules + rubric screen → Airtable, with a health check.
- Recipe catalog started from the six Observations.
- Few-shot seeded from the six Observations and hand-flagged material, each labeled with Axis A, Axis B, function, and stock/flow.
- Rubric v1 as a versioned prompt (Part I §7, as decided).
- Airtable base created with the candidate schema; Cowork scheduled-task variant tried for this first source so the repo-vs-Cowork line is learned early.
- Substrate is whatever this one source needed. Nothing more.

**Phase 1 — Lens skill**
- On-demand mode as a Claude skill wrapping the recipe catalog: takes a report, a proxy idea, or a grid slice; returns draft Observations or explicit misses.
- Grid enumerated and stored as capital type × dimension, with function priority and stock/flow pairing; per-question baseline selection; sub-economy peer sets documented when first needed.
- Add Tier 1 Lens datasets to the catalog as recipes.
- Annual baseline refresh job for published measures.

**Phase 2 — Scanner, Tier 1/1.5**
- Form D, bankruptcy, EMMA, IEDC, USASpending, legislature, 990s, SBA/PPP, DLGF sales disclosures, news RSS enrichment.
- Entities table and alias table live; accumulation candidates on.
- Second and third sources force the shared connector interface into shape.
- ~2–5 days per source including normalization and health checks. No slack assumed; add it.

**Phase 3 — Scanner, Tier 2/3**
- UCC/entity portals (IN SOS, MI DoS/LARA): terms check, then narrow scrapers or drop. Expect thin secured-lending coverage.
- MI Treasury local finance; MEDC PDFs; public notices (terms permitting).
- Property: IN is done via Gateway. MI (BS&A) only if terms allow automated access.
- Agendas: survey the bodies, then one body at a time, IN RDCs first.
- Open-ended by design. ~1–3 days per Tier 3 body plus permanent maintenance.

**Phase 4 — Ongoing**
- Quarterly rubric/few-shot refresh; source demotion by kept-rate.
- Entity-resolution upgrade only if the alias table fails.
- Maintenance: ~10–20% of one person indefinitely for the Tier 2/3 surface.

### 6. Cost

- **Infra:** near zero at start (files + GitHub Actions). Tens of dollars/month later.
- **LLM screening:** tens of dollars/month; scales with rules-stage survivors.
- **Bulk data:** none (decision). The cost moves to maintenance time on portal scrapers, or to coverage that isn't there.
- **People:** Dustin's time, with Claude doing the labor. Phases 0–2 ≈ 5–9 weeks of directed sessions if worked steadily; Phase 3 is per-source and ongoing, and it is now entirely Dustin's maintenance load — which is why source demotion by kept-rate matters more than in v0.2.

### 7. Risks

- **Maintenance is the real cost;** Tier 3 sources break silently. Health checks from source one.
- **Michigan lags Indiana** for a long time, and the no-purchase decision widens it. Label coverage; don't imply symmetry.
- **No floors + sole reviewer** means early review load is the highest it will ever be. If it's unworkable, add floors per source from evidence — not before.
- **Lens can fabricate if unconstrained.** The recipe catalog is the constraint. No recipe, no measure.
- **Peer sets can manufacture difference.** Per-question, per-sub-economy, named in the method note.
- **Proxy bias.** Every proxy carries a stated caveat (the #006 model). If the caveat swallows the finding, kill it.
- **Scope creep in sources.** Add by kept-rate evidence.
- **Single-operator dependency** is now the chosen design, not a risk to mitigate: one editor, one maintainer, same person. The system's uptime is Dustin's attention. Accept it consciously.
- **Public notice aggregators** are the one source with a Good Daily–shaped legal exposure. Terms first.

### 8. Not decided here

Which source is Phase 0; public-notice terms. Everything structural is decided.
