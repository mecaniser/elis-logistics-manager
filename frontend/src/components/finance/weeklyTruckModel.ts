import type { HistoryRow } from './historyTypes'
import type { TrendRange } from './historyTrendModel'
const dateNumber=(date:string)=>Date.parse(`${date}T00:00:00Z`)
const DAY = 86400000
const iso = (n: number) => new Date(n).toISOString().slice(0,10)
export type Downtime = {start:string; end:string; description:string}
export function truckDowntime(rows: HistoryRow[], tenant: number, assetId: number): Downtime[] {
  if (tenant !== 1) return []
  const own = rows.filter(r=>r.asset_id===assetId).sort((a,b)=>a.date.localeCompare(b.date))
  const vin = own[0]?.vin
  if (vin==='4V4WC9EG9LN250022') return [{start:'2026-05-10',end:'2026-06-22',description:'Owner-reported downtime: waiting for a driver · May 10–June 22, 2026'}]
  if (vin!=='4V4WC9EG2LN250024') return []
  const first = own.find(r=>r.date>='2026-03-01' && /77\s*cargo/i.test(r.provider))
  const previous = first ? own.filter(r=>r.date<first.date && /277/.test(r.provider)) : []
  const last = previous[previous.length-1]
  return first && last && last.date>='2026-03-01' ? [{start:iso(dateNumber(last.date)+DAY),end:iso(dateNumber(first.date)-DAY),description:`Carrier transition, maintenance and waiting for a driver. Estimated between statements: last 277 Logistics ${last.date}; first 77 Cargo ${first.date}. These are not confirmed service dates.`}] : []
}
export function weeklyTruckPoints(rows: HistoryRow[], assetId: number, range: TrendRange, downtime: Downtime[]) {
  const begin=dateNumber(range.start), end=dateNumber(range.end)
  const monday=begin-((new Date(begin).getUTCDay()+6)%7)*DAY
  const points: {date:string;through:string;value:number|null;average:number|null;records:HistoryRow[];status:string;offRoad:boolean}[]=[]
  for(let day=monday;day<=end;day+=7*DAY) {
    const start=iso(Math.max(day,begin)), through=iso(Math.min(day+6*DAY,end))
    const records=rows.filter(r=>r.asset_id===assetId && r.date>=start && r.date<=through)
    const complete=records.length>0 && records.every(r=>r.status==='arithmetic_matched' && r.remainder!==null)
    const value=complete ? records.reduce((sum,r)=>sum+Math.round(Number(r.remainder)*100),0)/100 : null
    const offRoad=downtime.some(d=>start>=d.start && through<=d.end)
    points.push({date:start,through,value,average:null as number|null,records,status:records.some(r=>r.status!=='arithmetic_matched')?'Review evidence':offRoad?'Out of service (owner reported)':records.length?'Verified statements':'No statement recorded',offRoad})
  }
  return points.map((p,index)=>{
    const window=points.slice(Math.max(0,index-3),index+1)
    return {...p,average:window.length===4 && window.every(w=>w.value!==null && dateNumber(w.through)-dateNumber(w.date)===6*DAY) ? window.reduce((sum,w)=>sum+w.value!,0)/4 : null}
  })
}
