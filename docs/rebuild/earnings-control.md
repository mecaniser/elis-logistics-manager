# Earnings control — implementation checklist

1. [x] Trace old/new calculations. Legacy vehicle targets are stored on Truck; trailer ROI in analytics.py calculates target = total_cost − expected_resale_value and reserve allocation = weekly target × earning statements. loan_balance_service.py derives principal from cumulative earnings; it is not lender payment evidence. New retention subtracts funded reserves only and omits unfunded saved vehicle targets.
2. [x] Define distinction: operating result; planning protection; recorded financing; withdrawal cash. Saved targets can inform estimates without creating funded balances or journal entries. Repair costs are incurred once; funded reserve coverage offsets retention once. Owner reimbursement does not add a second expense. Capital allocations and principal are not operating expenses.
3. [x] Reuse saved vehicle settings with source links; identify missing information instead of resetting existing values.
4. [x] Show period planning bridge and old/new differences separately from reconciled bank cash.
5. [ ] Financial regression tests and real-data comparison; desktop/mobile acceptance.
6. [x] Provisional preview: main integration, release checks, deployment and live acceptance. Final financial cutover remains gated by step 5 and missing inputs.

## Known calculation differences requiring visible treatment
- $141.86 displayed trailer weekly target is rounded from $22,129.69 / 156. Thirteen earning weeks produce $1,844.14 using the unrounded rate. Neither figure proves that money remains in a bank account.
- Prior screens count earning statements, while the approved new plan calls for calendar-time protection. Preserve old allocation amounts for comparison; identify prospective planning values explicitly rather than silently rewriting history.
- The truck screenshot has $9,600 in saved statement allocations but $0 in reserve ledger deposits. Do not manufacture ledger deposits or ask the owner to re-enter the targets.
- $2,193.94 trailer “Free Usable Profit” precedes modeled principal; the same screen's after-principal result is −$844.14. Neither should be presented as verified withdrawal cash.
- The September 21 freight bridge remains $23,700 → $5,836.92, including support $200 once. Internal truck/trailer allocation is not another company expense.

## Local implementation and evidence — September 27

Read-only `earnings_plan` report extension reuses saved repair/capital targets, distinguishes actual funding by purpose, includes unposted legacy statements exactly once, clips acquisition/recovery dates where known, and allocates trailer targets only on documented assignment days. No ledger entries or balances are created. Explicit accounting capital plans take precedence over legacy settings. Current saved settings are an estimate, not effective-dated historical assumptions.

September 21–27 local snapshot: posted freight $23,700; statement remainder $5,836.92; repair targets $600; trailer capital targets $290.77; pair planning subtotals $1,710.66 and $3,235.49. These are before incomplete truck recovery and unverified financing. Unrounded rates with cumulative cent rounding explain the one-cent difference from rounded weekly labels. Source months/year contain unposted statements, now included once as unverified management history. Full prior/new difference acceptance is still open.

49 focused finance/retention/planning/migration tests pass. Frontend build and lint pass. Local weekly panel and its source details verified; no production changes.

### Remaining gates
- Owner answers pending for each truck's resale/sale date and actual trailer HELOC payments; do not repeat requests for trailer plans or truck repair targets already saved.
- Cash-purchased trailer 003130 lacks acquisition date. Historical trailer assignments are incomplete before September 21: show gaps; do not retroactively apply today's pairing.
- Existing freight graph and retention score continue to use their posted/funded bases. They are not yet switched to this provisional planning basis; consolidate only after the difference report and missing financing/recovery treatment are resolved.
- Reuse known owner statement that trucks are paid off; persisted payoff provenance still needs implementation, not a repeat request for original loan settings.
- Provisional preview is deployed (see release evidence below); final take-home and the complete six-step rebuild remain open.

## Release and next-step comparison — September 27

PR #97 released provisional planning at 6148181; Railway web bc93df3d-7be0-40aa-9133-ea3402440f5d succeeded, matching tested frontend assets. Health 200 and anonymous accounting 401. Live inspection showed production lacked the local dated trailer assignments: this exposed a missing legacy-pairing bridge, not missing vehicle settings.

Follow-up reuses dated settlement trailer links as explicit planning inference until superseded. Confirmed assignments take precedence; conflicting observations do not allocate targets; no historical assignment is written. Missing capital plans are labeled incomplete/partial instead of showing an unexplained zero.

Read-only `python -m scripts.compare_earnings_periods --tenant 1 --start 2026-01-01 --end 2026-09-27` compares a full period against adjacent monthly reports. Local snapshot passes exact-cent additivity for both trucks after the inferred-pairing bridge. Private detailed output is /tmp/elis-earnings-period-comparison.json. Full financing/recovery completeness and consistency with the existing retention score remain open; do not equate additivity with finalized take-home.

Follow-up checks: 314 backend tests, frontend lint/build pass. Initial release also passed 31 frontend tests. No financial writes or schema changes.

## Live acceptance — PR #98

Merged/deployed commit `69d833c5ad28b2aa57dd05454a3f20f7dce2e688`; Railway web deployment `67460070-2f95-4c1c-805a-382f80b83f59` SUCCESS. Merge tree matches tested tree `0c17c0bb1de4478d974270a3a9848540d2adbf65`. Production serves `index-C1WSgSq4.js` and `index--zATyXC-.css`; health 200, anonymous accounting 401. Authenticated Money page shows saved trailer targets and partial capital labels; source disclosure identifies inferred pairing and unposted legacy history. No browser error logs observed.

Next: complete the old/new difference report and align retention score with the planning bridge while keeping incomplete recovery/financing visibly provisional. Preserve the existing paid-off-truck owner confirmation; do not ask the user to reenter saved vehicle targets.

## Retention alignment — local implementation

Planning scores now use the exact planning subtotal and matching posted plus unposted freight population, with linked legacy settlements excluded once. The recorded accounting retention report remains separately available. Target settings remain effective-dated; zero/nonpositive freight gives no score, losses remain negative, and incomplete plans retain provisional status. No new financial writes.

Verified 315 backend tests, including planning-score bridge equality, funded target offsets, personal repair payment and matching legacy freight. Frontend lint/build pass. January–September local period additivity still passes. Score alignment is local only pending release; remaining inputs are truck resale/sale plans and actual trailer financing evidence.
