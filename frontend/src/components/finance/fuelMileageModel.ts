import type { FuelSource } from './freightFlowModel'
import type { HistoryReport } from './historyTypes'

type Evidence = {miles:string|null|undefined; basis:string|null|undefined; rows:FuelSource['rows']; amount:string; reviewed:boolean}
export function summarizeFuel(items:Evidence[]) {
  const issues = new Set<string>()
  let miles=0, diesel=0, purchased=0, unknown=0
  let distanceKnown=true, volumeKnown=true
  for(const item of items){
    const distance=Number(item.miles)
    if(item.miles==null||!Number.isFinite(distance)||distance<=0||!['reported','independent'].includes(item.basis||'')){
      distanceKnown=false;issues.add('Comparable mileage is missing or estimated.')
    }else miles+=distance
    if(!item.reviewed) issues.add('Statement source needs reconciliation.')
    if(!item.rows.length){volumeKnown=false;issues.add('Purchase rows are missing.')}
    let cents=0
    for(const row of item.rows){
      const amount=Number(row.amount)
      if(!Number.isFinite(amount))issues.add('Purchase amount is invalid.')
      else { cents+=Math.round(amount*100); if(amount<=0)issues.add('Credits or nonpositive purchases need review.') }
      const gallons=Number(row.gallons)
      if(row.gallons==null||!Number.isFinite(gallons)||gallons<=0){volumeKnown=false;issues.add('Purchase gallons are incomplete.');continue}
      purchased+=gallons
      if(row.product==='diesel')diesel+=gallons
      else if(row.product!=='def'){unknown++;issues.add('Fuel products need classification; DEF must be excluded.')}
    }
    if(cents!==Math.round(Number(item.amount)*100))issues.add('Purchase rows do not match the fuel charge.')
  }
  if(!items.length)issues.add('No statements available.')
  if(!diesel)issues.add('No confirmed diesel volume available.')
  const mpg=issues.size===0&&diesel>0?miles/diesel:null
  return {miles:distanceKnown&&items.length?miles:null,purchased:volumeKnown&&items.length?purchased:null,diesel:volumeKnown&&!unknown?diesel:null,unknown,mpg,
    expected:distanceKnown&&items.length?[miles/7,miles/6]:null,
    status:mpg===null?'Insufficient evidence':mpg<6?'Below reference':mpg>7?'Above reference':'Within reference',issues:[...issues]}
}
export function fuelMileageReport(sources:FuelSource[],history:HistoryReport|null|undefined){
  const selected=[...new Set(sources.map(source=>source.asset_id))].map(assetId=>{
    const group=sources.filter(source=>source.asset_id===assetId)
    const first=group[0]
    const identity=history?.rows.find(row=>row.asset_id===assetId&&row.vin)
    const dates=group.map(source=>source.date).sort()
    return {id:String(assetId),assetId,name:identity?.vin?`VIN …${identity.vin.slice(-6)}`:first.name,
      date:dates[0]===dates[dates.length-1]?dates[0]:`${dates[0]} – ${dates[dates.length-1]}`,
      ...summarizeFuel(group.map(source=>{
        const row=history?.rows.find(r=>r.id===source.legacy_id)
        return {miles:source.basis==='posted'?source.miles:row?.miles,basis:source.basis==='posted'?source.mileage_basis:row?.mileage_basis,
          rows:source.basis==='posted'?source.rows:row?.fuel_rows||[],amount:source.amount,reviewed:source.basis==='posted'||row?.status==='arithmetic_matched'}
      }))}
  })
  const dates=sources.map(s=>s.date).sort()
  const end=dates[dates.length-1]
  const start=end?new Date(Date.parse(`${end}T00:00:00Z`)-27*86400000).toISOString().slice(0,10):null
  const rolling=[...new Set(sources.map(s=>s.asset_id))].map(assetId=>{
    const rows=history?.rows.filter(r=>r.asset_id===assetId&&start&&r.date>=start&&end&&r.date<=end)||[]
    return {assetId,name:selected.find(s=>s.assetId===assetId)?.name||String(assetId),count:rows.length,
      ...summarizeFuel(rows.map(r=>({miles:r.miles,basis:r.mileage_basis,rows:r.fuel_rows,amount:r.fuel||'0',reviewed:r.status==='arithmetic_matched'})))}
  })
  return {selected,rolling,start,end}
}
