import { useEffect, useState } from 'react'
import { bankProfilesApi } from '../services/api'
import BankDialog from '../components/BankDialog'
import BankSelect from '../components/BankSelect'
import MoneyInput from '../components/MoneyInput'
import { centsFromMoneyInput } from '../components/moneyAmount'

type Account = {account_id:string; name:string; last4:string; kind:string}
type Data = {profiles:{id:string; name:string; accounts:Account[]}[]; routes:{id:string; profile_id:string; source_id:string; destination_id:string; enabled:boolean}[]}
type Charge = {id:string; account_id:string; description:string; amount_cents:number; date:string; status:string; draft_id:string|null}
const money = (v:number) => (v/100).toLocaleString('en-US',{style:'currency',currency:'USD'})
export default function ProfileChargeEntry({tenantId,onClose,onCreated}:{tenantId:number;onClose:()=>void;onCreated:()=>void}) {
  const [data,setData] = useState<Data>({profiles:[],routes:[]})
  const [charges,setCharges] = useState<Charge[]>([])
  const [routeId,setRoute] = useState('')
  const [chargeId,setCharge] = useState('')
  const [reference,setReference] = useState('')
  const [description,setDescription] = useState('')
  const [date,setDate] = useState(new Date().toLocaleDateString('en-CA'))
  const [amount,setAmount] = useState('')
  const [confirmed,setConfirmed] = useState(false)
  const [busy,setBusy] = useState(true)
  const [error,setError] = useState('')
  const route = data.routes.find(r => r.id === routeId)
  useEffect(() => {
    let active=true
    void Promise.all([bankProfilesApi.request<Data>(tenantId),bankProfilesApi.request<Charge[]>(tenantId,'/funding-charges')]).then(([p,c]) => {if(active){setData(p.data);setCharges(c.data)}}).catch(()=>{if(active)setError('Unable to load bank accounts. Close and try again.')}).finally(()=>{if(active)setBusy(false)})
    return () => {active=false}
  },[tenantId])
  const options = data.routes.filter(r => r.enabled).flatMap(r => {
    const profile=data.profiles.find(p=>p.id===r.profile_id)
    const from=profile?.accounts.find(a=>a.account_id===r.source_id)
    const to=profile?.accounts.find(a=>a.account_id===r.destination_id)
    return from?.kind==='credit' && to?.kind==='checking' ? [{value:r.id,label:`${profile?.name} · ${from.name} ••${from.last4} → ${to.name} ••${to.last4}`}] : []
  })
  const loadCharges = async () => {
    if(!route) return
    setBusy(true);setError('')
    try {await bankProfilesApi.request(tenantId,`/${route.profile_id}/sync`,'post');setCharges((await bankProfilesApi.request<Charge[]>(tenantId,'/funding-charges')).data)}
    catch {setError('Unable to read bank charges. Check this profile’s connection.')}
    finally {setBusy(false)}
  }
  const save = async () => {
    if(!confirmed||!route) return
    setBusy(true);setError('')
    try {
      await bankProfilesApi.request(tenantId,'/charges/draft','post',{route_id:routeId,charge_id:chargeId||null,reference,description,charge_date:date,amount_cents:chargeId?0:centsFromMoneyInput(amount),confirmed_uncovered:confirmed})
      onCreated()
    } catch(e) {setError((e as {response?:{data?:{detail?:string}}}).response?.data?.detail || 'Enter a valid full charge amount.');try {setCharges((await bankProfilesApi.request<Charge[]>(tenantId,'/funding-charges')).data)} catch { /* Preserve the original error. */ }}
    finally {setBusy(false)}
  }
  return <BankDialog title="Add a charge to fund" onClose={onClose}>
    {error&&<p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
    <label className="block text-sm font-medium">Bank connection and transfer route<BankSelect inline ariaLabel="Charge funding route" value={routeId} options={[{value:'',label:'Choose credit line → checking'},...options]} onChange={v=>{setRoute(v);setCharge('');setConfirmed(false)}} /></label>
    {busy&&!data.profiles.length&&<p role="status" className="text-sm text-slate-500">Loading bank accounts…</p>}
    {route&&<>
      {charges.filter(c=>c.account_id===route.destination_id && c.status==='duplicate_review').map(c=><p key={c.id} className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Possible match to a manual charge: {c.description} · {c.date} · {money(c.amount_cents)}. Automatic funding is on hold to avoid paying twice.</p>)}
      <button type="button" disabled={busy} onClick={()=>void loadCharges()} className="min-h-11 text-sm font-semibold text-blue-700">{busy?'Checking…':'Refresh bank charges'}</button>
      <label className="block text-sm font-medium">Charge<BankSelect inline ariaLabel="Charge to fund" value={chargeId} options={[{value:'',label:'Enter a charge not listed below'},...charges.filter(c=>c.account_id===route.destination_id && ((!c.draft_id && ['eligible','historical'].includes(c.status)) || c.status === 'dismissed')).map(c=>({value:c.id,label:`${c.date} · ${c.description} · ${money(c.amount_cents)}`}))]} onChange={v=>{setCharge(v);setConfirmed(false)}} /></label>
      {!chargeId&&<div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm">Charge reference<input value={reference} onChange={e=>{setReference(e.target.value);setConfirmed(false)}} maxLength={100} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label>
        <label className="text-sm">Description<input value={description} onChange={e=>{setDescription(e.target.value);setConfirmed(false)}} maxLength={120} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label>
        <label className="text-sm">Charge date<input type="date" value={date} onChange={e=>{setDate(e.target.value);setConfirmed(false)}} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label>
        <label className="text-sm">Full amount<MoneyInput value={amount} onChange={v=>{setAmount(v);setConfirmed(false)}} className="mt-1 min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label>
      </div>}
      <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} className="mt-1" />This debit needs coverage in checking and has not already been funded.</label>
      <button type="button" disabled={busy||!confirmed} onClick={()=>void save()} className="min-h-11 rounded-xl bg-blue-700 px-4 font-semibold text-white disabled:opacity-45">Add funding draft</button>
      <p className="text-xs text-slate-500">One draft covers the full charge. You review it before bank preparation.</p>
    </>}
    {!busy&&!options.length&&<p>No credit-line-to-checking routes are enabled. Add a route in Monitoring settings.</p>}
  </BankDialog>
}
