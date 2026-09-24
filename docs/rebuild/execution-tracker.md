# ELIS rebuild execution tracker

Updated 2026-09-23 after source-backed dashboard integration and historical reconciliation.
Implementation checkpoint: `5786bd7`. Production unchanged.

## Outcome and current judgment

The owner needs an understandable, familiar dashboard that explains truck–trailer performance, spending, protected capital and cash available to withdraw. A collection of financial forms and passing unit tests does not complete that outcome.

The financial foundation is useful and retained. The separate Finance workspace is a staging implementation, not an accepted replacement for the existing dashboard. Remaining work includes product integration and analysis features as well as missing business records. The earlier handoff must not be interpreted as “all development finished; only the owner's documents remain.”

## Status definitions

- **Implemented locally:** code exists; record its scope and limits.
- **Verified:** name the automated, browser, or real-record evidence. Synthetic checks are not real-business reconciliation.
- **Pending implementation:** engineering or product work remains; do not classify it as missing user input.
- **Needs business evidence:** identify the exact record/policy and what it blocks. Reuse available records first.
- **Accepted:** verified with the business's records and accepted in the browser for the stated scope.
- **Released:** deployed and verified live. No rebuild stage has reached this status.

Update this tracker at each implementation milestone and handoff. Do not assign a completion percentage based on file count, test count, or the existence of a screen.

## Approved plan, stage by stage

| Stage | Current evidence | Remaining work / exit condition |
| --- | --- | --- |
| 1. Definitions and examples | Owner-approved definitions; both original September 21 PDFs now trace through extraction, local posting and browser display: $23,700 → $5,836.92, support once | Resolve service-date exception before finalized accrual interpretation. Cash and ownership examples still require actual bank/asset evidence. |
| 2. Evidence, imports and accounting | Additive ledger, immutable history, CSV mapping, matching, reversals and draft reports; local SQLite/PostgreSQL checks | Unify existing settlement/repair intake with the new evidence/posting path. Verify supported PDF layouts, amendments and cross-period service dates using real records. Current accrual uses the entered effective date; adjustments remain manual. |
| 3. Equipment, repair funding and HELOC | Dated assignments, capital plans, reserves, owner claims, financing entries and disposal checks exist | Confirm acquisitions, protected balances and opening obligations. HELOC currently supports manually evidenced allocations; complete statement-driven tracing/reconciliation and a usable review flow. Verify lifetime history and sale scenarios. |
| 4. Reconstruct history | 175 source records inventoried; 37 derived allocations excluded; 78 real PDFs preserved; 77 arithmetic matched and one row ambiguity. Per-record review and CSV register exist | 97 originals unavailable. Reconcile 21 unexplained $200 gross differences, bank receipts and historical outside costs; only the September 21 pair is posted in staging. Historical review is not completed accrual reconstruction. |
| 5. Operations, Motive and screens | Familiar five-section Dashboard now has source-based revenue shares, paired costs/mile and exact earnings-gap explanation; linked historical reconciliation and selectable line trends | Finish existing intake/repair workflow integration, pair capital detail and full outside-cost performance. Add independent travel and load/payment matching. Verify Motive vehicle mapping, pagination, resets and interval coverage; implement the validated reconciliation flow. |
| 6. Acceptance and release | Synthetic desktop/mobile review and 24 financial tests recorded; cutover gate exists | Real-business acceptance, staging migration/auth checks, complete difference report, documented rollback and live verification. Full repository checks still have known baseline failures/lint debt. |

## Does Home answer the owner's questions yet?

| Owner question | Current answer | Required improvement |
| --- | --- | --- |
| What can I take home? | Provisional as-of calculation from entered evidence | Actual bank/obligation/reserve reconciliation; separate cash certainty from settlement earnings certainty |
| Which truck–trailer pair performs better? | Net earnings and earnings/calendar day | Comparable period, mileage coverage, earnings/mile, fuel/mile and incurred repair costs in one compact comparison |
| What is dragging the result down? | Aggregate category shares and basic exceptions | Ranked reasons for each pair's difference, dollar impact, evidence quality and a concrete next investigation |
| What capital is protected and what remains to recover? | Asset schedule with targets, funded amount and shortfall | Confirm balances; summarize progress in pair detail; show repair funding and capital separately without inventing historical savings |
| Is travel, fuel and settlement activity consistent? | Guarded MPG logic and completed-load exceptions | Verified independent travel, reviewed product rows, matched windows and load reconciliation; no unsupported misconduct conclusion |

## Integration direction from the owner's review

1. Keep the familiar application navigation, vehicle identities, settlement/PDF access, repair records and useful period controls.
2. Bring the corrected calculations into that experience. Avoid maintaining two competing places to enter the same settlement, repair or payment.
3. Retain the approved five-section Home hierarchy, expressed with familiar components. Combine repeated profit/expense presentations and move detailed history into the relevant workflows.
4. Use one company performance period and a clearly separate cash as-of date. Pair detail can narrow the scope without silently changing the company summary.
5. Keep setup and accounting administration in workflows. Prioritize actionable operating discrepancies on Home; explain missing evidence beside the metric it limits.
6. Correct settlement-based operating insight can be reviewed before Motive and complete tax history exist. Missing bank evidence blocks a confirmed withdrawal figure; missing consumption evidence blocks measured MPG; missing accounting policy blocks finalized books. Each limitation applies to its dependent result.

## Next milestone: one familiar dashboard, one real period

