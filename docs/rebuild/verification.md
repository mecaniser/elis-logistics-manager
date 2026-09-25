# Local verification — reconciled finance

Date: 2026-09-23. Branch: `codex/reconciled-logistics-rebuild`.
Baseline: `ae6ceefc0a144498ae168b6dfc1af7ecb4ec438d`.

## Later source-history milestone

The sections below retain the earlier foundation verification. The current local preview on port 8016 now uses the isolated real-source database at `backend/settlements_extracted/rebuild-20260923/review.db`; it does not use the synthetic balances below. Production remains unchanged.

- Finance and historical reconciliation suites: **35 passed**, 15 existing deprecation warnings. Latest run includes the ambiguous source-row guard.
- Frontend build, scoped finance/history ESLint and `git diff --check` pass. The existing bundle-size warning and repository baseline failures remain.
- Local API confirms 175 source records, 78 preserved originals, 77 arithmetic matches, one source-row review and 97 unavailable originals. All measured-MPG values remain null. A foreign-business history request returns 404.
- The two posted September 21 originals reconcile to $5,836.92. Owner cash remains null/provisional because bank and opening evidence are absent. Other historical statements have not been posted to the new ledger.
- Desktop 1440px, mobile 390px and normal user-width 1832px dashboard/history views were inspected. Controls measure 44px, tables scroll within their panels and mobile has no document overflow. Known unsupported dates remain chart gaps. Search, disclosure, metric selection and period coverage warnings were exercised.
- The independent finish review resolved all five findings and accepted the final desktop chart recapture. Its SHIP disposition is scoped local design acceptance, not production or complete financial acceptance. See `history-design-audit.md` and `historical-reconciliation.md`.
- Private JSON and CSV review exports were regenerated from the current endpoint after verification. Originals and legacy interpretations remain preserved.

## Result

The additive finance workspace is implemented and locally verified. This is not production acceptance: real opening balances, funded reserves, asset/depreciation records, financing statements, historical reconstruction, Motive access and business browser acceptance remain outstanding. No production data was modified or migrated.

| Check | Result |
| --- | --- |
| New finance backend suite | **24 passed**, 15 warnings |
| Entire backend suite | **78 passed, 12 failed**, 16 warnings |
| Unchanged baseline backend suite, separately extracted | **54 passed, the same 12 failed**, 16 warnings |
| ESLint on all new Finance/Home/service/component files | Passed |
| Frontend production build | Passed; existing large bundle warning remains |
| Repository-wide frontend lint | 197 errors and 30 warnings in existing code; new Finance files pass separately |
| Whitespace validation | `git diff --check` passed |
| PostgreSQL 16 disposable database | Additive schema, exact decimal balanced posting, and all ten UPDATE/DELETE immutability guards passed |
| Browser | Desktop and 390px mobile synthetic preview inspected; no document overflow at 390px |
| Independent interface review | All three requested corrections resolved; verdict scope is those three findings |
| Design handoff | Scoped documentation completed in `design-verification.md` |

The backend baseline failures are six repair tests and five settlement tests that omit required tenant context, plus the existing profit-derived financed-trailer payoff assertion. They reproduce on the unchanged baseline; they are not new-module regressions. Whole-repository tests/lint are therefore **not green**.

## Financial acceptance exercised

- September 21 synthetic source values reconcile $23,700 freight to $5,836.92 settlement remainder; $200 support is included once. Weekly/monthly/yearly selections agree for identical included entries.
- Reserve-funded repair payment reduces cash and reserve together; an owner-paid vendor bill substitutes one reimbursement claim.
- Card charges and repayment recognize expense once; mixed operating/equipment cash repayments require a full supported allocation.
- Idempotent retries, conflicting keys, duplicate sources, duplicate/amended evidence, statement balance errors, partial payments, split transaction allocations, credits and refunds are covered.
- Cross-business access and malformed selectors fail; closed periods require explicit reopening; reversals remain traceable.
- Equipment disposal requires its cost/depreciation to match the ledger; lifetime acquisition is deducted once and payoff remains separate from disposal profit.
- Estimated miles cannot produce measured MPG; effective-dated assignments preserve earlier history.
- Automatic matching requires an approved mapping and unique exact reference/amount.
- Frozen report packages preserve referenced original documents and source-event history; incomplete packages and Home cutover are blocked. A reconciled synthetic package and explicit cutover succeed in tests.

## Browser evidence and interaction scope

Preview: `http://127.0.0.1:8016/finance`, backed exclusively by `/tmp/elis-finance-demo-1.db`, with a visibly named **ELIS · Synthetic preview** business. The server binds loopback. User services on other ports were left running. The disposable PostgreSQL smoke container was removed after verification.

Desktop and mobile captures are local review artifacts at `.impeccable/review/desktop.png` and `mobile.png`. The mobile width was independently read from the rendered document: viewport and document width were both 390px.

The browser submitted a synthetic $500 reserve-covered repair and confirmed its retained obligation, unchanged $10,836.92 provisional availability and success message. Other interactions inspected the five-section Home, pair disclosure, workflow navigation, card allocation fields, disabled accountant-package download, visible readiness gaps, and disabled unconfigured Motive fetch. Later repayment fields reuse the existing form pattern. These checks do not claim every workflow has been exercised in a live business.

The independent reviewer scored these three fixes resolved: stale business/date data hidden during refresh, legacy comparison nested inside the revenue section, and cash kept provisional until its prerequisites are confirmed. A generic independent agent substituted for the unavailable named Impeccable reviewer; its verdict does not certify financial correctness or deployment.

## Reproduce

Use backend requirements in a virtual environment and a disposable database. Tests construct their own in-memory SQLite database:

```sh
DATABASE_URL=sqlite:////tmp/elis-finance-tests.db ELIS_FINANCE_LOCAL_TENANTS=1 PYTHONPATH=backend /tmp/elis-finance-venv/bin/pytest backend/tests/test_finance.py -q
npm --prefix frontend run build
```

For a new synthetic preview, use `backend/scripts/seed_finance_demo.py` with an empty database whose URL starts `sqlite:////tmp/elis-finance-demo`. It refuses other database paths and nonempty databases. Never seed a real business database.

## Remaining release gates

Follow `implementation-and-rollout.md`: production-shaped staging migration, authenticated tenant configuration, real source reconstruction and differences, complete bank/card and obligation reconciliation, asset/HELOC/tax policy confirmation, provider coverage verification, and actual-business desktop/mobile acceptance. The old Home remains active until the explicit reconciled cutover action passes its checks.
