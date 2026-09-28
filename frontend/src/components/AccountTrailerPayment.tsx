import {useEffect,useState} from 'react'
import {bankProfilesApi} from '../services/api'
import {financeApi,financeError,dollars} from '../services/finance'
import EquipmentPayments,{type PaymentAsset} from './EquipmentPayments'

type Checking={account_id:string|null;name:string;last4:string}
type Route={id:string;source_id:string;destination_id:string;enabled:boolean}
export type TrailerPaymentIntent={asset_id:number;name:string;amount:string}
const input='mt-1 block min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm'
const button='min-h-11 rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white disabled:opacity-45'
export default function AccountTrailerPayment({tenantId,accountId,accountName,profileId,profileName,checking,routes,target,busy,onStart,onRoutesChanged}:{tenantId:number;accountId:string;accountName:string;profileId:string;profileName:string;checking:Checking[];routes:Route[];target?:string;busy:boolean;onStart:(routeId:string,payment:TrailerPaymentIntent)=>void;onRoutesChanged:()=>void}){
 const [assets,setAssets]=useState<PaymentAsset[]>([]),[selected,setSelected]=useState(target||''),[source,setSource]=useState(''),[confirmed,setConfirmed]=useState(false),[saving,setSaving]=useState(false),[error,setError]=useState(''),[loaded,setLoaded]=useState(false),[version,setVersion]=useState(0)
 useEffect(()=>{let active=true;void financeApi.equipmentPayments(new Date().toLocaleDateString('en-CA')).then(r=>{if(active){setAssets(r.assets);setSelected(v=>v||String(r.assets.find((a:PaymentAsset)=>a.bank_account_id===accountId)?.id||''));setLoaded(true)}}).catch(e=>{if(active){setError(financeError(e));setLoaded(true)}});return()=>{active=false}},[accountId,version])
 const asset=assets.find(a=>String(a.id)===selected),linked=asset?.bank_account_id===accountId
 const candidates=checking.filter(a=>a.account_id)
 const sourceId=source||candidates.find(a=>routes.some(r=>r.enabled&&r.source_id===a.account_id&&r.destination_id===accountId))?.account_id||candidates[0]?.account_id||''
 const route=routes.find(r=>r.source_id===sourceId&&r.destination_id===accountId)
 const payment=asset?.due?.amount||asset?.monthly_payment||'0'
 async function link(){if(!asset)return;setSaving(true);setError('');try{await bankProfilesApi.request(tenantId,`/equipment/${asset.id}/account`,'put',{account_id:accountId});setAssets(v=>v.map(a=>a.id===asset.id?{...a,bank_account_id:accountId}:a))}catch(e){setError(financeError(e))}finally{setSaving(false)}}
 async function enableRoute(){setSaving(true);setError('');try{await bankProfilesApi.request(tenantId,route?`/routes/${route.id}`:'/routes',route?'put':'post',route?{enabled:true}:{profile_id:profileId,source_id:sourceId,destination_id:accountId,bank_route_confirmed:true});setConfirmed(false);onRoutesChanged()}catch(e){setError(financeError(e))}finally{setSaving(false)}}
 return <section aria-label="Trailer installment" className="space-y-4">
 <div><h3 className="font-semibold">Pay trailer installment</h3><p className="mt-1 text-sm text-slate-600">A dedicated payment to {accountName}, labeled with your trailer in ELIS.</p></div>
 {error&&<p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{error}</p>}
 {!loaded?<p role="status">Loading trailer plans…</p>:!assets.length?<p className="text-sm">Save a financed trailer plan first.</p>:<>
 <label className="block text-sm">Trailer<select className={input} value={selected} onChange={e=>{setSelected(e.target.value);setError('')}}><option value="">Choose trailer</option>{assets.map(a=><option key={a.id} value={a.id}>{a.name}{a.bank_account_id&&a.bank_account_id!==accountId?' · linked to another credit line':''}</option>)}</select></label>
 {asset&&<>
 {!linked?<div className="space-y-3 rounded-lg bg-blue-50 p-3 text-sm"><p>{asset.bank_account_id?'Change this trailer’s credit line to':'Use'} {accountName} for {asset.name}. Other borrowing on this account stays separate.</p><button type="button" disabled={saving||busy} className={button} onClick={()=>void link()}>{saving?'Saving…':'Use this credit line'}</button></div>:<>
 <div className="rounded-xl bg-blue-50 p-4"><p className="text-sm text-slate-600">{asset.due?'Planned payment':'Monthly plan'}</p><strong className="block text-2xl tabular-nums text-blue-900">{dollars(payment)}</strong><p className="mt-1 text-sm text-slate-600">{asset.due?`Statement due ${asset.due.due}`:'Due date not entered — add it from the lender statement below.'}</p></div>
 <label className="block text-sm">Pay from checking<select className={input} value={sourceId} onChange={e=>{setSource(e.target.value);setConfirmed(false)}}>{candidates.map(a=><option key={a.account_id} value={a.account_id!}>{a.name} · ••{a.last4}{routes.some(r=>r.enabled&&r.source_id===a.account_id&&r.destination_id===accountId)?'':' · route setup needed'}</option>)}</select></label>
 {!candidates.length?<p className="text-sm">Connect a checking account under this bank login first.</p>:!route?.enabled?<div className="space-y-3 rounded-lg border border-slate-200 p-3 text-sm"><p>Confirm this checking account can pay the credit line under the {profileName} bank login.</p><label className="flex items-start gap-2"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>I can make this transfer in Truliant using this login.</label><button type="button" className={button} disabled={!confirmed||saving||busy} onClick={()=>void enableRoute()}>Enable this payment route</button></div>:<button type="button" className={button} disabled={busy||saving} onClick={()=>onStart(route.id,{asset_id:asset.id,name:asset.name,amount:payment})}>{busy?'Checking available cash…':'Review trailer payment'}</button>}
 <p className="text-xs leading-5 text-slate-500">Next: check available cash and amount, prepare the bank form, then approve at your bank. This does not schedule a payment. Match the posted payment and its principal/interest split afterward.</p>
 <EquipmentPayments key={asset.id} selectedAsset={asset.id} onSaved={()=>setVersion(v=>v+1)}/>
 </>}
 </>}
 </>}
 </section>
}
