# Airtable — base, views, Monday digest

Base is created by `make deliver` on first run (needs AIRTABLE_TOKEN + AIRTABLE_WORKSPACE_ID), or by Claude via the Airtable connector if approved in-session. Schema: candidate_schema.json.

## Views to create on `candidates` (once)
- **Inbox** — filter `status = new`; sort `created_at` desc; fields shown: headline, feed, screen_result, measure, why_it_might_matter, evidence_urls, status, editor_note. This is the only view Dustin uses.
- **Kept** — filter `status = kept`. What qr-linkedin and Observations draw from.
- **By source** — group by `source`; shows kept-rate at a glance.
- **Health** — on the `sources` table, filter `health != ok`.

## Monday digest (Airtable Automation, no code)
Trigger: "At a scheduled time" — weekly, Monday 07:00.
Action 1: "Find records" — table `candidates`, view `Inbox`.
Action 2: "Send email" — to Dustin; subject `Research inbox: {count} new`; body: a list of `headline` — `screen_result` with a link to the record. Airtable's grid-to-email formatting is fine.
Condition: only send if count > 0 — add a conditional group so an empty week sends nothing.

## Health alert (optional second automation)
Trigger: "When record matches conditions" on `sources`, `health != ok`. Action: send email "Source {source_id} is {health}". Belt and braces alongside the VM's own failure alert.
