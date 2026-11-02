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
