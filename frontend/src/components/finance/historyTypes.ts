export interface HistoryIssue { code: string; title: string; detail: string; amount: string | null }
export interface HistoryRow {
  id: number; asset_id: number; name: string; date: string; provider: string; status: string; evidence_id: string | null; basis: string; source_ref: string | null;
  freight: string | null; carrier: string | null; driver_pay: string | null; fuel: string | null; remainder: string | null; calculated_remainder: string | null; difference: string | null;
  miles: string | null; stored_miles: string | null; mileage_basis: string; gallons_purchased: string | null; fuel_per_mile: string | null; rolling_fuel_per_mile: string | null; driver_percent: string | null;
  categories: Record<string, string>; trailer_allocation: string; repair_target: string; legacy_net: string | null;
  loads: {load_id: string; pickup: string; delivery: string; empty_miles: string | null; loaded_miles: string | null; freight_gross: string}[];
  fuel_rows: {date: string; gallons: string | null; amount: string; product: string; location: string}[];
  differences: {field: string; stored: string; source: string; difference: string}[]; issues: HistoryIssue[];
}
export interface HistoryReport { version: string; tenant_id: number; period: {start: string | null; end: string | null}; coverage: {source_records: number; derived_allocations_excluded: number; originals_preserved: number; arithmetic_matched: number; needs_mapping: number; originals_need_review: number; missing_sources: number; flagged_records: number; issue_counts: Record<string, number>}; rows: HistoryRow[]; limitations: string[] }
