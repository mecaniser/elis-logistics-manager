# Retention score design handoff

September 23, 2026. **Final disposition: SHIP for the scoped local finish review.** The independent reviewer found no material fixes in the desktop, mobile and user-viewport captures. This decision covers the retention presentation and its reviewed local interactions; production deployment, owner acceptance and financial completeness remain open.

## Scope and design authority

The owner approved a **30% retained-freight target and 28% acceptable floor**. A score of 100 means meeting the target. The feature extends the existing **Truck + trailer performance** section and familiar application, preserving equipment identities, daily and mileage metrics, source links, navigation and the separate cash-availability section.

This is an ordinary extension of the incumbent visual system, following [freight-flow-design.md](freight-flow-design.md). Impeccable's document reference informed this scoped handoff. The named documenter was unavailable, so a default agent provided the documentation fallback. No root product/design system, global tokens or design sidecar were created.

Implementation: `frontend/src/components/finance/RetentionScore.tsx`, `RetentionScore.css` and integration in `OwnerOverview.tsx`. Financial definitions and remaining implementation obligations are maintained in [metric-dictionary.md](metric-dictionary.md) and [execution-tracker.md](execution-tracker.md).

## Implemented design and behavior

| Element | Behavior and purpose |
| --- | --- |
| Leading figures | Each pair shows its normalized score beside dollars retained per $100 of freight. Large tabular figures preserve an interpretable dollar basis alongside target attainment. |
| Comparable bars | Horizontal bullet bars share the same scale across pairs. The scale includes zero, losses and above-target results; a shaded acceptable-to-target range, dashed floor and solid target mark the benchmarks. Text labels explain the markers. |
| Status | Every result explicitly says **Provisional**, followed by Target met, Acceptable, Below acceptable or No positive freight revenue. Status comes from the unrounded ratio; display rounding cannot promote a result into a better band. |
| Edge cases | Above-target scores can exceed 100; losses remain negative and use the loss color. Zero or negative freight shows dashes and the no-positive-revenue status, withholding the bar. |
| Calculation disclosure | “How this score is calculated” expands the recorded-cost/funding bridge, retained contribution, freight denominator and specific evidence gaps. Zero recorded amounts do not establish that a cost is absent. |
| Target disclosure | “Adjust retention targets” exposes editable target, acceptable floor and prospective effective date, with persisted target history and inline error/success feedback. Earlier reports retain the benchmark effective at their period start. |
| Visual continuity | Existing white panels, system typography, muted secondary text and the Finance accent remain. The chart adds restrained slate benchmark shading and an amber loss treatment. No decorative animation was introduced. |
| Responsive and accessible behavior | Pair cards stack at narrow widths; target fields become one column below 700px. Native disclosures support keyboard use; the chart has an accessible text summary. Inputs and reviewed disclosure targets meet a 44px minimum. |

Score = retained contribution / positive freight revenue / target percentage × 10,000. Equivalently, retained dollars per $100 divided by the target percentage, multiplied by 100. At the approved target: $30 retained per $100 scores 100; $28 scores approximately 93.33 and is acceptable; $25 scores approximately 83.33 and is below acceptable; $33 scores 110; a $3 loss scores −10.

The contribution bridge includes recorded outside costs/income, allocated company result, business-paid equipment obligations and new funded protection, with offsets for repairs already covered by protected funds. Shared company costs are allocated by freight for pair comparison; company ledger totals are not duplicated. Period totals determine the score. Book depreciation and equipment disposal results stay in ownership reporting. The metric is management contribution, not book profit or a confirmed withdrawal amount.

For the posted September 21 source statements, the reviewed display shows **603: 103.9 / $31.16 per $100** and **609: 60.5 / $18.15 per $100**. Both remain provisional.

## Emil review: before, after and purpose

| Before | After | Why |
| --- | --- | --- |
| Pair performance led with absolute daily and mileage figures. | A normalized retention score and dollars per $100 lead, with existing metrics retained below. | Compare freight retention against one approved business target without losing operating context. |
| No explicit acceptable retention benchmark appeared beside each pair. | Same-scale bars show the 28% acceptable floor and 30% target. | Make the distance to each benchmark directly comparable. |
| An aggregate result could obscure its recorded-cost basis. | Expandable calculation and evidence gaps accompany an always-visible provisional status. | Let the owner inspect the calculation without implying all costs or cash are reconciled. |
| No prospective retention-target workflow existed. | Dated target changes preserve history and earlier report benchmarks. | Permit policy changes without silently rewriting prior comparisons. |
| Browser-local and server dates could disagree at the UTC boundary. | The server supplies the minimum effective date and the form names its timezone. | Keep the displayed permissible date consistent with save validation. |

## Verification evidence

| Evidence class | Result and boundary |
| --- | --- |
| Implementation-agent automated checks | 47 focused backend financial/history tests passed, including 12 new retention cases; nine existing freight presentation tests passed. Scoped frontend lint and build passed. The existing bundle-size warning remains; this is not a claim that all repository checks pass. |
| Implementation-agent browser checks | Desktop 1440px, mobile 390px and user 1832px section captures were validated. Checks found no horizontal overflow, 44px disclosure targets and no error logs. Calculation disclosure and target validation/save/history were exercised locally. |
| Target persistence | A 35% acceptable floor against the 30% target was rejected. The approved 30%/28% values were saved in the isolated review database effective September 24, 2026, using the explicitly labeled UTC setting because the business timezone is unconfirmed. The saved revision appeared in target history. This was a local review-database change. |
| Independent fresh finish review | Reviewer examined the three validated section captures and returned **SHIP**, with no material fixes at the scoped local finish level. This is visual finish evidence, not production acceptance or an independent accounting audit. |
| Detector | `.impeccable/review/retention/detector.json` contains `[]`. This empty artifact does not establish financial completeness. |
| Documentation check | Documenter read the implementation, incumbent freight handoff, metric definitions and execution checkpoint; opened all three rendered captures and checked the detector artifact. Automated and browser interaction outcomes above are supplied implementation evidence, not rerun by the documenter. |

Saved rendered evidence: [desktop](../../.impeccable/review/retention/desktop.png), [mobile](../../.impeccable/review/retention/mobile.png), and [user viewport](../../.impeccable/review/retention/user-1832.png). These are actual section captures used for review, not shipping assets.

## Remaining work and acceptance

**Every score remains provisional until per-period completeness/attestation engineering is implemented and its required evidence is satisfied.** The current application has no path to attest a final score. Finishing this visual review does not remove that limitation.

Unfunded reserve targets and scheduled financing obligations are not silently treated as funded deductions. Finalized cash-retention treatment still needs explicit engineering and verification, including equipment-card repayment attribution, operational reversal reconciliation and effective-dated historical driver attribution. Current driver names are equipment labels; unassigned equipment remains a review gap.

Historical imports, bank/payment reconciliation, outside-repair integration, HELOC evidence and reconciliation, Motive coverage, owner browser acceptance and cutover remain open in the execution tracker. The implementation agent retains ownership of unfinished engineering; unavailable business records are a separate dependency. No production changes or deployment occurred, and no final after-all-cost take-home score is claimed.
