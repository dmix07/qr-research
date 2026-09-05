# QUESTIONS.md — things that need Dustin

1. ~~**GitHub.**~~ Resolved: `gh` installed (no Homebrew on this machine, so pulled the binary release directly), `gh auth login` + `gh auth refresh -s workflow` completed with your browser sign-in, pushed to `main`.
2. ~~**DigitalOcean server.**~~ Resolved: installed at `/opt/qr-research` on 167.99.233.188, `qr-research.timer` enabled (next run Mon 2026-09-07 06:19 UTC), `.env` copied over, service run once successfully — all three sources `ok`, 10 candidates delivered to Airtable. Two things you should know:
   - The droplet forced a root password change on first login; I completed it (with your explicit go-ahead) and generated a random new root password to get past it, then installed my own SSH key for real access. That generated password only exists in this conversation transcript — if you want a root password you chose yourself, reset it via the DigitalOcean console's "Reset Root Password" (Access tab).
   - The droplet has only 1GB RAM and no swap, which OOM-killed the first run against the 236k-row Gateway parcel file. I added a 2GB swapfile (free, persists across reboots via `/etc/fstab`) and the second run completed cleanly. If weekly Gateway-file growth or an added source pushes memory further, the next fix is a bigger droplet (that costs more money — I'd ask before resizing).
3. **Airtable views** (`Inbox`, `Kept`, `By source` on `candidates`; `Health` on `sources`) — Airtable's API has no view-creation endpoint, so these need manual clicks, once, in the base (`appBVtPxGG9DJpnxL`):
   - Open the `candidates` table → click the `+` next to the view list (left sidebar) → **Grid view** → name it `Inbox` → add a filter `status = new` → sort `created_at` descending → in the row-height/fields menu, hide every field except headline, feed, screen_result, measure, why_it_might_matter, evidence_urls, status, editor_note.
   - Repeat `+` → **Grid view** → name `Kept` → filter `status = kept`.
   - Repeat `+` → **Grid view** → name `By source` → group by `source` (Group button in the toolbar).
   - Open the `sources` table → `+` → **Grid view** → name `Health` → filter `health != ok`.
4. **Monday digest & health-alert automations.** Both exist as draft (off) Airtable automations, built via the Airtable MCP automation builder — I could create automations directly, so this didn't need manual clicks:
   - `Monday research digest`: https://airtable.com/appBVtPxGG9DJpnxL/wflBNSYyDgNyIYTZN — every Monday 11:00 UTC, finds `candidates` where `status = new`, emails dustin@quarterlineandrock.com a list of headline + screen_result.
   - `Source health alert`: https://airtable.com/appBVtPxGG9DJpnxL/wfl7hEKWZ8yBRxXZF — fires when a `sources` row's `health` leaves `ok`, emails dustin@quarterlineandrock.com.
   - Open each link and click the toggle to turn it on (drafts are never live).
   - One gap: the automation builder has no way to encode "only send if count > 0," so the Monday digest currently sends every week, including "0 new." If you want the empty-week suppression from `integrations/AIRTABLE_SETUP.md`, add it yourself in the UI: open the digest automation → click the `sendEmail` step → **Add condition** above it → field `status` view/count... (Airtable's UI conditions gate on a *record's* fields, not a count, so the practical way is: click **+** after the find-records step → **Condition** → "Continue only if" → set it to the find step's output using the record-count helper the builder UI exposes there) — or simplest, just leave it as-is; a one-line "0 new" email is cheap.
5. **Screener key.** Without `SCREENER_API_KEY` the LLM stage is skipped and candidates keep their generator tags.
6. **Census key.** Free, instant: https://api.census.gov/data/key_signup.html. Unblocks ACS (#005/#006 inputs).

Provisional choices made for each are in DECISIONS.md.
