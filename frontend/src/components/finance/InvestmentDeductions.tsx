import {useState} from 'react'
import {Link} from 'react-router-dom'
import {dollars,type EarningsPlan} from '../../services/finance'

export default function InvestmentDeductions({plan,kind,label}:{plan:EarningsPlan;kind:'capital'|'loan';label:string}) {
 const [open,setOpen]=useState(false)
 return <div className="investment-deduction"><button type="button" className="freight-drill-button" aria-expanded={open} onClick={()=>setOpen(!open)}>{label}<svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{transform:open?'rotate(90deg)':undefined}}><path d="m9 18 6-6-6-6"/></svg></button>{open&&<div className="investment-detail-panel rounded-md border border-slate-200 bg-white p-3 shadow-lg text-sm"><dl className="finance-waterfall">{plan.pairs.flatMap(pair=>(pair.asset_deductions||[]).filter(row=>Number(kind==='capital'?row.capital_target:row.loan_target)!==0).map(row=>{const asset=plan.settings.find(s=>s.asset_id===row.asset_id);return <div key={`${pair.asset_id}-${row.asset_id}`}><dt><Link to={`/vehicles/${row.asset_id}`}>{asset?.vin?`VIN …${asset.vin.slice(-6)}`:asset?.name}</Link>{kind==='loan'&&Number(row.recorded_loan_deductions)>0&&<small> · {dollars(row.recorded_loan_deductions)} already deducted</small>}</dt><dd>{dollars(kind==='capital'?row.capital_target:row.additional_loan)}</dd></div>}))}</dl><p className="text-xs text-slate-500 mt-2">Selected period · included once in the total.</p></div>}</div>
}
