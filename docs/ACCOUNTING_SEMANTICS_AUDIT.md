# Elis Logistics Manager Financial Semantics Audit

**Prepared:** August 11, 2026<br>
**Role:** Accounting Specialist advisory workstream<br>
**Audience:** Product & Delivery Lead, engineering, bookkeeping/accounting reviewer<br>
**Status:** Policy and validation deliverable; no production mutation, deployment, or certified statement

This document provides accounting-policy and product-semantics guidance. It is not a CPA opinion, tax return, audit, review, compilation, or certified financial statement. Final tax elections, entity treatment, opening balances, and lender submissions require review by the company's qualified tax/accounting professional and, where applicable, its lender.

## Executive conclusion

**NO-GO for calling the current balance sheet, retained earnings, Schedule C, loan balances, depreciation, or lender package accounting-ready.** The journal-entry engine balances individual postings, but the reports mix at least three incompatible sources:

1. journal-ledger balances;
2. operational settlement, repair, and vehicle records injected directly into statements; and
3. calculated tax/debt estimates that are not tied to source documents or posted entries.

The result can be arithmetically populated but not ledger-reconcilable. The rebuild should establish one authoritative double-entry book ledger, preserve operational subledgers, and produce book, tax, and lender views through explicit adjustments rather than hidden substitutions.

The principal unresolved business fact is whether Elis Logistics is the principal earning gross transportation revenue or an owner/lessor/participant entitled only to a net settlement share. That contract-level conclusion controls gross-versus-net revenue. Product code must not decide it from the tenant name.

## Evidence reviewed in the repository

- Settlement fields and parser semantics, including gross revenue, categorized deductions, operating profit, prior-balance cash adjustments, reported cash settlement, trailer allocations, and repair reserves.
- Automatic settlement and repair journal postings.
- Minimal and per-asset charts of accounts and account-code mappings.
- Balance sheet, income statement, tax-year summary, Schedule C, general ledger, and export endpoints.
- Vehicle purchase, loan, investment, depreciation, and loan-balance fields.
- Loan-interest and replayed “principal payment” calculations.
- Repair-reserve operational ledger and repair lifecycle.
- Accounting-related migrations, documentation, and representative parser/accounting tests.

No production database, bank feed, general-ledger export, loan statement, tax return, ownership document, carrier agreement, title, or lender request list was accessed. Therefore this is a semantic/code audit, not a validation of live balances.

### Repository evidence map

| Semantic area | Current implementation evidence |
|---|---|
| Elis net-only settlement journal | `backend/app/services/accounting_service.py`, `create_settlement_journal_entry()` around lines 348–571 |
| Hybrid balance sheet and operational retained-earnings override | `backend/app/services/accounting_service.py`, `generate_balance_sheet()` around lines 785–1014 |
| Gross/current expense/operating profit/prior balance/cash separation | `backend/app/utils/pdf_parser.py` around lines 289–454 |
| Trailer allocation and reserve reductions to source gross/net | `backend/app/routers/settlements.py` around lines 181–315 |
| Profit-derived principal and forecast balance | `backend/app/services/loan_balance_service.py` around lines 26–173 |
| Tax-style depreciation calculations and conflicting posting codes | `backend/app/services/depreciation_service.py` around lines 16–292 |
| Tax-year summary and Schedule C mapping | `backend/app/routers/accounting.py` around lines 765–870 |
| Every new repair marked reserve-funded and posted as cash repair expense | `backend/app/routers/repairs.py` around lines 169–192 and `backend/app/services/accounting_service.py` around lines 574–685 |
| Minimal Elis chart | `backend/app/services/accounting_service.py`, `initialize_minimal_logistics_accounts()` around lines 155–202 |
| Destructive chart reset | `backend/app/routers/accounting.py` around lines 76–110 |

## Current-state findings

### Critical: the reporting basis is internally inconsistent

- Elis settlement posting debits Cash and credits Settlement Income for `net_profit` only. It ignores `cash_settlement_amount`, `cash_adjustments`, gross revenue, deductions, reimbursements, reserves, and receivable timing.
- The balance sheet then discards ledger retained earnings for logistics tenants and recomputes it as all-time `gross_revenue - expenses - repairs` from operational tables. That is not retained earnings because it ignores opening equity, owner contributions/distributions, taxes, depreciation, manual adjustments, and formal year-end closes.
- Vehicle cost is injected from `Truck.total_cost`, loan balance from `Truck.current_loan_balance` or `loan_amount`, and sometimes depreciation from the calculator rather than journal entries. Those assets and liabilities therefore need not have balancing equity/cash/loan postings.
- Cash is ledger-derived while vehicle cost, debt, and retained earnings can be operationally derived. `Assets = Liabilities + Equity` is not enforced in the generated balance sheet.
- The tax-year summary combines a ledger-derived income statement with this hybrid balance sheet, so its account balances and earnings need not share the same accounting basis.

### Critical: settlement revenue and cash are conflated

- The parser correctly distinguishes operating profit from prior-balance cash offsets, but automatic Elis posting uses operating `net_profit` as both revenue and cash.
- In the representative source case, gross revenue is $880, current deductions are $460, operating profit is $420, a prior-balance offset is negative $99, and cash paid is $321. The current Elis journal would post Dr Cash $420 / Cr Revenue $420, overstating cash by $99 and failing to clear the prior balance.
- Negative or zero Elis `net_profit` settlements produce no journal entry, even when they contain cash movement, a receivable/payable change, current-period expenses, or a prior-balance settlement.
- Reimbursements are credited to revenue in the per-asset path. Accounting treatment should normally reduce the specifically reimbursed expense when identifiable; only otherwise should a separately defined recovery/other-income policy apply.

### Critical: gross-versus-net revenue policy is encoded by tenant name

- `uses_per_asset_accounting()` makes “LS Logistics” gross and expense-based while every other logistics tenant, including Elis, receives net-only accounting.
- Whether an entity reports gross revenue or a net fee/share depends on the underlying rights, obligations, control, and contract economics—not its display name or whether accounts are per vehicle.
- Trailer split rows reallocate operational revenue between truck and trailer records. Within one legal entity this is segment allocation, not new external revenue. If the trailer belongs to a different legal entity or owner, the posting may instead be rental expense/payable and rental income/receivable, supported by a contract and intercompany reconciliation.

