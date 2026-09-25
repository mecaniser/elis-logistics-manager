# Source-history dashboard design audit

Reviewed September 23, 2026. **Final disposition: SHIP for the scoped local finish review.** All five identified code findings are resolved and the final desktop history recapture renders both fuel series, axes and grid. This verdict covers the local dashboard/history presentation; it does not mean production deployment, owner acceptance, complete historical reconciliation or completion of the rebuild.

## Scope and design authority

This milestone retains the familiar ELIS shell and applies the approved graph-led cash, truck–trailer comparison and settlement-history direction. Its mode is **Operate**: explain performance, expose evidence and guide the next investigation. The dark navigation, system sans typography, white panels and blue/purple analytical accents remain recognizable. No new visual-world exercise was required.

Impeccable's audit/document references and the Emil design-engineering skill informed this handoff. The session's Impeccable context step had already run. No root `PRODUCT.md` or `DESIGN.md` exists; this scoped document does not invent a global brand, extract a new global token contract or create a design sidecar. The earlier [Finance design verification](design-verification.md) remains historical evidence of a separate synthetic preview.

Reviewed implementation: `frontend/src/components/finance/OwnerOverview.tsx`, `HistoryTrend.tsx`, `frontend/src/pages/SettlementHistory.tsx`, `OwnerDashboard.css` and shared `Finance.css`. The independent finish reviewer also inspected the related finance/evidence services and tests. Named skill reviewer agents were unavailable, so an independent default agent performed the bounded review. This documentation author inspected code and supplied review/QA notes; browser interaction and screenshot inspection evidence below is attributed to the implementation agent and independent reviewer respectively.

## Implemented surface patterns

| Pattern | Current behavior |
| --- | --- |
| Cash and period | Cash leads the familiar dashboard, with its own as-of date. Unknown cash says “Cash needs reconciliation.” Settlement remainder stays separate from funds available to withdraw. Selecting a period with unposted records displays incomplete coverage. |
| Revenue shares | A stacked freight allocation graphic is followed by category dollars and percentages. Carrier/driver shares, company remainder and internal trailer allocations have distinct meanings; funding targets are not presented as confirmed savings. |
| Pair comparison | Trucks and assigned trailers appear together, side by side on desktop and stacked on mobile. Exact signed category effects explain the earnings difference. Source details and outside-cost coverage are reachable through disclosures. |
| Trend | One measure selector changes the history plot. Known unsupported dates for plotted assets remain null gaps. A labeled chart and exact-value table expose the same basis; chart animation is disabled. |
| History review | Coverage counts precede filters and record disclosures. Source status remains visible even when originals are unavailable. Records expose original downloads, deduction/load/fuel rows, saved/source differences and investigation items. Counts distinguish rendered rows from matching records. |
| Responsive detail | Dense monetary tables scroll within their panels and preserve entire amounts. Main record disclosures have an explicit chevron; native details/select semantics and scoped focus outlines remain. Dashboard/history controls use 44px minimum heights. |

These are surface-specific implementation observations, not application-wide design mandates. The dashboard uses local Finance variables for ink, muted text, accent and borders, with additional literal chart/status/surface colors. The reviewed appearance is the light theme.

## Audit health and integrity

**Implementation integrity: PASS within this scope.** The visible hierarchy is specific to fleet settlement review, preserves evidence uncertainty and links explanatory graphs to exact figures and originals. The session detector returned `[]`; that deterministic result supports the review but does not establish accessibility or financial correctness by itself.

Scores use Impeccable's 0–4 scale. They describe the bounded evidence available, not certification or a release gate for the whole application.

| Dimension | Score | Evidence and limit |
| --- | ---: | --- |
| Accessibility | 3/4 | Native labeled inputs/selects/details, explicit focus outlines, textual statuses, exact chart tables and disabled chart motion. Ten checked dashboard controls measured 44px high. No full keyboard journey, screen-reader session or comprehensive contrast/WCAG audit was performed. |
| Performance | 2/4 | No chart entrance animation or heavy decorative effects; history initially renders 20 records. The existing Vite warning remains: approximately 2,244.55 kB JavaScript / 660.46 kB gzip. Build success is not load-time or interaction-performance measurement; no runtime benchmark was recorded. |
| Responsiveness | 3/4 | Supplied browser measurements show mobile width and scroll width both 390px; a 518px history table stays inside its scrolling panel. Desktop 1440px, mobile 390px and user viewport 1832px captures were reviewed. Other widths, browser engines and enlarged-text behavior were not comprehensively tested. |
| Theming | 2/4 | Shared Finance variables and owner-surface overrides provide a partial token vocabulary. Charts and several surfaces use literal colors. No dark theme or theme-switching acceptance is claimed. |
| Design / implementation integrity | 4/4 | Familiar shell, restrained graph-led hierarchy, exact difference explanations, explicit source limitations and resolved reviewer findings. No detector findings; no decorative financial claims. |
| **Total** | **14/20** | **Good under the audit rubric; performance and token coverage remain weaker dimensions.** |

