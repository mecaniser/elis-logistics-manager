import type { TimeSeriesData, TimeSeriesPeriod } from '../services/api'
type View = 'weekly' | 'monthly' | 'yearly' | 'all_time'
type Period = { week_key?: string; week_end?: string | null; month_key?: string; year_key?: string; has_settlement_data: boolean }
export type ReportSelection = { scope: string; key: string } | null

/** Prefer recorded results (including zero/negative), never the age of a repair.
 * Manual choices apply only to the same tenant, equipment filter and time view. */
export function resolveReportPeriod(view: View, periods: Period[], manual: ReportSelection, scope: string): string {
  if (view === 'all_time') return ''
  const key = view === 'weekly' ? 'week_key' : view === 'monthly' ? 'month_key' : 'year_key'
  const available = periods.filter(period => !!period[key])
  if (manual?.scope === scope && available.some(period => period[key] === manual.key)) return manual.key
  const recorded = available.filter(period => period.has_settlement_data)
  const candidates = recorded.length ? recorded : available
  const ordered = [...candidates].sort((a, b) => {
    const order = (period: Period) => view === 'weekly' ? period.week_end || period.week_key || '' : period[key] || ''
    return order(a).localeCompare(order(b)) || String(a[key]).localeCompare(String(b[key]))
  })
  return ordered[ordered.length - 1]?.[key] || ''
}

/** Monthly/yearly analytics also contain invoice-only rows. Use recorded
 * settlement counts rather than revenue (zero is a valid settlement result). */
export function recordedReportPeriods(view: View, series: TimeSeriesData | null): TimeSeriesPeriod[] {
  if (!series || view === 'all_time') return []
  if (view === 'weekly') return series.by_week
  const months = series.by_month.filter(period => (period.settlement_count ?? 0) > 0)
  if (view === 'monthly') return months
  const years = new Set(months.map(period => period.month_key?.slice(0, 4)))
  return series.by_year.filter(period => years.has(period.year_key))
}
