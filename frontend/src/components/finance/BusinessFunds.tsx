import {useState} from 'react'
import {Link} from 'react-router-dom'
import {dollars, type EarningsPlan} from '../../services/finance'
import {ownerEarningsModel} from './ownerEarningsModel'
import './BusinessFunds.css'
export default function BusinessFunds({plan}:{plan:EarningsPlan}) {
 const [open,setOpen]=useState(false)
 const model=ownerEarningsModel(plan)
 const repair=model.rows.find(r=>r.label==='Repair reserve')?.amount||0
 const capital=model.rows.find(r=>r.label==='Equipment capital recovery')?.amount||0
 const funds=plan.business_funds
 return <section className="business-funds" aria-label="Money kept in the business">
  <h3>Kept in the business · still your money</h3>
  <p className="finance-help">These amounts reduce what you take home, not what the business owns. They are already included in the statement remainder.</p>
  <div className="business-fund-tiles"><div className="business-fund-repair"><span>Kept for repairs · this period</span><strong>{dollars(-repair/100)}</strong></div><div className="business-fund-capital"><span>Kept to recover your investment · this period</span><strong>{dollars(-capital/100)}</strong></div></div>
  {funds&&<><button className="business-funds-toggle" onClick={()=>setOpen(!open)} aria-expanded={open}>Running fund balances · through {funds.end}<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{transform:open?'rotate(90deg)':undefined}}><path d="m9 18 6-6-6-6"/></svg></button>
   <div className="business-fund-tiles"><div className="business-fund-repair"><span>Repair fund remaining</span><strong>{dollars(funds.repair.balance)}</strong><small>Recorded set-asides minus repairs paid from the fund{Number(funds.repair.balance)<0?' · repairs exceeded the fund':''}</small></div><div className="business-fund-capital"><span>Your investment recovered so far</span><strong>{dollars(funds.capital.balance)}</strong><small>Accumulated from settlement earnings · before owner withdrawals</small></div></div>
   {open&&<div className="business-funds-detail"><p className="finance-help">Movement for {funds.start} – {funds.end}. History uses recorded settlement allocations; the period amounts above use your calendar-based plan.</p>
   <table><thead><tr><th>Fund</th><th>Opening</th><th>Added</th><th>Used</th><th>Closing</th></tr></thead><tbody><tr><th>Repairs</th><td>{dollars(funds.repair.opening)}</td><td>{dollars(funds.repair.added)}</td><td>{dollars(funds.repair.used)}</td><td>{dollars(funds.repair.balance)}</td></tr><tr><th>Investment recovery</th><td>{dollars(funds.capital.opening)}</td><td>{dollars(funds.capital.added)}</td><td>Not tracked here</td><td>{dollars(funds.capital.balance)}</td></tr></tbody></table>
   <p className="finance-help">Repair history starts {funds.repair_since}. Recovery is calculated from each saved equipment plan. A bank match is not required. Recovery totals do not tell us how much you have already withdrawn.</p>
   {funds.equipment.map(a=><p key={a.asset_id}><Link to={`/vehicles/${a.asset_id}`}>{a.name}</Link> · {a.unavailable||dollars(a.balance!)}</p>)}
   </div>}
  </>}
 </section>
}
