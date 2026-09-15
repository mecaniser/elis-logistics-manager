import { useEffect, useRef, useState } from 'react'
import { bankMonitorApi } from '../services/api'

type Account = { nickname: string; last4: string }
type Draft = { id: string; charge_reference: string; amount_cents: number; from_last4: string; to_last4: string; memo: string; status: string; bank_date: string }
const runtime = () => (window as any).chrome?.runtime
const REQUIRED_EXTENSION_VERSION = '0.1.6'
const send = (extension: string, message: unknown): Promise<any> => new Promise((resolve, reject) => {
  if (!/^[a-p]{32}$/.test(extension)) return reject(new Error('Enter the 32-letter Chrome extension ID.'))
  if (!runtime()?.sendMessage) return reject(new Error('Chrome cannot see an enabled extension connection for this page. Reload ELIS Bank Form Assistant in chrome://extensions in this Chrome profile, then reload this page.'))
  runtime().sendMessage(extension, message, (response: any) => {
    if (runtime().lastError || !response) reject(new Error('Extension unavailable. Check installation and extension ID.'))
    else if (!response.ok) reject(Object.assign(new Error(response.error || 'Preparation stopped. Review the bank tab.'), {code: response.code}))
    else resolve(response)
  })
})

export default function BankTransferQueue({ tenantId, checking, sources }: { tenantId: number; checking: Account[]; sources: Account[] }) {
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [extension, setExtension] = useState(localStorage.getItem('elis-bank-extension-id') || '')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [reference, setReference] = useState('')
  const [amount, setAmount] = useState('')
  const [memo, setMemo] = useState('Cvr ')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [reviewed, setReviewed] = useState(false)
  const active = useRef(true)
  useEffect(() => {
    active.current = true
    bankMonitorApi.drafts(tenantId).then(r => { if (active.current) setDrafts(r.data) }).catch(() => { if (active.current) setError('Unable to load transfer queue.') })
    return () => { active.current = false }
  }, [tenantId])
  const reload = async () => { const r = await bankMonitorApi.drafts(tenantId); if (active.current) setDrafts(r.data) }
  const create = async (event: React.FormEvent) => {
    event.preventDefault(); if (!reviewed) return
    setBusy(true); setError(''); setNotice('')
    try {
      if (!/^\d+\.\d{2}$/.test(amount)) throw new Error('Enter the full charge amount with two decimal places.')
      const [whole, fraction] = amount.split('.')
      await bankMonitorApi.createDraft(tenantId, { charge_reference: reference, amount_cents: Number(whole) * 100 + Number(fraction), from_last4: from, to_last4: to, memo })
      if (!active.current) return
      await reload(); setNotice('Reviewed draft added. No bank form has been filled.'); setReviewed(false)
    } catch (e: any) { if (active.current) setError(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : e.message || 'Unable to add draft.') }
    finally { if (active.current) setBusy(false) }
  }
  const connect = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      const response = await send(extension, { type: 'ELIS_PING' })
      localStorage.setItem('elis-bank-extension-id', extension)
      if (response.version !== REQUIRED_EXTENSION_VERSION) throw new Error(`Chrome extension ${response.version || 'version unknown'} is loaded. Reload ELIS Bank Form Assistant ${REQUIRED_EXTENSION_VERSION} in this Chrome profile before continuing.`)
      if (active.current) setNotice(`Chrome extension connected (${response.version}). No bank form opened or transfer prepared.`)
    } catch (e: any) { if (active.current) setError(e.message) }
    finally { if (active.current) setBusy(false) }
  }
  const prepare = async (draft: Draft) => {
    setBusy(true); setError(''); setNotice('')
    let claimed = false
    try {
      const ping = await send(extension, { type: 'ELIS_PING' })
      if (ping.version !== REQUIRED_EXTENSION_VERSION) throw new Error(`Chrome extension ${ping.version || 'version unknown'} is loaded. Reload version ${REQUIRED_EXTENSION_VERSION} before preparing a form.`)
      localStorage.setItem('elis-bank-extension-id', extension)
      const result = await bankMonitorApi.prepareDraft(tenantId, draft.id)
      claimed = true
      if (!active.current) throw new Error('Business changed. Preparation stopped.')
      setNotice('Open the extension review tab and approve preparation within two minutes. No bank form opens until you approve.')
      await send(extension, { type: 'ELIS_PREPARE', draft: result.data })
      await bankMonitorApi.draftOutcome(tenantId, draft.id, 'prepared_awaiting_submission')
      if (active.current) setNotice('Form prepared in Chrome. Review and submit in Truliant. ELIS has not confirmed a transfer.')
    } catch (e: any) {
      const notStarted = claimed && e.code === 'PREPARATION_NOT_STARTED'
      let restored = false
      if (claimed) {
        try {
          await bankMonitorApi.draftOutcome(tenantId, draft.id, notStarted ? 'preparation_not_started' : 'preparation_failed')
          restored = notStarted
        } catch { /* Keep the claim locked when its outcome cannot be saved. */ }
      }
      if (active.current) {
        setNotice(restored ? 'Approval expired or was canceled. No bank form opened. This draft is ready to prepare again.' : '')
        if (!restored) setError(notStarted ? 'No bank form opened, but ELIS could not restore the draft. Refresh before continuing.' : typeof e.response?.data?.detail === 'string' ? e.response.data.detail : e.message)
      }
    } finally { if (active.current) { await reload().catch(() => {}); setBusy(false) } }
  }
  const verify = async (draft: Draft) => {
    setBusy(true); setError(''); setNotice('')
    try {
      const ping = await send(extension, { type: 'ELIS_PING' })
      if (ping.version !== REQUIRED_EXTENSION_VERSION) throw new Error(`Chrome extension ${ping.version || 'version unknown'} is loaded. Reload version ${REQUIRED_EXTENSION_VERSION} before checking histories.`)
      let result
      try {
        result = await send(extension, { type: 'ELIS_VERIFY', draft })
      } catch (e: any) {
        if (e.code !== 'VERIFICATION_REAUTH_REQUIRED') throw e
        setNotice('The extension was reloaded. Approve the read-only verification window; it will not prepare or submit a transfer.')
        await send(extension, { type: 'ELIS_REAUTHORIZE_VERIFY', draft })
        result = await send(extension, { type: 'ELIS_VERIFY', draft })
      }
      await bankMonitorApi.draftHistoryMatch(tenantId, draft.id, result.evidence)
      await send(extension, { type: 'ELIS_ACK', id: draft.id })
      if (active.current) setNotice('The extension found one matching posted entry in each account. Review the bank history if anything differs.')
    } catch (e: any) { if (active.current) setError(e.message || 'Bank verification failed; completion remains unconfirmed.') }
    finally { if (active.current) { await reload().catch(() => {}); setBusy(false) } }
  }
  return <section className="bg-white border rounded-lg p-5 space-y-4">
    <h2 className="text-lg font-semibold">Transfers for individual charges</h2>
    <p className="text-sm text-gray-600">Each draft covers one full charge. Choose HELOC only when it can cover the entire amount; otherwise choose the business credit line. The Chrome extension fills the form; you submit in Truliant.</p>
    <p className="text-sm text-amber-800">First integration preview: charge matching is reviewed manually. After submitting in the bank, check both account histories using the extension. This matching logic still needs a live acceptance test.</p>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {notice && <p role="status" className="text-green-800">{notice}</p>}
    <label className="block text-sm">Chrome extension ID<input className="block border rounded p-2 w-full" value={extension} maxLength={32} onChange={e => setExtension(e.target.value.trim())} placeholder="From chrome://extensions after installation" /></label>
    <button type="button" disabled={busy} onClick={connect} className="text-blue-700 underline disabled:opacity-50">Connect extension</button>
    <form onSubmit={create} className="space-y-3 border-t pt-4">
      <label className="block text-sm">Unique charge reference<input required maxLength={120} pattern="[A-Za-z0-9 .:_\-]+" className="block border rounded p-2 w-full" value={reference} onChange={e => { setReference(e.target.value); setReviewed(false) }} placeholder="Bank transaction reference, or date and bill identifier" /></label>
      <div className="flex flex-wrap gap-4">
        <label className="text-sm">Full charge amount ($)<input required inputMode="decimal" className="block border rounded p-2" placeholder="118.20" value={amount} onChange={e => { setAmount(e.target.value); setReviewed(false) }} /></label>
        <label className="text-sm">From<select required className="block border rounded p-2" value={from} onChange={e => { setFrom(e.target.value); setReviewed(false) }}><option value="">Select credit source</option>{sources.map(a => <option key={a.last4} value={a.last4}>{a.nickname} · {a.last4}</option>)}</select></label>
        <label className="text-sm">To<select required className="block border rounded p-2" value={to} onChange={e => { setTo(e.target.value); setReviewed(false) }}><option value="">Select checking</option>{checking.map(a => <option key={a.last4} value={a.last4}>{a.nickname} · {a.last4}</option>)}</select></label>
      </div>
      <label className="block text-sm">Memo (starts with Cvr, 34 characters maximum)<input required maxLength={34} className="block border rounded p-2 w-full" value={memo} onChange={e => { setMemo(e.target.value); setReviewed(false) }} /></label>
      <label className="flex gap-2 text-sm"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I checked bank history: this full charge needs funding and has no matching transfer or unresolved submission.</label>
      <button disabled={busy || !reviewed} className="bg-blue-700 text-white px-4 py-2 rounded disabled:opacity-50">Add reviewed transfer</button>
    </form>
    {drafts.length === 0 && <p>No reviewed transfer drafts yet.</p>}
    {drafts.map(d => <div key={d.id} className="border-t py-3 space-y-1">
      <p className="font-medium">${(d.amount_cents / 100).toFixed(2)} · {d.memo}</p>
      <p className="text-sm">••{d.from_last4} → ••{d.to_last4} · {d.charge_reference}</p>
      <p className="text-sm">{d.status === 'reviewed' ? 'Ready to prepare' : d.status === 'prepared_awaiting_submission' ? 'Transfer submitted; history verification pending' : d.status.replace(/_/g, ' ')} · {d.status === 'bank_history_matched' ? 'Matched in both bank histories by extension' : 'Completion unconfirmed'}</p>
      {d.status === 'reviewed' && <button disabled={busy} onClick={() => prepare(d)} className="text-blue-700 underline disabled:opacity-50">Prepare in Truliant</button>}
      {!['reviewed', 'bank_history_matched'].includes(d.status) && <button disabled={busy} onClick={() => verify(d)} className="text-blue-700 underline">I finished in Truliant — check both histories</button>}
      {!['reviewed', 'bank_history_matched'].includes(d.status) && <p className="text-sm text-amber-800">Check the bank tab and history before another attempt. This draft is locked to prevent duplicate preparation.</p>}
    </div>)}
  </section>
}
