# QUESTIONS.md — things that need Dustin

1. **GitHub.** No credentials to push from the build environment. `git init && git remote add origin <url> && git add -A && git commit -m "phase 0-1" && git push -u origin main`. Then add secrets (Settings → Secrets → Actions): `CONTACT_EMAIL`, `AIRTABLE_TOKEN`, `AIRTABLE_WORKSPACE_ID` (or `AIRTABLE_BASE_ID`), `SCREENER_API_KEY`, and optionally `CENSUS_API_KEY`.
2. **Airtable.** Base created Sept 5: `appBVtPxGG9DJpnxL` ("Q&R Research Candidates", Quarterline & Rock workspace) with candidates / sources / entities tables. Record writes via the connector weren't approved in-session; the first VM run upserts them with `AIRTABLE_TOKEN`. Or drag `examples/candidates_for_airtable.csv` into `candidates`. Views + Monday digest: `integrations/AIRTABLE_SETUP.md`.
3. **Screener key.** Without `SCREENER_API_KEY` the LLM stage is skipped and candidates keep their generator tags.
4. **Census key.** Free, instant: https://api.census.gov/data/key_signup.html. Unblocks ACS (#005/#006 inputs).

Provisional choices made for each are in DECISIONS.md.
