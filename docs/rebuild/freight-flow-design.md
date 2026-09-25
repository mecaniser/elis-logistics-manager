# Freight allocation design handoff

September 23, 2026. **Final disposition: SHIP for the scoped local finish review.** The single fidelity finding is resolved and the corrected desktop/mobile disclosures are verified. This handoff covers the approved freight chart refinement, not owner acceptance, production deployment or completion of the rebuild.

## Scope and design authority

The owner approved the Money flow / Sankey prototype, then its implementation in the existing Dashboard revenue section. The surface remains **Operate**: explain where freight revenue goes and expose exact statement figures. It extends the incumbent system documented in [history-design-audit.md](history-design-audit.md); the familiar shell, system typography, white panels and restrained analytical colors remain.

The approved prototype is `freight-flow-options.html` under `/Users/sergio_m1_promax/.codex/visualizations/2026/09/23/01a0cea9-b402-7db2-81de-9254254efba9/`. Impeccable's document reference informed this scoped handoff. The session context step already ran. No new global `PRODUCT.md`, `DESIGN.md`, tokens or design sidecar were created.

Implementation: `frontend/src/components/finance/FreightFlow.tsx`, `FreightFlow.css`, `freightFlowModel.ts` and integration in `OwnerOverview.tsx`. Named Impeccable reviewer/documenter agents were unavailable; independent default agents supplied the scoped review and documentation fallback. This documenter inspected source and supplied evidence, without running a new browser session or audit.

## Implemented behavior

| Pattern | Behavior and purpose |
| --- | --- |
| Money flow | Default for reconciled positive freight with nonnegative allocations. Proportional ribbons connect freight to directly labeled destinations; labels show dollars and share of original freight without a legend lookup. |
| Detail hierarchy | Carrier retention, driver pay, fuel purchases, other charges and statement remainder lead. Expandable exact figures retain every original category, its amount and its individual freight percentage. |
| Signed waterfall | Alternate view shows sequential deductions, credits and remaining amounts. It is selected automatically for credits, negative remainder or nonpositive freight; invalid/nonpositive gross displays “Share unavailable.” |
| Reconciliation | Cent-precise reconciliation is required before either chart appears. Unsupported or mismatched inputs show a status message and expanded reported figures, withholding misleading geometry. |
| Responsive interaction | Narrow layouts reduce ribbon width and stack direct labels. Buttons have 44px minimum heights, pressed states and native keyboard operation. The exact-figures disclosure has a visible rotating chevron. |
| Visual treatment | Tabular monetary figures, slate carrier/other colors, purple driver, brown fuel and blue remainder preserve the approved prototype within the existing Finance styling. View changes are immediate. |

The reviewed source pair retains **$23,700.00 freight → $5,836.92 statement remainder**. Carrier retention is $2,844.00, driver pay $7,110.00 and fuel purchases $6,844.83. Other charges total **$1,064.25**, comprising insurance $600.00, tolls $264.25 and support $200.00; fuel is separate. Rounded individual shares are 2.5%, 1.1% and 0.8% respectively.

Statement remainder remains before outside bills and cash protection. Carrier and driver settlement shares are not personal take-home; internal trailer allocations remain within the business and reserves are not operating expenses.

## Emil review: before, after and purpose

| Before | After | Why |
| --- | --- | --- |
| A stacked allocation required matching chart segments to categories. | Proportional money-flow ribbons terminate beside direct amount and percentage labels. | Explain the allocation with less cross-referencing. |
| A positive allocation shape could misrepresent credits or losses. | A signed waterfall preserves direction and intermediate remaining balances. | Keep the visual consistent with the financial inputs. |
| Small charges competed with the main allocations. | One other-charges destination leads to all underlying exact categories. | Keep the overview readable while retaining traceable detail. |
| Initial implementation omitted individual percentages in the exact disclosure. | Insurance, tolls, support and all other underlying categories again show their freight shares, with a guard for invalid/nonpositive gross. | Restore approved prototype fidelity. **Resolved and verified on desktop/mobile.** |

## Verification evidence

| Evidence class | Result and boundary |
| --- | --- |
| Implementation-agent local checks | Nine presentation-model tests passed, covering source totals, cent precision, credits, losses, zero values and unsupported inputs; the model was unchanged by the disclosure correction. Final targeted lint, frontend build and diff whitespace checks passed. The existing bundle-size warning remains. |
| Implementation-agent browser checks | Review covered 1440px desktop, 390px mobile and the user's 1832px viewport, both chart views, keyboard view changes and disclosure operation. Supplied checks found 44px buttons, no horizontal page overflow and no console errors. Corrected desktop/mobile disclosure captures rendered successfully; DOM checks confirmed insurance 2.5%, tolls 1.1% and support 0.8%. Mobile page width and scroll width both remained 390px. |
| Independent finish review | All five initial captures were valid. Initial verdict: **FIX**, solely for missing individual category percentages in exact details. Final verdict: **SHIP** after reviewing the corrected desktop/mobile disclosure; no finding remains from that bounded correction review. The reviewer did not independently operate the browser. |
| Documentation | Read the implementation, incumbent design handoff, execution tracker and supplied reviewer notes. No additional accounting validation, browser audit or production check was run. |

Saved rendered evidence:

- [Money flow desktop](../../.impeccable/review/freight-flow/desktop.png), [mobile](../../.impeccable/review/freight-flow/mobile.png), [user viewport](../../.impeccable/review/freight-flow/user.png)
- [Waterfall desktop](../../.impeccable/review/freight-flow/waterfall-desktop.png), [mobile](../../.impeccable/review/freight-flow/waterfall-mobile.png)
- [Corrected exact details desktop](../../.impeccable/review/freight-flow/details-desktop.png), [mobile](../../.impeccable/review/freight-flow/details-mobile.png)

The temporary review notes are `/tmp/elis-freight-flow-review.md`; this handoff preserves their scoped outcome durably. Screenshots are review evidence, not shipping assets.

## Remaining acceptance

No underlying data, backend calculation, ledger record or production behavior changed. Local presentation validation does not establish bank receipts, owner-available cash, complete historical accounting or live release acceptance. The outstanding accounting, integration and cutover work remains in [execution-tracker.md](execution-tracker.md).
