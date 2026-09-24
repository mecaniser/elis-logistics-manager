# ELIS rebuild execution tracker

Updated 2026-09-24 after payment-account connections and automatic owner-payment accounting. Production unchanged.

## Current execution lane — keep the original objective in view

The original question is whether fuel use and other costs explain why one truck retains less than the other. Repair payment work is part of outside-expense reconciliation (stages 2–3), not a replacement objective or a new banking product.

| Order | Work | Status and next exit condition |
| --- | --- | --- |
| Current | Repair payees, payment methods, personal/business account identities, owner reimbursements | Local integrated path now records eligible confirmed personal payments once; connects selected identities to existing statement or monitored sources; matches actual repayments. Verify the owner's real account links and three earlier personal confirmations without assuming prior reimbursements. |
| Next | Outside costs → available cash and pair retention | Validate a real repair through expense, owner funding/repayment and the truck/trailer results; reconcile business cash/Zelle evidence and funded repair reserves. Business cash, card and mixed-payment intake still need a simpler operator path. |
| Then | Original fuel and settlement anomaly investigation | Return to the historical register, 21 unexplained $200 gross differences and missing originals. Compare matched fuel purchases, driver pay and mileage windows; add independent Motive/odometer evidence before calling anything consumption. Existing fuel-spending signals are not evidence of missing freight or theft. |
| Remaining | Capital, HELOC and lifetime return | Finish statement-based mixed-use financing allocation, actual payments, recovery targets and disposal acceptance. Preserve gaps instead of inferring payoff or saved reserves. |
| Release | Integrate and reconcile before cutover | Difference report, main integration, production auth/migration checks and browser acceptance remain separate gates. Local functionality does not establish production readiness. |

Do not hide pending engineering under “waiting for records.” Missing private bank/card/HELOC statements, opening balances and Motive coverage block their dependent conclusions only. The stage-by-stage baseline and dated evidence below remain part of this same plan.

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

## Main integration and release setup — September 23

Integrated origin/main `14f1f572a2fdf05bb8503fa91d1c3efe7ffb61f9` (43 previously absent main commits). Resolved routing/navigation conflicts by retaining gated Home, legacy Dashboard, finance/history routes and main's Bank Monitor, account menu, business switcher and details drawer. Money & Accounting now uses main's shared navigation definitions. This is main merged into the rebuild branch, not a merge/deployment to production.

Combined frontend build and scoped integration lint pass; all14 frontend model tests pass. Combined full backend suite before the new auth test:157 passed, same12 documented baseline failures. Focused accounting/history/retention/Bank Monitor suites including a new configured-session authority regression:93 passed. The new test verifies missing/wrong signed principal rejection, correct authorized access, foreign-business rejection, missing allowlist fail-closed behavior and disabled local preview under configured authentication. Local browser confirms both retained pair scores and Bank Monitor navigation. Preview DB was backed up before merged-server startup; legacy asset/settlement/repair and finance event/posting/line counts remain unchanged and ten immutability triggers remain installed.

Read-only Railway inspection identified production as project Elis Pro Tech App, service web, repository mecaniser/elis-logistics-manager, running main14f1f57. Production database is PostgreSQL. Username/password authentication is configured and an unauthenticated accounting request returns401. `APP_AUTH_TENANT_IDS` is currently absent: confirm authorized business scope and configure it before deploying the new finance routes, otherwise they fail closed. The session signer already supports the existing password fallback; absence of a separate secret is not itself a new release blocker. Local finance/preview flags are absent in production. No production variables, schema, records or deployments were changed.

Still required: production-shaped PostgreSQL migration/restart rehearsal, confirmed backup/restore and rollback procedure, authenticated live/staging scope verification, historical posting dry-run/difference report, and explicit deployment/cutover. New tables are an engineering schema change; historical source reconstruction is a separate controlled backfill. Neither requires the owner to write SQL or manually recreate records already accessible in this application. Owner inputs are unavailable source documents and factual confirmations of opening obligations/funded earmarks, not completion of score or importer engineering.

Integration follow-up: the first Bank Monitor browser attempt exposed a redirect loop when local app authentication is disabled but the Bank Monitor endpoint correctly requires a signed session. Fixed the shared401 handler to check the app session before redirecting; an endpoint-specific denial remains visible, and genuine session expiry retains login recovery. Bank Monitor access controls are unchanged. Four new frontend regression tests pass (18 total frontend model tests). The local Bank Monitor route is not an authenticated production acceptance result. The upstream merge includes an existing whitespace-only finding in an old Impeccable critique; integration source diffs pass whitespace checks.

