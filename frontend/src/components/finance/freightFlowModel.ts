export interface FuelSource {
  id:string; legacy_id:number|null; asset_id:number; name:string; date:string; amount:string; basis:string;
  rows:{date:string;location:string;amount:string;gallons:string|null;product:string}[];
}
export interface FreightBreakdown {
  fuel_sources?: FuelSource[]
  freight_gross: string
  settlement_remainder: string
  rows: {category: string; amount: string}[]
}
export interface FlowRow { key: string; label: string; cents: number; unitPrice?: string|null }
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
export function pricePerGallon(amount:string, gallons:string|null):string|null {
  const charge=cents(amount), volume=Number(gallons)
  return Number.isSafeInteger(charge)&&Number.isFinite(volume)&&volume>0?(charge/100/volume).toFixed(3):null
}
export function fuelBranches(total: string, sources: FuelSource[]): FlowRow[] {
  const locations = new Map<string, number>()
  const volumes = new Map<string, {gallons:number;complete:boolean}>()
  let detailed = 0
  for (const source of sources) {
    for (const row of source.rows) {
      const value = cents(row.amount)
      if (!Number.isSafeInteger(value)) continue
      const location = row.location.replace(/^.*?\[Drv\]\s*/, '').trim() || 'Location not recorded'
      locations.set(location, (locations.get(location) || 0) + value)
      const volume = volumes.get(location) || {gallons:0,complete:true}
      const gallons = Number(row.gallons)
      volume.complete = volume.complete && row.gallons!==null && Number.isFinite(gallons) && gallons>0
      volume.gallons += Number.isFinite(gallons)?gallons:0
      volumes.set(location,volume)
      detailed += value
    }
  }
  const result:FlowRow[] = [...locations].map(([location, value], i) => {
    const volume=volumes.get(location)!
    return {key:`fuel-location-${i}`,label:`Fuel · ${location}`,cents:value,unitPrice:volume.complete&&volume.gallons>0?(value/100/volume.gallons).toFixed(3):null}
  })
  const difference = cents(total) - detailed
  if (difference) result.push({key:'fuel-unresolved',label:'Fuel · detail unavailable / difference',cents:difference})
  return result
}
export function freightFlowModel(data: FreightBreakdown, expandOther = false, fuelDetails?: FlowRow[]) {
  const gross = cents(data.freight_gross)
  const remainder = cents(data.settlement_remainder)
  const amounts = new Map<string, number>()
  for (const row of data.rows) amounts.set(row.category, (amounts.get(row.category) ?? 0) + cents(row.amount))
  const details = [...amounts].map(([key, value]) => ({key, label: flowLabel(key), cents: value}))
  const primary = ['carrier', 'driver_pay', 'fuel']
  const others = details.filter(row => !primary.includes(row.key))
  const otherTotal = others.reduce((sum, row) => sum + row.cents, 0)
  const deductions: FlowRow[] = primary.filter(key => amounts.has(key)).flatMap(key => key==='fuel'&&fuelDetails?fuelDetails:[{key, label: flowLabel(key), cents: amounts.get(key)!}])
  if (expandOther) deductions.push(...others)
  else if (others.length) deductions.push({key: 'other', label: others.some(row => row.cents < 0) ? 'Other charges / credits' : 'Other charges', cents: otherTotal})
  const valid = [gross, remainder, ...details.map(row => row.cents), otherTotal, ...deductions.map(row=>row.cents)].every(Number.isSafeInteger)
  const total = details.reduce((sum, row) => sum + row.cents, 0) + remainder
  const reconciled = valid && Number.isSafeInteger(total) && total === gross && deductions.reduce((sum,row)=>sum+row.cents,0)+remainder===gross
  const canFlow = reconciled && gross > 0 && remainder >= 0 && details.every(row => row.cents >= 0) && deductions.every(row => row.cents >= 0)
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
