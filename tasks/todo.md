# Trailer Loan Investment Option

## Plan
- [x] Inspect the existing investment form, truck API validation, loan replay service, settlement interest accrual, and ROI display to identify where trailers are excluded from loan handling.
- [x] Add a stored loan duration field and allow trailers to carry `loan_amount`, `current_loan_balance`, `interest_rate`, and loan duration using the same revenue-vehicle rules as trucks.
- [x] Update trailer settlement/ROI calculations so weekly trailer income can pay back cash first, then loan principal, while loan interest reduces trailer profit.
- [x] Update the vehicle form and investment detail display so trailers can select a loan setup with amount, term, and interest, and total cost includes the loan.
- [x] Add focused backend tests for trailer loan creation, payoff replay, and managed trailer-income split interest.
- [x] Run backend tests, frontend typecheck, diff hygiene, and document the result below.

## Review
- Backend:
  - Added `loan_term_months` to the vehicle model/schema/API contract and created [backend/migrate_add_loan_term_months.py](/Users/sergio/GitHub/elis-logistics-app/backend/migrate_add_loan_term_months.py:1), registered in both migration runners.
  - Updated trailer validation so `total_cost = cash + loan + registration + additional expenses`, matching trucks/SUVs instead of rejecting trailer loans.
  - Extended loan replay and current-balance sync to revenue vehicles (`truck` and `trailer`). If cash is zero, loan principal can start paying down from first net profit; if cash exists, cash still recovers first.
  - Managed trailer split settlements now deduct trailer weekly loan interest from the trailer-side settlement expense categories and net profit.
- Frontend:
  - Trailer investment forms now expose `Loan ($)`, `Term (mo)`, and `Rate (%)`, and total trailer investment includes loans.
  - Vehicle detail investment/ROI loan display now applies to trailers as well as trucks and shows the saved term.
- Verification:
  - `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_trucks.py -q` passed: `23 passed`
  - `cd frontend && npx tsc --noEmit --pretty false` passed
  - `python3 -m compileall backend/app backend/migrate_add_loan_term_months.py backend/run_all_migrations.py backend/run_all_production_migrations.py` passed
  - `backend/venv/bin/python backend/migrate_add_loan_term_months.py` applied the new local DB column
  - `git diff --check -- ...` passed for touched files
  - Frontend dev server is running at `http://127.0.0.1:5173/`

# Loan Term Migration SQLite Path Fix

## Plan
- [x] Reproduce the migration failure path from the reported `trucks.loan_term_months` missing-column error.
- [x] Update the new migration to alter the SQLite database through `app.database.engine` instead of a hardcoded DB file path.
- [x] Verify the single migration, loan-interest recalculation migration, backend tests, compile checks, and diff hygiene.

## Review
- Fixed [backend/migrate_add_loan_term_months.py](/Users/sergio/GitHub/elis-logistics-app/backend/migrate_add_loan_term_months.py:1) so SQLite migrations use the configured SQLAlchemy engine connection. This keeps the altered DB aligned with whatever `DATABASE_URL` and current working directory the migration runner is using.
- Verification:
  - `backend/venv/bin/python backend/migrate_add_loan_term_months.py` passed and added the column to `sqlite:///./elisgroup.db`
  - `backend/venv/bin/python backend/migrate_recalculate_loan_interest_with_principal.py` passed after the fix
  - `PYTHONPATH=backend backend/venv/bin/python - <<'PY' ...` confirmed `loan_term_months` exists on the active DB
  - `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_trucks.py -q` passed: `23 passed`
  - `python3 -m compileall backend/app backend/migrate_add_loan_term_months.py backend/migrate_recalculate_loan_interest_with_principal.py backend/run_all_production_migrations.py` passed

# Repair Reserve Ledger + Business Rollup

