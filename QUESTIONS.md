# QUESTIONS.md — things that need Dustin

1. **GitHub.** Repo is committed locally (`main`, one commit) with `origin` already pointed at `https://github.com/dmix07/qr-research.git`, but the push failed: this environment has no `gh`, no SSH key registered for github.com, and GitHub rejects HTTPS password auth. Do one of:
   - Run `git -C "<repo>" push -u origin main` yourself from a machine/terminal that already has GitHub credentials, or
   - Hand me a personal access token (repo scope) and I'll push over HTTPS with it, or
   - Add an SSH key to your GitHub account and to this machine (`~/.ssh`) and tell me to switch the remote to `git@github.com:dmix07/qr-research.git`.
2. **DigitalOcean server.** Deploy step 2 (SSH in, run `deploy/install.sh`, copy `.env`, start the service) is blocked — no server address/user was given. Reply with the IP (or hostname) and login user (`deploy/README.md` assumes `ubuntu`; the task said `root` — either works, `install.sh` just needs sudo) and I'll run the install, copy `.env.txt` over as `/opt/qr-research/.env`, and start `qr-research.service`.
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
