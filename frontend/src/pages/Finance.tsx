import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import OwnerOverview from '../components/finance/OwnerOverview'
import { useTenant } from '../contexts/tenantState'
import CommandForm from '../components/finance/CommandForm'
import { actions } from '../components/finance/commandFields'
import { Context, Evidence, Event, RecordData, Report, Workspace, dollars, financeApi, financeError } from '../services/finance'
import './Finance.css'

const tabs = [['home', 'Overview'], ['settlements', 'Settlements'], ['assets', 'Assets'], ['repairs', 'Repairs'], ['money', 'Money'], ['accounting', 'Accounting'], ['connections', 'Connections']]
const today = () => new Date().toLocaleDateString('en-CA')
function periodStart(period: string) { const d = new Date(); if (period === 'week') d.setDate(d.getDate() - (d.getDay() + 6) % 7); else if (period === 'month') d.setDate(1); else { d.setMonth(0); d.setDate(1) } return d.toLocaleDateString('en-CA') }
function label(key: string) { return key.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()) }
function DataTable({rows, columns}: {rows: RecordData[]; columns: string[]}) { return rows.length ? <div className="finance-table-scroll"><table><thead><tr>{columns.map(c => <th key={c}>{label(c)}</th>)}</tr></thead><tbody>{rows.map((r, i) => <tr key={String(r.id || i)}>{columns.map(c => <td key={c}>{r[c] === null || r[c] === undefined ? 'Not established' : typeof r[c] === 'object' ? JSON.stringify(r[c]) : String(r[c])}</td>)}</tr>)}</tbody></table></div> : <p className="finance-empty">No records in this view yet.</p> }
function CashView({cash}: {cash: Report['owner_cash']}) { return <section className="finance-cash"><div><h2>Available to owner</h2><p className="finance-help">Cash position as of {cash.as_of}. Protected money stays in the business.</p><p className="finance-cash-value">{dollars(cash.available)}</p><span className={`finance-status ${cash.status === 'reconciled' ? 'is-ready' : ''}`}>{cash.status === 'reconciled' ? 'Reconciled cash' : 'Provisional · evidence needed'}</span>{cash.available !== null && Number(cash.available) < 0 && <p className="finance-error">Funding shortfall — no cash is available for an owner withdrawal.</p>}</div><dl className="finance-waterfall">{[['Business bank + cash on hand', cash.business_cash], ['Protected repair & capital', cash.protected_reserves], ['Uncovered bills', cash.uncovered_bills], ['Owner reimbursement', cash.owner_reimbursement], ['Card balances owed', cash.card_obligations], ['Additional committed financing', cash.committed_financing]].map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{dollars(value)}</dd></div>)}</dl>{cash.issues.length > 0 && <div className="finance-cash-notes">{cash.issues.map(issue => <p key={issue}>{issue}</p>)}<Link to="/finance/money">Reconcile accounts</Link></div>}</section> }