## Plan
- [x] Audit and patch the backend schema, shared helpers, and migration scripts for the reserve ledger and `repairs.paid_from_reserve`.
- [x] Refactor settlement and repair side-effect flows so reserve sync and journal-entry work can run in a single caller-owned transaction.
- [x] Wire reserve synchronization into every settlement and repair write path, and add the new reserve API router with tenant-scoped balance and ledger endpoints.
- [x] Implement the reserve backfill script with `--dry-run`, chunked commits, and idempotent deposit reconciliation for 2026+ settlements only.
- [x] Add backend tests for reserve lifecycle behavior, tenant isolation, backfill idempotency, query-count protection, and atomic rollback behavior.
- [x] Verify the backend with targeted pytest runs, migration/backfill dry-runs, and schema checks before touching the frontend.
- [x] Replace the current heuristic reserve UI with ledger-backed reserve totals in `VehicleDetail.tsx`, add the dashboard business-total rollup, and add the repair `paid_from_reserve` checkbox flow.
- [x] Verify frontend TypeScript build and capture final review notes below.

## Review
- Added `repair_reserve_ledger` model, reserve helpers, reserve router, `reserve_regime.py`, `backfill_repair_reserves.py`, and the `paid_from_reserve` repair flag plus migration registration. The reserve router is mounted in `backend/app/main.py`, and `CLAUDE.md` now documents the caller-owned side-effect transaction rule.
- Settlement and repair write flows now sync reserve ledger entries inside the same transaction as sibling side effects. During verification, a real rollback bug surfaced in manual settlement create; that route now calls `db.rollback()` on journal-entry failure so source settlement rows, derived trailer rows, and reserve rows do not leak through partial failure.
- Frontend changes landed in `frontend/src/services/api.ts`, `Repairs.tsx`, `VehicleDetail.tsx`, and `Dashboard.tsx`. Repairs now send `paid_from_reserve`, vehicle detail shows ledger-backed deposit/withdrawal/balance totals, and the dashboard includes a business-total rollup plus current reserve balance context.
- `backend/venv/bin/pytest backend/tests/test_repair_reserves.py -q` passed: 12 targeted tests covering cutoff behavior, create/update/delete reserve sync for settlements and repairs, reserve-balance math, tenant isolation, bulk endpoint query count, backfill idempotency, and atomic rollback.
- `python3 -m compileall backend/app backend/backfill_repair_reserves.py` passed.
- `npx tsc --noEmit --pretty false` passed in `frontend/`.
- Local DB verification required using the repo-root SQLite file (`./elisgroup.db`), which is the active `DATABASE_URL`, not `backend/elisgroup.db`. After running `backend/migrate_add_repair_reserve_fields.py`, `backend/migrate_add_paid_from_reserve_to_repairs.py`, and `Base.metadata.create_all(...)`, `backend/venv/bin/python backend/backfill_repair_reserves.py --dry-run` passed with `0` pending updates on the current local file.
- Remaining gap: I did not add the full import-path regression matrix or the forced mid-run backfill crash-recovery test from the original 23-test design. The current suite covers the core reserve ledger contract and the new API surface.

# 77 Cargo LLC Settlement Parser

## Plan
- [x] Inspect the current settlement parser, extractor, analytics, and UI category handling for single-truck uploads.
- [x] Add a dedicated `77 Cargo LLC` parser path that extracts the unit 417 sample values from the new PDF layout.
- [x] Wire `77 Cargo LLC` detection through the extractor flow and expose the type in the extractor UI.
- [x] Treat `tolls` as a first-class expense category across accounting, analytics, dashboard, and settlement editing views.
- [x] Add targeted backend tests for parser extraction, settlement type detection, and upload with manual truck selection.
- [x] Verify the change with targeted automated tests and capture the outcomes below.

## Review
- `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_77_cargo_parser.py -q` passed: 5 tests covering parser extraction, extractor detection, upload with manual `truck_id`, analytics/dashboard toll totals, and toll journal-entry account mapping.
- `npx tsc --noEmit --pretty false` passed in `frontend/` after removing three unused locals in touched pages.
- Direct parser validation against `/Users/sergio/Documents/Elis Logistics/Volvo_VNR_0024/driver_settlement_2226_ELIS_LOGISTICS_LLC.pdf` produced the expected sample values: `gross_revenue=6380.00`, `expenses=5894.61`, `net_profit=485.39`, `tolls=393.30`, and `license_plate=None`.
- `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_settlements.py -q` still fails for pre-existing reasons unrelated to this change: those tests post/get settlements without the now-required tenant header and expect legacy status codes.

