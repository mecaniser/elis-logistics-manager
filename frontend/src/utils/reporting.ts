/** Settlement remaining is distinct from incurred expense and verified cash paid. */
export function reportRemaining(period: { settlement_remainder?: number } | null | undefined): number {
  return Number(period?.settlement_remainder) || 0
}
export function reportExpenseTotal(period: { expenses?: number; total_expenses?: number; repairs?: number }, includeRepairs: boolean): number {
  if (period.total_expenses !== undefined) return Number(period.total_expenses) || 0
  return (Number(period.expenses) || 0) + (includeRepairs ? Number(period.repairs) || 0 : 0)
}
/** Date-only accounting values must never move into the prior day in western timezones. */
export function formatReportDate(value: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})/.exec(value)
  if (!match) return value
  const date = new Date(`${match[1]}T00:00:00Z`)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { timeZone: 'UTC' })
}

/** Wording only: never changes settlement grouping or payment attribution.
 * Use the viewer's local calendar day. A recently completed Monday–Sunday
 * period remains pending through its usual Tuesday/Wednesday arrival window. */
export function awaitingWeeklySettlements(view: string, period: { week_start?: string | null; week_end?: string | null } | null | undefined, hasSettlements: boolean, now = new Date()): boolean {
  if (view !== 'weekly' || hasSettlements || !period?.week_start || !period.week_end) return false
  const start = new Date(`${period.week_start}T12:00:00Z`)
  const end = new Date(`${period.week_end}T12:00:00Z`)
  if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || !Number.isFinite(now.getTime())) return false
  if (start.toISOString().slice(0, 10) !== period.week_start || end.toISOString().slice(0, 10) !== period.week_end) return false
  if (start.getUTCDay() !== 1 || end.getUTCDay() !== 0 || end.getTime() - start.getTime() !== 6 * 86400000) return false
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate(), 12)
  return today > end.getTime() && today <= end.getTime() + 3 * 86400000
}

/** Activity keys and settlement pay-date keys differ. Before claiming that a
 * run is awaiting all settlements, inspect recorded service intervals as well.
 * Shared endpoints alone do not identify the same run. This is only a wording
 * guard, not an attribution or aggregation rule. */
export function hasRecordedSettlementForRun(period: { week_start?: string | null; week_end?: string | null } | null | undefined, rows: { week_key?: string; week_start?: string | null; week_end?: string | null }[]): boolean {
  if (!period?.week_start || !period.week_end) return false
  return rows.some(row => {
    if (row.week_start && row.week_end && row.week_start < period.week_end! && row.week_end > period.week_start!) return true
    // A statement in the arrival window (including backend date fallbacks) makes an
    // assertion that all statements are still pending unsafe.
    if (!row.week_key) return false
    const end = new Date(`${period.week_end}T12:00:00Z`)
    if (!Number.isFinite(end.getTime())) return false
    end.setUTCDate(end.getUTCDate() + 3)
    return row.week_key > period.week_end! && row.week_key <= end.toISOString().slice(0, 10)
  })
}
