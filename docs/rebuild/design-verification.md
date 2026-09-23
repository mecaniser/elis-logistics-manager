# Finance workspace design verification

Reviewed: 2026-09-23. Disposition: existing ELIS interface extended; scoped design handoff complete.

## Scope and authority

This records the implemented Finance surface against [interface-direction.md](interface-direction.md). The existing application world is retained: system sans typography, light operational surfaces, company navigation, business switcher, and access to legacy workflows. This work does not establish a new global visual identity or repair preexisting application-wide design drift.

The Impeccable documentation reference was read. Root `PRODUCT.md` and `DESIGN.md` were absent at inspection. No root design system or `.impeccable/design.json` sidecar was generated: the authorized documentation scope is this surface handoff, and the Finance composition and local colors are not promoted to global rules. The direction brief's generic finish reference to `DESIGN.md` is fulfilled here as scoped documentation under the retained-world decision; global extraction remains outside this change.

## Built patterns

| Pattern | Implemented behavior and source |
| --- | --- |
| App continuity | `frontend/src/index.css` supplies the incumbent system sans stack. `frontend/src/components/Layout.tsx` retains the dark company bar, business selection, responsive navigation, and light page background. Finance is an additional navigation destination. |
| Surface hierarchy | `frontend/src/pages/Finance.css` scopes its vocabulary under `.finance-app`: dark blue-grey text, muted supporting copy, restrained green actions, amber incomplete-evidence labels, and red errors. The cash summary is a pale green panel; remaining Home sections use spacing and dividers. No decorative shadows or artwork are introduced. |
| Numbers and typography | Tabular numerals support financial comparison. The page title is 30px on desktop and 25px at the mobile breakpoint; section titles are 20px. Cash has a responsive 26–44px emphasis. Labels and table text remain subordinate to the amounts they explain. These are Finance-local values. |
| Navigation and dates | Seven workspace tabs retain a visible active underline and `aria-current`. Period start/end and a separate cash as-of date make the reporting bases explicit. Tabs scroll horizontally when space is limited. |
| Home sequence | Exactly five top-level content sections: Available to owner; Where the freight revenue goes; Truck and trailer performance; Needs your attention; Performance over time. Legacy settlement comparison is a disclosure inside revenue distribution, not a sixth section. |
| Evidence and uncertainty | Cash status is textual as well as colored. Missing evidence remains visible next to the provisional result and links to reconciliation. Missing table values display “Not established.” Negative availability receives a funding-shortfall message. Period accrual earnings, reserve funding, and cash available to withdraw have separate explanations. |
| Detail on demand | Pair rows expand to supporting component and settlement tables. Existing reports and source documents remain accessible. The trend shows one selectable measure with animation disabled. |
| Workflow forms | `frontend/src/components/finance/CommandForm.tsx` and `commandFields.ts` provide labeled inputs, source selectors, contextual help, repeatable rows, explicit posting actions, disabled saving states, alert errors, and status confirmation. Accounting package download is disabled until report readiness passes; draft download remains distinct. |
| Responsive behavior | The Finance container is capped at 1160px. At 700px and below, the cash panel and workflow grids stack; date controls use two columns; pair summaries and exception rows reflow. Dense tables stay within overflow containers. Inputs and buttons have a 40px minimum height; scoped focus outlines are present. |

## Evidence checked

Source inspection covered `Finance.tsx`, `Finance.css`, both Finance component files, incumbent `index.css` and `Layout.tsx`, and the direction brief. The cash-state prerequisite logic in `backend/app/services/finance.py` was checked to confirm the status label's meaning.

The final UI reviewer reported a pass after three bounded corrections. The final source confirms:

1. **Stale scope is hidden.** Report rendering requires the loaded tenant, period start, period end, and cash as-of date to match the current selection. A request sequence prevents older overlapping loads from replacing the latest result. Load errors hide report content and present retry guidance.
2. **Home retains five sections.** Legacy comparison is nested under revenue distribution; workflow forms and source documents render outside Home.
3. **Cash stays provisional until its prerequisites are met.** The backend includes policy, opening balance, historical obligation coverage, owner funding treatment, account coverage, statement coverage, and other cash issues in its result. The UI shows “Reconciled cash” only for a reconciled result; otherwise it shows “Provisional · evidence needed” with available issue detail.

The saved [desktop capture](../../.impeccable/review/desktop.png) and [mobile capture](../../.impeccable/review/mobile.png) were visually inspected for this handoff. Both show the explicitly labeled synthetic preview business, the same five-section hierarchy, nested legacy comparison, and provisional cash with prerequisite messages. The desktop reconciliation uses two columns; the mobile reconciliation and pair details stack. The screenshot amounts are synthetic fixture values, not verified business balances.

This documentation pass inspected saved rendered evidence and source; it did not independently rerun browser interactions, accounting tests, accessibility tooling, or production checks. The reviewer pass and captures establish the bounded visual review, not production deployment or live accounting acceptance.

### Later functional additions

After the three-correction visual verdict, two small additions received a bounded source and functional-contract check:

- The deposit/transfer matching form now exposes operating, investing, and financing portions for card repayments. All three reuse the existing money-input pattern, default to `0.00`, and explain allocation against underlying charges. Their payload names match the backend schema, and the existing form normalization applies the standard two-decimal money validation.
- The Accounting income statement now displays `disposal_gain` between depreciation and net income. It uses the existing table pattern and the matching report field, keeping disposal effects separately visible.

These additions do not change Home, Finance CSS, or the application layout. They were not part of the three-correction visual verdict or its saved captures. This follow-up checked source wiring and functional contracts only; it did not add a new browser visual verdict or rerun the accounting tests.

## Deviations and handoff

No material visual deviation from the retained-world direction was found within the reviewed Finance surface. The documentation location is the explicit scoped exception described above; no global design-system change is intended.

No artwork is required for this operational finance interface. No shipping raster assets were added; the two PNGs are review evidence only. Further Finance work should retain the as-of/period distinction, evidence-state messaging, five-section Home composition, and progressive disclosure. Those requirements belong to this Finance surface and are not application-wide prohibitions.
