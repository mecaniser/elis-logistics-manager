import InvestmentDeductions from './InvestmentDeductions'
import OwnerEarningsBridge from './OwnerEarningsBridge'
import {ownerEarningsModel} from './ownerEarningsModel'
import type {EarningsPlan} from '../../services/finance'
import FuelMileageReport from './FuelMileageReport'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { type HistoryReport } from './historyTypes'
import { dollars } from '../../services/finance'
import { freightFlowModel, fuelBranches, pricePerGallon, type FlowRow, type FreightBreakdown } from './freightFlowModel'
import './FreightFlow.css'

const amount = (cents: number) => dollars(cents / 100)
export default function FreightFlow({data,history,historyError,plan}: {plan?:EarningsPlan;data: FreightBreakdown;history?:HistoryReport|null;historyError?:string}) {
  const [view, setView] = useState<'flow' | 'waterfall'>('flow')
  const [expandedOther,setExpandedOther] = useState(false)
  const [fuelOpen,setFuelOpen] = useState(false)
  const [mileageOpen,setMileageOpen] = useState(false)
  const [purchaseOpen,setPurchaseOpen] = useState(false)
  const fuelSources = (data.fuel_sources||[]).map(source=>({...source,rows:source.basis==='posted'?source.rows:(history?.rows.find(row=>row.id===source.legacy_id)?.fuel_rows||[])}))
  const fuelTotal = (data.rows.filter(row=>row.category==='fuel').reduce((sum,row)=>sum+Math.round(Number(row.amount)*100),0)/100).toFixed(2)
  const model = freightFlowModel(data,expandedOther,fuelOpen?fuelBranches(fuelTotal,fuelSources):undefined)
  const color = (key:string) => key.startsWith('fuel-')?'fuel':['carrier','driver_pay','fuel','remainder'].includes(key)?key:'other'
  const label = (key:string,text:string) => key==='other'||key==='fuel'?<button type="button" className="freight-drill-button" aria-expanded={key==='other'?expandedOther:fuelOpen} onClick={()=>{if(key==='other')setExpandedOther(!expandedOther);else{setFuelOpen(!fuelOpen);setPurchaseOpen(false);setMileageOpen(false)}}}>{text}<span aria-hidden="true">{(key==='fuel'?fuelOpen:expandedOther)?'−':'+'}</span></button>:<span>{text}</span>
  const selected = model.canFlow ? view : 'waterfall'
  const share = (value: number) => Number.isSafeInteger(value) && Number.isSafeInteger(model.gross) && model.gross > 0 ? `${(value / model.gross * 100).toFixed(1)}% of freight` : 'Share unavailable'
  const metric = (row:FlowRow) => row.key.startsWith('fuel-')?(row.unitPrice?`$${row.unitPrice}/gal`:'Price/gal unavailable'):share(row.cents)
  const scale = model.canFlow ? 250 / model.gross : 0
  const otherKeys = new Set(model.others.map(row=>row.key))
  const headers: {key:string;label:string;y:number}[] = []
  const seenGroups = new Set<string>()
  const groupFor = (key:string) => fuelOpen&&key.startsWith('fuel-')?'fuel':expandedOther&&otherKeys.has(key)?'other':null
  let source = 0
  let target = 0
  const ribbons = model.flows.map(row => {
    const group = groupFor(row.key)
    if(group&&!seenGroups.has(group)){
      headers.push({key:group,label:group==='fuel'?'Fuel purchases':'Other charges',y:target+22})
      seenGroups.add(group);target+=54
    }
    const height = row.cents * scale
    // Keep enough space for two-line labels even for a zero-adjacent deduction.
    const slot = Math.max(height, 50)
    const destination = target + (slot - height) / 2
    const ribbon = {...row, height, source, destination, labelY: target + slot / 2}
    source += height
    target += slot + 20
    return ribbon
  })
  const chartHeight = Math.max(270, target - 20)
  const owner=plan?ownerEarningsModel(plan):null
  const linked=Boolean(owner?.reconciled&&owner.start===model.remainder&&owner.end>=0&&owner.rows.every(row=>row.amount<=0)&&model.canFlow)
  const continuation=linked&&owner?[...owner.rows.filter(row=>row.amount<0).map((row,index)=>({key:`owner-${index}`,label:row.label,cents:-row.amount,tone:row.tone})),{key:'owner-final',label:'Estimated left for you',cents:owner.end,tone:'final'}]:[]
  let continuationSource=0
  let continuationTarget=chartHeight+60
  const remainderRibbon=ribbons.find(row=>row.key==='remainder')
  const continued=continuation.map(row=>{
    const height=row.cents*scale
    const slot=Math.max(height,50)
    const destination=continuationTarget+(slot-height)/2
    const result={...row,height,source:(remainderRibbon?.destination||0)+(remainderRibbon?.height||0)-continuationSource-height,destination,labelY:continuationTarget+slot/2}
    continuationSource+=height;continuationTarget+=slot+20
    return result
  })
  const fullHeight=continued.length?continuationTarget-20:chartHeight
  const sourceTop = (chartHeight - 250) / 2
  const span = model.max - model.min || 1
  const position = (value: number) => (value - model.min) / span * 100
  const bar = (start: number, end: number) => ({left: `${position(Math.min(start, end))}%`, width: `${Math.abs(end - start) / span * 100}%`})

  return <div className="freight-flow">
    {model.reconciled ? <>
      <div className="freight-flow-toolbar"><p className="finance-help">Statement allocation · selected reporting period</p><div className="freight-flow-switch" role="group" aria-label="Revenue chart view">
        <button type="button" className="finance-secondary" aria-pressed={selected === 'flow'} disabled={!model.canFlow} onClick={() => setView('flow')}>Money flow</button>
        <button type="button" className="finance-secondary" aria-pressed={selected === 'waterfall'} onClick={() => setView('waterfall')}>Waterfall</button>
      </div></div>


      {!model.canFlow && <p className="finance-help">Credits, a negative remainder or nonpositive freight use the signed waterfall so amounts retain their direction.</p>}
      {selected === 'flow' ? <>
        <div className="freight-flow-origin"><span>Freight billed</span><strong className="freight-amount-carrier">{amount(model.gross)}</strong></div>
        <div className="freight-flow-diagram" style={{height: fullHeight}}>
          <svg viewBox={`0 0 100 ${fullHeight}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
            {ribbons.map(row => {const y = row.source + sourceTop;return <g key={row.key} className={`freight-color-${color(row.key)}`}><path opacity=".25" d={`M 2 ${y} C 52 ${y} 48 ${row.destination} 98 ${row.destination} L 98 ${row.destination + row.height} C 48 ${row.destination + row.height} 52 ${y + row.height} 2 ${y + row.height} Z`} /><rect x="98" y={row.destination} width="2" height={row.height} /></g>})}
            {continued.map(row=><g key={row.key} className={`owner-flow-${row.tone}`}><path opacity=".25" d={`M 98 ${row.source} C ${(row.source-(remainderRibbon?.destination||0))/250*80} ${row.source} ${(row.source-(remainderRibbon?.destination||0))/250*80} ${row.destination+row.height} 98 ${row.destination+row.height} L 98 ${row.destination} C ${(row.source+row.height-(remainderRibbon?.destination||0))/250*80} ${row.destination} ${(row.source+row.height-(remainderRibbon?.destination||0))/250*80} ${row.source+row.height} 98 ${row.source+row.height} Z`}/><rect x="98" y={row.destination} width="2" height={row.height}/></g>)}
            <rect className="freight-color-carrier" x="0" y={sourceTop} width="2" height="250" />
          </svg>
          <ul aria-label="Freight allocation amounts and metrics">{headers.map(header=><li key={header.key} className="freight-flow-label freight-group-label" style={{top:header.y}}>{label(header.key,header.label)}{header.key==='fuel'&&<div className="fuel-group-actions"><button type="button" className="freight-drill-button" aria-expanded={mileageOpen} onClick={()=>setMileageOpen(!mileageOpen)}>Miles vs fuel</button><button type="button" className="freight-drill-button" aria-expanded={purchaseOpen} onClick={()=>setPurchaseOpen(!purchaseOpen)}>Purchase details</button></div>}</li>)}{ribbons.map(row => <li key={row.key} className="freight-flow-label" style={{top: row.labelY}}>{label(row.key,row.label)}<div><strong className={`freight-amount-${color(row.key)}`}>{amount(row.cents)}</strong><small>{metric(row)}</small></div></li>)}{continued.map(row=><li key={row.key} className={`freight-flow-label owner-flow-label-${row.tone}`} style={{top:row.labelY}}>{plan&&(row.label==='Equipment capital recovery'||row.label==='Additional planned loan payments')?<InvestmentDeductions plan={plan} kind={row.label==='Equipment capital recovery'?'capital':'loan'} label={row.label}/>:<span>{row.label}</span>}<div><strong>{amount(row.cents)}</strong>{row.tone==='final'&&<small>Estimate · before unverified payments</small>}</div></li>)}</ul>
        </div>
      </> : <div className="freight-waterfall" aria-label="Freight less deductions, with credits added">
        <div className="freight-waterfall-row"><div className="freight-waterfall-label"><span>Freight billed</span><strong className="freight-amount-carrier">{amount(model.gross)}</strong></div><div className="freight-waterfall-track" aria-hidden="true"><i className="freight-color-carrier" style={bar(0, model.gross)} /></div></div>
        {model.steps.map((row,index) => <div className="freight-waterfall-row" key={row.key}>
          {groupFor(row.key)&& (index===0||groupFor(model.steps[index-1].key)!==groupFor(row.key))&&<div className="freight-group-label">{label(groupFor(row.key)!,groupFor(row.key)==='fuel'?'Fuel purchases':'Other charges')}{groupFor(row.key)==='fuel'&&<div className="fuel-group-actions"><button type="button" className="freight-drill-button" aria-expanded={mileageOpen} onClick={()=>setMileageOpen(!mileageOpen)}>Miles vs fuel</button><button type="button" className="freight-drill-button" aria-expanded={purchaseOpen} onClick={()=>setPurchaseOpen(!purchaseOpen)}>Purchase details</button></div>}</div>}<div className="freight-waterfall-label">{label(row.key,row.label)}<div><strong className={`freight-amount-${color(row.key)}`}>{row.cents > 0 ? '−' : row.cents < 0 ? '+' : ''}{amount(Math.abs(row.cents))}</strong><small>{metric(row)}</small></div></div><div className="freight-waterfall-track" aria-hidden="true"><i className={`freight-color-${color(row.key)}`} style={bar(row.before, row.after)} /><span className="freight-waterfall-zero" style={{left: `${position(0)}%`}} /></div><div className="freight-waterfall-after">{amount(row.after)} remaining</div></div>)}
        <div className="freight-waterfall-row"><div className="freight-waterfall-label"><span>Statement remainder</span><div><strong className="freight-amount-remainder">{amount(model.remainder)}</strong><small>{share(model.remainder)}</small></div></div><div className="freight-waterfall-track" aria-hidden="true"><i className="freight-color-remainder" style={bar(0, model.remainder)} /><span className="freight-waterfall-zero" style={{left: `${position(0)}%`}} /></div></div>
      </div>}
    </> : <p className="finance-error" role="status">The reported allocation does not reconcile to freight. Review the exact statement figures below before interpreting a flow.</p>}
    {plan&&selected==='flow'&&linked&&<div className="owner-flow-footnote"><span>Loan principal: not verified · Capital targets may be incomplete.</span><Link to="/finance/money">Trailer allocation & payment details</Link></div>}
    {plan&&(!linked||selected==='waterfall')&&<OwnerEarningsBridge plan={plan}/>}
    {mileageOpen&&<FuelMileageReport sources={data.fuel_sources||[]} history={history}/>}
    {purchaseOpen&&<section className="freight-fuel-detail" aria-label="Fuel purchase details"><div className="finance-section-heading"><h3>Fuel purchases by settlement</h3><button type="button" className="finance-secondary" onClick={()=>setPurchaseOpen(false)}>Close</button></div>
      {!(data.fuel_sources?.length)&&<p>No purchase detail is available for these statements.</p>}
      {data.fuel_sources?.filter(source=>Number(source.amount)!==0||source.rows.length).map(source=>{
        const reviewed = history?.rows.find(row=>row.id===source.legacy_id)
        const purchases = source.basis==='posted'?source.rows:(reviewed?.fuel_rows||[])
        const total = purchases.reduce((sum,p)=>sum+Math.round(Number(p.amount)*100),0)
        const difference = Math.round(Number(source.amount)*100)-total
        return <article key={source.id}><div className="finance-section-heading"><strong>{reviewed?.vin?`VIN …${reviewed.vin.slice(-6)}`:source.name} · {source.date}</strong><strong className="freight-amount-fuel">{dollars(source.amount)}</strong></div>
          {purchases.length?<><div className="freight-purchases">{purchases.map((p,i)=><div key={i}><span>{p.date}</span><span>{p.location||'Location not recorded'}<small>{p.product==='unknown'?'Product not classified':p.product}{p.gallons!==null&&p.gallons!==undefined?` · ${p.gallons} gal`:''} · {pricePerGallon(p.amount,p.gallons)!==null?`$${pricePerGallon(p.amount,p.gallons)}/gal`:'Price/gal unavailable'}</small></span><strong className="freight-amount-fuel">{dollars(p.amount)}</strong></div>)}</div>{difference!==0&&<p className="finance-error">Purchase rows total {dollars(total/100)}; difference from statement fuel charge: {dollars(difference/100)}.</p>}</>:<p className="finance-help">{source.basis==='saved'&&!history&&!historyError?'Loading purchase records…':'Purchase details unavailable. The statement fuel total is retained.'}</p>}
          <Link to={`/settlements/reconciliation?asset=${source.asset_id}#review-records`}>Review settlement sources</Link>
        </article>
      })}
    </section>}
    {!model.reconciled&&<section className="freight-flow-details" aria-label="Reported statement figures">
      <h3>Reported statement figures</h3>
      <dl className="freight-flow-values"><div><dt>Freight billed</dt><dd>{dollars(data.freight_gross)}</dd></div>{data.rows.map((row, i) => <div key={`${row.category}-${i}`}><dt>{model.details.find(d => d.key === row.category)?.label}</dt><dd>{dollars(row.amount)}<small>{share(Math.round(Number(row.amount) * 100))}</small></dd></div>)}<div><dt>Statement remainder</dt><dd>{dollars(data.settlement_remainder)}</dd></div></dl>
    </section>}
    <p className="finance-help">Statement remainder is before outside bills and cash protection. Carrier and driver amounts are settlement shares, not their personal take-home. Internal trailer allocations stay in your business; reserves are not operating expenses.</p>
  </div>
}
