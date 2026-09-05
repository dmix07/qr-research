# Reproduction notes — Observations #001 and #002 from raw FDIC pulls

Run: `make reproduce` · Data pulled Sept 5, 2026 from api.fdic.gov (institutions index 2026-09-04; SOD index 2026-08-14).

| Figure | Published | Reproduced | Status |
|---|---|---|---|
| Institutions HQ'd in five counties, peak | 47, ~50 years ago | **47 in 1974** | exact |
| Institutions HQ'd in five counties, today | 4 | **4 (June 2025)** | exact |
| Regional deposits at institutions run from elsewhere | 59¢ of $1 | **59%** (2025, by institution HQ county) | exact |
| Region share of US deposits, 1994 | ~1 in 500 | **1 in 494** | exact |
| Region share of US deposits, latest | ~1 in 1,300 | **1 in 1,282** (2025) | exact |
| Region as share of national banks' deposits | ~18¢ of $100 | **14.7¢ (2025) · 16.5¢ (2024)**, HCs > $100B, deposit-weighted | disagreement, explained below |

## The 18¢ figure

"National banks" is not defined in the published method note. Tested definitions on 2025 data:

- Holding companies with > $100B US deposits (JPMorgan, PNC, Fifth Third, KeyCorp, Huntington): 14.7¢
- > $20B or > $50B (adds Old National, Flagstar): 15.8¢
- All out-of-state holding companies (8): 15.5¢
- > $300B (JPMorgan, PNC only): 8.7¢
- Same > $100B set on 2024 data: 16.5¢

The published 18¢ was written in August 2026 and most plausibly used 2024 SOD with a slightly broader set or a simple average rather than deposit-weighted (simple average of the five is 31¢, so probably not that). The reproduced range is 15–17¢; the published figure is 18¢; the story — a fraction of a percent, and shrinking — is unchanged. The disagreement is definitional, not a data problem.

**Recommendation for the recipe:** define "national banks" explicitly (proposed: holding companies with > $100B in US deposits, deposit-weighted) and state the year. The next published refresh of #002 should carry that definition in its method note so the number is reproducible to the cent.

## Caveats surfaced by the reproduction (belong in the recipe caveat fields)

- **Institution HQ county is the current/last HQ.** An institution that moved its headquarters is counted at its final location for its whole life. This could shift the 1974 peak by a few in either direction. The exact match to 47 suggests it didn't, but it's a known limitation of the institutions dataset.
- **Pre-1989 thrifts.** FDIC institution records cover FDIC-insured institutions; FSLIC-insured savings & loans before 1989 may be incomplete. The published note says "banks and thrifts" and the reproduced peak matches, so coverage appears adequate here, but this should be checked if #001 is extended earlier than 1970.
- **"Run from elsewhere" has two readings.** By institution HQ (used here, matches 59¢): 1st Source, Lake City, Crystal Valley, and one other are "here." By holding-company HQ it would be the same set in 2025 but could diverge in future years if a local bank is acquired but keeps its charter.
- **SOD deposits are branch-assigned by the bank.** Large depositors are sometimes booked to a main office elsewhere; SOD is the standard source but not a perfect geography of where money originates.

# Observation #006 from raw Gateway PARCEL files (Sept 5, 2026; 2025 assessment)

| Bucket | Published (2024) | Reproduced (2025) | Definition used |
|---|---|---|---|
| Owner's home | 82 | **81** | owner mailing house number + ZIP5 = property's |
| Someone nearby | 14 | **15** | owner ZIP5 is a ZIP within the three counties |
| Elsewhere IN/MI | 2 | **1** | owner state IN or MI, ZIP outside region |
| Out of state | 2 | **3** | everything else |

Within rounding; also a year newer. Two other definitions tested: exact address string match gives 55 (too strict — formatting differs), ZIP-only gives 86 (too loose). The house-number + ZIP definition is now fixed in the recipe. Sample: 152,044 single-family parcels (classes 510–515).