The auth-handler follow-up's `api.ts` file has19 pre-existing explicit-any lint errors, reproduced against its unchanged merge-commit version; the new handler introduces none. App/Layout/navigation scoped lint remains passing. Browser confirms the endpoint denial is now stable instead of redirecting repeatedly.


## PostgreSQL release rehearsal and access scope — September 24

The owner confirmed accounting access for all three active businesses (IDs 1, 2, 3). Saved `APP_AUTH_TENANT_IDS=1,2,3` on Railway production/web using `--skip-deploys`, then read back that exact value. This is a saved configuration change, not a running deployment or live authenticated acceptance result. No production records or schema were changed.

Added recorded migration `2026_09_24_reconciled_finance`, including guards for pre-existing finance tables. A read-only production dump was restored into an isolated loopback PostgreSQL 18.6 container. Two actual application startups preserved all 2,352 rows in 15 legacy tables (migration registry compared separately). Both pre-migration and post-migration backups restored to separate databases with identical table fingerprints. Signed-session checks permitted all three configured businesses, rejected missing/wrong principals and unauthorized selectors, and kept owner preview disabled. All ten SQL UPDATE/DELETE guard probes failed as intended; balanced decimal probes were rolled back. The focused finance, migration, retention and source-history suite passed: 49 tests.

Rehearsal details and recovery procedure: `release-rehearsal.md`. Private dumps/results are ignored local artifacts and must not be committed. Production deploy/cutover has not occurred. Remaining engineering is unchanged: historical posting dry-run/difference report, intake/repair integration and score completeness/funding rules; then actual business evidence, browser acceptance and release. Passing schema recovery does not finalize accounting or certify take-home cash.


## Historical posting dry-run — September 24

Implemented a tenant-scoped read-only posting plan and reproducible local JSON/CSV export. Against the preserved 175-source history: 18 new review candidates, 155 blocked records, one existing local posting and one existing local posting needing service-date review. Candidate freight $157,725.00 and remainder $45,336.93 reconcile to proposed lines. Original hashes, schema/category compatibility, closed periods, duplicate references, existing events and amendments gate candidates. Automatic posting remains disabled.

Simulated all 18 through the actual engine in an independent disposable SQLite database; balanced lines and repeat-request idempotency passed. The user-facing database and production were not changed. Added eight regression cases; the combined focused suite passed 57 tests. No frontend files changed; no new browser/build claim. Detailed findings, limitations and repair evidence inventory are in `historical-reconciliation.md`.

Next: recover the referenced repair evidence, finish older-layout classification and source identity, resolve historical adjustment differences, and implement remaining retention rules. Missing owner records remain distinct from these engineering tasks. No deployment or finalized owner-cash score yet.


## Repair evidence recovery and local access — September 24

Restored the user's local preview and left Maintenance & Repairs open. Reproduced the local logout trap: AuthContext set the client unauthenticated even though the deliberately unconfigured local server still grants preview access. Logout now rechecks the server. Frontend build and four existing auth-recovery tests pass; scoped lint has zero errors and the existing Fast Refresh export warning. Browser logout with the rebuilt assets returns to the preview rather than the unusable login form. Production authentication settings were not changed.

Recovered all 201 existing Cloudinary attachment references for 41 of 58 repair records, with magic-byte validation and SHA-256 filenames. This includes 29 PDF originals (30 pages); 17 repairs have no referenced attachment. Saved private originals and a dated record-to-source manifest under ignored `backend/settlements_extracted/release-20260924/repairs/`. Added a reproducible read-only recovery script with tenant filtering, four-request concurrency, no redirects and a 20 MB per-file limit. No legacy repair, financial event or production record was modified.

Text-extracted invoice totals match saved costs for 28 PDFs; this is amount matching, not full invoice or payment reconciliation. Visually reviewed a representative matching invoice and the unmatched Tarpstop layout. Repair138 is saved at $238.00; original invoice INV323391 shows Invoice Total $238.86 and Amount Paid $238.86, a $0.86 discrepancy. Preserved the discrepancy for reviewed correction; the document does not establish payer or the corresponding bank transaction. Its extraction layout remains a mapping exception. Poppler rendering stalled; PDFium rendering succeeded for both inspected pages.