# 77 Cargo Regression 2280

## Plan
- [x] Reproduce the subtotal mismatch against `driver_settlement_2280_ELIS_LOGISTICS_LLC.pdf` and inspect the raw text extraction.
- [x] Patch the 77 Cargo load-row parser to accept rows where part of the route text shares the mileage line.
- [x] Add a regression test for the 2280 layout and verify both the test fixture and the real PDF parse successfully.

## Review
- Root cause: the 77 Cargo row regex assumed the `Pickup Delivery` dates were followed immediately by the `Empty Loaded` mileage columns. Settlement `2280` includes an inline route fragment on the same row (`LAFAYETTE, IN - GEORGETOWN,`) before the mileage values, so load `3604` was skipped and the subtotal guard failed.
- `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_77_cargo_parser.py -q` passed: 6 tests, including a new regression fixture that mirrors the `2280` wrapped-description layout.
- Direct parser validation against `/Users/sergio/Documents/Elis Logistics/Volvo_VNR_0024/driver_settlement_2280_ELIS_LOGISTICS_LLC.pdf` now succeeds with `gross_revenue=10076.00`, `expenses=6537.91`, `net_profit=3538.09`, and 4 parsed loads.
- Direct parser validation against `/Users/sergio/Documents/Elis Logistics/Volvo_VNR_0024/driver_settlement_2226_ELIS_LOGISTICS_LLC.pdf` still succeeds with `gross_revenue=6380.00`, `expenses=5894.61`, `net_profit=485.39`, and `tolls=393.30`.

# Vehicle ROI Investigation 417 / VIN 0024

## Plan
- [x] Inspect the ROI backend endpoint plus dashboard and vehicle detail pages to map the cumulative net profit calculation.
- [x] Trace how settlement deductions and expense categories are stored for the 77 Cargo / truck 417 path and compare that with the ROI math.
- [x] If the cumulative metric is skipping deductions, implement the smallest correct fix and verify it with targeted checks.

## Review
- Backend finding: ROI cumulative net profit is calculated in `backend/app/routers/analytics.py` as `sum(gross_revenue) - sum(expenses) - sum(repairs)`. It does not ignore deductions if those deductions are already included in each settlement's stored `expenses`.
- Parser finding: the new 77 Cargo settlement parser still deducts non-driver items when they exist. Direct validation against the source PDFs for the `Volvo_VNR_0024` folder showed `driver_settlement_2226_ELIS_LOGISTICS_LLC.pdf` includes `deduct=920.45`, `driver_settlement_1882_ELIS_LOGISTICS_LLC.pdf` includes `deduct=100.00`, while `driver_settlement_1915_ELIS_LOGISTICS_LLC.pdf` and `driver_settlement_2280_ELIS_LOGISTICS_LLC.pdf` contain no extra non-driver deduction lines beyond driver pay / insurance / prepass, so there is no separate `deduct` amount to subtract there.
- UI bug fixed: the vehicle detail ROI card was double-counting loan interest in the displayed `Total Expenses` line even though backend `cumulative_settlement_expenses` already includes loan interest. Updated `frontend/src/pages/VehicleDetail.tsx` to stop adding `cumulative_loan_interest` a second time and clarified the settlement label.
- Verification: `npx tsc --noEmit --pretty false` passed in `frontend/`.

# Loan Payoff Interest Sync

## Plan
- [x] Trace why truck 0024 can show clean return while new settlements still receive `loan_interest`.
- [x] Fix stored loan-balance recalculation so it replays from original loan principal and resyncs when truck investment fields change.
- [x] Use the recalculated balance when injecting interest into new settlements, then verify with targeted regression tests.

