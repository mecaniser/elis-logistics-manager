import { documentRows } from './documentRows'
import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { dollars, financeApi, type Evidence, type Workspace } from '../../services/finance'
import type { HistoryRow } from './historyTypes'
import type { RepairReviewRow } from '../repairs/repairReview'

export default function SupportingDocuments({evidence,asOf,children,legacyRepairs}:{evidence:Evidence[];asOf:string;children:ReactNode;legacyRepairs:Workspace['legacy_repairs']}) {
  const [open,setOpen]=useState(false)
  const [expanded,setExpanded]=useState<string|null>(null)
  const [search,setSearch]=useState('')
  const [type,setType]=useState('all')
  const [limit,setLimit]=useState(20)
  const [repairs,setRepairs]=useState<RepairReviewRow[]>([])
  const [settlements,setSettlements]=useState<HistoryRow[]>([])
  const [status,setStatus]=useState('')
  const [retry,setRetry]=useState(0)
  useEffect(()=>{
    if(!open)return
    let active=true
    setStatus('Loading document details…')
    Promise.all([financeApi.repairHistory(asOf),financeApi.history()]).then(([r,h])=>{if(active){setRepairs(r.rows);setSettlements(h.rows);setStatus('')}}).catch(()=>{if(active)setStatus('Some document details could not load. Your saved files are still available.')})
    return ()=>{active=false}
  },[open,asOf,retry])
  const rows=documentRows(evidence,repairs,settlements,legacyRepairs)
  const filtered=rows.filter(r=>(type==='all'||r.category===type)&&[r.title,r.categoryLabel,r.date,r.amount,r.equipment,r.repair?.description,r.doc.filename,r.doc.source_key].join(' ').toLowerCase().includes(search.toLowerCase()))
  const chevron=<svg className="document-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>
  return <section className="finance-section supporting-documents"><details open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary>{chevron}<strong>Supporting documents</strong><span>{evidence.length} records · All dates</span></summary>
    <div className="document-filters"><label>Find a document<input type="search" value={search} placeholder="Vendor, date, amount or truck" onChange={e=>{setSearch(e.target.value);setLimit(20)}}/></label><label>Document type<select value={type} onChange={e=>{setType(e.target.value);setLimit(20)}}><option value="all">All documents</option><option value="repair">Repair documents</option><option value="settlement">Settlements</option><option value="confirmation">Payment confirmations</option><option value="other">Other records</option></select></label></div>
    {status&&<p role="status">{status}{status.includes('could not')&&<button type="button" className="finance-secondary" onClick={()=>setRetry(n=>n+1)}>Try again</button>}</p>}
    <p className="document-count">{Math.min(limit,filtered.length)} of {filtered.length} records</p>
    {!filtered.length&&<p>No matching documents.</p>}
    {filtered.slice(0,limit).map(r=>{
      const amountLabel=r.category==='settlement'?'Remainder':r.category==='confirmation'?'Recorded payment':r.related.length>1?'First repair cost':'Repair cost'
      const isExpanded=expanded===r.doc.id
      return <article key={r.doc.id} className="supporting-record">
        <div className="document-identity"><h3 title={r.title}>{r.title}</h3><p><span className="document-kind">{r.categoryLabel}</span> · {r.date||'Date unknown'}{r.equipment?` · ${r.equipment}`:''}{r.doc.supersedes_id?' · Amended':''}</p></div>
        <div className="document-amount">{r.amount!=null&&<><strong>{dollars(r.amount)}</strong><small>{amountLabel}</small></>}</div>
        <div className="document-actions">
          {r.action&&<span className="document-review" title={r.action}>Review</span>}
          {(r.settlement||r.repair)&&<Link className="finance-secondary" aria-label={`Open ${r.settlement?'settlement':'repair'}: ${r.title}`} to={r.settlement?`/settlements/reconciliation?asset=${r.settlement.asset_id}&id=${r.settlement.id}#review-records`:`/repairs?repair=${r.repair?.legacy_id}`}>Open</Link>}
          <button type="button" className="finance-secondary document-icon" aria-label={`Download ${r.categoryLabel.toLowerCase()}: ${r.title}`} title="Download" onClick={()=>void financeApi.download(`/evidence/${r.doc.id}/original`,r.doc.filename).catch(()=>setStatus('Download failed. Please try again.'))}><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg></button>
          <button type="button" className="finance-secondary document-icon" aria-label={`Details: ${r.title}`} aria-expanded={isExpanded} aria-controls={`document-${r.doc.id}`} title="Details" onClick={()=>setExpanded(isExpanded?null:r.doc.id)}>{chevron}</button>
        </div>
        {isExpanded&&<div id={`document-${r.doc.id}`} className="document-technical">
          {r.repair&&<p>{r.repair.description}</p>}{r.related.length>1&&<p>Supports {r.related.length} repairs.</p>}{r.action&&<p>{r.action}</p>}{r.category==='confirmation'&&<p>Your payment confirmation; not a bank receipt.</p>}
          <p>{r.doc.filename}</p><p>Reference: {r.doc.source_key}</p><details><summary>{chevron}Extracted data</summary><pre>{JSON.stringify(r.doc.extracted,null,2)}</pre></details>
        </div>}
      </article>
    })}
    {filtered.length>limit&&<button type="button" className="finance-secondary" onClick={()=>setLimit(n=>n+20)}>Show 20 more</button>}
    <details className="document-upload"><summary>{chevron}Add supporting document</summary>{children}</details>
  </details></section>
}
