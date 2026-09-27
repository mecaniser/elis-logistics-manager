import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { dollars, financeApi, type Evidence, type Workspace } from '../../services/finance'
import type { HistoryRow } from './historyTypes'
import type { RepairReviewRow } from '../repairs/repairReview'

export default function SupportingDocuments({evidence,asOf,children,legacyRepairs}:{evidence:Evidence[];asOf:string;children:ReactNode;legacyRepairs:Workspace['legacy_repairs']}) {
  const [open,setOpen]=useState(false)
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
  const rows=evidence.map(doc=>{
    const confirmation=doc.source_key.startsWith('repair-confirmation:')
    const related=repairs.filter(r=>r.evidence.some(e=>e.id===doc.id)||r.confirmation?.id===doc.id||(confirmation&&r.legacy_id===Number(doc.source_key.split(':')[1])))
    const repair=related[0]
    const settlement=settlements.find(s=>s.evidence_id===doc.id||(doc.source_key.startsWith('legacy-settlement:')&&s.id===Number(doc.source_key.split(':')[1])))
    const category=confirmation?'confirmation':doc.source_key.startsWith('recovered-repair:')||repair?'repair':settlement||doc.source_key.startsWith('legacy-settlement:')?'settlement':'other'
    const categoryLabel={confirmation:'Your payment confirmation',repair:'Repair document',settlement:'Settlement PDF',other:'Supporting document'}[category]
    const title=(confirmation&&typeof doc.extracted.payee==='string'?doc.extracted.payee:null)||repair?.payee.name||settlement?.provider||({confirmation:'Saved repair payment details',repair:'Repair invoice or receipt',settlement:'Carrier settlement',other:'Supporting document'}[category])
    const date=confirmation&&typeof doc.extracted.paid_date==='string'?doc.extracted.paid_date:repair?.date||settlement?.date
    const amount=confirmation?doc.extracted.paid_amount:repair?.recorded_cost??settlement?.remainder
    const assetId=legacyRepairs.find(r=>r.id===repair?.legacy_id)?.asset_id
    const repairVin=settlements.find(r=>r.asset_id===assetId&&r.vin)?.vin
    const equipment=repairVin?`VIN …${repairVin.slice(-6)}`:settlement?.vin?`VIN …${settlement.vin.slice(-6)}`:repair?.asset_name||settlement?.name
    const action=repair?.issues.some(i=>['invoice_amount_difference','conflicting_invoice_totals'].includes(i))?'Invoice amount differs from saved repair. Review it in Repairs.':settlement?.status==='needs_review'?'Settlement amounts need review.':null
    return {doc,category,categoryLabel,title,date,amount,equipment,repair,settlement,action,related}
  })
  const filtered=rows.filter(r=>(type==='all'||r.category===type)&&[r.title,r.categoryLabel,r.date,r.amount,r.equipment,r.repair?.description,r.doc.filename,r.doc.source_key].join(' ').toLowerCase().includes(search.toLowerCase()))
  return <section className="finance-section supporting-documents"><details open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary><strong>Supporting documents</strong><span>{evidence.length} saved records · Open only when you need a source</span></summary>
    <p className="finance-help">Invoices, settlement PDFs and your saved payment confirmations. These are supporting records, not a new to-do list. This archive covers all dates for the selected business. A saved file does not confirm payment or reconciliation.</p>
    <div className="document-filters"><label>Find a document<input type="search" value={search} placeholder="Vendor, date, amount or truck" onChange={e=>{setSearch(e.target.value);setLimit(20)}}/></label><label>Document type<select value={type} onChange={e=>{setType(e.target.value);setLimit(20)}}><option value="all">All documents</option><option value="repair">Repair documents</option><option value="settlement">Settlements</option><option value="confirmation">Payment confirmations</option><option value="other">Other records</option></select></label></div>
    {status&&<p role="status">{status}{status.includes('could not')&&<button type="button" className="finance-secondary" onClick={()=>setRetry(n=>n+1)}>Try again</button>}</p>}
    <p className="finance-help">Showing {Math.min(limit,filtered.length)} of {filtered.length} matching records.</p>
    {!filtered.length&&<p>No matching documents. Try another name or document type.</p>}
    {filtered.slice(0,limit).map(r=><article key={r.doc.id} className="supporting-record"><div><span className="document-kind">{r.categoryLabel}{r.doc.supersedes_id?' · Updated version':''}</span><h3>{r.title}</h3><p>{r.date||'Date not identified'}{r.amount!=null?` · ${dollars(r.amount)}${r.category==='settlement'?' statement remainder':r.category==='confirmation'?' recorded payment':r.related.length>1?' first linked repair cost':' saved repair cost'}`:''}{r.equipment?` · ${r.equipment}`:''}</p>{r.repair&&<p className="finance-muted">{r.repair.description}</p>}{r.related.length>1&&<p>Supports {r.related.length} repair records.</p>}<p className="finance-help">{r.action|| (r.category==='confirmation'?'Saved record of your answers; not a bank receipt.':'Saved for reference.')}</p></div><div className="document-actions"><button type="button" className="finance-secondary" onClick={()=>void financeApi.download(`/evidence/${r.doc.id}/original`,r.doc.filename).catch(()=>setStatus('Download failed. Please try again.'))}>{r.category==='confirmation'?'Download confirmation':'Download document'}</button>{r.settlement&&<Link className="finance-secondary" to={`/settlements/reconciliation?asset=${r.settlement.asset_id}&id=${r.settlement.id}#review-records`}>Open settlement</Link>}{r.repair&&<Link className="finance-secondary" to={`/repairs?repair=${r.repair.legacy_id}`}>Open repair</Link>}</div><details className="document-technical"><summary>File details</summary><p>{r.doc.filename}</p><p>Internal reference: {r.doc.source_key}</p><pre>{JSON.stringify(r.doc.extracted,null,2)}</pre></details></article>)}
    {filtered.length>limit&&<button type="button" className="finance-secondary" onClick={()=>setLimit(n=>n+20)}>Show 20 more</button>}
    <details className="document-upload"><summary>Add another supporting document</summary><p className="finance-help">Use Settlements or Repairs for normal uploads. Use this option for additional supporting files or a replacement document.</p>{children}</details>
  </details></section>
}
