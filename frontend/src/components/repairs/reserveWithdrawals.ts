import type { RepairReserveWithdrawal, TimeSeriesPeriod } from '../../services/api'

type View = 'weekly' | 'monthly' | 'yearly' | 'all_time'
type Period = Pick<TimeSeriesPeriod, 'week_key' | 'week_start' | 'week_end' | 'month_key' | 'year_key'>

function validDay(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const day = new Date(`${value}T12:00:00Z`)
  return Number.isFinite(day.getTime()) && day.toISOString().slice(0, 10) === value
}

/** Sum dated ledger movements, never service-date invoice costs. Missing data
 * stays unavailable. A weekly key without bounds is the backend's one-day
 * settlement period; it is not evidence for an invented seven-day interval. */
function sumDatedAmounts(entries: { truck_id: number; date: string; amount: number }[] | undefined, view: View, period: Period | null, truckId?: number | null): number | null {
  if (!entries) return null
  let matches: (day: string) => boolean
  if (view === 'all_time') matches = () => true
  else if (view === 'monthly') {
    const key = period?.month_key
    if (!key || !/^\d{4}-(0[1-9]|1[0-2])$/.test(key)) return null
    matches = day => day.slice(0, 7) === key
  } else if (view === 'yearly') {
    const key = period?.year_key
    if (!key || !/^\d{4}$/.test(key)) return null
    matches = day => day.slice(0, 4) === key
  } else {
    const start = period?.week_start || period?.week_key
    const end = period?.week_end || period?.week_key
    if (!start || !end || !validDay(start) || !validDay(end) || start > end) return null
    matches = day => day >= start && day <= end
  }
  let cents = 0
  for (const entry of entries) {
    if (truckId != null && entry.truck_id !== truckId) continue
    if (!validDay(entry.date) || !Number.isFinite(entry.amount)) return null
    if (!matches(entry.date)) continue
    const value = entry.amount * 100
    const rounded = Math.round(value)
    if (!Number.isSafeInteger(rounded) || Math.abs(value - rounded) > 0.000001) return null
    cents += rounded
    if (!Number.isSafeInteger(cents)) return null
  }
  return cents / 100
}

export function reserveWithdrawalsForPeriod(entries: RepairReserveWithdrawal[] | undefined, view: View, period: Period | null, truckId?: number | null): number | null {
  return sumDatedAmounts(entries?.map(entry => ({ truck_id: entry.truck_id, date: entry.payment_date, amount: entry.amount })), view, period, truckId)
}

export interface ExpenseActivityPeriod extends Period {
  week_label?: string
  month_label?: string
  year_label?: string
  has_settlement_data: boolean
}

/** Add dated repair/payment activity to the selector without inventing any
 * settlement revenue, profit or mileage values for those supplemental periods. */
export function expenseActivityPeriods(view: View, settlementPeriods: Period[] | undefined, withdrawals: RepairReserveWithdrawal[] | undefined, repairs: { repair_date?: string | null }[] | undefined): ExpenseActivityPeriod[] {
  if (view === 'all_time') return []
  const keyName = view === 'weekly' ? 'week_key' : view === 'monthly' ? 'month_key' : 'year_key'
  const result: ExpenseActivityPeriod[] = (settlementPeriods || []).map(period => ({ ...period, has_settlement_data: true }))
  const keys = new Set(result.map(period => period[keyName]))
  const days = [...(withdrawals || []).map(entry => entry.payment_date), ...(repairs || []).map(repair => repair.repair_date)].filter((day): day is string => !!day && validDay(day))
  for (const day of days) {
    if (view === 'weekly') {
      if (result.some(period => {
        const start = period.week_start || period.week_key
        const end = period.week_end || period.week_key
        return start && end && day >= start && day <= end
      })) continue
      const value = new Date(`${day}T12:00:00Z`)
      value.setUTCDate(value.getUTCDate() - (value.getUTCDay() + 6) % 7)
      const start = value.toISOString().slice(0, 10)
      value.setUTCDate(value.getUTCDate() + 6)
      const end = value.toISOString().slice(0, 10)
      const key = `activity-week:${start}`
      if (!keys.has(key)) { result.push({ week_key: key, week_start: start, week_end: end, week_label: `${start} – ${end} · no settlement`, has_settlement_data: false }); keys.add(key) }
    } else if (view === 'monthly') {
      const key = day.slice(0, 7)
      if (!keys.has(key)) {
        const label = new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${key}-01T12:00:00Z`))
        result.push({ month_key: key, month_label: `${label} · no settlement`, has_settlement_data: false }); keys.add(key)
      }
    } else {
      const key = day.slice(0, 4)
      if (!keys.has(key)) { result.push({ year_key: key, year_label: `${key} · no settlement`, has_settlement_data: false }); keys.add(key) }
    }
  }
  return result.sort((a, b) => String(a.week_end || a.week_key || a.month_key || a.year_key).localeCompare(String(b.week_end || b.week_key || b.month_key || b.year_key)))
}

export function serviceRepairCostsForPeriod(repairs: { truck_id: number; cost: number; repair_date?: string | null }[] | undefined, view: View, period: Period | null, truckId?: number | null): number | null {
  if (!repairs) return null
  const dated = repairs.filter(repair => !!repair.repair_date).map(repair => ({ truck_id: repair.truck_id, date: repair.repair_date!, amount: repair.cost }))
  return sumDatedAmounts(dated, view, period, truckId)
}
