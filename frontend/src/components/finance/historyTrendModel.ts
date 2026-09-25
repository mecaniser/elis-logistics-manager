import type { HistoryRow } from './historyTypes'

export type TrendMetric = 'remainder' | 'fuel' | 'driver'
export type TrendRange = { start: string; end: string }
export type TrendSegment = { assetId: number; key: string; dates: string[] }

const DAY = 86_400_000
export const dateNumber = (day: string) => Date.parse(`${day}T00:00:00Z`)
export const inRange = (day: string, range: TrendRange) => day >= range.start && day <= range.end
export const metricValue = (row: HistoryRow, metric: TrendMetric): number | null => {
  if (row.status !== 'arithmetic_matched') return null
  const raw = metric === 'fuel' ? row.rolling_fuel_per_mile : metric === 'driver' ? row.driver_percent : row.remainder
  return raw == null || !Number.isFinite(Number(raw)) ? null : Number(raw)
}

// A truck's series is independent of statement dates from the other truck.
// Do not bridge more than two normal weekly settlement cycles without evidence.
export function trendSegments(rows: HistoryRow[], range: TrendRange, metric: TrendMetric): TrendSegment[] {
  const groups = new Map<number, HistoryRow[]>()
  for (const row of rows) {
    if (!inRange(row.date, range)) continue
    groups.set(row.asset_id, [...(groups.get(row.asset_id) || []), row])
  }
  const segments: TrendSegment[] = []
  for (const [assetId, assetRows] of groups) {
    let current: string[] = []
    let previous: string | null = null
    for (const row of assetRows.sort((a, b) => a.date.localeCompare(b.date))) {
      if (metricValue(row,metric)===null) {
        if (current.length) segments.push({assetId,key:`${assetId}-${current[0]}`,dates:current})
        current=[];previous=null
        continue
      }
      if (previous && dateNumber(row.date) - dateNumber(previous) > 15 * DAY) {
        segments.push({assetId, key: `${assetId}-${current[0]}`, dates: current})
        current = []
      }
      if (!current.includes(row.date)) current.push(row.date)
      previous = row.date
    }
    if (current.length) segments.push({assetId, key: `${assetId}-${current[0]}`, dates: current})
  }
  return segments
}

export function monthBuckets(rows: HistoryRow[], range: TrendRange, assetId: number) {
  const months: {month: string; matched: number; needsReview: number; missingOriginal: number}[] = []
  let cursor = range.start.slice(0, 7)
  while (cursor <= range.end.slice(0, 7)) {
    const inMonth = rows.filter(row => row.asset_id === assetId && row.date.startsWith(cursor) && inRange(row.date, range))
    months.push({month: cursor, matched: inMonth.filter(row => row.status === 'arithmetic_matched').length,
      needsReview: inMonth.filter(row => row.status === 'needs_review').length,
      missingOriginal: inMonth.filter(row => row.status === 'missing_source').length})
    const [year, month] = cursor.split('-').map(Number)
    cursor = `${year + (month === 12 ? 1 : 0)}-${String(month === 12 ? 1 : month + 1).padStart(2, '0')}`
  }
  return months
}
