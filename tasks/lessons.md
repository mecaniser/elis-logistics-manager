# Lessons

## 2026-04-30
- When a user corrects an ROI or payoff assumption, check both paths separately: the read-side ROI calculation and the write-side stored fields used during future settlement imports.
- Do not assume `truck.current_loan_balance` is authoritative just because ROI looks correct. Verify whether the app is recomputing payoff dynamically in one place while persisting stale balance in another.
- When the business rule is "loan payoff comes from settlement replay", prefer derived metrics and forecasts over manual override inputs. Add override fields only when the user explicitly wants off-ledger/manual payoff support.
- When replaying principal from cumulative profit, do not apply cumulative excess directly to an already-reduced balance. Compute cumulative principal paid against the original loan first, then derive each settlement's incremental principal payment from the change in that cumulative total.

## 2026-05-01
- When a user says a repeated settlement workflow should auto-fill for a specific truck, prefer storing truck-level defaults in the data model and applying them in both backend write paths and frontend forms instead of hardcoding one screen.
- Before telling the user a local migration has been applied, verify the migration script targets the same SQLite path as `app.database.DATABASE_URL`. Several legacy scripts still hardcode `backend/elisgroup.db`, while the app runs against `./elisgroup.db`.
- When a runtime 500 appears immediately after model changes, test a direct ORM query against the active local DB first. A missing column on any selected model can break unrelated endpoints before business logic runs.

- When a user asks for reserve or trailer context inside a selected dashboard period, do not mix period deductions with all-time repairs. Use stored period allocations for current-period lines and compute cumulative snapshots only up to the selected period boundary.
