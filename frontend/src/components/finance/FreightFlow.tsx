import { useState } from 'react'
import { Link } from 'react-router-dom'
import { type HistoryReport } from './historyTypes'
import { dollars } from '../../services/finance'
import { freightFlowModel, type FreightBreakdown } from './freightFlowModel'
import './FreightFlow.css'

const amount = (cents: number) => dollars(cents / 100)
export default function FreightFlow({data,history,historyError}: {data: FreightBreakdown;history?:HistoryReport|null;historyError?:string}) {
  const [view, setView] = useState<'flow' | 'waterfall'>('flow')
  const [expandedOther,setExpandedOther] = useState(false)
  const [fuelOpen,setFuelOpen] = useState(false)
  const model = freightFlowModel(data,expandedOther)
  const color = (key:string) => ['carrier','driver_pay','fuel','remainder'].includes(key)?key:'other'
  const label = (key:string,text:string) => key==='other'||key==='fuel'?<button type="button" className="freight-drill-button" aria-expanded={key==='other'?expandedOther:fuelOpen} onClick={()=>key==='other'?setExpandedOther(!expandedOther):setFuelOpen(!fuelOpen)}>{text}<span aria-hidden="true">{key==='fuel'&&fuelOpen?'−':'+'}</span></button>:<span>{text}</span>
  const selected = model.canFlow ? view : 'waterfall'
  const share = (value: number) => Number.isSafeInteger(value) && Number.isSafeInteger(model.gross) && model.gross > 0 ? `${(value / model.gross * 100).toFixed(1)}% of freight` : 'Share unavailable'
  const scale = model.canFlow ? 250 / model.gross : 0
  let source = 0
  let target = 0
  const ribbons = model.flows.map(row => {
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
      {expandedOther&&<button type="button" className="finance-secondary" onClick={()=>setExpandedOther(false)}>Collapse other charges</button>}
      {!model.canFlow && <p className="finance-help">Credits, a negative remainder or nonpositive freight use the signed waterfall so amounts retain their direction.</p>}
      {selected === 'flow' ? <>
        <div className="freight-flow-origin"><span>Freight billed</span><strong>{amount(model.gross)}</strong></div>
        <div className="freight-flow-diagram" style={{height: chartHeight}}>
          <svg viewBox={`0 0 100 ${chartHeight}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
            {ribbons.map(row => {const y = row.source + sourceTop;return <g key={row.key} className={`freight-color-${color(row.key)}`}><path opacity=".25" d={`M 2 ${y} C 52 ${y} 48 ${row.destination} 98 ${row.destination} L 98 ${row.destination + row.height} C 48 ${row.destination + row.height} 52 ${y + row.height} 2 ${y + row.height} Z`} /><rect x="98" y={row.destination} width="2" height={row.height} /></g>})}
            <rect className="freight-color-carrier" x="0" y={sourceTop} width="2" height="250" />
          </svg>
          <ul aria-label="Freight allocation amounts and percentages">{ribbons.map(row => <li key={row.key} className="freight-flow-label" style={{top: row.labelY}}>{label(row.key,row.label)}<div><strong>{amount(row.cents)}</strong><small>{share(row.cents)}</small></div></li>)}</ul>
        </div>
      </> : <div className="freight-waterfall" aria-label="Freight less deductions, with credits added">
        <div className="freight-waterfall-row"><div className="freight-waterfall-label"><span>Freight billed</span><strong>{amount(model.gross)}</strong></div><div className="freight-waterfall-track" aria-hidden="true"><i className="freight-color-carrier" style={bar(0, model.gross)} /></div></div>
        {model.steps.map(row => <div className="freight-waterfall-row" key={row.key}><div className="freight-waterfall-label">{label(row.key,row.label)}<div><strong>{row.cents > 0 ? '−' : row.cents < 0 ? '+' : ''}{amount(Math.abs(row.cents))}</strong><small>{share(row.cents)}</small></div></div><div className="freight-waterfall-track" aria-hidden="true"><i className={`freight-color-${color(row.key)}`} style={bar(row.before, row.after)} /><span className="freight-waterfall-zero" style={{left: `${position(0)}%`}} /></div><div className="freight-waterfall-after">{amount(row.after)} remaining</div></div>)}
        <div className="freight-waterfall-row"><div className="freight-waterfall-label"><span>Statement remainder</span><div><strong>{amount(model.remainder)}</strong><small>{share(model.remainder)}</small></div></div><div className="freight-waterfall-track" aria-hidden="true"><i className="freight-color-remainder" style={bar(0, model.remainder)} /><span className="freight-waterfall-zero" style={{left: `${position(0)}%`}} /></div></div>
      </div>}
    </> : <p className="finance-error" role="status">The reported allocation does not reconcile to freight. Review the exact statement figures below before interpreting a flow.</p>}
    {fuelOpen&&<section className="freight-fuel-detail" aria-label="Fuel purchase details"><div className="finance-section-heading"><h3>Fuel purchases by settlement</h3><button type="button" className="finance-secondary" onClick={()=>setFuelOpen(false)}>Close</button></div>
      {!(data.fuel_sources?.length)&&<p>No purchase detail is available for these statements.</p>}
      {data.fuel_sources?.filter(source=>Number(source.amount)!==0||source.rows.length).map(source=>{
        const reviewed = history?.rows.find(row=>row.id===source.legacy_id)
        const purchases = source.basis==='posted'?source.rows:(reviewed?.fuel_rows||[])
        const total = purchases.reduce((sum,p)=>sum+Math.round(Number(p.amount)*100),0)
        const difference = Math.round(Number(source.amount)*100)-total
        return <article key={source.id}><div className="finance-section-heading"><strong>{reviewed?.vin?`VIN …${reviewed.vin.slice(-6)}`:source.name} · {source.date}</strong><strong>{dollars(source.amount)}</strong></div>
          {purchases.length?<><div className="freight-purchases">{purchases.map((p,i)=><div key={i}><span>{p.date}</span><span>{p.location||'Location not recorded'}<small>{p.product==='unknown'?'Product not classified':p.product}{p.gallons!==null&&p.gallons!==undefined?` · ${p.gallons} gal`:''}</small></span><strong>{dollars(p.amount)}</strong></div>)}</div>{difference!==0&&<p className="finance-error">Purchase rows total {dollars(total/100)}; difference from statement fuel charge: {dollars(difference/100)}.</p>}</>:<p className="finance-help">{source.basis==='saved'&&!history&&!historyError?'Loading purchase records…':'Purchase details unavailable. The statement fuel total is retained.'}</p>}
          <Link to={`/settlements/reconciliation?asset=${source.asset_id}#review-records`}>Review settlement sources</Link>
        </article>
      })}
    </section>}
    <details className="owner-details freight-flow-details" open={!model.reconciled || undefined}>
      <summary><span>{model.reconciled ? 'All charges and exact figures' : 'Reported statement figures'}</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg></summary>
      <dl className="freight-flow-values"><div><dt>Freight billed</dt><dd>{dollars(data.freight_gross)}</dd></div>{data.rows.map((row, i) => <div key={`${row.category}-${i}`}><dt>{model.details.find(d => d.key === row.category)?.label}</dt><dd>{dollars(row.amount)}<small>{share(Math.round(Number(row.amount) * 100))}</small></dd></div>)}<div><dt>Statement remainder</dt><dd>{dollars(data.settlement_remainder)}</dd></div></dl>
    </details>
    <p className="finance-help">Statement remainder is before outside bills and cash protection. Carrier and driver amounts are settlement shares, not their personal take-home. Internal trailer allocations stay in your business; reserves are not operating expenses.</p>
  </div>
}