export default function Finance() {
  const {section = 'home'} = useParams()
  const [searchParams] = useSearchParams()
  const advancedRepairs = section !== 'repairs' || searchParams.get('advanced') === '1'
  const {currentTenant} = useTenant()
  const [start, setStart] = useState(() => periodStart('week'))
  const [end, setEnd] = useState(today)
  const [asOf, setAsOf] = useState(today)
  const requestSequence = useRef(0)
  const [data, setData] = useState<{context: Context; workspace: Workspace; evidence: Evidence[]; events: Event[]; report: Report} | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [actionIndex, setActionIndex] = useState(0)
  const [documentSource, setDocumentSource] = useState('')
  const [replacement, setReplacement] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState('')
  const [uploadBusy, setUploadBusy] = useState(false)
  const [reconstructionStatus, setReconstructionStatus] = useState('')
  const [motiveStatus, setMotiveStatus] = useState('')
  const load = useCallback(async () => {
    if (!currentTenant) return
    const sequence = ++requestSequence.current
    setLoading(true); setError('')
    try { const [context, workspace, evidence, events, report] = await Promise.all([financeApi.context(), financeApi.workspace(asOf), financeApi.evidence(), financeApi.events(), financeApi.report(start, end, asOf)]); if (sequence === requestSequence.current) setData({context, workspace, evidence, events, report}) } catch (e) { if (sequence === requestSequence.current) setError(financeError(e)) } finally { if (sequence === requestSequence.current) setLoading(false) }
  }, [currentTenant, start, end, asOf])
  useEffect(() => { void load() }, [load])
  useEffect(() => { setActionIndex(0) }, [section])
  async function upload(e: FormEvent<HTMLFormElement>) { e.preventDefault(); if (!file) return; setUploadBusy(true); setUploadStatus(''); try { const result = await financeApi.upload(file, documentSource, replacement); setUploadStatus(result.duplicate ? 'This document is already preserved. Its existing version is available below.' : 'Original preserved. Review extracted details before posting.'); await load() } catch (e) { setUploadStatus(financeError(e)) } finally { setUploadBusy(false) } }
  async function fetchMotive(e: FormEvent<HTMLFormElement>) { e.preventDefault(); const f = new FormData(e.currentTarget); setMotiveStatus('Fetching read-only evidence…'); try { await financeApi.motive({asset_id: Number(f.get('asset')), vehicle_id: Number(f.get('vehicle')), start: String(f.get('start')), end: String(f.get('end'))}); setMotiveStatus('Motive evidence saved below. Verify vehicle and odometer interval before recording travel.'); await load() } catch (e) { setMotiveStatus(financeError(e)) } }
  async function reconstruct() {
    if (!data) return
    setReconstructionStatus('Preserving historical source documents…')
    try {
      const ids = data.report.legacy_comparison.rows.filter(r => !data.evidence.some(e => e.source_key === `legacy-settlement:${r.legacy_id}`)).map(r => Number(r.legacy_id))
      const results: {status: string}[] = []
      for (let i = 0; i < ids.length; i += 20) { const response = await financeApi.reconstruct(ids.slice(i, i + 20)); results.push(...response.results) }
      await load()
      setReconstructionStatus(`${results.filter(r => r.status === 'preserved_for_review').length} originals preserved for review; ${results.filter(r => r.status === 'gap').length} sources need re-upload. Existing accounting totals were preserved.`)
    } catch (e) { setReconstructionStatus(financeError(e)) }
  }
  async function download(draft: boolean) { if (!data) return; try { await financeApi.download(`/report-runs/${data.report.id}/package?draft=${draft}`, `elis-${draft ? 'draft' : 'accountant'}-${end}.zip`) } catch (e) { setError(financeError(e)) } }
  const activeActions = actions[section] || []
  const action = activeActions[actionIndex] || activeActions[0]
  const r = data?.report
  const currentScope = data?.context.tenant_id === currentTenant?.id && r?.period.start === start && r?.period.end === end && r?.as_of === asOf
  const comparison = r ? (<details><summary>Compare with existing settlement reports</summary><p className="finance-help">{r.legacy_comparison.note}</p><button className="finance-secondary" onClick={() => void reconstruct()}>Recover original PDFs for this period</button>{reconstructionStatus && <p role="status">{reconstructionStatus}</p>}<DataTable rows={r.legacy_comparison.rows} columns={['name', 'date', 'freight_gross', 'carrier_retention', 'operating_deductions', 'settlement_remainder', 'legacy_net', 'difference']} /></details>) : null
  return <div className="finance-app">
    <header className="finance-header"><div><h1>{section === 'home' ? 'Dashboard' : tabs.find(t => t[0] === section)?.[1] || 'Finance'}</h1><p className="finance-help">Cash, equipment performance and the records behind every result.</p></div><Link className="finance-secondary" to="/legacy-dashboard">Previous dashboard</Link></header>
    {section !== 'home' && <nav className="finance-tabs" aria-label="Finance workspace">{tabs.map(([path, title]) => <Link key={path} className={section === path ? 'active' : ''} aria-current={section === path ? 'page' : undefined} to={path === 'home' ? '/finance' : `/finance/${path}`}>{title}</Link>)}</nav>}
    <div className="finance-actions" aria-label="Reporting period presets">{['week', 'month', 'year'].map(p => <button key={p} className="finance-secondary" onClick={() => { setStart(periodStart(p)); setEnd(today()); setAsOf(today()) }}>This {p}</button>)}</div>
    <div className="finance-period"><label>Period start<input aria-label="Period start" type="date" value={start} onChange={e => setStart(e.target.value)} /></label><label>Period end<input aria-label="Period end" type="date" value={end} onChange={e => setEnd(e.target.value)} /></label><label>Cash as of<input aria-label="Cash as of" type="date" value={asOf} onChange={e => setAsOf(e.target.value)} /></label><button className="finance-secondary" onClick={() => void load()} disabled={loading}>{loading ? 'Loading…' : 'Refresh evidence'}</button></div>
    {error && <div role="alert" className="finance-error"><p>{error}</p><p>Check your selected business and server accounting access, then retry.</p><button className="finance-secondary" onClick={() => void load()}>Retry</button></div>}
    {(!data || !currentScope) && loading && <p role="status" className="finance-empty">Loading reconciled records…</p>}
    {data && r && currentScope && !error && <>
      <div className="finance-report-label"><span>{r.label}</span><span>{r.period.calendar_days} calendar days · USD · draft books; settlement insight uses statement dates</span></div>
      {section === 'home' && <OwnerOverview report={r} context={data.context} onSaved={load} />}
      {section === 'money' && <><CashView cash={r.owner_cash} /><section className="finance-section"><h2>Transactions to match</h2><DataTable rows={data.workspace.transactions.filter(t => !t.matched)} columns={['date', 'description', 'amount', 'id']} /><h2>Outstanding obligations</h2><DataTable rows={data.workspace.claims.filter(c => Number(c.remaining) > 0)} columns={['description', 'creditor', 'remaining', 'source_ref']} /><h2>Protected cash</h2><DataTable rows={data.workspace.reserves} columns={['pair_id', 'purpose', 'balance', 'note']} /></section></>}
      {section === 'assets' && <section className="finance-section"><h2>Capital recovery</h2><DataTable rows={r.capital} columns={['asset_id', 'acquisition_cost', 'expected_resale', 'target', 'funded', 'shortfall', 'planned_sale', 'required_weekly', 'realized_lifetime_profit']} /><p className="finance-help">Expected resale remains separate from bank cash. No capital is marked recovered without a confirmed funded allocation.</p><h2>Assignments over time</h2><DataTable rows={data.workspace.assignments} columns={['truck_id', 'trailer_id', 'start', 'end']} /></section>}
      {section === 'repairs' && !advancedRepairs && <section className="finance-section"><h2>Upload invoices. Confirm only what’s missing.</h2><p className="finance-help">Your repair cards already contain the work, equipment and cost. Add cash or Zelle payment details there, individually or for matching invoices together.</p><Link className="finance-primary" to="/repairs">Open repair invoices</Link><p className="finance-help"><Link to="/finance/repairs?advanced=1">Advanced accounting tools</Link></p></section>}
      {section === 'repairs' && advancedRepairs && <section className="finance-section"><h2>Repair obligations</h2><DataTable rows={data.workspace.claims.filter(c => c.category === 'repairs')} columns={['description', 'asset_id', 'amount', 'remaining', 'creditor']} /><Link to="/repairs">Existing repair and invoice records</Link></section>}
      {section === 'settlements' && <section className="finance-section"><h2>Posted settlements</h2><DataTable rows={data.workspace.settlements} columns={['source_ref', 'date', 'freight_gross', 'carrier_retention', 'reported_payout']} /><Link to="/settlements">Existing PDF settlement workflow</Link></section>}
      {section === 'accounting' && <>
        <section className="finance-section"><div className="finance-section-heading"><h2>Report readiness</h2><span className="finance-status">{r.readiness.status}</span></div><ul className="finance-checks">{r.readiness.checks.map(c => <li key={c.code}><span>{c.label}</span><strong>{c.status === 'pass' ? 'Confirmed' : c.status === 'block' ? 'Needs reconciliation' : 'Not confirmed'}</strong></li>)}</ul><div className="finance-actions"><button className="finance-secondary" onClick={() => void download(true)}>Download draft package</button><button className="finance-primary" disabled={r.readiness.status !== 'pass'} onClick={() => void download(false)}>Download accountant package</button></div></section>
        <section className="finance-section"><h2>Income statement</h2><DataTable rows={[r.ledger.income_statement]} columns={['revenue', 'operating_earnings', 'interest', 'depreciation', 'disposal_gain', 'net_income']} /><h2>Balance sheet</h2><DataTable rows={[r.ledger.balance_sheet]} columns={['assets', 'liabilities', 'equity_including_earnings', 'difference']} /><h2>Cash flow</h2><DataTable rows={[r.ledger.cash_flow]} columns={['opening_balance', 'operating', 'investing', 'financing', 'unclassified', 'net_change', 'closing_balance']} /><details><summary>Trial balance and general ledger</summary><DataTable rows={r.ledger.trial_balance} columns={['account', 'debit', 'credit']} /><DataTable rows={r.ledger.general_ledger} columns={['date', 'description', 'account', 'asset_id', 'debit', 'credit', 'posting_id']} /></details></section>
      </>}
      {section === 'connections' && <>
        <section className="finance-section"><h2>Fuel and distance</h2>{r.fuel.map(f => <div className="finance-fuel" key={f.asset_id}><strong>{f.name}</strong><span>Measured MPG: {f.measured_mpg || 'Not established'}</span><span>Miles per gallon purchased: {f.miles_per_gallon_purchased || 'Needs a complete 28-day interval'}</span><p className="finance-help">{f.note}</p></div>)}</section>
        <form className="finance-form" onSubmit={fetchMotive}><h2>Motive connection</h2><p className="finance-help">{data.context.motive_configured ? 'Read-only connection configured. Fetch a vehicle’s history, then verify its mapping and odometer readings.' : 'Connection needs a business-specific Motive API key configured on the server. You can upload Motive exports and odometer evidence below now.'}</p><div className="finance-fields"><label>ELIS asset<select name="asset" required><option value="">Choose…</option>{data.context.assets.filter(a => a.type === 'truck').map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label><label>Motive vehicle ID<input name="vehicle" type="number" min="1" required /></label><label>Start<input name="start" type="date" required defaultValue={start} /></label><label>End<input name="end" type="date" required defaultValue={end} /></label></div><button className="finance-primary" disabled={!data.context.motive_configured}>Fetch read-only history</button>{motiveStatus && <p role="status">{motiveStatus}</p>}</form>
      </>}
      {advancedRepairs && activeActions.length > 0 && <section className="finance-section"><label className="finance-action-picker">Record or reconcile<select value={actionIndex} onChange={e => setActionIndex(Number(e.target.value))}>{activeActions.map((a, i) => <option key={a.kind} value={i}>{a.label}</option>)}</select></label>{action && <CommandForm key={`${section}-${action.kind}`} action={action} reportId={r.id} context={data.context} workspace={data.workspace} evidence={data.evidence} events={data.events} onSaved={load} />}</section>}
      {advancedRepairs && section !== 'home' && <section className="finance-section"><h2>Source documents</h2><form onSubmit={upload} className="finance-upload"><label>Original PDF, CSV, image or statement<input type="file" required onChange={e => setFile(e.target.files?.[0] || null)} /></label><label>Source reference<input required value={documentSource} onChange={e => setDocumentSource(e.target.value)} placeholder="Carrier settlement number or invoice reference" /></label><label>Amends an earlier document<select value={replacement} onChange={e => setReplacement(e.target.value)}><option value="">New source</option>{data.evidence.map(d => <option key={d.id} value={d.id}>{d.source_key} · {d.filename}</option>)}</select></label><button className="finance-secondary" disabled={uploadBusy}>{uploadBusy ? 'Preserving original…' : 'Upload evidence'}</button>{uploadStatus && <p role="status">{uploadStatus}</p>}</form>{data.evidence.map(d => <details className="finance-document" key={d.id}><summary>{d.source_key} <span className="finance-muted">{d.filename}{d.supersedes_id ? ' · amended version' : ''}</span></summary><button className="finance-secondary" onClick={() => void financeApi.download(`/evidence/${d.id}/original`, d.filename).catch(e => setError(financeError(e)))}>Download original</button><pre>{JSON.stringify(d.extracted, null, 2)}</pre></details>)}</section>}
      {['settlements', 'accounting'].includes(section) && <section className="finance-section">{comparison}</section>}
      <footer className="finance-footer">Report snapshot {r.id.slice(0, 8)} · Original sources and previous reports remain preserved. Payments and tax filing are performed outside this app.</footer>
    </>}
  </div>
}