### Critical: reserves reduce revenue without establishing restricted cash

- A repair reserve currently reduces source settlement gross revenue and net profit and is also tracked in a separate operational reserve ledger.
- An internally designated reserve is not an expense and ordinarily does not reduce external revenue. If cash remains in the same unrestricted bank account, it is a management designation/subledger. If a carrier withholds cash that Elis still owns, it is a reserve receivable or restricted-cash asset. If it is a nonrefundable contractual charge, it may be an expense. Source documents must decide which.
- Repairs are always posted Dr Maintenance & Repairs / Cr Cash even when marked paid from reserve. That can double-reduce reported economics or misstate which asset funded the repair.

### Critical: loan balances are forecasts, not debt accounting

- Weekly interest is estimated as current balance times annual rate divided by 52 and added to settlement expense. It is not reconciled to lender statements, payment dates, daily accrual, fees, or amortization tables.
- “Principal paid” is inferred from cumulative operating profit after recovery of `cash_investment`. Profit availability does not prove that a lender payment occurred. This model is useful as a payoff-allocation scenario, but it cannot be the book debt schedule.
- The inferred balance is injected into the balance sheet. There are no complete acquisition, debt-funding, principal-payment, interest-payment, fee, refinance, or payoff journal events tying debt to cash.
- For trailers, original loan fallback behavior is inconsistent with trucks, creating a risk that a positive trailer loan disappears when the stored current balance is zero/null.

### High: asset and depreciation semantics mix book and tax rules

- `total_cost` is constructed from cash investment, loan amount, registration, and additional expenses, but the product does not establish legal ownership, acquisition date, placed-in-service date, business-use percentage, capitalizable costs, trade-in basis, or disposition history.
- The default `MACRS_5` selection is a tax assumption, not a book-depreciation policy. The calculator also includes Section 179 and bonus depreciation in accumulated depreciation without separate, approved tax-adjustment entries.
- The depreciation service uses account codes that conflict with the shared Elis chart (`6013` versus `5400`; accumulated depreciation `1501` versus `1600`) and can create per-truck accounts even when Elis uses shared accounts.
- Book depreciation should reflect a consistently approved useful life and residual value. Tax depreciation, Section 179, bonus depreciation, listed-property limits, business-use tests, conventions, and recapture belong in a tax fixed-asset schedule and tax-basis adjustment layer.
- IRS guidance says depreciable cost recovery begins when qualifying property is placed in service, and Section 179 is an election subject to eligibility and limits. It must not be inferred merely because a UI field has a value.

### High: repair versus capitalization requires facts, not one account

- Every repair record posts to Maintenance & Repairs. There is no improvement/capitalization review, component asset, insurance recovery, warranty recovery, or disposal-of-replaced-component workflow.
- IRS tangible-property guidance requires facts-and-circumstances analysis. Betterments, restorations, and adaptations generally must be capitalized; routine repairs generally may be deducted. A fleet rebuild to like-new condition is an IRS example of a capital improvement.
- The product needs an accounting-review status, invoice support, vehicle/unit-of-property link, work description, and `expense | capital improvement | pending review` disposition.

### High: equity and closing are incomplete

- Owner Equity and Retained Earnings accounts exist, but there are no controlled owner contribution, distribution/draw, opening balance, or year-end close workflows.
- Current-period income should remain current-year earnings on financial statements until closing. Retained earnings is accumulated prior-period earnings after closing entries and distributions, not an all-time operational profit formula.
- Entity form matters. A sole proprietor/single-member disregarded LLC commonly uses owner capital/draw terminology; corporations commonly use contributed capital, retained earnings, and distributions/dividends; partnerships require partner-specific capital accounts. The chart should be parameterized after entity classification is confirmed.

### High: Schedule C is unsafe without entity and line mapping

- The endpoint is available by tenant business type and does not verify federal tax classification. IRS Schedule C is for sole proprietors and generally single-member domestic LLCs that have not elected corporate treatment. A multi-member LLC generally files as a partnership unless it elects corporate treatment; an S corporation does not file Schedule C for entity operations.
- The endpoint labels total expenses as “line 27,” although Schedule C has specific expense lines and other-expense detail; it maps by internal account display names, but the mapping keys are operational category slugs. Most accounts therefore fall through to “other expenses.”
- It omits cost-of-goods/services considerations, returns/allowances, vehicle-specific substantiation, depreciation/Form 4562, business-use allocation, meals limits, payroll/tax distinctions, and tax-basis adjustments.
- Rename this output “tax organizer draft” until entity eligibility, mappings, and accountant review are complete. It must never imply filed-return readiness.

### High: auditability and control gaps

- Account reset can delete the tenant's journal lines and entries. That is incompatible with a closed-period audit trail and lender support package.
- Manual general-ledger account endpoints retrieve records by ID without tenant scoping in several places. This is also a data-boundary issue for financial records.
- Journal updates/deletes, source edits, opening entries, and period status lack an immutable change log, preparer/approver fields, attachments, reversal links, and locked-period enforcement.
- Account creation accepts free-form account types and mappings contain conflicting/reused codes. The chart requires stable semantic account identifiers distinct from editable codes and names.

## Recommended accounting architecture and policy

### One book ledger, explicit reporting bases

1. Make posted journal lines the sole authority for the trial balance, balance sheet, income statement, retained earnings, and cash flow.
2. Keep settlements, repairs, vehicles, reserve activity, and lender statements as source/subledger records that reconcile to posted entries.
3. Adopt an **accrual management-book default** for the rebuild: recognize externally earned revenue and related settlement receivable at the approved service/settlement earning date; clear the receivable when cash is received or deductions are applied.
4. Add a **cash-tax reporting view only after accountant approval**. IRS Publication 538 distinguishes cash timing (generally received/paid) from accrual timing (generally earned/incurred) and requires consistent use. Do not silently mix them.
5. Store `book_basis`, `tax_basis`, and `lender_adjustment` as explicit report layers or adjustment books. A tax election does not rewrite historical book source facts.

### Revenue policy decision gate

Before implementing final settlement postings, obtain the carrier/management/lease agreements and answer:

- Who contracts with the shipper/broker and is primarily responsible for transportation?
- Who bears fuel, driver, insurance, claims, service-failure, and collection risk?
- Are settlement deductions Elis expenses paid on its behalf, or amounts belonging to another operator?
- Is Elis entitled to gross freight revenue, a fixed rental charge, a management fee, or residual profit?
- Does title/loan ownership align with the revenue entity?

Until this is resolved, support two posting templates and mark the tenant's approved template with effective dates. Do not infer it from tenant name.

### Proposed chart of accounts

Codes are illustrative. Stable internal semantic IDs should survive renumbering.

| Code | Account | Type | Purpose |
|---|---|---|---|
| 1000 | Operating Cash | Asset | Reconciled bank cash |
| 1010 | Restricted Cash—Repair Reserve | Asset | Only for separately controlled cash |
| 1100 | Settlement Receivable | Asset | Earned but not yet paid carrier settlements |
| 1120 | Reserve Receivable | Asset | Carrier-held funds still owned by Elis |
| 1200 | Prepaids and Deposits | Asset | Insurance, permits, deposits by period |
| 1500 | Revenue Equipment—Trucks | Asset | Historical book cost |
| 1510 | Revenue Equipment—Trailers | Asset | Historical book cost |
| 1520 | Vehicles—Other | Asset | SUVs/other owned equipment |
| 1590 | Accumulated Depreciation—Equipment | Contra asset | Book accumulated depreciation |
| 2000 | Accounts Payable | Liability | Vendor obligations |
| 2050 | Settlement/Cash Clearing | Liability or asset by balance | Unresolved carrier timing/offsets |
| 2100 | Vehicle Loans Payable—Current | Liability | Next 12 months of principal for lender view |
| 2110 | Vehicle Loans Payable—Long-Term | Liability | Remaining principal |
| 2150 | Accrued Interest | Liability | Incurred but unpaid sourced interest |
| 2200 | Taxes and Fees Payable | Liability | Specific supported obligations |
| 2300 | Due to Related Party | Liability | Documented owner/affiliate loans, not equity |
| 3000 | Owner/Member Contributed Capital | Equity | Contributions; label by entity form |
| 3010 | Owner/Member Distributions | Contra equity | Draws/distributions; label by entity form |
| 3100 | Retained Earnings / Cumulative Capital | Equity | Prior closed earnings; label by entity form |
| 4000 | Freight/Settlement Revenue—Gross | Revenue | Use only under approved principal/gross policy |
| 4050 | Settlement Participation/Management Revenue | Revenue | Use under approved net policy |
| 4100 | Trailer Rental Revenue—External | Revenue | External rental only, not internal allocation |
| 4200 | Reimbursements/Recoveries | Revenue or contra expense | Used only when original expense cannot be identified |
| 5000-series | Direct Operating Costs | Expense | Fuel, tolls, driver/contract labor, dispatch, carrier fees |
| 5100 | Repairs and Maintenance | Expense | Deductible/book-expensed repairs after review |
| 5200 | Insurance | Expense | Period expense, with prepaids as needed |
| 5300 | Interest Expense | Expense | Sourced accrual/payment interest only |
| 5400 | Book Depreciation Expense | Expense | Book depreciation, separate from tax adjustment |
| 5500 | Licenses, Registrations, and Road Taxes | Expense | Classification subject to period/basis review |
| 5600 | Professional and Administrative | Expense | Bookkeeping, legal, software, bank fees, etc. |
| 5900 | Gain/Loss on Asset Disposal | Other income/expense | Supported asset disposition result |
| 9990 | Opening Balance Suspense | Temporary clearing | Must be zero before final opening approval |

Do not create “Section 179 Deduction” as an ordinary book expense account. Track it in the tax fixed-asset schedule and post only to a clearly identified tax-adjustment ledger if the reporting design supports one.

## Proposed posting examples

### 1. Representative settlement—gross/principal model

Source facts: gross earned $880; current-period deductions $460; prior-balance deduction $99; cash paid $321. Assume the $460 is valid Elis expense and the $99 clears a prior carrier receivable/advance balance.

**At earning/settlement approval date**

| Account | Debit | Credit |
|---|---:|---:|
| Settlement Receivable | 880 | — |
| Freight/Settlement Revenue—Gross | — | 880 |
| Current operating expense accounts | 460 | — |
| Settlement Receivable | — | 460 |

**At payment/offset date**

| Account | Debit | Credit |
|---|---:|---:|
| Operating Cash | 321 | — |
| Prior Balance Liability or Settlement/Cash Clearing | 99 | — |
| Settlement Receivable | — | 420 |

If the $99 represents recovery of an amount owed *to* Elis rather than settlement of an Elis obligation, reverse the balance-side classification. The source statement and opening balance must identify the counterparty and sign. Never force it into current revenue or expense merely to match cash.

### 2. Representative settlement—net agent/participation model

If contracts establish that Elis earns only the $420 residual and the carrier/operator owns gross revenue and deductions:

| Account | Debit | Credit |
|---|---:|---:|
| Settlement Receivable | 420 | — |
| Settlement Participation/Management Revenue | — | 420 |

Then clear the $420 receivable with $321 cash plus the properly identified $99 prior-balance item as above. Do not also post the carrier's $880 revenue or $460 costs to Elis.

### 3. Reimbursement

If a $100 reimbursement relates to a previously posted $100 repair:

| Account | Debit | Credit |
|---|---:|---:|
| Settlement Receivable or Cash | 100 | — |
| Repairs and Maintenance | — | 100 |

If it cannot be matched after documented review, credit Reimbursements/Recoveries under the approved policy; do not automatically call every reimbursement revenue.

### 4. Repair reserve

**Internal designation with no separate bank account:** no general-ledger entry; record a management subledger designation only.

**Transfer to a separately controlled reserve bank account:**

| Account | Debit | Credit |
|---|---:|---:|
| Restricted Cash—Repair Reserve | 500 | — |
| Operating Cash | — | 500 |

**Carrier withholds $500 still owned by Elis:** Dr Reserve Receivable $500 / Cr Settlement Receivable $500 when clearing the settlement. It does not reduce external revenue.