Next work is still substantive: classify the 12 image-only repair records and 17 attachment gaps, reconcile payer/payment/settlement-funded costs, incorporate invoices without duplicate expenses, and finish retention funding/completeness rules. Complimentary work, nominal placeholder amounts and notes describing recoveries or settlement deductions must not become new unpaid bills by inference. Recovery artifacts are not yet imported into the application's immutable evidence tables.


## Repair register and cash-payment clarification — September 24

Implemented tenant-scoped `GET /api/v1/accounting/repair-history?as_of=...`: preserved source IDs/hashes, invoice amounts/differences, explicit obligation/payment links, vendor outstanding and owner reimbursement remain separate. Unknown payment status does not become an unpaid bill. Optional `legacy_repair_id` on bill/owner-advance commands verifies the actual tenant/asset and rejects duplicate repair obligations, while preserving idempotency digests for pre-existing commands. Reversed obligations require correction review rather than automatic re-import.

Imported recovered documents into the local review database only after a SQLite backup and source-hash/repair-ownership checks. The 201 attachment references contain 190 unique byte-identical documents; all 190 were preserved once, retaining their repair associations and available invoice extraction/review metadata. A repeat import reused 190 and added zero. Financial event/posting counts did not change. API register covers 58 repairs: 41 with evidence, 17 without, nine cost/recovery-review entries, 28 legacy reserve flags and one source amount discrepancy. No linked payment events exist yet. The local backend was restarted against this same review database; live local API returned these counts. Production was not changed.

Verification: 62 focused finance, repair, settlement-history, reconstruction, migration and retention tests pass. New cases cover absent-payment/reserve inference, personal partial payment substituting a claim, duplicate repair rejection, cross-business access, as-of scope and backward-compatible command replay. No frontend changes or new UI acceptance are claimed for this register.

Owner clarified that repairs are mostly paid in cash, with some checking-account Zelle payments. Bank matching alone is therefore insufficient and absent bank transactions are not unpaid evidence. A follow-up asks whether cash is business cash on hand, personal funds, or mixed; do not infer the answer. Owner-paid cash can use the evidenced owner-payment/substitution flow. Business cash on hand needs an explicit cash-account/payment/reconciliation workflow (remaining engineering); existing business payments currently require a bank/card transaction. No cash balance, reimbursement claim, or reserve funding has been inferred. Zelle payments require the corresponding checking-account source and linked obligation.

## Repair evidence in the existing workflow — September 24

Connected the existing Maintenance & Repairs page to the read-only repair-history API. The same repair cards now show preserved-document coverage, invoice differences, explicit payment activity and expandable vendor/owner balances. Added as-of review and filters for invoice differences, missing documents, unverified payments and cost-treatment exceptions. Unknown balances remain “Not established,” rather than zero or unpaid. Downloads use the tenant-scoped preserved-original endpoint. The old form's reserve copy now explicitly describes legacy tracking rather than claiming confirmed cash funding.

Verified locally with all 58 real review records: 41 with documents, 17 without, one invoice difference ($238.00 saved versus $238.86 source), nine cost-treatment exceptions and zero linked payment activities. Desktop and 390px mobile rendering, keyboard disclosure, discrepancy filtering and empty-search recovery checked in browser. Original-download button requested its tenant-scoped source and received HTTP 200; browser automation did not emit a download event, so filesystem download completion is not verified. New frontend model tests: four passed. Existing repair-history backend tests: five passed. Frontend build and new-component/service lint pass; Repairs.tsx retains the same six pre-existing explicit-any lint errors, verified against HEAD. Impeccable detector returned no findings. Existing bundle-size warning remains.

This is a read-only review integration, not payment intake completion. No financial events, repair amounts, reserve balances or production records changed. Next engineering: business cash-on-hand/payment reconciliation and repair obligation/payment intake; then remaining retention completeness and fuel/travel evidence reconciliation. The owner's cash-source question (business cash, personal funds or mixed) remains unanswered. Do not infer owner advances or bank balances. Fuel spending differences remain investigation signals; independent mileage and supported consumption intervals are still required for measured-MPG conclusions.

## Cashbook and repair payment intake — September 24

