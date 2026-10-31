# DBN equipment-type coordination

2026-10-31. Coordination specification only; no source edits, grants, deployment or production financial changes performed here.

The owner confirmed DBN invoice `INV-828ACD84-000023` / RO `TPS-828ACD84-000038` / ID `47da4a04-b18b-44a9-8e8a-a2f31a9b4c72` is six Aufine tires on trailer **T1003130**. EDG already has this trailer as tenant1 asset3, VIN `7VGAA5324T1003130`, tag `559-4574`. The earlier interim truck609 assignment is superseded. The owner did not confirm the ETSINV-1177 match, August3 completion, price/payment or funding in this answer.

Current DBN linkage still names tractor609, vehicle `3190c0ef-9e69-4836-8e92-b9fd44d0838b`, VIN `4V4WC9EG2LN250024`. The candidate ETS vehicle `2be81675-84fc-42f2-9402-d72e6b876e1f` / external152648 is a separate no-VIN/no-plate imported placeholder. Do not merge that placeholder into the truck or trailer from unit number alone. The owner's actual-equipment confirmation is separate evidence; any DBN correction needs its own audited source action.

## Compatibility boundary for the DBN task

EDG can already consume the deployed `db094-repair-financial-v2` vehicle ID/VIN plus an explicit reviewed equipment allocation. DBN's company equipment types can therefore ship without an EDG export change if the financial manifest stays unchanged.

EDG's v2 consumer deliberately validates exact row keys and canonical revisions/snapshot hashes. Adding `equipment_type`, an asset object or other fields to v2 is a breaking change. Coordinate a separately versioned manifest and source/consumer contract tests before exposing new fields there. Do not relax strict validation or substitute raw invoice totals as a fallback. Preserve invoice/customer authorization, quote/settlement separation, partial-payment facts, and hash semantics.

If the source changes an RO's vehicle ID or VIN to the actual trailer, EDG's existing attribution pin will require review. Refresh the source snapshot and record a fresh reviewed attribution; never rewrite a prior decision or silently move an imported cost/reserve entry. Before import, the already-confirmed trailer can be selected against that fresh authorized revision. After import, changing the booked equipment needs an explicit financial reclassification that preserves prior evidence and corrects dependent effects once.

Keep repaired equipment identity distinct from an associated/towing tractor. A declared type alone does not identify which trailer received work; do not use a current default pairing as historical proof. Mixed truck/trailer invoices need line-specific amounts and identities before splitting, so neither equipment receives the whole combined expense twice.

## Current intended allocation

The15reconciled DBN orders have evidenced intended equipment: truck603 six, truck609 eight, trailerT1003130 one. RO000055's candidate ETS job contains an extra trailer-tire line not present in the current DBN invoice; that candidate cannot be merged wholesale without further reconciliation. Historical attribution, conflicting dates/amounts, actual payment evidence and release/activation approvals remain separate holds.