## Review
- Root cause 1: settlement creation/import paths used persisted `truck.current_loan_balance` directly, so if that field became stale after truck investment edits, new settlements could still accrue interest even though ROI math showed the truck had already reached clean return.
- Root cause 2: the existing loan-balance replay in `backend/app/routers/settlements.py` started from the already-reduced stored balance instead of the original `loan_amount`, so repeated recalculations were not stable.
- Fix: added `backend/app/services/loan_balance_service.py` to recalculate principal from full settlement/repair history starting at original `loan_amount`, updated settlement interest injection to use that recalculated balance, updated `backend/app/routers/trucks.py` to resync stored balance whenever truck investment fields change unless `current_loan_balance` was explicitly provided, and added `backend/migrate_recalculate_current_loan_balances.py` to backfill existing DB rows.
- Verification: `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_trucks.py -q` passed with 8 tests, including new regressions for paid-off balance resync and “no interest after payoff” settlement creation. `python3 -m compileall backend/app` also passed. `PYTHONPATH=backend backend/venv/bin/python backend/migrate_recalculate_current_loan_balances.py` ran successfully against the local DB (0 trucks in this local file).

# Loan Paid Off Date Override

## Plan
- [x] Add an optional `loan_paid_off_date` field to truck storage, schemas, and migration scripts.
- [x] Apply the payoff-date override in settlement interest accrual and ROI loan-balance display so post-payoff settlements always carry zero interest.
- [x] Wire the field through truck edit and vehicle detail UI, then add targeted regression tests and verification.

## Review
- Added `loan_paid_off_date` to truck model/schema/API types, plus a new migration script `backend/migrate_add_loan_paid_off_date.py`, and registered it in both migration runner scripts.
- Backend behavior: settlement creation/import now computes loan balance as of the settlement date and forces that balance to `0` on or after the manual payoff date. Current ROI also reports the payoff date and uses a zero current balance whenever the override has taken effect.
- UI behavior: truck create/edit now includes a `Paid Off` date input whenever a loan amount is present, and vehicle detail shows the payoff date alongside the loan balance card.
- Verification: `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_trucks.py -q` passed with 12 tests, including new regressions for updating the payoff date, skipping interest on/after the payoff date, preserving interest before the payoff date, and exposing the override in ROI. `npx tsc --noEmit --pretty false` passed in `frontend/`. `python3 -m compileall backend/app backend/migrate_add_loan_paid_off_date.py backend/run_all_migrations.py backend/run_all_production_migrations.py` also passed.

# Derived Loan Payoff Forecast

## Plan
- [x] Replace the main payoff-date behavior with a replay-derived payoff date and payoff forecast based on settlement history.
- [x] Remove the newly added manual payoff-date input from the primary truck workflow so the UI matches the replay-driven model.
- [x] Verify the new ROI metrics and forecasting behavior with targeted tests and document how the derived payoff date is computed.

## Review
- Replay behavior now derives loan payoff strictly from settlement history: cumulative net profit recovers `cash_investment` first, then only the cumulative excess can reduce principal, capped at the original `loan_amount`. The derived `loan_payoff_date` is the first settlement date where the replayed remaining balance reaches `0`.
- Forecast behavior is now exposed from the same replay: when principal remains, ROI returns `average_principal_payment`, `estimated_settlements_to_payoff`, `projected_payoff_date`, and `latest_settlement_date`. The vehicle detail page shows those forecast values instead of a manual payoff override input.
- Cleanup: the active truck API/UI flow no longer accepts or depends on `loan_paid_off_date`. The legacy DB column remains in the model for compatibility with the already-run migration, but replay-based logic ignores it.
- Important bug fix: the original replay was overstating later principal payments by reapplying cumulative excess against an already-reduced balance. The service now computes cumulative principal paid first, then derives the incremental payment for each settlement, which keeps both the remaining balance and projected payoff honest.
- Verification:
  - `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_trucks.py -q` passed with 10 tests, including new ROI regressions for replay-derived payoff date and remaining-balance forecast.
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.
  - `python3 -m compileall backend/app backend/migrate_recalculate_loan_interest_with_principal.py backend/migrate_add_loan_paid_off_date.py backend/run_all_migrations.py backend/run_all_production_migrations.py` passed.

# Production Migration Runner Coverage

## Plan
- [x] Audit `run_all_production_migrations.py` against the production-safe migration scripts touched in this work.
- [x] Register the missing migration/backfill modules in the production runner in the correct order.
- [x] Verify the runner can import the added modules and that each added script exposes a `migrate()` entrypoint.

