import {useState} from 'react'
import {financeApi, financeError} from '../services/finance'
import MoneyInput from './MoneyInput'
const input='block w-full rounded-md border border-slate-300 px-3 py-2 min-h-11 bg-white'
export default function EquipmentStatementImport({onSaved}:{onSaved:()=>void}) {
 const [file,setFile]=useState<File|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('')
 const [account,setAccount]=useState(''),[accounts,setAccounts]=useState<{id:string;name:string}[]>([])
 const [name,setName]=useState(''),[start,setStart]=useState(''),[end,setEnd]=useState(''),[opening,setOpening]=useState(''),[closing,setClosing]=useState('')
 const [columns,setColumns]=useState({date:'Date',amount:'Amount',description:'Description',id:'ID'}),[reviewed,setReviewed]=useState(false)
 const [loaded,setLoaded]=useState(false)
 async function load(){try{const w=await financeApi.workspace(new Date().toLocaleDateString('en-CA'));setAccounts(w.accounts.filter(a=>a.account_type==='bank').map(a=>({id:String(a.id),name:String(a.name)})));setLoaded(true)}catch(e){setMessage(financeError(e))}}
 async function save(e:React.FormEvent){e.preventDefault();if(!file||!reviewed)return;setBusy(true);setMessage('');try{
   const doc=await financeApi.upload(file,`bank-statement:${file.name}`,'')
   let aid=account
   if(!aid){const a=await financeApi.command(start,{kind:'account',name,account_type:'bank'},crypto.randomUUID());aid=a.id;setAccount(aid);setAccounts(prev=>[...prev,{id:aid,name}])}
   const mapping=await financeApi.command(start,{kind:'csv_mapping',name:'Equipment payment statement',date_column:columns.date,amount_column:columns.amount,description_column:columns.description,id_column:columns.id,date_format:'%Y-%m-%d',invert_sign:false},crypto.randomUUID())
   await financeApi.command(end,{kind:'statement',account_id:aid,evidence_id:doc.id,mapping_id:mapping.id,start,end,opening:Number(opening.replace(/[$,]/g,'')).toFixed(2),closing:Number(closing.replace(/[$,]/g,'')).toFixed(2)},crypto.randomUUID())
   setMessage('Statement imported. Select its payment below.');onSaved()
 }catch(error){setMessage(financeError(error))}finally{setBusy(false)}}
 return <div className="rounded-lg border border-slate-200 p-4 mt-3">{!loaded?<button type="button" onClick={()=>void load()} className="text-blue-700 min-h-11">Choose the bank account for this statement</button>:<form onSubmit={e=>void save(e)} className="space-y-3">
 <p className="text-sm text-slate-600">Upload the paying bank account’s posted transactions. Use the same account for future imports. CSV dates must be YYYY-MM-DD and payments negative. Opening balance + transactions must equal closing balance.</p>
 <div className="grid sm:grid-cols-2 gap-3"><label className="text-sm">Paying account<select className={input} value={account} onChange={e=>setAccount(e.target.value)}><option value="">Add bank account…</option>{accounts.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>{!account&&<label className="text-sm">Account name + last four digits<input required className={input} value={name} onChange={e=>setName(e.target.value)}/></label>}
 <label className="text-sm">Statement starts<input required type="date" className={input} value={start} onChange={e=>setStart(e.target.value)}/></label><label className="text-sm">Statement ends<input required type="date" className={input} value={end} onChange={e=>setEnd(e.target.value)}/></label>
 <label className="text-sm">Opening balance<MoneyInput required allowNegative className={input} value={opening} onChange={setOpening}/></label><label className="text-sm">Closing balance<MoneyInput required allowNegative className={input} value={closing} onChange={setClosing}/></label>
 {Object.entries(columns).map(([key,value])=><label key={key} className="text-sm">CSV {key} column<input required className={input} value={value} onChange={e=>setColumns(c=>({...c,[key]:e.target.value}))}/></label>)}</div>
 <label className="block text-sm">Bank CSV<input type="file" accept=".csv,text/csv" required onChange={e=>setFile(e.target.files?.[0]||null)} className="block mt-2"/></label>
 <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={e=>setReviewed(e.target.checked)}/>This file contains posted transactions, with no pending payments or duplicate rows.</label>
 <button disabled={busy||!reviewed} className="rounded-md bg-blue-700 text-white px-4 py-2 min-h-11 disabled:opacity-50">{busy?'Importing…':'Import statement'}</button></form>}{message&&<p role="status" className="text-sm mt-2">{message}</p>}</div>
}
