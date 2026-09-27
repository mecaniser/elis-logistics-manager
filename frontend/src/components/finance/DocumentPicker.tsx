import { useEffect, useRef, useState } from 'react'
import { dollars, financeApi, type Evidence, type Workspace } from '../../services/finance'
import { documentRows } from './documentRows'
import type { HistoryRow } from './historyTypes'
import type { RepairReviewRow } from '../repairs/repairReview'

export default function DocumentPicker({id,label,value,onChange,evidence,workspace,optional=false}:{id:string;label:string;value:string;onChange:(value:string)=>void;evidence:Evidence[];workspace:Workspace;optional?:boolean}) {
  const dialog=useRef<HTMLDialogElement>(null)
  const trigger=useRef<HTMLButtonElement>(null)
  const [open,setOpen]=useState(false)
  const [search,setSearch]=useState('')
  const [type,setType]=useState('all')
  const [repairs,setRepairs]=useState<RepairReviewRow[]>([])
  const [settlements,setSettlements]=useState<HistoryRow[]>([])
  const [status,setStatus]=useState('')
  const [attempt,setAttempt]=useState(0)
  useEffect(()=>{
    if(!open)return
    let active=true
    setStatus('Loading…')
    Promise.all([financeApi.repairHistory(new Date().toLocaleDateString('en-CA')),financeApi.history()]).then(([r,h])=>{if(active){setRepairs(r.rows);setSettlements(h.rows);setStatus('')}}).catch(()=>{if(active)setStatus('Details unavailable. Try again.')})
    return ()=>{active=false}
  },[open,attempt])
  useEffect(()=>{if(open)dialog.current?.showModal();else dialog.current?.close()},[open])
  const rows=documentRows(evidence,repairs,settlements,workspace.legacy_repairs)
  const selected=rows.find(r=>r.doc.id===value)
  const close=()=>{setOpen(false);trigger.current?.focus()}
  const select=(next:string)=>{onChange(next);close()}
  const filtered=rows.filter(r=>(type==='all'||type===r.category)&&[r.title,r.categoryLabel,r.date,r.amount,r.equipment,r.repair?.description,r.doc.filename,r.doc.source_key].join(' ').toLowerCase().includes(search.trim().toLowerCase()))
  return <div className="document-picker">
    <label id={`${id}-label`} htmlFor={id}>{label}{optional&&<span className="finance-muted"> (optional)</span>}</label>
    <button ref={trigger} id={id} type="button" className="document-picker-trigger" aria-haspopup="dialog" aria-expanded={open} aria-labelledby={`${id}-label ${id}-value`} onClick={()=>{setSearch('');setType('all');setOpen(true)}}><span id={`${id}-value`}>{selected?`${selected.title}${selected.date?` · ${selected.date}`:''}`:'Select document…'}</span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg></button>
    <dialog ref={dialog} className="document-picker-dialog" aria-labelledby={`${id}-title`} onCancel={close} onClose={()=>setOpen(false)}>
      <header><h2 id={`${id}-title`}>{label}</h2><button type="button" className="finance-secondary" onClick={close}>Close</button></header>
      <div className="document-filters"><label>Find a document<input autoFocus type="search" value={search} placeholder="Vendor, date, amount or VIN" onKeyDown={e=>{if(e.key==='Enter')e.preventDefault()}} onChange={e=>setSearch(e.target.value)}/></label><label>Document type<select value={type} onChange={e=>setType(e.target.value)}><option value="all">All documents</option><option value="repair">Repairs</option><option value="settlement">Settlements</option><option value="confirmation">Payment confirmations</option><option value="other">Other documents</option></select></label></div>
      <div className="document-picker-status"><span role="status">{status||`${filtered.length} documents`}</span>{status.includes('unavailable')&&<button type="button" className="finance-secondary" onClick={()=>setAttempt(n=>n+1)}>Retry</button>}{optional&&value&&<button type="button" className="finance-secondary" onClick={()=>select('')}>Clear selection</button>}</div>
      <div className="document-picker-results">{filtered.map((r,index)=><button type="button" key={r.doc.id} className="document-picker-option" aria-pressed={value===r.doc.id} onClick={()=>select(r.doc.id)}><span><strong>{r.title}</strong><small>{r.categoryLabel} · {r.date||'Undated'}{r.equipment?` · ${r.equipment}`:''}</small><small>{r.repair?.description?.slice(0,80)||(!/^[a-f0-9]{32,}\./.test(r.doc.filename)?r.doc.filename:'Saved attachment')} · File {evidence.findIndex(e=>e.id===r.doc.id)+1}{r.doc.supersedes_id?' · Amended':''}</small></span><span className="document-picker-value">{r.amount!=null&&<><strong>{dollars(r.amount)}</strong><small>{r.category==='settlement'?'Remainder':r.category==='confirmation'?'Recorded payment':'Repair cost'}</small></>}{value===r.doc.id&&<small>Selected</small>}<span className="sr-only">Result {index+1}</span></span></button>)}{!filtered.length&&<p>No matching documents.</p>}</div>
    </dialog>
  </div>
}
