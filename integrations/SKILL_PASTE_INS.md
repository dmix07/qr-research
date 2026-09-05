# Paste-ins for existing Q&R skills

## dustin-morning — add under the calendar/tasks pull (Mondays only)

> **Research inbox (Mondays).** Query the Airtable base "Q&R Research Candidates", table `candidates`, filter `status = new`. Report the count and up to five headlines (field `headline`) with their `screen_result`. One line each. Do not summarize the measures — the review happens in Airtable, not here. If the count is zero, say "research inbox empty" and move on. If the `sources` table shows any `health != ok`, name the source; that is a task for the day.

## qr-linkedin — add to the topic-selection step

> **Check the research queue first.** Before proposing topics, query "Q&R Research Candidates" → `candidates` where `status = kept` and `feed = lens`. Each kept candidate already carries `measure`, `method`, `evidence_urls`, and `recipe_ids` — it has passed Dustin's review and meets the verification bar by construction. Prefer these over fresh ideas. Build the chart from the recipe named in `recipe_ids` (query `data/qr_research.sqlite` on the VM, or ask the Lens skill to export the series). Never post from a candidate whose status is not `kept`.

## Candidate schema addition (already applied in candidate_schema.json)

`chart_series` — multilineText, JSON: the x/y series behind the measure, when the recipe is a time series. Written by Lens drafts so qr-linkedin doesn't recompute.
