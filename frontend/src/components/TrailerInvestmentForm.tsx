import TrailerInvestmentProgress from './TrailerInvestmentProgress'
import { useEffect, useRef, useState } from 'react'
import { Truck, trucksApi } from '../services/api'

import { investmentPayload, savedInvestmentDraft, formatInvestmentAmount, type InvestmentDraft as Plan } from './investmentPlanModel'
const money = (value: unknown) => value == null ? '—' : Number(value).toLocaleString('en-US', {style:'currency',currency:'USD'})

function AmountInput({value, onChange}: {value: unknown; onChange:(value:string)=>void}) {
  const [focused, setFocused] = useState(false)
  return <input className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11 tabular-nums" type="text" inputMode="decimal" value={focused ? String(value ?? '') : formatInvestmentAmount(value)} onFocus={()=>setFocused(true)} onBlur={()=>setFocused(false)} onChange={e=>{const raw=e.target.value.replace(/[$,\s]/g,'');if(/^\d*(\.\d{0,2})?$/.test(raw))onChange(raw)}} />
}

export default function TrailerInvestmentForm({vehicle, compact=false}: {vehicle:Partial<Truck> & {id:number}; compact?:boolean}) {
  const [savedRevision,setSavedRevision] = useState(0)
  const [editing, setEditing] = useState(!compact)
  const saved = vehicle.investment_plans?.[vehicle.investment_plans.length - 1]
  const total = Number(vehicle.total_cost || 0)
  const borrowed = Number(vehicle.loan_amount || 0)
  const [plan, setPlan] = useState<Plan>((): Plan => saved ? savedInvestmentDraft(saved) : {
    funding: borrowed ? 'heloc' : 'cash', lender:'', rate_type:'fixed',
    start: vehicle.purchase_date?.slice(0,10) || '', effective:vehicle.purchase_date?.slice(0,10) || '',
    months:60, acquisition_cost:total.toFixed(2), initial_cash:(total-borrowed).toFixed(2),
    financed:borrowed.toFixed(2), annual_rate:vehicle.interest_rate || 0,
    net_resale:vehicle.expected_resale_value ?? 40000, monthly_allocation:1600,
    balance_at_sale:0, financed_fees:0, quoted_monthly_payment:null,
  })
  const revision = useRef(0)
  const [result, setResult] = useState<Plan | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(()=>{let current=true;const version=revision.current;if(saved)void trucksApi.previewInvestment(vehicle.id,saved).then(r=>{if(current&&version===revision.current)setResult(r.data)}).catch(()=>{if(current)setMessage('Unable to load saved projection.')});return()=>{current=false}},[saved,vehicle.id])
  const change = (key:string, value:string | number | null) => {revision.current++;setPlan(p=>({...p,[key]:value}));setResult(null);setMessage('')}
  const field = (key:string,label:string,type='number') => <label className="text-sm text-slate-700" key={key}>{label}{['net_resale','monthly_allocation','financed','initial_cash','balance_at_sale','quoted_monthly_payment'].includes(key) ? <AmountInput value={plan[key]} onChange={value=>change(key,value || (key==='quoted_monthly_payment'?null:''))}/> : <input className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11" type={type} min={type==='number'?0:undefined} step={type==='number'?'any':undefined} value={plan[key] ?? ''} onChange={e=>change(key,e.target.value || (key==='quoted_monthly_payment'?null:''))}/>}</label>
  async function calculate(save:boolean) {
    const version=revision.current
    setBusy(true);setMessage('')
    try {
      if(save){ const response=await trucksApi.saveInvestment(vehicle.id,investmentPayload(plan));if(version===revision.current){setResult(response.data.projection);setMessage('Recovery plan saved. No payment or reserve was recorded.');setSavedRevision(r=>r+1)} }
      else {const response=await trucksApi.previewInvestment(vehicle.id,investmentPayload(plan));if(version===revision.current)setResult(response.data)}
    } catch(error) {const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;setMessage(typeof detail==='string'?detail:'Check purchase date, funding amounts and recovery settings.')}
    finally {setBusy(false)}
  }
  return <section className="rounded-lg border border-slate-200 bg-slate-50 p-4 mb-4" aria-label="Trailer recovery plan">
    <div className="flex items-center justify-between gap-3 mb-3"><h3 className="font-semibold text-slate-900">Investment recovery plan</h3><span className="text-xs text-slate-500">Forecast · saved purchase {money(total)}</span>{compact&&<button type="button" className="rounded-md border border-slate-300 px-3 py-2 text-sm min-h-11" aria-expanded={editing} onClick={()=>setEditing(!editing)}>{editing?'Close settings':'Edit plan'}</button>}</div>
    {editing&&<><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <label className="text-sm text-slate-700">Funding<select className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11" value={String(plan.funding)} onChange={e=>change('funding',e.target.value)}><option value="cash">Cash purchase</option><option value="heloc">HELOC</option><option value="dealer">Dealer financing</option><option value="other">Other loan</option></select></label>
      {field('start','Purchase date','date')}{field('effective','Effective from','date')}
      {field('months','Ownership period (months)')}{field('net_resale','Expected sale after selling costs ($)')}{field('monthly_allocation','Monthly trailer allocation ($)')}
      {plan.funding!=='cash'&&<>
        {field('lender','Lender / account nickname','text')}{field('financed','Amount borrowed ($)')}{field('initial_cash','Cash paid toward purchase & equipment ($)')}
        <label className="text-sm text-slate-700">Annual interest (%)<input type="number" min="0" max="100" step="0.01" className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11" value={Math.round(Number(plan.annual_rate)*10000)/100} onChange={e=>change('annual_rate',Number(e.target.value)/100)}/></label>
        <label className="text-sm text-slate-700">Rate type<select className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11" value={String(plan.rate_type)} onChange={e=>change('rate_type',e.target.value)}><option value="fixed">Fixed</option><option value="variable">Variable — projection uses current rate</option></select></label>
        {field('balance_at_sale','Loan balance to repay at sale ($)')}{field('quoted_monthly_payment','Lender payment override ($, optional)')}
      </>}
    </div>
    <p className="text-xs text-slate-500 mt-3">Effective from controls when Finance uses this plan. Leave the payment override blank to calculate from the loan terms.</p>
    <div className="flex flex-wrap gap-2 mt-4"><button type="button" disabled={busy} onClick={()=>void calculate(false)} className="rounded-md border border-slate-300 bg-white px-4 py-2 min-h-11 font-medium text-slate-800 disabled:opacity-50">Calculate</button><button type="button" disabled={busy||!result||!vehicle.id} onClick={()=>void calculate(true)} className="rounded-md bg-blue-600 px-4 py-2 min-h-11 font-medium text-white disabled:opacity-50">Save recovery plan</button></div></>}
    {result&&<>
    <div className="grid sm:grid-cols-2 gap-3 mt-4"><section className="rounded-lg bg-white border border-slate-200 p-3"><h4 className="text-sm font-semibold mb-2">Monthly trailer plan</h4><dl className="text-sm space-y-2">{[['monthly_allocation','Budget from trailer earnings'],['monthly_payment','Planned loan payment · includes interest'],['monthly_cash_recovery','Set aside to recover your cash'],['monthly_left','Estimated cash left each month']].map(([key,label])=><div className="flex justify-between gap-3" key={key}><dt>{label}</dt><dd className={`font-semibold ${key==='monthly_left'?'text-green-700':''}`}>{money(result[key])}</dd></div>)}</dl></section>
    <section className="rounded-lg bg-green-50 border border-green-200 p-3"><h4 className="text-sm font-semibold mb-2">After {String(result.months)} months + sale</h4><dl className="text-sm space-y-2">{[['net_resale','Expected sale proceeds'],['balance_at_sale','Loan to pay off when sold'],['sale_equity','Sale proceeds left after debt'],['projected_profit','Total estimated profit over ownership']].map(([key,label])=><div className="flex justify-between gap-3" key={key}><dt>{label}</dt><dd className={`font-semibold ${key==='projected_profit'?'text-green-700':''}`}>{money(result[key])}</dd></div>)}</dl></section></div>
    <p className="text-xs text-slate-500 mt-2">Trailer only · based on the monthly allocation for the full ownership period. Before additional trailer costs and tax. Combined truck + trailer earnings are shown in Finance.</p>
    {Number(result.quote_payment_difference)!==0&&<p className="text-xs text-amber-800 mt-2">Quote differs from rate-based payment ({money(result.rate_based_monthly_payment)}). Confirm final lender schedule.</p>}
    </>}
    {vehicle.id>0&&<TrailerInvestmentProgress id={vehicle.id} revision={savedRevision}/>}
    {!vehicle.id&&<p className="text-xs text-slate-500 mt-2">Preview only. Save the vehicle purchase before attaching a recovery plan.</p>}
    {message&&<p role="status" className="text-sm mt-3">{message}</p>}
  </section>
}
