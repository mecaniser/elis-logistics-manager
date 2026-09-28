import {useEffect,useState} from 'react'
import {trucksApi} from '../services/api'
import {dollars} from '../services/finance'

type Progress={unavailable?:string;as_of:string;start:string;source_count:number;allocated_income:string;loan_allocation:string;modeled_interest:string;modeled_principal_reduction:string;projected_balance:string;cash_recovery:string;cash_recovery_remaining:string;remaining_after_allocations:string;balance_target:string;target_date:string|null;planned_sale:string;recent_monthly_payment_pace:string;basis:string;sources:{id:number;date:string;kind:string;income:string;loan_allocation:string;cash_recovery:string}[]}
export default function TrailerInvestmentProgress({id,revision}:{id:number;revision:number}) {
 const [data,setData]=useState<Progress|null>(null)
 const [open,setOpen]=useState(false)
 const [limit,setLimit]=useState(10)
 const [error,setError]=useState(false)
 useEffect(()=>{let active=true;setError(false);void trucksApi.investmentProgress(id,new Date().toLocaleDateString('en-CA')).then(r=>{if(active)setData(r.data)}).catch(()=>{if(active)setError(true)});return()=>{active=false}},[id,revision])
 if(error)return <p role="status" className="text-sm text-amber-800 mt-3">Settlement progress could not be loaded.</p>
 if(!data)return null
 if(data.unavailable)return <p className="text-sm text-amber-800 mt-3">{data.unavailable}</p>
 const financed=Number(data.loan_allocation)!==0||Number(data.projected_balance)!==0
 return <div className="border-t border-slate-200 mt-4 pt-3"><button type="button" className="flex w-full items-center justify-between gap-3 text-sm font-semibold min-h-11" aria-expanded={open} onClick={()=>setOpen(!open)}><span>Settlement recovery progress · {data.source_count} records</span><span>{dollars(data.allocated_income)} allocated <svg className="inline ml-2" width="14" height="14" viewBox="0 0 24 24" stroke="currentColor" fill="none" strokeWidth="2" aria-hidden="true" style={{transform:open?'rotate(90deg)':undefined}}><path d="m9 18 6-6-6-6"/></svg></span></button>{open&&<>
 <p className="text-xs text-slate-500 mb-3">{data.start}–{data.as_of} · Saved settlement history. Projected allocations, not confirmed payments.</p>
 <dl className="grid grid-cols-2 lg:grid-cols-4 gap-3 text-sm">{[[financed?'Loan allocation':'Cash recovery',financed?data.loan_allocation:data.cash_recovery],[financed?'Projected debt remaining':'Cash still to recover',financed?data.projected_balance:data.cash_recovery_remaining],[financed?'Cash recovery allocated':'Recovery target',financed?data.cash_recovery:String(Number(data.cash_recovery)+Number(data.cash_recovery_remaining))],['Left before trailer costs',data.remaining_after_allocations]].map(([label,value])=><div key={label}><dt className="text-slate-600">{label}</dt><dd className="font-semibold tabular-nums">{dollars(value)}</dd></div>)}</dl>
 {financed&&<p className="text-sm mt-3">Projected to reach {dollars(data.balance_target)}: <strong>{data.target_date||'No date at the recent earnings pace'}</strong>. Planned sale: {data.planned_sale}. Uses the recent 90-day earnings pace.</p>}
 {financed&&<p className="text-xs text-slate-500 mt-2">Interest modeled: {dollars(data.modeled_interest)} · Principal reduction: {dollars(data.modeled_principal_reduction)}. Assumes allocated funds are paid; actual lender balance is not established.</p>}
 <p className="text-xs text-slate-500 mt-2">Each settlement uses the loan and cash-recovery shares of its saved monthly plan. Missing statements and operating costs can change the result.</p>
 <div className="overflow-x-auto mt-3"><table className="w-full text-sm text-left"><caption className="sr-only">Settlement allocations counted once</caption><thead><tr className="border-b"><th className="py-2">Source</th><th>Income</th><th>Loan allocation</th><th>Cash recovery</th></tr></thead><tbody>{data.sources.slice(0,limit).map(s=><tr key={s.id} className="border-b border-slate-200"><td className="py-2"><span>{s.date}</span><span className="block text-xs text-slate-500">{s.kind}</span></td><td>{dollars(s.income)}</td><td>{dollars(s.loan_allocation)}</td><td>{dollars(s.cash_recovery)}</td></tr>)}</tbody></table></div>{limit<data.sources.length&&<button type="button" className="mt-3 rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={()=>setLimit(limit+10)}>Show more</button>}
 </>}</div>
}