### 5. Vehicle purchase financed at acquisition

Assume truck purchase price and capitalizable acquisition costs total $80,000, funded by $20,000 owner cash already in the business and a $60,000 lender advance.

| Account | Debit | Credit |
|---|---:|---:|
| Revenue Equipment—Trucks | 80,000 | — |
| Operating Cash | — | 20,000 |
| Vehicle Loans Payable—Long-Term | — | 60,000 |

If the owner pays $20,000 personally rather than from company cash, credit Owner/Member Contributed Capital or Due to Related Party based on legal documentation and repayment intent.

Registration, title, transport, installation, and pre-service repairs require an approved capitalization policy and source review; `cash + loan` alone is not necessarily total depreciable basis.

### 6. Debt payment

For a documented $1,500 payment allocated by the lender to $1,100 principal and $400 interest:

| Account | Debit | Credit |
|---|---:|---:|
| Vehicle Loans Payable | 1,100 | — |
| Interest Expense | 400 | — |
| Operating Cash | — | 1,500 |

Principal reduces debt and is not an expense. Use the lender statement allocation, not operating profit, to establish principal paid. Accrue interest separately only when the reporting basis requires it and the calculation is supportable.

### 7. Owner contribution and distribution

**Contribution:** Dr Cash / Cr Owner or Member Contributed Capital.<br>
**Distribution/draw:** Dr Owner or Member Distributions / Cr Cash.

Neither is revenue or operating expense. Related-party loans require a note, repayment terms, and separate liability account.

### 8. Routine repair versus capital improvement

**Routine oil service, facts support expense:** Dr Repairs and Maintenance / Cr Cash or AP.<br>
**Engine rebuild that restores a major component or vehicle to like-new condition:** Dr Capital Improvement—specific vehicle / Cr Cash or AP, then depreciate under the approved book policy.

An invoice amount threshold may route review but cannot replace the facts-and-circumstances conclusion.

### 9. Book depreciation and tax adjustment

Monthly book entry: Dr Book Depreciation Expense / Cr Accumulated Depreciation—Equipment based on approved cost, placed-in-service date, useful life, residual value, and method.

Section 179, bonus depreciation, MACRS conventions, business-use limitations, and recapture remain in the tax fixed-asset schedule. The tax return reconciliation records the difference between book and tax depreciation; it does not overwrite book accumulated depreciation.

## Source-evidence checklist

No balance should receive “verified” status until its evidence and reconciliation fields are complete.

### Entity, ownership, and reporting basis

- [ ] Articles/organization documents and current ownership/member/shareholder schedule.
- [ ] EIN confirmation and federal/state tax classification elections (including Forms 8832/2553 if applicable).
- [ ] Prior two or three filed federal and state returns with depreciation schedules and carryforwards.
- [ ] Confirmed tax year and current tax accounting method; any Form 3115 history.
- [ ] Carrier, dispatch, management, equipment lease, trailer allocation, and owner/affiliate agreements.
- [ ] Written conclusion, approved by accountant, for principal-versus-agent/gross-versus-net settlement reporting.

### Cash and settlements

- [ ] Every bank account, statement from cutover through current period, and month-end reconciliation.
- [ ] Carrier settlement PDFs/source exports tied one-to-one to imported settlement IDs.
- [ ] Proof of deposit/ACH tied to `cash_settlement_amount`, including batch deposits.
- [ ] Schedule of open settlement receivables and carrier-held reserves at cutover.
- [ ] Prior-balance detail showing origin date, counterparty, original posting, remaining balance, and whether it is an asset or liability.
- [ ] Reimbursements tied to original expense/invoice or documented recovery classification.
- [ ] Repair reserve agreement and bank/custody evidence establishing internal designation, restricted cash, receivable, or expense treatment.
- [ ] Trailer split support identifying same-entity segment allocation versus external/intercompany rental.

### Vehicles and fixed assets

- [ ] Bill of sale/purchase agreement, title, VIN, legal owner, purchase date, and placed-in-service date for every vehicle/trailer/SUV.
- [ ] Funding proof: down payment, trade-in, lender advance, owner payment, taxes, registration, delivery, and other acquisition costs.
- [ ] Prior depreciation schedules, accumulated book depreciation, accumulated tax depreciation, Section 179/bonus elections, business-use percentage, and recapture history.
- [ ] Improvement invoices and disposition/trade-in/sale documents.
- [ ] Approved book useful life, residual value, and depreciation method by asset class.

### Debt

- [ ] Executed note, security agreement, amortization schedule, interest rate type, maturity, payment frequency, fees, and guarantors.
- [ ] Lender statements from origination through cutover/current date.
- [ ] Payment history split into principal, interest, fees, late charges, and escrow.
- [ ] Payoff/refinance/modification documents and current lender payoff/balance confirmation.
- [ ] Related-party notes and evidence distinguishing debt from capital.

### Expenses, liabilities, equity, and tax

- [ ] Vendor invoices and AP aging at cutover/current month-end.
- [ ] Repair invoices with work description, vehicle, mileage, warranty/insurance recovery, and capitalization review.
- [ ] Insurance policies and prepaid schedules.
- [ ] Payroll/contractor reports, Forms 941/W-2/1099, and driver classification support as applicable.
- [ ] Tax, registration, IFTA, Form 2290, toll, and permit statements.
- [ ] Owner contribution/distribution history and business-versus-personal bank activity.
- [ ] Opening trial balance or prior compiled/prepared financial statements, with accountant adjustments.

### Lender package

- [ ] Exact lender/program request list, required basis (cash, accrual, tax), periods, comparative columns, and freshness requirement.
- [ ] Current and prior-year P&L, balance sheet, and tax returns tied through a reconciliation bridge.
- [ ] Debt schedule by creditor tied to the balance sheet, including current/long-term split, payment, rate, maturity, collateral, and guarantor.
- [ ] Cash flow statement and debt-service calculation with documented add-backs.
- [ ] Accounts receivable/payable aging and concentration schedules if requested.
- [ ] Personal financial statement only for required guarantors/owners; do not mix personal assets into company books.
- [ ] Certification/attestation language approved by the preparer and lender; the application must not label system-generated statements “CPA prepared,” “reviewed,” or “audited.”

