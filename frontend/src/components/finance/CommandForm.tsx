import { FormEvent, useRef, useState } from 'react'
import { Action, Field } from './commandFields'
import { Context, Evidence, Event, RecordData, Value, Workspace, dollars, financeApi, financeError } from '../../services/finance'

interface Props { reportId: string; action: Action; context: Context; workspace: Workspace; evidence: Evidence[]; events: Event[]; onSaved: () => Promise<void> }
function initial(fields: Field[]): RecordData { return Object.fromEntries(fields.map(f => [f.name, f.type === 'table' ? [] : f.type === 'check' ? false : f.initial ?? (f.options?.[0] || '')])) }
export default function CommandForm({reportId, action, context, workspace, evidence, events, onSaved}: Props) {
  const [values, setValues] = useState<RecordData>(() => initial(action.fields))
  const [when, setWhen] = useState(new Date().toLocaleDateString('en-CA'))
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [busy, setBusy] = useState(false)
  const lastRequest = useRef({body: '', key: ''})
  const fields = action.fields.map(field => {
    if (action.kind === 'payment' && field.name === 'transaction_id') return {...field, optional: values.payer === 'owner'}
    if (action.kind === 'payment' && field.name === 'evidence_id') return {...field, optional: values.payer !== 'owner'}
    if (action.kind === 'statement' && field.name === 'cash_count_evidence_id') return {...field, optional: !workspace.accounts.some(a => a.id === values.account_id && a.account_type === 'cash')}
    return field
  })
  function choices(field: Field): {value: string; label: string}[] {
    if (field.options) return field.options.map(x => ({value: x, label: x.replace(/_/g, ' ')}))
    if (field.source === 'evidence') return evidence.map((e, index) => {
      const ids = Array.isArray(e.extracted.legacy_repair_ids) ? e.extracted.legacy_repair_ids : []
      const repair = workspace.legacy_repairs?.find(r => ids.includes(r.id))
      return {value: e.id, label: repair ? `${repair.date || 'Undated'} · ${repair.description.slice(0, 70)} · document ${index + 1}` : `${e.source_key} · ${e.filename}`}
    })
    if (['assets', 'trucks', 'trailers'].includes(field.source || '')) return context.assets.filter(a => field.source === 'assets' || a.type === (field.source === 'trucks' ? 'truck' : 'trailer')).map(a => ({value: String(a.id), label: a.name}))
    if (field.source === 'ledger_accounts') return Object.keys(context.accounts).map(x => ({value: x, label: x.replace(/_/g, ' ')}))
    if (field.source === 'receivables') return events.filter(e => ['settlement', 'disposal'].includes(e.kind)).map(e => ({value: e.id, label: String(e.payload.source_ref || `Equipment sale · ${context.assets.find(a => a.id === e.payload.asset_id)?.name || e.payload.asset_id} · ${e.effective_date}`)}))
    if (field.source === 'legacy_repairs') return (workspace.legacy_repairs || []).map(r => ({value: String(r.id), label: `${context.assets.find(a => a.id === r.asset_id)?.name || 'Equipment'} · ${r.date || 'Date needed'} · ${r.description} · ${r.cost === null ? 'Amount needed' : dollars(r.cost)}`}))
    if (field.source === 'claims') return workspace.claims.map(c => ({value: String(c.id), label: `${c.description} · ${dollars(c.remaining)} outstanding`}))
    if (field.source === 'transactions') return workspace.transactions.filter(t => !t.matched).map(t => ({value: String(t.id), label: `${t.date} · ${t.description} · ${dollars(t.amount)}`}))
    if (field.source === 'reserves') return workspace.reserves.filter(r => r.purpose === 'repair').map(r => ({value: String(r.id), label: `${context.assets.find(a => a.id === r.pair_id)?.name || r.pair_id} · ${dollars(r.balance)} funded`}))
    return events.filter(e => e.kind === field.source).map(e => ({value: e.id, label: String(e.payload.name || e.payload.source_ref || e.payload.description || `${e.kind} ${e.effective_date}`)}))
  }
  function control(field: Field, value: Value | undefined, update: (v: Value) => void, id: string) {
    if (field.type === 'check') return <label className="finance-check" htmlFor={id}><input id={id} type="checkbox" checked={Boolean(value)} onChange={e => update(e.target.checked)} />{field.label}</label>
    return <label htmlFor={id}>{field.label}{field.optional && <span className="finance-muted"> (optional)</span>}
      {field.type === 'select' ? <select id={id} required={!field.optional} value={String(value ?? '')} onChange={e => update(e.target.value)}><option value="">Choose…</option>{choices(field).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}</select> : <input id={id} type={field.type === 'date' ? 'date' : 'text'} inputMode={['money', 'quantity', 'number'].includes(field.type || '') ? 'decimal' : undefined} required={!field.optional} value={String(value ?? '')} onChange={e => update(e.target.value)} placeholder={field.type === 'money' ? '0.00' : undefined} />}
      {field.help && <span className="finance-field-help">{field.help}</span>}
    </label>
  }
  function normalize(field: Field, value: Value): Value | undefined {
    if ((value === '' || value === null || value === undefined) && field.optional) return undefined
    if (field.type === 'money') { const s = String(value).trim(); if (!/^-?\d+(\.\d{1,2})?$/.test(s)) throw new Error(`${field.label}: enter a dollar amount with at most two decimal places.`); const [whole, cents = ''] = s.split('.'); return `${whole}.${cents.padEnd(2, '0')}` }
    if (field.type === 'number' || ['asset_id', 'truck_id', 'trailer_id', 'pair_id', 'legacy_repair_id'].includes(field.name)) return Number(value)
    if (field.type === 'table') {
      const rows = value as RecordData[]
      if (field.name === 'deductions') { const result: RecordData = {}; for (const row of rows) { if (result[String(row.category)]) throw new Error('Use one combined amount per deduction category.'); result[String(row.category)] = normalize(field.columns![1], row.amount)! } return result }
      return rows.map(row => Object.fromEntries(field.columns!.map(c => [c.name, normalize(c, row[c.name])]).filter(([,v]) => v !== undefined))) as RecordData[]
    }
    return value
  }
  function fillProposal() {
    const doc = evidence.find(d => d.id === values.evidence_id)
    const proposal = doc?.extracted.proposal as RecordData | undefined
    if (!proposal) return
    const next: RecordData = {...values, ...proposal, evidence_id: doc!.id}
    next.deductions = Object.entries(proposal.deductions as RecordData).map(([category, amount]) => ({category, amount}))
    setValues(next)
    const parsed = doc?.extracted.settlement as RecordData | undefined
    if (parsed?.settlement_date) setWhen(String(parsed.settlement_date))
    setSaved('Extracted fields filled. Confirm vehicle, products, deductions and accounting date against the original before posting.')
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); setError(''); setSaved(''); setBusy(true)
    try {
      const payload: RecordData = {kind: action.kind}
      for (const f of fields) { const v = normalize(f, values[f.name]); if (v !== undefined) payload[f.name] = v }
      if (action.kind === 'policy') { payload.evidence_ids = payload.policy_evidence ? [payload.policy_evidence] : []; delete payload.policy_evidence }
      if (action.kind === 'activate_finance') payload.report_id = reportId
      const effective = action.kind === 'statement' ? String(payload.end) : when
      const body = JSON.stringify({effective, payload})
      if (lastRequest.current.body !== body) lastRequest.current = {body, key: crypto.randomUUID()}
      await financeApi.command(effective, payload, lastRequest.current.key)
      await onSaved(); setSaved('Saved with its source and audit history.'); setValues(initial(action.fields)); lastRequest.current = {body: '', key: ''}
    } catch (e) { setError(financeError(e)) } finally { setBusy(false) }
  }
  return <form className="finance-form" onSubmit={submit}>
    <h2>{action.label}</h2><p className="finance-help">{action.help}</p>
    {action.kind === 'settlement' && <div className="finance-proposal"><label>Start from a preserved settlement PDF<select value={String(values.evidence_id || '')} onChange={e => setValues(v => ({...v, evidence_id: e.target.value}))}><option value="">Choose source…</option>{evidence.filter(d => d.extracted.proposal).map(d => <option key={d.id} value={d.id}>{d.source_key} · {d.filename}</option>)}</select></label><button type="button" className="finance-secondary" disabled={!evidence.some(d => d.id === values.evidence_id && d.extracted.proposal)} onClick={fillProposal}>Fill extracted fields for review</button></div>}
    <div className="finance-fields">
      {action.kind !== 'statement' && <label htmlFor="effective-date">Effective / incurred date<input id="effective-date" type="date" value={when} required onChange={e => setWhen(e.target.value)} /></label>}
      {fields.filter(f => f.type !== 'table').map(field => <div key={field.name}>{control(field, values[field.name], v => setValues(old => ({...old, [field.name]: v})), `field-${field.name}`)}</div>)}
    </div>
    {fields.filter(f => f.type === 'table').map(field => <fieldset className="finance-lines" key={field.name}><legend>{field.label}</legend>{(values[field.name] as RecordData[]).map((row, i) => <div className="finance-line-fields" key={i}>{field.columns!.map(col => <div key={col.name}>{control(col, row[col.name], value => setValues(old => ({...old, [field.name]: (old[field.name] as RecordData[]).map((r, j) => j === i ? {...r, [col.name]: value} : r)})), `${field.name}-${i}-${col.name}`)}</div>)}<button type="button" className="finance-text-button" onClick={() => setValues(old => ({...old, [field.name]: (old[field.name] as RecordData[]).filter((_, j) => i !== j)}))}>Remove row {i + 1}</button></div>)}<button type="button" className="finance-secondary" onClick={() => setValues(old => ({...old, [field.name]: [...old[field.name] as RecordData[], initial(field.columns!)]}))}>Add {field.name === 'deductions' ? 'deduction' : 'row'}</button></fieldset>)}
    {error && <p role="alert" className="finance-error">{error}</p>}{saved && <p role="status" className="finance-success">{saved}</p>}
    <button className="finance-primary" disabled={busy}>{busy ? 'Validating and saving…' : action.label}</button>
  </form>
}
