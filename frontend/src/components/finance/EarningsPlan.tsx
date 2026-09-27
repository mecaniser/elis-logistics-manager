import { useState } from 'react'
import { Link } from 'react-router-dom'
import { dollars, type EarningsPlan as Plan } from '../../services/finance'

export default function EarningsPlan({plan}:{plan:Plan}) {
  const [expanded,setExpanded]=useState<number|null>(null)
  return <section className="owner-panel earnings-plan"><div className="finance-section-heading"><h2>After planned protection</h2><span className="finance-status">Estimate · saved records</span></div>
    <p className="finance-help">Uses your saved vehicle settings. Incomplete capital plans and unverified financing still need to be accounted for.</p>
    {plan.pairs.map(pair=><article key={pair.asset_id} className="earnings-plan-pair"><button type="button" aria-expanded={expanded===pair.asset_id} aria-controls={`earnings-plan-${pair.asset_id}`} onClick={()=>setExpanded(expanded===pair.asset_id?null:pair.asset_id)}><span>{plan.settings.find(s=>s.asset_id===pair.asset_id)?.vin?`Truck · VIN …${plan.settings.find(s=>s.asset_id===pair.asset_id)!.vin!.slice(-6)}`:pair.name}</span><strong>{dollars(pair.planning_subtotal)}</strong><svg width="16" height="16" viewBox="0 0 24 24" stroke="currentColor" fill="none" strokeWidth="2" aria-hidden="true" style={{transform:expanded===pair.asset_id?'rotate(90deg)':undefined}}><path d="m9 18 6-6-6-6"/></svg></button>
      <div className="earnings-plan-targets"><span>Repair target <b>{dollars(pair.repair_target)}</b></span><span>Capital target <b>{pair.capital_complete===false&&Number(pair.capital_target)===0?'Incomplete':dollars(pair.capital_target)}{pair.capital_complete===false&&Number(pair.capital_target)!==0?' · partial':''}</b></span><span>Already funded <b>{dollars(pair.already_funded)}</b></span></div>
      {expanded===pair.asset_id&&<div id={`earnings-plan-${pair.asset_id}`}><dl className="finance-waterfall">{pair.bridge.filter(row=>Number(row.amount)!==0||row.label==='Statement remainder').map((row,index)=><div key={index}><dt>{row.label}</dt><dd>{dollars(row.amount)}</dd></div>)}<div><dt>Additional planned protection</dt><dd>−{dollars(pair.additional_protection)}</dd></div><div><dt>Planning subtotal</dt><dd>{dollars(pair.planning_subtotal)}</dd></div></dl><ul>{pair.issues.map(issue=><li key={issue}>{issue}</li>)}</ul><div className="earnings-plan-settings">{plan.settings.filter(s=>pair.asset_ids.includes(s.asset_id)).map(s=><p key={s.asset_id}><Link to={s.source}>{s.vin?`VIN …${s.vin.slice(-6)}`:s.name}</Link> · Cost {dollars(s.cost)} · Expected resale {dollars(s.resale)} · Recovery target {dollars(s.capital_weekly)}/week</p>)}</div></div>}
    </article>)}
    {Number(plan.unassigned_result)!==0&&<p className="finance-error">Unassigned costs/income: {dollars(plan.unassigned_result)}. Not included in the pair subtotals.</p>}
  </section>
}