## Opening-balance approach

1. **Choose a cutover date:** Prefer the first day of a fiscal year or the day after a reconciled month-end. Freeze the source snapshot; do not import cumulative historical P&L and also open retained earnings for the same periods.
2. **Define legal entity and basis:** One opening ledger per legal/tax entity. Confirm book basis and reporting currency. Do not combine Elis and LS or owner personal balances merely because the application can display them together.
3. **Build source schedules:** Cash reconciliation, settlement AR/reserves, prepaids, fixed assets and accumulated book depreciation, AP/accruals, lender-confirmed debt, taxes payable, related-party balances, and equity rollforward.
4. **Post one controlled opening entry:** Debit and credit each balance-sheet account at the cutover date. Use account-level and asset/loan subledger references.
5. **Classify equity deliberately:** Prior-period accumulated earnings go to Retained Earnings/Cumulative Capital only after accountant approval. Contributions, distributions, and related-party loans remain separate. Entity form controls labels and partner/member detail.
6. **Use suspense temporarily, visibly:** Any unresolved difference goes to Opening Balance Suspense with owner, evidence request, and due date. The balance sheet remains draft and lender/tax exports remain blocked until suspense is zero.
7. **Choose history strategy:**
   - *Prospective cutover:* opening balance sheet plus current-period detailed activity; preserve legacy reports as read-only evidence.
   - *Full historical rebuild:* post every supported historical transaction, then prove the rebuilt closing trial balance equals the approved opening target. This is higher effort but supports comparative lender statements.
8. **Validate:** Opening trial balance nets to zero; cash equals bank reconciliation; debt equals lender confirmations; asset subledger equals control accounts; equity rollforward explains the plug; and `Assets = Liabilities + Equity` exactly.
9. **Approve and lock:** Require preparer and accountant/reviewer sign-off, then lock the opening period. Corrections occur through dated adjusting entries, never destructive reset/re-import.

## Period-close controls

### Every settlement cycle

- Source document hash/file, carrier, vehicle, service period, settlement date, and payment date recorded.
- Gross, each deduction, reimbursements, reserves, prior-balance offsets, receivable movement, and cash payout foot and cross-foot to the source.
- Duplicate source and duplicate economic-event controls pass.
- Approved gross/net template and effective date applied.
- Settlement subledger movement reconciles to Settlement Receivable/Clearing.

### Monthly close

1. Lock settlement ingestion through month-end and resolve parser exceptions.
2. Reconcile every bank and restricted-cash account to statement ending balances.
3. Reconcile settlement receivable, carrier reserves, repair reserve, AP, taxes, and related-party schedules to control accounts.
4. Reconcile each loan to lender statement; post principal, interest, fees, accruals, and current/long-term reclassification.
5. Review every repair/improvement exception and post capitalization or expense conclusion.
6. Reconcile fixed-asset additions/disposals and post book depreciation.
7. Review owner contributions/distributions and eliminate personal activity from expenses.
8. Review cut-off around month-end for settlement earning dates, cash dates, invoices, and repairs.
9. Run trial balance, balance-sheet equation, retained-earnings rollforward, and subledger-to-GL checks.
10. Produce P&L, balance sheet, cash flow, debt schedule, and variance review; explain material changes.
11. Require preparer/reviewer approval, evidence links, and close checklist completion.
12. Lock the period. Subsequent changes require a reversing/adjusting entry in an open period with reason and approval.

### Year-end/tax close

- Reconcile beginning equity to prior-year filed return/approved statements and current-year book income.
- Close revenue and expenses into the appropriate equity account only after all adjustments.
- Complete book-to-tax reconciliation, tax fixed-asset schedule, Section 179/bonus decisions, business-use support, and state adjustments.
- Reconcile tax return amounts to final book trial balance with permanent/temporary difference schedules.
- Preserve the filed return, accountant AJEs, final trial balance, and locked lender package as immutable versions.

## Cash flow and debt schedule requirements

### Cash flow statement

Generate the cash flow statement from posted ledger activity, not net profit plus hand-entered balances. At minimum:

- operating: cash receipts from settlements/rentals, cash operating expenses, interest, and taxes;
- investing: vehicle/equipment purchases, capital improvements, and sale proceeds;
- financing: loan proceeds, principal repayments, owner contributions, and distributions;
- beginning cash plus net change equals ending reconciled cash.

For an indirect statement, start from book net income and reconcile depreciation, gains/losses, and working-capital changes. Principal payments are financing cash flows, not operating expenses.

### Debt schedule

Maintain one row per legal note with lender, masked account, origination date, original principal, current principal, accrued interest, rate/type, scheduled payment, maturity, collateral/VIN, guarantor, current/long-term split, covenant status, and source-statement date. The total principal must equal Loans Payable on the balance sheet. A payoff forecast may be shown separately and must be labeled forecast, never current principal.

### Lender-package reconciliation

- Final trial balance is the source for P&L, balance sheet, and cash flow.
- Debt schedule total equals balance-sheet debt; Form 2202-style schedule, when requested, must also balance to liabilities.
- Fixed-asset schedule net book value equals the balance sheet.
- Retained earnings/cumulative capital equals prior ending balance plus current closed income minus distributions plus approved prior-period adjustments.
- Tax-return bridge explains book-versus-tax depreciation, meals/other limitations, timing, and other adjustments.
- Personal financial statements remain separate guarantor documents. SBA Form 413 assesses applicant/guarantor financial position; it is not the company balance sheet.
- Obtain the lender's exact checklist. SBA SOP 50 10 governs 7(a)/504 origination policy, but the applicable program, lender underwriting, loan size, and circumstances determine the actual package. SBA disaster Form 2202 is not a universal 7(a)/504 requirement.

## Accountant-review questions

### Entity and basis

1. What is each tenant's legal entity, ownership, federal tax classification, tax year, and tax accounting method?
2. Is Elis a disregarded single-member LLC, partnership, S corporation, or C corporation? Is a Schedule C organizer appropriate at all?
3. Should management books be accrual while tax reporting remains cash, and what bridge/adjustment process is required?
4. Are Elis and LS separate legal entities requiring due-to/due-from and intercompany eliminations rather than shared/per-asset accounts?

