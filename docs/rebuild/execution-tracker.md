# ELIS rebuild execution tracker

Updated 2026-09-23 after the owner's review of the local preview.
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
| 1. Definitions and examples | Owner-approved plan; metric dictionary; $23,700 → $5,836.92 fixture | Verify original records flow through extraction, posting and report with those totals. Fixture arithmetic alone does not close source verification. |
| 2. Evidence, imports and accounting | Additive ledger, immutable history, CSV mapping, matching, reversals and draft reports; local SQLite/PostgreSQL checks | Unify existing settlement/repair intake with the new evidence/posting path. Verify supported PDF layouts, amendments and cross-period service dates using real records. Current accrual uses the entered effective date; adjustments remain manual. |
| 3. Equipment, repair funding and HELOC | Dated assignments, capital plans, reserves, owner claims, financing entries and disposal checks exist | Confirm acquisitions, protected balances and opening obligations. HELOC currently supports manually evidenced allocations; complete statement-driven tracing/reconciliation and a usable review flow. Verify lifetime history and sale scenarios. |
| 4. Reconstruct history | Original-document retrieval and legacy comparison tools exist | Reconstruction has not been executed against the actual business. Recover accessible originals, post reviewed history in staging, retain gaps, and explain every changed total. |
| 5. Operations, Motive and screens | Five-section Home prototype; basic paired earnings; raw Motive fetch and manual interval entry | Integrate the owner's familiar dashboard and workflows. Add pair cost/mile, expense shares, movement/coverage comparisons and explanations of earnings differences. Verify Motive vehicle mapping, pagination, resets and interval coverage; implement the validated reconciliation flow. |
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

Owner: implementation agent. This remains pending, not completed by this document.

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