## Review
- Added `migrate_add_vin.py`, `migrate_create_vehicle_documents.py`, `migrate_wave1_correctness.py`, and `migrate_recalculate_current_loan_balances.py` to [backend/run_all_production_migrations.py](/Users/sergio/GitHub/elis-logistics-app/backend/run_all_production_migrations.py:1).
- Added a `migrate()` wrapper to [backend/migrate_recalculate_current_loan_balances.py](/Users/sergio/GitHub/elis-logistics-app/backend/migrate_recalculate_current_loan_balances.py:1) so the master runner can execute it like the other migration modules.
- Ordering note: `migrate_recalculate_current_loan_balances.py` now runs last, after the loan-interest replay migration, so the stored `current_loan_balance` values reflect the latest replay logic.
- Verification: `python3 -m compileall backend/run_all_production_migrations.py backend/migrate_recalculate_current_loan_balances.py` passed.

# Truck Trailer Revenue Split

## Plan
- [x] Add settlement-level fields to track a managed trailer income split from a truck settlement.
- [x] Apply the split during truck settlement create/upload by reducing truck revenue and creating a linked trailer settlement for the allocated share.
- [x] Verify the split stays visible in vehicle ROI/reporting and that deleting the source settlement also removes the managed trailer allocation.

## Review
- Added settlement fields for `trailer_income_split_trailer_id`, `trailer_income_split_amount`, and `source_settlement_id`, plus the migration script [backend/migrate_add_settlement_income_split_fields.py](/Users/sergio/GitHub/elis-logistics-app/backend/migrate_add_settlement_income_split_fields.py:1). The new migration is registered in both master migration runners.
- Backend behavior: when a truck settlement is created or uploaded with a trailer split, the truck settlement keeps only the truck's remainder revenue and net profit, and a managed child settlement is created for the trailer with the allocated weekly income. The child settlement is synced on source-settlement updates and removed automatically when the source settlement is deleted.
- Frontend behavior: the settlements upload form and manual settlement form now let the user choose a trailer and enter the weekly trailer share. Settlement cards also show when a trailer split exists or when a trailer settlement is a managed allocation.
- Verification:
  - `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_trucks.py -q` passed with 12 tests, including new coverage for split creation and split deletion.
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.
  - `python3 -m compileall backend/app backend/migrate_add_settlement_income_split_fields.py` passed.

# 77 Cargo Settlement Adjustments

## Plan
- [x] Inspect the uploaded 77 Cargo settlement data path end to end: PDF parse output, stored settlement fields, dashboard aggregation, and graph/detail rendering.
- [x] Confirm which expense pieces are currently extracted versus hidden in reporting, with special attention to `deduct` amounts and the 12% dispatch-fee gap on 77 Cargo settlements.
- [x] Implement the smallest correct backend/frontend change so settlement reporting surfaces all relevant 77 Cargo overview amounts without breaking existing net-profit math.
- [x] Add targeted regression coverage for the adjusted extraction/reporting behavior.
- [x] Verify with focused tests and direct inspection, then capture the findings below.

