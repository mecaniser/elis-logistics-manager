# Repair evidence review handoff

Scope: incremental integration into the existing `/repairs` page, preserving navigation, search, invoice/photos, upload, manual entry and editing. Operate mode; existing typography, colors and card layout remain the visual authority. Impeccable hardening and Emil design engineering guidance applied. No new animation; disclosures respond immediately and support Enter, with visible keyboard focus and explicit expanded state.

| Before | After | Why |
| --- | --- | --- |
| Preserved evidence existed only behind an API | Evidence and payment review within the existing repair cards | Keeps investigation with the repair and its originals |
| Source discrepancy invisible in the card | Invoice and saved amount shown together; one-click discrepancy filter | Makes the $0.86 source difference findable without silently correcting it |
| No payment certainty shown | Unknown balances read “Not established”; linked activity is not called fully paid | Cash receipts and personal funding must not be mistaken for unpaid bills |
| “Reserve-funded automatically” | “Legacy reserve tracking,” with its limits stated | Existing legacy mechanics do not prove funded cash reserves |

Desktop and 390px mobile visual pass complete. Filter controls wrap, labels remain readable, source/record amounts have textual labels rather than color alone. Keyboard disclosure, empty-search recovery and original HTTP response verified. New error/retry states do not remove the legacy repair list. Tenant/as-of changes discard stale evidence responses. New components and service lint pass; existing Repairs explicit-any debt remains unchanged. No broad redesign or production release is claimed.

Remaining workflow work: posting/linking repairs and cash payments needs a dedicated validated intake flow; this view intentionally performs no financial mutations. Missing documents, payer facts and business cash counts remain factual gaps.
