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

## Retention release — September 27

PR #100 merged current main including PR #99 Bank Monitor updates. Production commit `082e4e79e91da127eefc07c906f3f6d31076f274`, Railway deployment `2c0ccdf4-c786-4a3a-9f3c-5c9f40127110` SUCCESS; tested/merged tree `1d937a2577b9aa53c75ea6c5fbc6b56b8b34ec10`. 315 backend tests, 31 frontend tests, lint/build pass. Live score subtotals match planning; health 200 and anonymous accounting 401; no browser errors.

Read-only selected-week and January–September saved-settlement-net comparison accounts for all arithmetic differences with zero unexplained residual. Local snapshot only; not a complete production history or evidence audit. Detailed private report: `.gstack/deploy-reports/2026-09-27-earnings-comparison.md`. Missing truck recovery plans, actual financing evidence and historical assignment coverage remain.

## Preserve trailer contribution — September 27

Owner clarified the saved $400/week trailer allocation represents trailer contribution, not solely capital protection. Display its full source-record allocation, split out the saved recovery target, and combine the remaining trailer contribution with truck remainder. Show other recorded costs/payments/protection adjustments once at pair level. Do not infer missing allocation amounts or label the combined estimate final profit. Source posting status stays in a secondary disclosure.

## Freight chart population alignment
The overview chart now uses the planning report's exact included unposted legacy IDs plus the posted breakdown. Accounting revenue stays unchanged. Modeled legacy loan interest stays excluded; category differences are shown as unclassified statement adjustments. Source-posting status is a compact notice, not an exclusion from the management chart. Tested expected combined week 23,700 gross / 5,836.92 remainder, linked-source exclusion and category gaps. 317 backend tests and frontend lint/build pass.

## Interactive freight drilldown
Other charges expands into individual chart ribbons/waterfall steps and collapses without changing totals. Fuel opens purchases grouped by the exact included settlements. Posted entries retain posted purchase rows; saved entries use the tenant's existing reviewed history by legacy ID. Missing detail/product/location stays explicit, and purchase totals differing from chart charges show a discrepancy. Changing report/business resets drilldowns. Local desktop/mobile and waterfall checks passed; 317 backend and 32 frontend tests, lint/build passed.

## Fuel branch expansion and unit prices
Fuel expands in the chart by purchase location; the transaction list opens separately through Purchase details. Fuel, other charges and purchase details start closed, independently. Chart branches preserve the original fuel total with an explicit unresolved difference if purchase detail is absent or mismatched. Purchase rows show recorded amount/gallons at three decimal places; missing or nonpositive gallons show unavailable. 35 frontend tests and lint/build pass; no backend changes.
The category label remains visible as the expand/collapse toggle inside its chart group. Removed displaced collapse controls. Separate-tab browser QA verified Fuel and Other expand/collapse independently using the same label, both default closed; purchase details remain opt-in.
Expanded fuel-location branches display recorded cost per gallon instead of freight share in both flow and waterfall. Unit rate is total charges / total gallons for the location, only when every included row has positive known gallons. Missing coverage shows unavailable. Other categories retain freight shares. 36 frontend tests, lint/build and local browser verification passed.

## Fuel purchase comparison — September 27

Added an optional Miles vs fuel report within the expanded fuel flow, grouped by stable asset/VIN. Shows reported/independent miles, purchased gallons, expected diesel at the owner's 6–7 MPG reference, and a weighted 28-day statement-date comparison. Posted mileage remains tied to its immutable statement snapshot; saved rows use reviewed source history. Estimated miles, unknown products, missing gallons, credits, unreconciled sources and purchase-total mismatches block MPG conclusions. DEF is excluded from diesel volume. This does not claim measured consumption or establish missing loads.

Local validation: 317 backend tests, 39 frontend tests, lint and production build passed. Selected week: VIN 250024 has 3,665 reported miles / 676.7 all-product gallons; VIN 250022 has 3,114 / 471.1. Products remain unknown, so neither receives an established diesel MPG. No data writes or schema changes.

## Owner earnings bridge — local preview

The dashboard now follows the freight allocation with a compact signed bridge from statement remainder to estimated owner earnings. It reuses the existing pair bridges, includes unassigned company results, shows repair and capital targets, preserves reserve-funded repair offsets, and deducts recorded equipment principal once. Missing principal evidence is labeled Not confirmed. The trailer disclosure splits the internal allocation into protected capital and remaining trailer earnings without treating the whole allocation as a company expense.

Selected-week preview: $5,836.92 minus $600 repair target and $290.77 capital target = $4,946.15 before unverified financing, incomplete capital plans and unrecorded expenses. The $800 trailer allocation contains $290.77 recovery and $509.23 contribution before other costs/financing. This is not verified withdrawal cash. No financial records changed.

43 frontend tests pass, including reserve offsets, principal, company losses and bridge reconciliation. Lint/build and desktop/mobile browser checks pass. Color-coded freight amounts are included in this local change. Deployment remains pending.

## Continuous owner flow — local preview

The overview's money-flow chart now continues directly from the statement-remainder node into recorded owner costs, repair reserves, capital recovery, recorded principal and the estimated owner remainder. Uses the same monetary scale for both stages. Overview no longer repeats the standalone owner bridge; pair detail stays below. Trailer allocation detail remains on Money. Signed adjustments, losses or a mismatched bridge use the existing signed breakdown rather than a falsely balanced flow. Unknown loan amounts stay outside the sized branches and are explicitly unresolved. No calculation/data changes. 43 frontend tests, lint/build and desktop/mobile expanded-flow checks pass; not deployed.
