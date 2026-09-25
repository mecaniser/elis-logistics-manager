export interface FreightBreakdown {
  freight_gross: string
  settlement_remainder: string
  rows: {category: string; amount: string}[]
}
export interface FlowRow { key: string; label: string; cents: number }
const labels: Record<string, string> = {
  carrier: 'Carrier retention', driver_pay: 'Driver pay', fuel: 'Fuel purchases',
  insurance: 'Insurance', tolls: 'Tolls', support: 'Support', fleet_manager_support: 'Support',
}
export const flowLabel = (key: string) => labels[key] || key.replace(/_/g, ' ')
function cents(value: string): number {
  if (!/^-?\d+\.\d{2}$/.test(value)) return NaN
  const result = Number(value.replace('.', ''))
  return Number.isSafeInteger(result) ? result : NaN
}
export function freightFlowModel(data: FreightBreakdown) {
  const gross = cents(data.freight_gross)
  const remainder = cents(data.settlement_remainder)
  const amounts = new Map<string, number>()
  for (const row of data.rows) amounts.set(row.category, (amounts.get(row.category) ?? 0) + cents(row.amount))
  const details = [...amounts].map(([key, value]) => ({key, label: flowLabel(key), cents: value}))
  const primary = ['carrier', 'driver_pay', 'fuel']
  const others = details.filter(row => !primary.includes(row.key))
  const otherTotal = others.reduce((sum, row) => sum + row.cents, 0)
  const deductions: FlowRow[] = primary.filter(key => amounts.has(key)).map(key => ({key, label: flowLabel(key), cents: amounts.get(key)!}))
  if (others.length) deductions.push({key: 'other', label: others.some(row => row.cents < 0) ? 'Other charges / credits' : 'Other charges', cents: otherTotal})
  const valid = [gross, remainder, ...details.map(row => row.cents), otherTotal].every(Number.isSafeInteger)
  const total = details.reduce((sum, row) => sum + row.cents, 0) + remainder
  const reconciled = valid && Number.isSafeInteger(total) && total === gross
  const canFlow = reconciled && gross > 0 && remainder >= 0 && details.every(row => row.cents >= 0)
  const flows = [...deductions, {key: 'remainder', label: 'Statement remainder', cents: remainder}].filter(row => row.cents > 0 || row.key === 'remainder')
  let running = gross
  const steps = deductions.map(row => {
    const before = running
    running -= row.cents
    return {...row, before, after: running}
  })
  const domain = [0, gross, remainder, ...steps.flatMap(row => [row.before, row.after])]
  return {gross, remainder, details, others, flows, steps, reconciled, canFlow, min: Math.min(...domain), max: Math.max(...domain)}
}
