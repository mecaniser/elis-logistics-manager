import type { RepairReviewReport } from '../components/repairs/repairReview'
import axios from 'axios'
import type { HistoryReport } from '../components/finance/historyTypes'

const client = axios.create({ baseURL: '/api/v1/accounting', withCredentials: true })
client.interceptors.request.use(config => {
  const tenant = localStorage.getItem('currentTenantId')
  if (!tenant) throw new Error('Select a business first.')
  config.headers['X-Tenant-ID'] = tenant
  return config
})
export type Value = string | number | boolean | null | Value[] | { [key: string]: Value }
export type RecordData = { [key: string]: Value }
export interface Evidence { id: string; filename: string; source_key: string; extracted: RecordData; supersedes_id: string | null }
export interface Event { id: string; kind: string; effective_date: string; payload: RecordData }
export interface Context { tenant_id: number; currency: string; assets: { id: number; name: string; type: string }[]; accounts: Record<string, string>; motive_configured: boolean; home_enabled: boolean; owner_preview: boolean }
export interface Cash { available: string | null; business_cash: string | null; protected_reserves: string; uncovered_bills: string; owner_reimbursement: string; card_obligations: string; committed_financing: string; status: string; as_of: string; issues: string[]; coverage: {name: string; type: string; balance: string | null; reconciled_through: string | null}[] }
export interface Readiness { status: string; checks: { code: string; label: string; status: string }[] }
export interface Workspace { accounts: RecordData[]; statements: RecordData[]; transactions: RecordData[]; claims: RecordData[]; reserves: RecordData[]; capital: RecordData[]; settlements: RecordData[]; assignments: RecordData[]; policy: RecordData | null; owner_cash: Cash; readiness: Readiness }
export interface RetentionReport {
  settings_timezone:string; minimum_effective_date:string; scheduled_targets:{effective_date:string;target_percent:string;acceptable_percent:string}[];
  targets: {target_percent:string; acceptable_percent:string; effective_date:string|null};
  note:string; pairs:{asset_id:number; retained:string; freight:string; retained_per_100:string|null; score:string|null; band:'target_met'|'acceptable'|'below_floor'|'no_revenue'; status:'provisional'; issues:string[]; bridge:{label:string;amount:string}[]; source_event_ids:string[]}[]
}
export interface Report { retention: RetentionReport; owner_insights: OwnerInsights; id: string; label: string; as_of: string; period: {start: string; end: string; calendar_days: number}; owner_cash: Cash; readiness: Readiness; ledger: {income_statement: {revenue: string; operating_earnings: string; net_income: string; interest: string; depreciation: string; disposal_gain: string}; general_ledger: RecordData[]; trial_balance: RecordData[]; balance_sheet: RecordData; cash_flow: RecordData}; revenue_breakdown: {freight_gross: string; settlement_remainder: string; rows: {category: string; amount: string; percent_of_freight: string | null}[]}; pairs: {truck_id: number; name: string; trailer_ids: number[]; freight_gross: string; earnings: string; per_calendar_day: string; settlements: RecordData[]; components: RecordData[]}[]; shared_company_result: string; unassigned_asset_result: string; capital: RecordData[]; fuel: {asset_id: number; name: string; measured_mpg: string | null; miles_per_gallon_purchased: string | null; note: string; alerts: string[]}[]; exceptions: {code: string; message: string; status: string; href: string}[]; trend: {date: string; freight: string; earnings: string}[]; legacy_comparison: {rows: RecordData[]; totals: RecordData; note: string} }
export const financeApi = {
  repairHistory: (as_of: string) => client.get<RepairReviewReport>('/repair-history', {params: {as_of}}).then(r => r.data),
  history: () => client.get<HistoryReport>('/settlement-history').then(r => r.data),
  context: () => client.get<Context>('/context').then(r => r.data),
  workspace: (as_of: string) => client.get<Workspace>('/workspace', { params: { as_of } }).then(r => r.data),
  events: async () => { const result: Event[] = []; let cursor: number | null = 0; do { const r: {data: {items: Event[]; next_cursor: number | null}} = await client.get('/events', {params: {cursor, limit: 500}}); result.push(...r.data.items); cursor = r.data.next_cursor } while (cursor !== null); return result },
  evidence: async () => { const result: Evidence[] = []; let cursor: string | null = null; do { const r: {data: {items: Evidence[]; next_cursor: string | null}} = await client.get('/evidence', {params: {cursor, limit: 500}}); result.push(...r.data.items); cursor = r.data.next_cursor } while (cursor !== null); return result },
  command: (effective_date: string, payload: RecordData, key: string) => client.post<Event>('/events', {effective_date, payload}, { headers: {'Idempotency-Key': key} }).then(r => r.data),
  upload: (file: File, source: string, supersedes: string) => { const data = new FormData(); data.append('file', file); data.append('source_key', source); if (supersedes) data.append('supersedes_id', supersedes); return client.post('/evidence', data).then(r => r.data) },
  report: (start: string, end: string, as_of: string) => client.post<Report>('/report-runs', {start, end, as_of}).then(r => r.data),
  reconstruct: (legacy_ids: number[]) => client.post('/reconstruction', {legacy_ids}).then(r => r.data),
  motive: (payload: RecordData) => client.post('/connections/motive/fetch', payload).then(r => r.data),
  download: async (path: string, name: string) => { const r = await client.get(path, {responseType: 'blob'}); const url = URL.createObjectURL(r.data); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url) },
}
export function financeError(error: unknown): string {
  if (axios.isAxiosError(error)) { const detail = error.response?.data?.error || error.response?.data?.detail; if (typeof detail === 'string') return detail; if (Array.isArray(detail)) return detail.map(d => `${d.loc?.slice(1).join(' → ')}: ${d.msg}`).join('; '); if (detail?.message) return detail.message + (detail.field_errors?.length ? ' ' + detail.field_errors.map((f: {field: string; message: string}) => `${f.field}: ${f.message}`).join('; ') : '') }
  return error instanceof Error ? error.message : 'The request failed. Please retry.'
}
export const dollars = (value: unknown) => value === null || value === undefined ? 'Not established' : new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(Number(value))
export interface OwnerPair { asset_id: number; name: string; trailer_ids: number[]; freight: string; remainder: string; recorded_net: string; outside_statement_effect: string; remainder_per_calendar_day: string | null; miles: string | null; mileage_basis: string; statement_count: number; fuel_per_mile: string | null; remainder_per_mile: string | null; empty_mile_percent: string | null; categories: Record<string,string>; shares: Record<string,string | null>; remainder_percent: string | null }
export interface OwnerInsights { unposted_in_period: number; pairs: OwnerPair[]; comparisons: {base_name: string; compared_name: string; difference: string; effects: {category: string; amount: string}[]; fuel_rate_change_percent: string | null; note: string}[]; issues: {code: string; title: string; detail: string; href: string}[]; note: string }
