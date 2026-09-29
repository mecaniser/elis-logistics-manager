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
  <div className="finance-section-heading"><h3>Business funds</h3>{funds&&<span className="finance-help">Through {funds.end}</span>}</div>
  <div className="business-fund-tiles"><div className="business-fund-repair"><span>Repair fund</span><strong>{funds?dollars(funds.repair.balance):'—'}</strong><small>{Number(funds?.repair.balance)<0?'Shortfall':'Remaining'}</small><div className="business-fund-period"><span>Period plan</span><b>{dollars(Math.abs(repair)/100)}</b></div></div><div className="business-fund-capital"><span>Investment recovered</span><strong>{funds?dollars(funds.capital.balance):'—'}</strong><small>Before withdrawals</small><div className="business-fund-period"><span>Period plan</span><b>{dollars(Math.abs(capital)/100)}</b></div></div></div>
  {funds&&<><button className="business-funds-toggle" onClick={()=>setOpen(!open)} aria-expanded={open}>Fund history<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true" style={{transform:open?'rotate(90deg)':undefined}}><path d="m9 18 6-6-6-6"/></svg></button>
   {open&&<div className="business-funds-detail"><p className="finance-help">{funds.start} – {funds.end} · Settlement history</p>
   <table><thead><tr><th>Fund</th><th>Opening</th><th>Added</th><th>Used</th><th>Total</th></tr></thead><tbody><tr><th>Repairs</th><td>{dollars(funds.repair.opening)}</td><td>{dollars(funds.repair.added)}</td><td>{dollars(funds.repair.used)}</td><td>{dollars(funds.repair.balance)}</td></tr><tr><th>Investment recovery</th><td>{dollars(funds.capital.opening)}</td><td>{dollars(funds.capital.added)}</td><td>—</td><td>{dollars(funds.capital.balance)}</td></tr></tbody></table>

   {funds.equipment.map(a=><p key={a.asset_id}><Link to={`/vehicles/${a.asset_id}`}>{a.name}</Link> · {a.unavailable||dollars(a.balance!)}</p>)}
   </div>}
  </>}
 </section>
}