### Revenue and settlements

5. Under the carrier, dispatch, lease, and management contracts, is Elis principal or agent for each revenue stream?
6. Which deductions are Elis expenses, reductions of receivable, owner/operator pass-throughs, financing items, or prior-period items?
7. What event and date establish revenue earned: service completion/week end, carrier settlement approval, invoice, or cash receipt for tax only?
8. How should reimbursements and negative-balance recoveries be classified and matched to original transactions?
9. Does Elis own repair-reserve funds? Where are they held, are they refundable, and are withdrawals controlled?
10. Are trailer allocations internal segment reporting, external leases, or intercompany transactions?

### Assets, repairs, and depreciation

11. Who legally owns each vehicle, and which entity reports its revenue, debt, depreciation, and disposition?
12. What acquisition costs belong in basis, and are any registration or additional costs period expenses/prepaids instead?
13. What are approved book useful lives/residual values and tax classes/conventions by asset type?
14. Which Section 179/bonus elections were actually made, and what prior depreciation/recapture schedules govern opening tax basis?
15. What capitalization threshold, routine-maintenance policy, and review evidence should apply without overriding the betterment/restoration/adaptation rules?

### Debt and equity

16. What are lender-confirmed principal, accrued interest, fees, and current/long-term classifications at cutover?
17. Are owner-funded vehicle purchases contributions, reimbursable advances, or bona fide related-party loans?
18. What equity account structure is correct for the confirmed entity form, including partner/member-specific capital if required?
19. Are there historical distributions, personal expenses, or prior-period corrections that must be separated from operating expense?

### Opening, tax, and lender package

20. What approved trial balance or filed-return schedules should anchor the cutover?
21. Which historical periods must be rebuilt for lender comparatives, and which can remain archived with a prospective opening entry?
22. What materiality and approval threshold applies to prior-period adjustments?
23. Which exact lender/program package is being targeted, on what basis, with which comparative periods, covenant calculations, and preparer language?
24. Which reports may be labeled management-prepared, tax-basis, accrual-basis, or accountant-prepared? No stronger assurance label should be generated by the app.

## Direct mapping to the 12 Phase 0 product questions

The numbering and question text below match `docs/frontend-financial-reporting-ux-audit.md` in the Product & Delivery worktree. “Existing records” means records can populate a draft or prove a fact; it does not mean the current application-derived value is authoritative. A blank or unresolved item remains `unknown` and blocks readiness. In particular, the product must not infer cash basis from settlement cash activity or from the current net-profit posting pattern.

