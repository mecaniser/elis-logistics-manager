import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTenant } from '../contexts/tenantState'
import { dollars, financeApi, financeError } from '../services/finance'
import { HistoryReport } from '../components/finance/historyTypes'
import HistoryTrend from '../components/finance/HistoryTrend'
import './Finance.css'
import './OwnerDashboard.css'
const text = (s: string) => s.replace(/_/g, ' ')
export default function SettlementHistory() {
  const {currentTenant} = useTenant()
  const [params] = useSearchParams()
  const [report,setReport] = useState<HistoryReport | null>(null)
  const [error,setError] = useState('')
  const [asset,setAsset] = useState(params.get('asset') || 'all')
  const [status,setStatus] = useState(params.get('status')==='missing_source'?'missing_source':'all')
  const [query,setQuery] = useState(params.get('id') || '')
  const [visibleCount,setVisibleCount] = useState(20)
  const [retry,setRetry] = useState(0)
  const [attaching,setAttaching] = useState<number|null>(null)
  const [attachmentNotice,setAttachmentNotice] = useState('')
  useEffect(()=>{if(params.get('status')==='missing_source')setStatus('missing_source')},[params])
  useEffect(()=>{let active=true;setReport(null);setError('');financeApi.history().then(r=>{if(active)setReport(r)}).catch(e=>{if(active)setError(financeError(e))});return()=>{active=false}},[currentTenant,retry])
  const rows = report?.rows.filter(r => (asset==='all'||String(r.asset_id)===asset) && (status==='all'||(status==='cost' ? r.issues.some(x=>['fuel_spending','driver_rate','payout_difference','stored_difference','repeated_load','expense_spike','source_row_review','load_total','fuel_total'].includes(x.code)) : r.status===status)) && (!query || `${r.id} ${r.source_ref||''} ${r.name} ${r.date} ${r.provider}`.toLowerCase().includes(query.toLowerCase()))) || []
  async function download(id: string) { try {await financeApi.download(`/evidence/${id}/original`,'settlement-original.pdf')}catch(e){setError(financeError(e))} }
  async function attachOriginal(id: number, file: File | undefined) {
    if (!file) return
    setAttaching(id);setAttachmentNotice('')
    try {
      const result = await financeApi.upload(file,`legacy-settlement:${id}`,'')
      setAttachmentNotice(result.duplicate ? 'This PDF was already saved. Check its existing record before linking it here.' : `Original PDF saved for settlement ${id}. Review the refreshed comparison before posting.`)
      setRetry(value=>value+1)
    } catch(e) {setAttachmentNotice(`Settlement ${id}: ${financeError(e)}`)}
    finally {setAttaching(null)}
  }
  return <div className="finance-app owner-dashboard"><header className="finance-header"><div><h1>Settlement reconciliation</h1><p className="finance-help">Follow every original from freight and driver pay to fuel, deductions and payout.</p></div><Link className="finance-secondary" to="/settlements">Back to settlements</Link></header>
    {error && <div role="alert" className="finance-error">{error}<button className="finance-secondary" onClick={()=>setRetry(retry+1)}>Retry</button></div>}
    {!report&&!error&&<p role="status">Checking settlement history…</p>}
    {report&&report.tenant_id===currentTenant?.id&&<>
      <section className="owner-panel"><h2>History coverage</h2><p className="finance-help">{report.period.start} through {report.period.end} · Statement-date basis · Review in progress</p><div className="owner-coverage"><span><strong>{report.coverage.source_records}</strong> source records</span><span><strong>{report.coverage.arithmetic_matched}</strong> arithmetic matched</span><span><strong>{report.coverage.originals_need_review}</strong> originals need review</span><span><strong>{report.coverage.missing_sources}</strong> originals unavailable</span></div><p className="finance-help">{report.coverage.derived_allocations_excluded} trailer allocations excluded from additional revenue. Driver pay means the amount on the settlement; bank receipt has not been verified.</p></section>
      <section className="owner-panel"><HistoryTrend history={report} /></section>
      <section className="owner-panel" id="review-records"><h2>Review each settlement</h2><p className="finance-help">If you have an original PDF for a saved record, open that record and attach it. We preserve the PDF, compare it with the saved amounts and flag differences. A missing original can remain visible while you search for it; no amount is assumed to be zero.</p><div className="owner-filters"><label>Equipment<select value={asset} onChange={e=>setAsset(e.target.value)}><option value="all">All equipment</option>{[...new Map(report.rows.map(r=>[r.asset_id,r.name])).entries()].map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label><label>Review status<select value={status} onChange={e=>setStatus(e.target.value)}><option value="all">All records</option><option value="cost">Cost and amount exceptions</option><option value="arithmetic_matched">Arithmetic matched</option><option value="needs_review">Mapping or source review</option><option value="missing_source">Original unavailable</option></select></label><label>Find a statement<input type="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Date, carrier, reference…" /></label></div><p className="finance-help">Showing {Math.min(visibleCount, rows.length)} of {rows.length} matching records. Expand a record for reconciliation and supporting rows.</p>
      {attachmentNotice&&<p className="history-attachment-notice" role="status">{attachmentNotice}</p>}
      {rows.length===0&&<p className="finance-empty">No records match these filters.</p>}
      {rows.slice(0,visibleCount).map(r=><details className="history-record" key={r.id} open={params.get('id')===String(r.id)&&query===params.get('id') ? true : undefined}><summary><span><strong>{r.name}</strong><small>{r.date} · {r.source_ref||r.provider}</small></span><span><small>Statement payout</small><strong>{dollars(r.remainder)}</strong></span><span className={`finance-status ${r.status==='arithmetic_matched'?'is-ready':''}`}>{r.status==='arithmetic_matched'?'Arithmetic matched':r.status==='missing_source'?'Original unavailable':'Needs review'}</span><svg className="history-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m9 5 7 7-7 7" /></svg></summary>
        <div className="history-body"><p className="finance-help">{r.basis==='source_statement'?'Amounts extracted from the original PDF.':'Stored amounts only; source mapping has not been verified.'} Deposit matching and driver payment verification remain open.</p>
        <div className="finance-table-scroll"><table><caption className="sr-only">Settlement {r.source_ref||r.id} calculation</caption><thead><tr><th>Freight</th><th>Carrier</th><th>Driver</th><th>Fuel</th><th>Calculated payout</th><th>Unexplained difference</th></tr></thead><tbody><tr>{[r.freight,r.carrier,r.driver_pay,r.fuel,r.calculated_remainder,r.difference].map((v,i)=><td key={i}>{dollars(v)}</td>)}</tr></tbody></table></div>
        <div className="owner-metrics"><span>Reported miles <strong>{r.miles||'Not verified'}</strong></span><span>Gallons purchased <strong>{r.gallons_purchased||'Not verified'}</strong></span><span>Fuel cost / mile <strong>{r.fuel_per_mile?`$${r.fuel_per_mile}`:'Not established'}</strong></span><span>Measured MPG <strong>Not established</strong></span></div>
        {r.issues.length>0&&<ul className="owner-issues">{r.issues.map((i,n)=><li key={n}><strong>{i.title}</strong><p>{i.detail}</p></li>)}</ul>}
        <details className="owner-details"><summary>All deductions and internal allocations</summary><dl className="finance-waterfall">{Object.entries(r.categories).map(([k,v])=><div key={k}><dt>{text(k)}</dt><dd>{dollars(v)}</dd></div>)}<div><dt>Internal trailer allocation</dt><dd>{dollars(r.trailer_allocation)}</dd></div><div><dt>Repair funding target, not confirmed savings</dt><dd>{dollars(r.repair_target)}</dd></div></dl></details>
        {!!r.differences.length&&<div className="finance-table-scroll"><table><caption>Saved record versus original</caption><thead><tr><th>Field</th><th>Saved</th><th>Original</th><th>Difference</th></tr></thead><tbody>{r.differences.map(d=><tr key={d.field}><td>{text(d.field)}</td><td>{d.stored}</td><td>{d.source}</td><td>{d.difference}</td></tr>)}</tbody></table></div>}
        {!!r.loads.length&&<details className="owner-details"><summary>{r.loads.length} load rows</summary><div className="finance-table-scroll"><table><thead><tr><th>Load</th><th>Pickup</th><th>Delivery</th><th>Loaded miles</th><th>Empty miles</th><th>Freight</th></tr></thead><tbody>{r.loads.map((l,i)=><tr key={i}><td>{l.load_id}</td><td>{l.pickup}</td><td>{l.delivery}</td><td>{l.loaded_miles ?? 'Not stated'}</td><td>{l.empty_miles ?? 'Not stated'}</td><td>{dollars(l.freight_gross)}</td></tr>)}</tbody></table></div></details>}
        {!!r.fuel_rows.length&&<details className="owner-details"><summary>{r.fuel_rows.length} fuel purchase rows</summary><div className="finance-table-scroll"><table><thead><tr><th>Date</th><th>Location</th><th>Product</th><th>Gallons</th><th>Charge</th></tr></thead><tbody>{r.fuel_rows.map((f,i)=><tr key={i}><td>{f.date}</td><td>{f.location}</td><td>{f.product==='unknown'?'Unclassified':f.product}</td><td>{f.gallons||'Not stated'}</td><td>{dollars(f.amount)}</td></tr>)}</tbody></table></div></details>}
        {r.evidence_id?<button className="finance-secondary" onClick={()=>void download(r.evidence_id!)}>Download original PDF</button>:r.provider==='Manual Entry'?<p className="finance-help">This manual entry has no carrier settlement PDF. Review its <Link to="/finance/assets">equipment records</Link> instead.</p>:<label className="history-original-upload">Attach original PDF for settlement {r.id}<input type="file" accept="application/pdf,.pdf" disabled={attaching===r.id} onChange={event=>{void attachOriginal(r.id,event.target.files?.[0]);event.target.value=''}} /><small>{attaching===r.id?'Saving and checking the document…':'Up to 20 MB. This adds source evidence; it does not post or replace the saved settlement.'}</small></label>}
        </div></details>)}
      {rows.length > visibleCount && <button className="finance-secondary" onClick={()=>setVisibleCount(n=>n+20)}>Show 20 more records</button>}
      </section><footer className="finance-footer">{report.limitations.join(' ')}</footer>
    </>}
  </div>
}