## Review
- Root cause 1: the 77 Cargo parser was already extracting booked expenses correctly for `fuel`, `tolls`, `insurance`, `prepass`, `driver_pay`, and `deduct`, but analytics/dashboard treated `deduct` as generic `custom`, so those deductions were missing from the main expense graphs and tables.
- Root cause 2: the 77 Cargo PDF contains a separate load gross before the 88% pay-rate reduction. The app only stored the post-dispatch amount as `gross_revenue`, so the 12% carrier/dispatch gap was not available anywhere in the UI.
- Fix: added `overview_amounts` to settlements for display-only derived values, and the 77 Cargo parser now stores `dispatch_fee`, `gross_before_dispatch`, and `pay_rate_percent` there without changing booked `expenses` or `net_profit`.
- Fix: promoted `deduct` to a first-class dashboard/time-series category so deductions now appear in dashboard graphs and detailed expense tables instead of being hidden under generic custom handling.
- UI: settlement cards now show the 77 Cargo dispatch-fee overview and the pre-dispatch gross/pay-rate context when available. The extractor view also shows the derived dispatch fee separately from booked expenses.
- Verification:
  - `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_77_cargo_parser.py -q` passed: 6 tests, including the new 77 Cargo overview-amount assertions and dashboard deduction coverage.
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.
  - `python3 -m compileall backend/app backend/migrate_add_settlement_overview_amounts.py backend/run_all_migrations.py backend/run_all_production_migrations.py` passed.
  - `backend/venv/bin/python backend/migrate_add_settlement_overview_amounts.py` passed against the active local app database (`sqlite:///./elisgroup.db`), and `pragma table_info(settlements)` now shows `overview_amounts`.
  - Direct parser validation against `/Users/sergio/Documents/Elis Logistics/Volvo_VNR_0024/driver_settlement_2226_ELIS_LOGISTICS_LLC.pdf` now reports `gross_revenue=6380.00`, `expenses=5894.61`, `net_profit=485.39`, booked categories `{fuel=1658.36, tolls=393.30, insurance=600.00, prepass=147.50, driver_pay=2175.00, deduct=920.45}`, and overview amounts `{dispatch_fee=870.00, gross_before_dispatch=7250.00, pay_rate_percent=88}`.

# Per-Mile Metrics

## Plan
- [x] Extend the analytics data model so weekly, monthly, and overall aggregates include miles-driven totals and enough revenue/expense detail to calculate per-mile metrics consistently.
- [x] Use post-dispatch settlement revenue as the default operational revenue basis, and expose separate 77 Cargo raw-gross metrics from `overview_amounts.gross_before_dispatch` when available.
- [x] Add two cost-per-mile variants everywhere relevant: settlement-only cost per mile and all-in cost per mile including repairs.
- [x] Update frontend API types and dashboard UI to show weekly, monthly, and overall per-mile metrics clearly.
- [x] Add regression coverage for the new analytics calculations and verify the end-to-end output below.

## Review
- Backend: `analytics/dashboard` now returns `operational_metrics` at the combined, trucks, and trailers levels with miles driven, post-dispatch revenue, settlement expenses, repair costs, raw 77 Cargo gross, and the derived per-mile metrics. The calculations use post-dispatch revenue by default and only compute raw-gross-per-mile from settlements that actually expose `overview_amounts.gross_before_dispatch`.
- Backend: `analytics/time-series` now includes `miles_driven`, `raw_gross_revenue`, and `raw_gross_miles_driven` for weekly, monthly, and yearly rows, plus `deduct` remains first-class in each aggregate so the period views have the inputs needed for the new cards.
- Frontend: the dashboard now shows five operational metric cards for the selected weekly, monthly, yearly, or all-time period: miles, revenue per mile, 77 Cargo raw gross per mile, settlement cost per mile, and all-in cost per mile. All-in cost per mile uses the existing repair-period matching logic, so weekly/monthly/yearly/all-time views all include repairs.
- Verification:
  - `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_77_cargo_parser.py -q` passed with 7 tests, including a new regression that asserts the dashboard operational metrics and the weekly/monthly/yearly time-series mileage/raw-gross fields for a 77 Cargo settlement plus repair.
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.
  - `python3 -m compileall backend/app backend/tests/test_77_cargo_parser.py` passed.
- Limitation noted: `/api/analytics/time-series` still does not embed monthly/yearly repair totals into the emitted rows; the dashboard continues to source repairs for all-in period calculations from the separate `repairs_by_month` feed on `/api/analytics/dashboard`, which is why the UI works correctly without further backend shape changes.

# Migration Return Status Fix

## Plan
- [x] Inspect the production runner and the two flagged settlement migration scripts to confirm why they are reported as failed.
- [x] Update the migration scripts to return runner-compatible success/failure status codes.
- [x] Verify the fixed modules locally and capture the result below.

## Review
- Updated `backend/migrate_add_missing_settlement_columns.py` and `backend/migrate_add_duplicate_block_ids_warning.py` so `migrate()` returns `0` on success and `1` on failure, matching the production runner contract.
- Verification passed with the project virtualenv:
  - `PYTHONPATH=backend backend/venv/bin/python backend/migrate_add_missing_settlement_columns.py`
  - `PYTHONPATH=backend backend/venv/bin/python backend/migrate_add_duplicate_block_ids_warning.py`
  - Both completed successfully and exited with status `0` while reporting the existing columns as already present.