The score does not require a new visual rebuild. Existing bundle size and partial theming are recorded limitations, not newly proven runtime failures. Further performance work should begin with measurement rather than a claim that this review established responsiveness under load.

## Emil review: before, after and purpose

| Before | After | Why |
| --- | --- | --- |
| Earlier overview emphasized textual totals and separate detail. | Freight shares, paired results and exact signed category differences lead into one selectable history graph. | Make the operating comparison legible while keeping detail available on demand. |
| Fuel interpretation could blur purchased fuel, spending and consumption. | Spending per reported mile is labeled with its basis; measured MPG stays “Not established.” | Avoid giving unsupported precision or suggesting a misconduct finding. |
| Narrow tables wrapped monetary values mid-number. | Monetary cells preserve the number; the table scrolls within its panel. | Exact amounts remain readable on mobile without widening the page. |
| **P2:** Filtering before constructing dates erased known unsupported history dates. | Known dates for plotted assets remain in the series with null unsupported values and `connectNulls={false}`. | A known missing source must break the line, not imply continuous verified evidence. **Resolved.** |
| **P2:** “Cost and amount exceptions” omitted load/fuel reconciliation discrepancies. | The filter includes `load_total` and `fuel_total`. | The filter reaches both amount discrepancy types its label promises. **Resolved.** |
| **P3:** Main historical summaries removed the native marker without a replacement. | An 18px chevron visibly rotates when the record opens. | The evidence entry point looks interactive and reveals state. **Resolved.** |
| **P3:** Checked controls were 40–41px high. | Scoped controls have 44px minimum heights, confirmed by the supplied measurement of ten dashboard controls. | Improve touch usability without changing the established visual language. **Resolved.** |
| **P3:** “175 records shown” described matching records while only 20 rendered. | “Showing 20 of 175 matching records,” with the count updated as filtering/reveal changes. | Keep pagination state truthful. **Resolved.** |
| A frequently used analytical view could acquire decorative motion during polish. | Chart animation stays disabled; no entrance sequence was added. The reduced-motion rule removes button press scaling. | Repeated financial review should not wait for animation. |

Original finish-review findings: **0 P0, 0 P1, 2 P2, 3 P3; all five resolved.** A subsequent blank desktop chart screenshot was a capture limitation, not an established code defect. The replacement was checked after rendering and resolved that limitation. No further correction or recapture is outstanding within this finish-review scope.

## Verification evidence

| Evidence class | Result and boundary |
| --- | --- |
| Local checks, supplied by implementation agent | Frontend build, scoped finance/history lint and `git diff --check` passed; 35 focused backend financial/history tests passed. Existing repository-wide baseline failures and lint debt remain outside this result. |
| Browser interactions, supplied by implementation agent | Month preset warned of four unposted records; week reset the range. Searching `2617` returned one record; expanded detail showed $11,900 freight, $2,159.58 remainder and zero arithmetic difference. Fuel measure selection worked. Unfiltered list showed 20 of 175. No captured console errors. |
| Bounded independent finish review | Reviewer inspected code and five saved captures, requested five targeted corrections, checked those corrections and then inspected only the replacement desktop history capture. Final verdict: **SHIP for the exact scoped local finish review**. Reviewer did not independently operate the browser. |
| Documentation pass | Read current source, reconciliation/tracker documents and session QA/reviewer notes. No extra browser, accounting test suite or production check was run for this documentation-only handoff. |

Saved rendered evidence:

- [Dashboard desktop, 1440px](../../.impeccable/review/history/desktop.png)
- [Dashboard mobile, 390px](../../.impeccable/review/history/mobile.png)
- [Dashboard at the user's 1832px viewport](../../.impeccable/review/history/user-dashboard.png)
- [Historical reconciliation desktop, final rendered-chart capture](../../.impeccable/review/history/history-desktop.png)
- [Historical reconciliation mobile](../../.impeccable/review/history/history-mobile.png)

Session working notes are `/tmp/elis-history-qa-notes.md` and `/tmp/elis-history-finish-review.md`; the durable scope and verdict are preserved here because temporary notes are not a lasting repository artifact. No artwork or shipping image asset was added; these PNGs are review evidence.

## Real-source scope and remaining acceptance

This milestone inventories **175 source records**, excluding 37 derived trailer allocations from additional revenue. **78 originals were preserved: 77 arithmetic matched and one needs source-row review. 97 originals remain unavailable.** Only the September 21 pair was posted to the isolated local ledger. Source selection and historical review do not post or alter production records.

The reviewed source pair reconciles $23,700 freight to $5,836.92 statement remainder. The $1,517.76 pair difference is explained by the category effects. The 21.86% fuel-spending-per-mile difference uses reported distance; it does not establish measured consumption. Bank deposits, actual driver receipt, confirmed withdrawable cash, final accrual books and proven loss remain unestablished. Arithmetic matching cannot substitute for that evidence.

See [historical reconciliation](historical-reconciliation.md) for source differences and [execution tracker](execution-tracker.md) for unfinished engineering and evidence work. The synthetic preview remains a separate historical verification exercise; its balances were not copied into the source review. Production is unchanged. Owner browser acceptance, complete business reconciliation, cutover and live release verification remain open.