Implemented business cash-on-hand accounts through the same immutable account/statement/transaction/payment pipeline. Cashbook CSVs require a separate closing-count evidence document; opening plus signed transactions must reconcile to the count. Negative physical balances and spending before available funding are rejected. Cashbook payments use an explicit cash payer and a reconciled cash transaction; bank/Zelle, card and owner payment identities cannot be interchanged. Both sides of bank/cash transfers must match and cash transfers must use the same date. Transfers preserve company cash without creating income or expenses. Cash balances now participate in cash coverage and availability; incomplete records still remain provisional. Closing-count evidence is included in report/export manifests. Old statement idempotency digests remain compatible.

The existing finance forms now expose cash accounts, counted cashbook reconciliation and cash payments. Bill/owner-cost forms can select a tenant-scoped existing repair and use the existing duplicate-obligation protection. Repair-card disclosures link to this intake. Required payment fields adapt to the selected payer. Recovered repair-document choices show repair dates/descriptions instead of hash filenames. Cash labels now include cash on hand. No historical repair is auto-posted or assumed unpaid.

Verified: 54 focused backend tests pass, including 12 cashbook cases covering missing count evidence, negative funding, partial/repeated payments, bank-to-cash transfers, personal payment/reimbursement, reserve-funded repairs, repeat imports, cross-business evidence/repair selection, old command replay and report evidence manifests. All 22 frontend model tests pass; frontend build and changed-file lint pass. Desktop/mobile payment controls and live local cash-account/cashbook form options verified; no fabricated transaction was submitted through the real review database. Impeccable detector returned no findings. Existing bundle warning and broader repository baseline debt remain.

Backed up review.db before restarting the local backend. Verified counts remain 5 finance events, 2 postings and 268 evidence records. Production unchanged. This completes the basic cashbook-backed payment path, not historical payment reconciliation. Remaining inputs: actual cash ownership/payer, receipts/payment dates, cash counts/opening cash, and Zelle checking records. A direct cash-entry wizard and scoped repair prefill would further improve the current generic accounting forms. Historical repair classification, source corrections, remaining retention rules and fuel/travel reconciliation remain tracked engineering/evidence work.

## 2026-09-24 — Invoice-first repair confirmations

- Implemented inline payment questions in existing repair cards, with unknown/partial/unpaid answers and optional date/reference. No account setup required to save what the owner knows.
- Added batch confirmation for matching extracted invoices; current local history has 28 candidates. Amount/treatment conflicts remain individual exceptions.
- Added immutable owner-confirmation evidence with revision/snapshot checks, tenant scope, idempotency and no financial side effects.
- Preserved original PDFs atomically during existing repair upload; retained legacy mechanics pending migration.
- Finance Repairs now leads to invoice cards; generic accounting tools remain explicitly advanced.
- Fixed repair date-only display shifting back one day.
- Validation and limits: see `repair-confirmation-workflow.md`. No historical payment answers invented, no production deployment. Confirmation-to-ledger automation, OCR/payment extraction, and historical accounting cutover remain unfinished.

## 2026-09-24 — Repair payees and payment methods

- Repair cards now distinguish vendor/payee, document type, and owner-confirmed payment method.
- Added vendor and method filters (cash, Zelle, credit card, other, unknown); vendor names also participate in search. Batch confirmation respects the visible filtered repairs.
- Known issuer extraction examines invoice headers, not payment instructions or repair descriptions. Current preserved text identifies 28 CaroMeck invoices; 30 remain unidentified. Truck Pit Stop is an available payee, not an inferred assignment to undocumented repairs.
- Inline confirmations accept a vendor/person name, including manual/other records. Corrections retain existing revision history; omitted payee preserves old request digests. No ledger or cash side effects.
- New PDF parsing includes known vendor extraction. Image OCR and arbitrary vendor extraction remain outside this checkpoint; image-only and undocumented entries are labeled explicitly, not assumed manual or unpaid.
- Validation: 16 backend repair tests and 23 frontend tests passed, scoped new-component lint/build passed, desktop/mobile filters and credit-card option verified without saving invented facts. Production unchanged.

## 2026-09-24 — Dropdown styling as part of ongoing implementation

- Added shared native-select styling in `frontend/src/index.css`: consistent 44px minimum control height, typography, chevron, focus/hover/disabled/error states, and reduced-motion support.
- Progressive customizable-select styles also cover open menus, selected options, checkmarks, long labels and bounded scrolling. Unsupported browsers retain their native picker; no JavaScript replacement changes selection, required validation or form submission semantics.
- Desktop open-menu and keyboard ArrowDown/Enter selection verified in the in-app browser; mobile 390px picker placement and wrapped option labels verified. Restored All methods afterward. Build and whitespace checks passed; existing bundle-size warning remains.
- Ongoing UI work should include control styling, open/closed states, keyboard access and desktop/mobile inspection in the same checkpoint instead of deferring those details to a final redesign.
- This change touches only shared dropdown styles and this tracker. Concurrent account/login work was left untouched. Production unchanged.