# Trailer Split Autofill Defaults

## Plan
- [x] Inspect the vehicle data model and settlement upload flow to identify where a truck-level attached trailer/default split should live.
- [x] Add truck-level default trailer split fields and expose them through the API plus vehicle edit form.
- [x] Autofill the settlement upload/manual forms from the selected truck's default trailer split while keeping the values editable.
- [x] Verify the behavior with targeted checks and capture the outcome below.

## Review
- Added truck-level default split fields `default_trailer_id` and `default_trailer_income_split_amount` to the truck model/schema/API, plus the migration script [backend/migrate_add_default_trailer_split_to_trucks.py](/Users/sergio/GitHub/elis-logistics-app/backend/migrate_add_default_trailer_split_to_trucks.py:1). The new migration is registered in both master migration runners.
- Backend behavior: truck create/update now validates that default split settings only point to a trailer in the same tenant, and settlement create/upload now falls back to those truck defaults when explicit split fields are omitted. That means the business rule lives in the stored truck configuration, not just in the upload form.
- Frontend behavior: the Vehicles form now lets a truck store its default attached trailer and default weekly trailer split amount, and the Settlements upload/manual forms auto-fill those values whenever that truck is selected while still allowing the user to edit them before saving.
- Verification:
  - `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_trucks.py -q` passed with 14 tests, including new coverage for saving truck default split settings and using them automatically during settlement creation.
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.
  - `python3 -m compileall backend/app backend/migrate_add_default_trailer_split_to_trucks.py backend/run_all_migrations.py backend/run_all_production_migrations.py` passed.

# Weekly Repair Reserve

## Plan
- [x] Inspect the existing settlement split flow and choose how a weekly repair reserve should be modeled without colliding with trailer split behavior.
- [x] Add truck-level default repair reserve settings plus settlement-level reserve tracking in backend models, schemas, migrations, and write paths.
- [x] Autofill the settlement upload/manual UI from the selected truck defaults while keeping the reserve editable and visible in settlement cards.
- [x] Verify the reserve flow with targeted tests/build checks and capture the result below.

## Review
- Added `default_repair_reserve_amount` to trucks and `repair_reserve_amount` to settlements, plus the migration script [backend/migrate_add_repair_reserve_fields.py](/Users/sergio/GitHub/elis-logistics-app/backend/migrate_add_repair_reserve_fields.py:1). The new migration is registered in both master migration runners.
- Backend behavior: truck create/update can now store a default weekly repair reserve for trucks, and settlement create/upload falls back to that stored default when no explicit reserve is provided. The reserve is applied on top of any trailer split by reducing the source truck settlement `gross_revenue` and `net_profit`, and the amount is stored on the settlement for later display/editing.
- Frontend behavior: the Vehicles form now includes `Default Repair Reserve ($)` for trucks, and the Settlements upload/manual flows auto-fill that amount whenever a truck with a default reserve is selected. Settlement cards now show the booked `Repair Reserve` amount separately.
- Verification:
  - `PYTHONPATH=backend backend/venv/bin/pytest backend/tests/test_trucks.py -q` passed with 15 tests, including new coverage for saving a truck default repair reserve and automatically applying it during settlement creation.
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.
  - `python3 -m compileall backend/app backend/migrate_add_repair_reserve_fields.py backend/run_all_migrations.py backend/run_all_production_migrations.py` passed.

# Vehicle Profit Composition

## Plan
- [x] Inspect the current vehicle detail ROI view and decide how to present truck-only, trailer-only, and combined profit without changing existing settlement math.
- [x] Load the attached trailer ROI on the truck detail page and add a dedicated profit composition UI.
- [x] Verify the frontend build and capture the results below.