| # | Phase 0 product question | Existing records can decide | User/lender decision or evidence | CPA/bookkeeper decision or validation | Defensible product handling/default |
|---:|---|---|---|---|---|
| 1 | Which legal entity/entities and whether consolidated or per-business reports are required? | **Partial only.** Tenant records and vehicle/settlement ownership links show current application grouping, not legal ownership or an approved reporting entity. Organization documents, EIN records, titles, contracts, and prior returns can prove legal entities. | **User required** to supply current ownership/legal documents and state whether the package is for Elis, LS, another entity, or a requested combination. **Lender required** to state borrower, guarantors, affiliates, and whether combined/consolidated statements are wanted. | **CPA/bookkeeper required** to map each opening balance and transaction to the proper entity and define intercompany/due-to-due-from/elimination treatment. | Default to **one ledger and statements per confirmed legal entity**. No consolidation or cross-tenant summing until scope and elimination rules are approved. Application tenant names are not legal-entity evidence. |
| 2 | Who is the target lender, and what exact statement periods, comparisons, schedules, notes, and certification language do they require? | **No.** The repository has generic report/export capabilities and no authoritative lender request, program, period, or certification contract. | **User and lender required.** Obtain the lender contact/request list, loan program/product, as-of/period requirements, comparative periods, projections, schedules, notes, delivery format, freshness, and exact representation language. | **CPA/bookkeeper required** to confirm which requested items can be prepared from the books, the accounting basis, proposed notes, and what preparer language is supportable. | No universal “SBA package” default. Show package requirements as `unknown` and block “lender ready.” Never generate “CPA prepared,” “compiled,” “reviewed,” “audited,” or certified wording without the appropriately authorized professional engagement. |
| 3 | Are statements cash basis, accrual basis, tax basis, or another basis? Is more than one basis required? | **Partial only.** Prior filed returns, prior accountant statements, bookkeeping settings, and Form 3115/elections can evidence prior treatment. Current code mixes ledger, cash, operational, and tax-derived values and therefore cannot establish a basis. | **User/lender required** to provide prior statements/returns and the lender's required presentation basis. | **CPA required** to confirm tax accounting method, any change-of-method implications, book basis, tax-basis adjustments, and whether separate book/tax/lender views are appropriate. Bookkeeper implements the approved method and cut-off rules. | **No accounting-basis default.** Persist `basis = unknown` until approved. The architectural recommendation is an accrual-capable authoritative book ledger with explicit adjustment/reporting layers, but this is not a decision that the company uses accrual or cash basis. Never infer cash basis. |
| 4 | What are the authoritative opening balances and conversion date for the accounting ledger? | **Partial only.** Bank statements, lender statements, AP/AR schedules, fixed-asset/depreciation schedules, prior trial balances, and filed returns can support balances. Current hybrid reports cannot serve as the opening trial balance without reconciliation. | **User required** to provide missing source records, identify the desired history/comparative scope, and approve the operational cutover window. A lender may determine how much comparative history is needed. | **CPA/bookkeeper required** to prepare/reconcile the opening trial balance, classify equity and prior-period adjustments, approve the conversion date, and clear opening suspense. | Recommended default approach: **the day after a fully reconciled month-end, preferably fiscal-year start**, using one controlled opening entry and a locked legacy snapshot. This is a process default only; the actual date and balances remain unapproved until source-reconciled. Opening suspense must be zero before readiness. |
| 5 | Which bank/credit accounts are in reconciliation scope, what is the source of statement balances, and what tolerance/materiality is allowed? | **Partial only.** Bank statements, account lists, settlement ACH evidence, credit-card statements, and GL accounts identify candidates and statement balances. The current app has no authoritative reconciliation scope or bank-feed contract. | **User required** to disclose every business bank, reserve, card, payment, and clearing account and provide statements/access. **Lender may require** specific accounts, freshness, or explanations. | **Bookkeeper required** to define reconciliation cadence, outstanding-item treatment, source hierarchy, and prepare reconciliations. **CPA/lender required** for reporting materiality or waiver thresholds. | Do not default account scope. Recommended control default: every confirmed balance-sheet cash/credit account reconciles to an external statement; unexplained reconciliation difference must be **exactly zero to the ledger currency precision** (normally one cent if the confirmed currency uses cents). Materiality may prioritize investigation but must not silently write off a difference. |
| 6 | What makes a period complete/closed, who may close/reopen it, and what events invalidate prior readiness/signoff? | **Partial only.** Source completeness, posting timestamps, statement dates, unresolved exceptions, and package snapshots can drive objective gates, but no current record proves the authority model. | **User required** to assign preparer, reviewer, close authority, reopen authority, deadlines, and escalation. **Lender may specify** acceptable statement age or require refreshed interim statements after material changes. | **CPA/bookkeeper required** to approve the close checklist, cut-off/accrual rules, materiality, adjusting-entry process, and year-end/tax close responsibilities. | Recommended control default: a period closes only after all versioned required gates pass; preparer and reviewer are distinct where staffing permits; reopening requires reason and authorization; any post-snapshot source/entry change marks prior readiness and packages `superseded`, never silently updates them. |
| 7 | For each debt instrument: lender, origination date, original principal, current verified balance date, rate/type, payment frequency/amount, maturity, fees, balloon terms, collateral, and current/long-term classification rule. | **Partial only.** Vehicle records contain some original/current amount, rate, and term fields, but values may be estimates/replays and lack lender, statement date, payment, maturity, fees, balloon, and contractual allocation. Executed notes, amendments, amortization schedules, and lender statements can decide contractual facts. | **User required** to supply every note, statement, payment record, refinance/payoff document, and related-party loan. **Lender/servicer required** where a current payoff, principal, accrued interest, or contractual allocation must be confirmed. | **Bookkeeper required** to reconcile cash payments to principal/interest/fees and the debt control account. **CPA required** for current/long-term classification policy, debt issuance costs, modifications, related-party debt/equity questions, and presentation. | No numeric or lender-field defaults. Missing contractual fields remain `unknown` and block debt tie-out. Use lender-verified principal as of a dated source; never substitute `loan_amount`, stored current balance, or profit-replayed balance. |
| 8 | Is the existing replay/projected vehicle payoff model operational planning only, or may any part support lender reporting? | **Yes, for the current model's nature.** Repository evidence shows it infers principal from cumulative profit after cash-investment recovery and forecasts payoff; it does not record proven lender payments. | **User may choose** to retain it as an operational scenario. **Lender must explicitly accept** any forecast inclusion and specify assumptions/presentation if requested. | **CPA/bookkeeper required** to keep forecast amounts out of actual debt and financial statements and reconcile actual principal/interest to lender evidence. | **Default: operational planning only.** It cannot support current debt, historical principal paid, contractual payment, or maturity. It may appear only as a clearly labeled supplemental forecast, sourced from reconciled actual opening debt and disclosed assumptions, if the lender requests it. |
| 9 | For each asset: legal owner, class, placed-in-service date, original basis, additions, disposals, salvage value, book useful life/method, tax method, Section 179/bonus treatment, and impairment policy. | **Partial only.** Vehicle fields contain VIN/name/type, purchase date, total cost, cost basis, depreciation method, and tax-deduction inputs, but do not prove ownership, placed-in-service status, approved basis, business use, additions/disposals, or book policy. Titles, bills of sale, invoices, prior depreciation schedules, and disposition records can prove facts. | **User required** to provide ownership/acquisition/use/disposal documents and identify actual in-service/use dates. Lender may require collateral values/appraisals, which are not book basis. | **CPA required** for basis, book life/method/residual value, tax class/convention, Section 179/bonus elections, business-use limits, impairment, disposition/recapture, and book-to-tax reconciliation. Bookkeeper maintains the approved asset subledger. | Defaults: keep **book and tax schedules separate** and mark missing inputs unknown. Do not default MACRS 5-year, salvage value, useful life, Section 179, bonus, or impairment. Legal owner comes from title/contract, not the tenant holding the UI record. |
| 10 | What is the authoritative rule for owner contributions/draws, retained earnings, repairs/reserves, trailer allocations, loan principal, and interest in the three statements? | **Partial only.** Existing postings and operational records reveal current behavior, not approved policy. Contracts, invoices, bank/lender records, ownership, and prior accountant entries can establish transaction facts. | **User required** to disclose owner payments/transfers, reserve custody and refund rights, trailer/affiliate agreements, and business purpose. Lender may prescribe presentation or add-back treatment but does not determine tax law. | **CPA/bookkeeper required** to approve the policy matrix and effective dates, including entity-specific equity labels, gross/net revenue, reserve asset/expense treatment, repairs versus improvements, intercompany allocations, debt allocation, interest accrual, and statement/cash-flow classification. | Defensible defaults: contributions/distributions are equity, not revenue/expense; documented principal reduces debt and is financing cash flow, not expense; sourced business interest is expense under the approved basis; internal segment allocations do not create entity-level external revenue; current-period income is not hard-coded retained earnings. **No default** for reserve ownership, gross/net settlement reporting, repair capitalization, or intercompany treatment without evidence/review. |
| 11 | What readiness gates, evidence, reviewer roles, signoff wording, and package retention/versioning policy are required? | **Partial only.** The ledger/subledgers can supply balance, tie-out, evidence-link, freshness, and exception facts after rebuild. The current app lacks a complete readiness and assurance authority model. | **User required** to assign roles, retention needs, internal approval, and package recipients. **Lender required** to state required schedules, certifications/representations, signatures, age, and resubmission conditions. | **CPA/bookkeeper required** to define accounting close/tie-out gates, workpaper evidence, reviewer responsibilities, adjustment treatment, and permissible preparation wording. Only a properly engaged/licensed professional can supply any professional assurance report. | Recommended conservative default: gates are `pass | block | unknown`; all required gates must pass; unknown blocks readiness; source evidence and reviewer timestamps are mandatory; packages are immutable snapshots with checksums and retention; later changes create a new version and supersede the old. Default wording is **“management-prepared draft; unaudited; not reviewed or compiled by a CPA”** unless an authorized professional supplies different language. |
| 12 | What currency/rounding/negative-number convention and timezone/report cutoff apply? | **Partial only.** Source documents and bank/lender statements show transaction currencies and timestamps; current numeric fields mostly lack explicit currency and therefore cannot prove a single-currency policy. The repository/environment timezone is not evidence of the entity's accounting cutoff. | **User required** to confirm functional/reporting currency and business timezone. **Lender required** to state currency, units, conversion, and cutoff expectations if different. | **CPA/bookkeeper required** to approve functional currency, foreign-currency policy if any, rounding precision/tolerance, cut-off convention, and treatment of late source documents. | No currency or timezone default until confirmed. Safe display defaults after confirmation: store/post decimal amounts at the approved precision; calculate from unrounded detail; round only presented totals under one documented rule; show negatives with both sign/parentheses and non-color cues; expose timezone and source cutoff on every snapshot. Do not infer America/New_York or USD from the runtime environment. |

