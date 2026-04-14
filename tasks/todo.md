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
