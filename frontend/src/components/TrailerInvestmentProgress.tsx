import {useEffect,useState} from 'react'
import {trucksApi} from '../services/api'
import {dollars} from '../services/finance'

type Progress={original_borrowed:string;initial_cash:string;cash_recovery_target:string;sale_equity:string;week_start:string;week_end:string;weekly_loan_target:string;weekly_cash_target:string;unavailable?:string;as_of:string;start:string;source_count:number;allocated_income:string;loan_allocation:string;modeled_interest:string;modeled_principal_reduction:string;projected_balance:string;cash_recovery:string;cash_recovery_remaining:string;remaining_after_allocations:string;balance_target:string;target_date:string|null;planned_sale:string;recent_monthly_payment_pace:string;basis:string;sources:{id:number;date:string;kind:string;income:string;loan_allocation:string;cash_recovery:string}[]}
export default function TrailerInvestmentProgress({id,revision}:{id:number;revision:number}) {
 const [data,setData]=useState<Progress|null>(null)
 const [open,setOpen]=useState(false)
 const [limit,setLimit]=useState(10)
 const [error,setError]=useState(false)
 useEffect(()=>{let active=true;setError(false);void trucksApi.investmentProgress(id,new Date().toLocaleDateString('en-CA')).then(r=>{if(active)setData(r.data)}).catch(()=>{if(active)setError(true)});return()=>{active=false}},[id,revision])
 if(error)return <p role="status" className="text-sm text-amber-800 mt-3">Settlement progress could not be loaded.</p>
 if(!data)return null
 if(data.unavailable)return <p className="text-sm text-amber-800 mt-3">{data.unavailable}</p>
 const financed=Number(data.original_borrowed)>0
 const metric=(name:string,value:string)=><div key={name} className="flex justify-between gap-3 py-1"><dt className="text-slate-600">{name}</dt><dd className="font-semibold tabular-nums">{dollars(value)}</dd></div>
 const progress=(value:string,total:string,color:string)=>{const pct=Math.max(0,Math.min(100,Number(total)>0?Number(value)/Number(total)*100:0));return <div className="h-2 rounded bg-slate-200 mt-3 overflow-hidden" role="progressbar" aria-label={color==='bg-blue-600'?'Projected principal repaid':'Projected cash recovery'} aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}><div className={`h-full ${color}`} style={{width:`${pct}%`}}/></div>}
 return <div className="border-t border-slate-200 mt-4 pt-4">
 <div className="flex justify-between gap-3 items-center"><h3 className="font-semibold text-sm">Repayment & recovery progress</h3><span className="text-xs text-amber-800">Projected · payments unconfirmed</span></div>
 <p className="text-xs text-slate-500 mt-1 mb-3">{data.start} – {data.as_of}</p>
 <div className={`grid gap-3 ${financed?'md:grid-cols-2':''}`}>
 {financed&&<section className="rounded-lg bg-blue-50 p-3"><h4 className="text-sm font-semibold text-blue-900 mb-2">Loan</h4><dl className="text-sm">{metric('Originally borrowed',data.original_borrowed)}{metric('Allocated to payments',data.loan_allocation)}{metric('Interest modeled',data.modeled_interest)}{metric('Principal reduction',data.modeled_principal_reduction)}{metric('Projected debt remaining',data.projected_balance)}</dl>{progress(data.modeled_principal_reduction,data.original_borrowed,'bg-blue-600')}</section>}
 <section className="rounded-lg bg-purple-50 p-3"><h4 className="text-sm font-semibold text-purple-900 mb-2">Your cash</h4><dl className="text-sm">{metric('Originally invested',data.initial_cash)}{metric('Recovery target from earnings',data.cash_recovery_target)}{metric('Recovery allocated',data.cash_recovery)}{metric('Still to allocate',data.cash_recovery_remaining)}{Number(data.sale_equity)>0&&metric('Expected net sale equity',data.sale_equity)}</dl>{progress(data.cash_recovery,data.cash_recovery_target,'bg-purple-600')}</section>
 </div>
 <div className="rounded-lg bg-slate-100 p-3 mt-3"><p className="text-xs text-slate-600 mb-1">Weekly plan · {data.week_start} – {data.week_end}</p><dl className="text-sm">{financed&&metric('Loan payment target',data.weekly_loan_target)}{metric('Cash recovery target',data.weekly_cash_target)}</dl></div>
 <div className="flex justify-between gap-3 rounded-lg bg-green-50 text-green-900 p-3 mt-3 text-sm"><span>Left from recorded allocations · before trailer costs</span><strong>{dollars(data.remaining_after_allocations)}</strong></div>
 {financed&&<p className="text-xs text-slate-500 mt-2">Debt target at sale: {dollars(data.balance_target)} · Estimated date at recent pace: {data.target_date||'Not established'} · Planned sale: {data.planned_sale}</p>}
 <button type="button" className="flex w-full items-center justify-between gap-3 text-sm min-h-11 mt-2" aria-expanded={open} onClick={()=>setOpen(!open)}><span>Allocation history · {data.source_count} records</span><svg width="14" height="14" viewBox="0 0 24 24" stroke="currentColor" fill="none" strokeWidth="2" aria-hidden="true" style={{transform:open?'rotate(90deg)':undefined}}><path d="m9 18 6-6-6-6"/></svg></button>{open&&<>
 <p className="text-xs text-slate-500">Historical allocations use each settlement’s share of the monthly plan; weekly targets use calendar dates, matching Finance. Neither confirms a bank payment.</p>
 <div className="overflow-x-auto mt-3"><table className="w-full text-sm text-left"><caption className="sr-only">Settlement allocations counted once</caption><thead><tr className="border-b"><th className="py-2">Source</th><th>Income</th><th>Loan allocation</th><th>Cash recovery</th></tr></thead><tbody>{data.sources.slice(0,limit).map(s=><tr key={s.id} className="border-b border-slate-200"><td className="py-2"><span>{s.date}</span><span className="block text-xs text-slate-500">{s.kind}</span></td><td>{dollars(s.income)}</td><td>{dollars(s.loan_allocation)}</td><td>{dollars(s.cash_recovery)}</td></tr>)}</tbody></table></div>{limit<data.sources.length&&<button type="button" className="mt-3 rounded-md border border-slate-300 px-3 py-2 text-sm" onClick={()=>setLimit(limit+10)}>Show more</button>}
 </>}</div>
}
