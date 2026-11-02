# Dashboard settlement remaining: QA and release hold

Status: draft review only. Do not merge or deploy until the release hold is explicitly lifted.

The dashboard's remaining metric sums saved settlement results after existing reserve and trailer allocations. Incurred repair invoices remain visible separately; verified reserve payments affect the reserve ledger rather than deducting the settlement remaining again. This is not a bank-confirmed available-cash report.

The change also prevents failed report loads from becoming false zeroes, isolates dashboard state when switching tenants, rejects stale business-series responses, retains signed expense-category credits, and formats date-only settlement values without timezone shifts.

## Validation

- 101 frontend Node tests passed, including actual-source loader tests for failed all-time reporting, genuine zero/negative results, and out-of-order success/failure.
- TypeScript/Vite production build and ESLint passed.
- Full isolated SQLite backend suite: 791 passed, 17 skipped, 1 existing failure in `test_daily_whole_charges_repeat_and_approval`.
- That failure reproduces on the unchanged base: its 22:00 UTC test clock is 17:00 Eastern after the DST transition, before the scheduler's 17:30 cutoff. Changing only the disposable baseline test clock to 23:00 UTC passes. The unrelated scheduler/test is unchanged in this PR.
- Two real Chromium matrices passed 16 checks each: financial views/mobile/navigation and failed requests/retry/tenant races/signed credits. No HTTP writes or external requests occurred in the financial matrix; synthetic record counts were unchanged.
- Independent re-review found no remaining blocker within this fix's scope, with 73 backend and 104 frontend checks independently passing. It did not independently repeat the browser or full-suite runs.

## Reproduce synthetic browser QA

The harness uses an in-memory SQLite database and real analytics routes with synthetic businesses. It does not start the production application lifecycle, rejects all non-GET/HEAD requests, and stubs the authentication shell/tenant list. It must bind localhost only.

```sh
DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 python -m uvicorn local_report_server:app --app-dir output/playwright --host 127.0.0.1 --port 8766
```

Build `frontend` first (`npm ci && npm run build` in that directory). Use an isolated Playwright CLI browser at `http://127.0.0.1:8766`. Run the exported async functions in `output/playwright/browser_regression.js` and `output/playwright/review_browser_regression.js` with the CLI's `run-code` command. The review matrix deliberately injects synthetic 503 responses and delays responses from the previously selected tenant. Screenshots/results are local artifacts, not production evidence.

## Remaining limits

- No PostgreSQL or production authentication integration run; the browser harness's accounting-context endpoint is intentionally unimplemented and returns 404.
- No source-document/bank receipt reconciliation or deployment verification.
- Missing repair dates remain excluded from dated periods; no accounting dates are invented.
- Outside paid cash needs separate reconciliation. Non-reserve settlement costs remain deducted; outside invoice amounts do not imply paid cash.
- Cumulative pie charts show positive spending; signed credits are in the detailed table/period bar chart. Reimbursement exclusions are unchanged.
- Successful malformed/old API responses missing `settlement_remainder` lack runtime schema validation coverage.
- Tenant switching intentionally resets dashboard selections to avoid retaining another tenant's state.