## Review
- Frontend-only change: `frontend/src/pages/VehicleDetail.tsx` now loads the selected truck first, then optionally loads the attached trailer and its ROI when the truck has a `default_trailer_id`. Trailer ROI fetch failures do not block the main truck detail page.
- UI behavior: truck detail now shows a dedicated `Profit Composition` block with `Truck Net Profit`, `Trailer Contribution`, and `Combined True Net Profit`. The existing cumulative net profit card is relabeled as truck-only when a trailer contribution is being shown, with an inline note that the trailer allocation is tracked separately.
- Verification:
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.

# Per-Mile Trend Indicators

## Plan
- [x] Inspect the current dashboard per-mile cards and confirm which period datasets are already available for comparison.
- [x] Add previous-period comparison helpers for the selected weekly/monthly/yearly expense-analysis view.
- [x] Show up/down trend arrows and comparison text on the per-mile visuals without changing backend calculations.
- [x] Verify the frontend build and capture the result below.

## Review
- Frontend-only change: `frontend/src/pages/Dashboard.tsx` now derives the immediately previous selected period from the already-loaded weekly/monthly/yearly time-series arrays and calculates the same four dollar-per-mile metrics for that comparison period.
- UI behavior: the per-mile cards now show a compact trend row with arrows and delta text versus the previous week, month, or year. Revenue-based cards are treated as better when they go up, while cost-based cards are treated as better when they go down, so the trend colors stay meaningful.
- All-time view intentionally does not attempt a trend comparison and instead shows `No prior comparison`.
- Verification:
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.

# Reserve Summary Panel

## Plan
- [x] Inspect what reserve and repair data is already available on the vehicle detail page and avoid adding a new backend endpoint if the totals can be derived safely.
- [x] Load stored settlement reserve amounts for the selected vehicle and compute reserve set aside, repairs used, and cushion available.
- [x] Add a reserve summary panel to the vehicle detail page and verify the frontend build.

## Review
- Frontend-only change: `frontend/src/pages/VehicleDetail.tsx` now loads all settlements for the selected vehicle alongside the existing ROI and repairs data so the page can sum `repair_reserve_amount` directly from stored settlement rows.
- UI behavior: truck detail now shows a `Repair Reserve Summary` panel with `Reserve Set Aside`, `Reserve Used by Repairs`, and `Reserve Cushion Available`. The panel also shows the truck’s default weekly reserve when configured.
- Calculation rule: reserve cushion is currently `sum(repair_reserve_amount on this truck's settlements) - cumulative_repair_costs`. That means older settlements with no stored reserve allocation will not contribute until they are re-uploaded or edited.
- Verification:
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.

# Dashboard Reserve And Trailer Breakdown

## Plan
- [x] Inspect the dashboard `Detailed Expense Analysis` math and identify which new period and cumulative fields are needed to show trailer contribution and reserve cushion correctly.
- [x] Extend the time-series backend and frontend types to carry weekly/monthly/yearly trailer split and repair reserve totals for the selected truck context.
- [x] Update the dashboard net profit details block to show current-period trailer split and repair reserve deductions plus up-to-date cumulative trailer contribution and reserve cushion.
- [x] Verify the backend/frontend changes and capture the result below.

## Review
- Backend: `backend/app/routers/analytics.py` now includes `trailer_income_split_amount` and `repair_reserve_amount` in weekly, monthly, and yearly time-series aggregates, and weekly rows now also return `week_start` / `week_end` so the dashboard can align weekly repair filtering to the actual settlement window.
- Frontend types: `frontend/src/services/api.ts` now exposes those new time-series fields so the dashboard can use stored period allocations instead of inferring them from net profit alone.
- Dashboard behavior: `frontend/src/pages/Dashboard.tsx` now reconstructs `Settlement Net Profit` before deductions, shows current-period `Less: Trailer Split` and `Less: Repair Reserve` lines, and adds an `Up-To-Date Position` block with cumulative trailer contribution, reserve set aside, repair spend to date, and reserve cushion available as of the selected period boundary.
- Correction applied from user feedback: cumulative repair spend on the dashboard is now capped at the selected period end date, instead of mixing a selected month/week with all truck repairs.
- Verification:
  - `npx tsc --noEmit --pretty false` passed in `frontend/`.
  - `python3 -m compileall backend/app/routers/analytics.py` passed.
