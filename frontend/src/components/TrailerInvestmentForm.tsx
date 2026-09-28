import { useEffect, useState } from 'react'
import { Truck, trucksApi } from '../services/api'

type Plan = Record<string, string | number | null>
const money = (value: unknown) => value == null ? '—' : Number(value).toLocaleString('en-US', {style:'currency',currency:'USD'})

export default function TrailerInvestmentForm({vehicle, compact=false}: {vehicle:Partial<Truck> & {id:number}; compact?:boolean}) {
  const [editing, setEditing] = useState(!compact)
  const saved = vehicle.investment_plans?.[vehicle.investment_plans.length - 1]
  const total = Number(vehicle.total_cost || 0)
  const borrowed = Number(vehicle.loan_amount || 0)
  const [plan, setPlan] = useState<Plan>((): Plan => saved ? {...saved, effective: new Date().toLocaleDateString('en-CA')} : {
    funding: borrowed ? 'heloc' : 'cash', lender:'', rate_type:'fixed',
    start: vehicle.purchase_date?.slice(0,10) || '', effective:new Date().toLocaleDateString('en-CA'),
    months:60, acquisition_cost:total.toFixed(2), initial_cash:(total-borrowed).toFixed(2),
    financed:borrowed.toFixed(2), annual_rate:vehicle.interest_rate || 0,
    net_resale:vehicle.expected_resale_value ?? 40000, monthly_allocation:1600,
    balance_at_sale:0, financed_fees:0, quoted_monthly_payment:null,
  })
  const [result, setResult] = useState<Plan | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(()=>{let current=true;if(saved)void trucksApi.previewInvestment(vehicle.id,saved).then(r=>{if(current)setResult(r.data)}).catch(()=>{if(current)setMessage('Unable to load saved projection.')});return()=>{current=false}},[saved,vehicle.id])
  const change = (key:string, value:string | number | null) => {setPlan(p=>({...p,[key]:value}));setResult(null);setMessage('')}
  const field = (key:string,label:string,type='number') => <label className="text-sm text-slate-700" key={key}>{label}<input className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11" type={type} min={type==='number'?0:undefined} step={type==='number'?'any':undefined} value={plan[key] ?? ''} onChange={e=>change(key,e.target.value || (key==='quoted_monthly_payment'?null:''))}/></label>
  async function calculate(save:boolean) {
    setBusy(true);setMessage('')
    try {
      if(save){ const response=await trucksApi.saveInvestment(vehicle.id,plan);setResult(response.data.projection);setMessage('Recovery plan saved. No payment or reserve was recorded.') }
      else setResult((await trucksApi.previewInvestment(vehicle.id,plan)).data)
    } catch(error) {const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;setMessage(typeof detail==='string'?detail:'Check purchase date, funding amounts and recovery settings.')}
    finally {setBusy(false)}
  }
  return <section className="rounded-lg border border-slate-200 bg-slate-50 p-4 mb-4" aria-label="Trailer recovery plan">
    <div className="flex items-center justify-between gap-3 mb-3"><h3 className="font-semibold text-slate-900">Investment recovery plan</h3><span className="text-xs text-slate-500">Forecast · saved purchase {money(total)}</span>{compact&&<button type="button" className="rounded-md border border-slate-300 px-3 py-2 text-sm min-h-11" aria-expanded={editing} onClick={()=>setEditing(!editing)}>{editing?'Close settings':'Edit plan'}</button>}</div>
    {editing&&<><div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <label className="text-sm text-slate-700">Funding<select className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11" value={String(plan.funding)} onChange={e=>{const funding=e.target.value;setPlan(p=>({...p,funding,...(funding==='cash'?{financed:0,initial_cash:p.acquisition_cost,annual_rate:0,balance_at_sale:0,quoted_monthly_payment:null}: {})}));setResult(null)}}><option value="cash">Cash purchase</option><option value="heloc">HELOC</option><option value="dealer">Dealer financing</option><option value="other">Other loan</option></select></label>
      {field('start','Purchase date','date')}{field('effective','Apply plan from','date')}
      {field('months','Ownership period (months)')}{field('net_resale','Expected sale after selling costs ($)')}{field('monthly_allocation','Monthly trailer allocation ($)')}
      {plan.funding!=='cash'&&<>
        {field('lender','Lender / account nickname','text')}{field('financed','Amount borrowed ($)')}{field('initial_cash','Your cash, including setup costs ($)')}
        <label className="text-sm text-slate-700">Annual interest (%)<input type="number" min="0" max="100" step="0.01" className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11" value={Math.round(Number(plan.annual_rate)*10000)/100} onChange={e=>change('annual_rate',Number(e.target.value)/100)}/></label>
        <label className="text-sm text-slate-700">Rate type<select className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 min-h-11" value={String(plan.rate_type)} onChange={e=>change('rate_type',e.target.value)}><option value="fixed">Fixed</option><option value="variable">Variable — projection uses current rate</option></select></label>
        {field('balance_at_sale','Loan balance to repay at sale ($)')}{field('quoted_monthly_payment','Quoted monthly payment ($, optional)')}
      </>}
    </div>
    <div className="flex flex-wrap gap-2 mt-4"><button type="button" disabled={busy} onClick={()=>void calculate(false)} className="rounded-md border border-slate-300 bg-white px-4 py-2 min-h-11 font-medium text-slate-800 disabled:opacity-50">Calculate</button><button type="button" disabled={busy||!result||!vehicle.id} onClick={()=>void calculate(true)} className="rounded-md bg-blue-600 px-4 py-2 min-h-11 font-medium text-white disabled:opacity-50">Save recovery plan</button></div></>}
    {result&&<><dl className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-4">{[['monthly_payment','Loan payment / month'],['monthly_cash_recovery','Cash recovery / month'],['monthly_left','Left / month'],['projected_profit','Lifetime profit']].map(([key,label])=><div key={key}><dt className="text-xs text-slate-600">{label}</dt><dd className="text-lg font-semibold tabular-nums">{money(result[key])}</dd></div>)}</dl><p className="text-xs text-slate-500 mt-3">Before additional operating costs and tax. Sale equity: {money(result.sale_equity)}. Cash ROI: {result.cash_roi_percent==null?'Not applicable (no cash invested)':`${result.cash_roi_percent}%`}.</p>{Number(result.quote_payment_difference)!==0&&<p className="text-xs text-amber-800 mt-2">Quote differs from rate-based payment ({money(result.rate_based_monthly_payment)}). Confirm final lender schedule.</p>}</>}
    {!vehicle.id&&<p className="text-xs text-slate-500 mt-2">Preview only. Save the vehicle purchase before attaching a recovery plan.</p>}
    {message&&<p role="status" className="text-sm mt-3">{message}</p>}
  </section>
}
