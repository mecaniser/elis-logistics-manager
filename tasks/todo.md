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