Owner: implementation agent. The source-backed presentation portion is implemented locally and browser reviewed. This milestone does not close funding, bank reconciliation or the overall plan.

- Use the September 21 source group already identified in the original audit. Recover available originals from the existing application before requesting documents from the owner.
- Trace originals → normalized rows → accounting entries → one reconciled presentation. Explain the support charge, carrier retention, internal trailer allocations and reserves exactly once.
- Integrate the five-section Home with the existing dashboard components and existing workflow entry points. Present the two earning pairs together and explain their result difference.
- Show expense dollars, share of original freight, fuel cost per reported/independent mile with its basis, and calendar-day earnings. Keep purchase MPG and measured consumption distinct.
- Demonstrate what changes when a repair is incurred, personally paid, reserve-funded or reimbursed. Keep missing real cash inputs visible.
- Review this milestone in the browser with actual source-backed settlement data and a before/after difference report. Then proceed through the remaining stages in this tracker.

## Evidence and input ownership

The implementation agent owns integration, extraction validation, reconstruction from accessible sources, report differences, test fixes required for the change, provider handling, and browser verification. Missing records are not a reason to leave independent engineering work unfinished.

Owner/accountant input is needed only for unavailable bank/card statements and balances, confirmed funded earmarks, acquisition/sale assumptions, private HELOC statements/use history, accounting/tax policy decisions, and authorized Motive access. Request specific gaps after inventorying what already exists. Do not invent balances or treat theoretical savings as funded cash.

Evidence references: `metric-dictionary.md`, `verification.md`, `implementation-and-rollout.md`, `design-verification.md`, and the earlier local dashboard critique under `.impeccable/critique/2026-09-23T14-38-39Z__frontend-src-pages-dashboard-tsx.md`.


## September 23 source-history implementation checkpoint

**Implemented locally:** graph-led familiar Dashboard; explicit incomplete-period warning; 175-record historical register; original source downloads; strict 77 Cargo and 277 summary/load normalization; saved/source differences; rolling fuel-spending, driver-share and other-cost review signals. Existing Settlements links to the review by source record. Charts preserve unsupported dates as gaps. Source selection never posts or edits production records.

**Verified:** September 21 source pair sums to $5,836.92 from $23,700.00; truck difference exactly $1,517.76; 21.86% fuel-spending/mile difference uses reported miles, not inferred consumption. Desktop1440, mobile390 and user1832 browser captures show the real source data. Month preset warns of four unposted records. Focused financial/history tests:35 passed; frontend build and changed finance/history lint passed. Full repository baseline failures/lint debt remain documented separately. Independent finish review and its precise outcome are recorded in the design handoff.

**Evidence:** `historical-reconciliation.md` contains the definition/difference report. Original PDFs, snapshot, review JSON, CSV and isolated database remain under the ignored local `backend/settlements_extracted/rebuild-20260923/`. The temporary synthetic demo database remains separate; its balances were not copied into this source review. Local8016 now serves this source-backed database, with unknown cash displayed honestly. Production remains unchanged.

**Next owned work:** trace the historical $200 gross adjustments and row ambiguity; recover missing historical originals; reconcile bank deposits and actual driver payments; integrate repair expenses/funding into the same intake path; finish HELOC statement allocation and Motive coverage. Missing records and unfinished engineering remain separately tracked. Browser acceptance by the owner and business cutover have not occurred.

## Approved money-flow presentation

The owner approved the Sankey/money-flow prototype for the freight allocation section. It is now connected locally to the existing report, with a signed waterfall alternative and expandable exact charges. No backend calculations, evidence, ledger records or production behavior changed. Negative/credit periods use the signed view; nonreconciling inputs retain exact figures and withhold the chart. Nine presentation-model tests cover the source total, cent precision, credits, losses, zero values and unsupported inputs. Follow the scoped design handoff for browser evidence and final review status. The accounting, history and cutover work above remains open.

## Retention score checkpoint — September 23

**Implemented locally:** per-pair normalized retention score, approved30% target/28% acceptable floor, same-scale comparison bars, dollars retained per$100, unrounded threshold classification, negative/no-revenue handling, expandable recorded-cost/funding bridge, and prospective adjustable targets with audit history. Shared company costs are allocated by freight only for comparison, without changing company ledger totals. Existing daily and mileage metrics remain available. No production deployment or cutover.

**Verified:**47 focused financial/history tests pass (12new retention cases); scoped frontend lint/build pass; existing bundle-size warning remains. Desktop1440, mobile390 and user1832 captures are under `.impeccable/review/retention/`. Mobile has no horizontal overflow and44px disclosure targets. Browser target validation, approved30/28 local save, persisted revision display and calculation disclosure were exercised. A local/UTC default-date mismatch was found and fixed by serving the minimum settings date and displaying its timezone. Independent design review is recorded in `retention-score-design.md`.

**Current source-backed result:**603 score103.9 at$31.16 per$100;609 score60.5 at$18.15 per$100, for the posted September21 statements. Both remain provisional. This does not close historical imports, bank/payment reconciliation, outside-repair integration, HELOC evidence, Motive, or production acceptance.

**Remaining score integration:** per-period completeness/attestation; explicit unfunded-target and scheduled-financing treatment before a finalized cash-retention score; equipment-card repayment attribution; operational reversal reconciliation; effective-dated historical driver attribution. Current UI identifies these limits rather than advertising final after-all-cost take-home pay. Metric details and worked no-double-counting examples are in `metric-dictionary.md`.
