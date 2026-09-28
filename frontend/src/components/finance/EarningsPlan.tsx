import OwnerEarningsBridge from './OwnerEarningsBridge'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { dollars, type EarningsPlan as Plan } from '../../services/finance'

export default function EarningsPlan({plan,detailsOnly=false}:{plan:Plan;detailsOnly?:boolean}) {
  const [expanded,setExpanded]=useState<number|null>(null)
  const [audit,setAudit]=useState<number|null>(null)
  return <section className="owner-panel earnings-plan"><div className="finance-section-heading"><h2>{detailsOnly?'By truck + trailer':'From settlement to your earnings'}</h2><span className="finance-status">Estimate · saved records</span></div>
    {!detailsOnly&&<><OwnerEarningsBridge plan={plan}/><h3>By truck + trailer</h3></>}
    {plan.pairs.map(pair=><article key={pair.asset_id} className="earnings-plan-pair"><button type="button" aria-expanded={expanded===pair.asset_id} aria-controls={`earnings-plan-${pair.asset_id}`} onClick={()=>setExpanded(expanded===pair.asset_id?null:pair.asset_id)}><span>{plan.settings.find(s=>s.asset_id===pair.asset_id)?.vin?`Truck · VIN …${plan.settings.find(s=>s.asset_id===pair.asset_id)!.vin!.slice(-6)}`:pair.name}</span><strong>{dollars(pair.planning_subtotal)}</strong><svg width="16" height="16" viewBox="0 0 24 24" stroke="currentColor" fill="none" strokeWidth="2" aria-hidden="true" style={{transform:expanded===pair.asset_id?'rotate(90deg)':undefined}}><path d="m9 18 6-6-6-6"/></svg></button>
      <div className="earnings-plan-targets"><span>Repair target <b>{dollars(pair.repair_target)}</b></span><span>Capital target <b>{pair.capital_complete===false&&Number(pair.capital_target)===0?'Incomplete':dollars(pair.capital_target)}{pair.capital_complete===false&&Number(pair.capital_target)!==0?' · partial':''}</b></span><span>Already funded <b>{dollars(pair.already_funded)}</b></span></div>
      {expanded===pair.asset_id&&<div id={`earnings-plan-${pair.asset_id}`}>{pair.allocation_split&&<dl className="finance-waterfall">
        <div><dt>Settlement remainder</dt><dd>{dollars(pair.allocation_split.statement_remainder)}</dd></div>
        <div><dt>Allocated to trailer</dt><dd>−{dollars(pair.allocation_split.trailer_allocation)}</dd></div>
        <div><dt>Repair protection target</dt><dd>−{dollars(pair.repair_target)}</dd></div>
        <div><dt><strong>Truck remainder before other costs</strong></dt><dd><strong>{dollars(pair.allocation_split.truck_remainder)}</strong></dd></div>
        <div><dt>Trailer allocation</dt><dd>{dollars(pair.allocation_split.trailer_allocation)}</dd></div>
        <div><dt>Trailer capital recovery target</dt><dd>−{dollars(pair.allocation_split.trailer_capital_target)}</dd></div>
        <div><dt><strong>Trailer contribution after recovery</strong></dt><dd><strong>{dollars(pair.allocation_split.trailer_contribution)}</strong></dd></div>
        {Number(pair.allocation_split.pair_adjustments)!==0&&<div><dt>Other recorded costs, payments and protection adjustments</dt><dd>{dollars(pair.allocation_split.pair_adjustments)}</dd></div>}
        <div><dt><strong>Combined planning subtotal</strong></dt><dd><strong>{dollars(pair.planning_subtotal)}</strong></dd></div>
      </dl>}
      <button type="button" aria-expanded={audit===pair.asset_id} onClick={()=>setAudit(audit===pair.asset_id?null:pair.asset_id)}>Calculation and source details <span aria-hidden="true">{audit===pair.asset_id?'−':'+'}</span></button>{audit===pair.asset_id&&<div><dl className="finance-waterfall">{pair.bridge.filter(row=>Number(row.amount)!==0).map((row,index)=><div key={index}><dt>{row.label==='Saved settlements not yet posted (unverified)'?'Saved settlement remainder · not posted to Accounting':row.label}</dt><dd>{dollars(row.amount)}</dd></div>)}<div><dt>Additional planned protection</dt><dd>−{dollars(pair.additional_protection)}</dd></div><div><dt>Planning subtotal</dt><dd>{dollars(pair.planning_subtotal)}</dd></div></dl><ul>{pair.issues.map(issue=><li key={issue}>{issue}</li>)}</ul><div className="earnings-plan-settings">{plan.settings.filter(s=>pair.asset_ids.includes(s.asset_id)).map(s=><p key={s.asset_id}><Link to={s.source}>{s.vin?`VIN …${s.vin.slice(-6)}`:s.name}</Link> · Cost {dollars(s.cost)} · Expected resale {dollars(s.resale)} · {s.investment_projection ? <>Loan {dollars(String(s.investment_projection.monthly_payment))}/month · Cash recovery {dollars(String(s.investment_projection.monthly_cash_recovery))}/month</> : <>Recovery target {dollars(s.capital_weekly)}/week</>}</p>)}</div></div>}</div>}
    </article>)}
    {Number(plan.unassigned_result)!==0&&<p className="finance-error">Unassigned costs/income: {dollars(plan.unassigned_result)}. Not included in the pair subtotals.</p>}
  </section>
}