### Phase 0 ownership summary

- **Can be decided now from repository evidence:** Question 8's current replay/payoff model is forecast/planning logic, not actual debt accounting. The safe default is operational-only. Repository evidence also proves why current reports cannot answer Questions 3, 4, 5, 7, 9, 10, or 11 authoritatively.
- **Requires user and/or lender:** Questions 1, 2, 4, 5, 6, 7, 9, 10, 11, and 12 require external scope, documents, authority, or package requirements. Question 3 requires the lender's requested basis and the user's prior records, but neither alone determines tax method.
- **Requires CPA and/or bookkeeper:** Questions 1 and 3–12 require accounting classification, reconciliation, close, or validation. Question 2 needs professional review of what preparation language and notes are supportable. A bookkeeper can prepare/reconcile within an approved policy; tax elections, entity tax treatment, book-to-tax conclusions, and any professional assurance language must go to the appropriately qualified professional.
- **Product & Delivery can approve without inventing accounting:** conservative unknown states; per-confirmed-entity isolation; immutable snapshots; exact tie-outs; no cash-basis inference; book/tax separation; forecast-versus-actual separation; blocked readiness when evidence is missing; and management-draft wording without CPA assurance claims.

## Authoritative guidance and requirement boundaries

- [IRS Publication 538, Accounting Periods and Methods](https://www.irs.gov/publications/p538): cash versus accrual timing and consistency. This is tax-method guidance, not a lender package specification.
- [IRS Publication 946, How To Depreciate Property](https://www.irs.gov/publications/p946): placed-in-service depreciation, MACRS, Section 179, special depreciation, limits, and records. These are tax rules; book useful life and residual value are separate accounting policies.
- [IRS tangible property final regulations overview](https://www.irs.gov/businesses/small-businesses-self-employed/tangible-property-final-regulations): repair versus capital improvement analysis, including betterment, restoration, and adaptation. Final classification remains fact-specific.
- [IRS Instructions for Schedule C](https://www.irs.gov/instructions/i1040sc): Schedule C eligibility and reporting instructions. Entity classification must be confirmed before the product offers this report as applicable.
- [IRS LLC filing as a corporation or partnership](https://www.irs.gov/businesses/small-businesses-self-employed/llc-filing-as-a-corporation-or-partnership): LLC federal classification depends on ownership and elections; “LLC” alone does not establish Schedule C treatment.
- [SBA SOP 50 10](https://www.sba.gov/document/sop-50-10-lender-development-company-loan-programs): SBA 7(a)/504 origination policy. Use the effective version and the lender's current checklist; it does not prescribe tax accounting elections.
- [SBA Form 413, Personal Financial Statement](https://www.sba.gov/document/sba-form-413-personal-financial-statement): personal/guarantor financial position for applicable SBA programs, separate from company books.
- [SBA Form 2202, Schedule of Liabilities](https://www.sba.gov/document/sba-form-2202-schedule-liabilities): SBA disaster-loan liability schedule whose total should balance to liabilities on the balance sheet; not a universal requirement for every SBA loan.

## Product & Delivery Lead handoff

### Required decisions before implementation

1. Obtain accountant-approved entity/basis and gross-versus-net conclusions.
2. Choose cutover date and prospective versus historical rebuild scope.
3. Confirm the target lender/program and exact document checklist.
4. Approve the stable semantic chart and whether separate entities require intercompany accounting.

### Recommended delivery sequence

1. **Foundation:** immutable semantic accounts, posting engine, source links, reversals, period locks, audit log, and tenant-safe access.
2. **Settlement correctness:** explicit gross/net templates; AR/cash clearing; prior balances; reimbursements; reserves; trailer/intercompany rules.
3. **Asset and debt subledgers:** acquisition events, lender-sourced payment allocation, improvements/disposals, and book fixed-asset schedule.
4. **Opening conversion:** evidence workspace, suspense workflow, trial-balance import, approval, and lock.
5. **Statements:** trial balance, P&L, balance sheet with enforced equation, retained-earnings rollforward, cash flow, and debt schedule—all ledger-derived.
6. **Reporting layers:** accountant-approved cash-tax organizer and lender package with explicit basis, as-of date, version, evidence status, and management-prepared disclaimer.

### Acceptance gates

- Every statement amount drills to journal lines, source records, and evidence.
- Trial balance nets to zero and balance sheet balances exactly.
- Bank, settlement receivable/reserve, asset, AP, debt, and equity subledgers reconcile to controls.
- Representative $880/$460/$99/$321 settlement posts correctly under both approved templates.
- Vehicle acquisition and each lender payment reconcile asset, cash, principal, and interest.
- Book and tax depreciation never overwrite each other.
- Closed periods cannot be reset or destructively edited.
- Debt schedule equals balance-sheet debt; fixed-asset schedule equals net equipment; cash flow change equals reconciled cash change.
- Schedule C/tax organizer is suppressed unless entity eligibility and mappings are approved.
- Lender exports state basis and preparation status and contain no unsupported CPA/audit/review assertion.