## 2026-09-24 — Payment identities and personal funding

- User confirmed repair entries normally represent paid invoices. New single-repair forms default to paid in full and the recorded invoice/repair date, both editable. Existing confirmations (including unknown dates) remain intact; no historical payments are silently posted.
- Added a business-scoped Payment accounts directory on Bank Monitor, plus inline account creation and selection on repair confirmations. Supports personal/business credit cards, bank accounts and cash identities with nickname and optional last four digits. Account choice supplies ownership; Zelle selects a bank account.
- Directory entries use immutable evidence storage; repeated identical creation returns the existing identity. Repair evidence keeps the selected account snapshot and ID. Server rejects foreign-business accounts and incompatible ownership/methods. No schema migration or real-account backfill is required for this checkpoint.
- This directory is not yet linked to Bank Monitor balance sources, automated monitoring settings, or finance ledger accounts. Existing monitoring configuration is unchanged. Owner confirmations still do not automatically create reimbursement postings. Personal card repayment must never create a second repair expense or duplicate owner claim.
- Validation: 20 backend account/repair tests passed, scoped frontend lint passed, frontend build passed with existing bundle-size warning. Browser verified the directory/editor, mobile layout, default paid/date and credit-card selector without saving invented accounts or repair answers. Existing local Bank Monitor monitoring panel requests sign-in; directory is available under local accounting preview. No production deployment.


## 2026-09-24 — Account workflow, balance links and owner reimbursement postings

| Before | After | Why |
| --- | --- | --- |
| Add/cancel presented as underlined text | Primary Add account button; type choices; grouped fields; explicit Save and Cancel actions | Make creation visible and familiar without expanding an unstructured form |
| Payment nickname disconnected from any balance | Explicit links to a business ledger account or authorized Bank Monitor source | Preserve account identity and show the observation/statement date |
| Personal-payment confirmation stopped at evidence | Eligible still-unreimbursed personal payments create one bill and one owner-funded payment atomically | Record the cost once and move the liability from vendor to owner |
| Reimbursement requires generic accounting commands | Owner reimbursements shows amounts owed and matches existing reconciled bank/cash transactions | Clear the obligation without another expense or a money transfer |

Engineering completed locally:
- Immutable account links preserve source identity and revisions. Type/ownership/tenant checks block personal-to-business-ledger links and duplicate source links. Changed sources require review. Bank Monitor access is independently checked before exposing monitored observations.
- Monitored balances retain their timestamp and stay distinct from reconciled statements; connecting an identity creates no cash or liability posting. Personal balances never enter business cash.
- New personal confirmations include whether the full payment remains owed. Dates, costs, stale records, prior obligations and closed periods are checked. Partial personal payment leaves the unpaid vendor portion and creates only the paid owner portion. Existing confirmed personal payments can be selected together to confirm they remain unreimbursed.
- Posting links are immutable; repeats and note-only changes do not repost. Financial corrections enter accounting review instead of silently changing posted history. A failed payment posting rolls back its bill too while preserving the confirmation for review.
- Matching an actual reimbursement derives its date and business payer from the reconciled transaction, supports partial repayment, and preserves idempotency. It does not submit a bank transfer.
- Existing review data contained three personal confirmations lacking reimbursement status during inspection. They are listed for owner confirmation; none was silently backfilled by the agent. Real balances/account ownership and prior repayments are not invented.

Still open: unmatched business cash/Zelle/card history; mixed-funding split intake; actual reserves; manual-existing-claim corrections; actual monitoring authentication and provider records; full cutover. The legacy upload journal remains separate until reconciled migration, so the two ledgers must never be summed.

Verification for this checkpoint: 72 targeted backend tests passed across finance, cashbook, payment identities, balance links, owner postings and repair confirmations/history; 23 frontend tests passed; scoped frontend lint/build and whitespace checks passed. The build retains its existing bundle-size warning. Desktop/mobile account form, keyboard type selection/Cancel, actual saved-card ownership selection, review checklist and unavailable-monitor state were inspected in the in-app browser without saving invented facts. The local Bank Monitor still requires its authenticated monitoring session; no live balance source or production reimbursement was claimed verified.
