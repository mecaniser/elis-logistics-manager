# Lessons

## 2026-04-30
- When a user corrects an ROI or payoff assumption, check both paths separately: the read-side ROI calculation and the write-side stored fields used during future settlement imports.
- Do not assume `truck.current_loan_balance` is authoritative just because ROI looks correct. Verify whether the app is recomputing payoff dynamically in one place while persisting stale balance in another.
