import { useCallback, useEffect, useRef, useState } from 'react'
import { bankMonitorApi } from '../services/api'

type Account = { nickname: string; last4: string }
type Draft = { id: string; charge_reference: string; amount_cents: number; from_last4: string; to_last4: string; memo: string; status: string; bank_date: string }
type ExtensionResponse = { ok: boolean; error?: string; code?: string; version?: string; accounts?: Account[]; progress?: { message?: string }; evidence?: unknown; checked_at?: string; [key: string]: unknown }
type ChromeRuntime = { sendMessage: (extension: string, message: unknown, callback: (response?: ExtensionResponse) => void) => void; lastError?: unknown }
type BalanceCheck = { checked_at: string; accounts: { last4: string; current_cents: number | null; available_credit_cents: number | null }[] }

const REQUIRED_EXTENSION_VERSION = '0.1.15'
const runtime = () => (window as Window & { chrome?: { runtime?: ChromeRuntime } }).chrome?.runtime
const money = (cents: number) => (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback
const send = <T extends ExtensionResponse>(extension: string, message: unknown): Promise<T> => new Promise((resolve, reject) => {
  if (!/^[a-p]{32}$/.test(extension)) return reject(new Error('Enter the 32-letter Chrome extension ID.'))
  const chromeRuntime = runtime()
  if (!chromeRuntime?.sendMessage) return reject(new Error('Chrome cannot reach the bank assistant. Reload the extension and this page.'))
  chromeRuntime.sendMessage(extension, message, response => {
    if (chromeRuntime.lastError || !response) reject(new Error('Bank assistant unavailable. Check that the extension is enabled in this Chrome profile.'))
    else if (!response.ok) reject(Object.assign(new Error(response.error || 'The bank assistant stopped. Review the Truliant tab.'), { code: response.code }))
    else resolve(response as T)
  })
})

function Icon({ name, className = 'h-5 w-5' }: { name: 'check' | 'alert' | 'refresh' | 'link' | 'arrow' | 'clock'; className?: string }) {
  const paths = {
    check: <path d="m5 12 4 4L19 6" />,
    alert: <><path d="M12 9v4" /><path d="M12 17h.01" /><path d="M10.3 3.7 2.6 17a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 3.7a2 2 0 0 0-3.4 0Z" /></>,
    refresh: <><path d="M20 6v5h-5" /><path d="M4 18v-5h5" /><path d="M18.5 9A7 7 0 0 0 6.1 5.4L4 7" /><path d="M5.5 15A7 7 0 0 0 17.9 18.6L20 17" /></>,
    link: <><path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1" /><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2A5 5 0 0 0 12 20l1.1-1.1" /></>,
    arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  }
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>{paths[name]}</svg>
}

const statusMeta = (status: string) => {
  if (status === 'reviewed' || status === 'preparation_not_started') return { label: 'Ready to prepare', tone: 'bg-blue-50 text-blue-800 ring-blue-200', action: 'prepare' as const }
  if (status === 'prepared_awaiting_submission') return { label: 'Form prepared · submission unconfirmed', tone: 'bg-amber-50 text-amber-800 ring-amber-200', action: 'verify' as const }
  if (status === 'bank_history_matched') return { label: 'Matched in both histories', tone: 'bg-emerald-50 text-emerald-800 ring-emerald-200', action: 'done' as const }
  if (status === 'preparation_failed') return { label: 'Preparation needs review', tone: 'bg-red-50 text-red-800 ring-red-200', action: 'blocked' as const }
  return { label: status.replace(/_/g, ' '), tone: 'bg-slate-100 text-slate-700 ring-slate-200', action: 'blocked' as const }
}

export default function BankTransferQueue({ tenantId, checking, sources, onAccountsDiscovered }: { tenantId: number; checking: Account[]; sources: Account[]; onAccountsDiscovered: (accounts: Account[]) => void }) {
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [extension, setExtension] = useState(localStorage.getItem('elis-bank-extension-id') || '')
  const [draftExtension, setDraftExtension] = useState(extension)
  const [connected, setConnected] = useState(false)
  const [editingConnection, setEditingConnection] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [operation, setOperation] = useState<{ message: string; started: number } | null>(null)
  const [clock, setClock] = useState(Date.now())
  const [reference, setReference] = useState('')
  const [amount, setAmount] = useState('')
  const [memo, setMemo] = useState('Cvr ')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [reviewed, setReviewed] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)
  const [balanceCheck, setBalanceCheck] = useState<BalanceCheck | null>(null)
  const active = useRef(true)

  const markDisconnected = useCallback(() => setConnected(false), [])
  const ping = useCallback(async () => {
    if (!extension) return false
    try {
      const response = await send<ExtensionResponse>(extension, { type: 'ELIS_PING' })
      const valid = response.version === REQUIRED_EXTENSION_VERSION
      if (active.current) setConnected(valid)
      return valid
    } catch {
      if (active.current) markDisconnected()
      return false
    }
  }, [extension, markDisconnected])

  useEffect(() => {
    active.current = true
    bankMonitorApi.drafts(tenantId).then(r => { if (active.current) setDrafts(r.data) }).catch(() => { if (active.current) setError('Unable to load transfer queue.') })
    return () => { active.current = false }
  }, [tenantId])
  useEffect(() => { void ping() }, [ping])
  useEffect(() => {
    const recheck = () => { if (document.visibilityState === 'visible') void ping() }
    window.addEventListener('focus', recheck)
    document.addEventListener('visibilitychange', recheck)
    return () => { window.removeEventListener('focus', recheck); document.removeEventListener('visibilitychange', recheck) }
  }, [ping])
  useEffect(() => {
    if (!operation) return
    setClock(Date.now())
    const timer = window.setInterval(() => setClock(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [operation])

  const reload = async () => { const r = await bankMonitorApi.drafts(tenantId); if (active.current) setDrafts(r.data) }
  const fail = (error: unknown, fallback: string) => { markDisconnected(); if (active.current) setError(errorMessage(error, fallback)) }
  const create = async (event: React.FormEvent) => {
    event.preventDefault(); if (!reviewed) return
    setBusy(true); setError(''); setNotice('')
    try {
      if (!/^\d+\.\d{2}$/.test(amount)) throw new Error('Enter the full charge amount with two decimal places.')
      if (!/^Cvr [A-Za-z0-9 ._-]{1,30}$/.test(memo)) throw new Error('Add what this transfer covers after “Cvr”.')
      const [whole, fraction] = amount.split('.')
      await bankMonitorApi.createDraft(tenantId, { charge_reference: reference, amount_cents: Number(whole) * 100 + Number(fraction), from_last4: from, to_last4: to, memo })
      if (!active.current) return
      await reload(); setNotice('Transfer draft added. No bank form was filled.'); setReviewed(false); setManualOpen(false)
    } catch (error: unknown) { if (active.current) setError(errorMessage(error, 'Unable to add draft.')) }
    finally { if (active.current) setBusy(false) }
  }
  const connect = async () => {
    setBusy(true); setError(''); setNotice(''); setOperation({ message: 'Connecting to the bank assistant…', started: Date.now() })
    try {
      const candidate = draftExtension.trim()
      const response = await send<ExtensionResponse>(candidate, { type: 'ELIS_PING' })
      if (response.version !== REQUIRED_EXTENSION_VERSION) throw new Error(`Extension ${response.version || 'version unknown'} is loaded. Reload version ${REQUIRED_EXTENSION_VERSION}.`)
      localStorage.setItem('elis-bank-extension-id', candidate)
      if (active.current) { setExtension(candidate); setDraftExtension(candidate); setConnected(true); setEditingConnection(false) }
      const discovered = await send<ExtensionResponse>(candidate, { type: 'ELIS_DISCOVER_ACCOUNTS' })
      const accounts = discovered.accounts || []
      if (active.current) { onAccountsDiscovered(accounts); setNotice(`Connected and imported ${accounts.length} accounts. Review and save the account roles in Settings.`) }
    } catch (error: unknown) { fail(error, 'Unable to connect to the bank assistant.') }
    finally { if (active.current) { setBusy(false); setOperation(null) } }
  }
  const discoverAccounts = async () => {
    setBusy(true); setError(''); setNotice(''); setOperation({ message: 'Reading accounts from Truliant…', started: Date.now() })
    try {
      const discovered = await send<ExtensionResponse>(extension, { type: 'ELIS_DISCOVER_ACCOUNTS' })
      const accounts = discovered.accounts || []
      if (active.current) { setConnected(true); onAccountsDiscovered(accounts); setNotice(`Imported ${accounts.length} accounts. Review and save their roles in Settings.`) }
    } catch (error: unknown) { fail(error, 'Unable to import accounts.') }
    finally { if (active.current) { setBusy(false); setOperation(null) } }
  }
  const checkBalances = async () => {
    setBusy(true); setError(''); setNotice(''); setOperation({ message: 'Reading current balances from Truliant…', started: Date.now() })
    try {
      if (!checking.length || !sources.length) throw new Error('Import and save the checking and credit accounts first.')
      const suffixes = [...checking, ...sources].map(account => account.last4)
      const result = await send<ExtensionResponse & BalanceCheck>(extension, { type: 'ELIS_CHECK_BALANCES', suffixes })
      if (active.current) { setConnected(true); setBalanceCheck(result) }
    } catch (error: unknown) { fail(error, 'Unable to check balances.') }
    finally { if (active.current) { setBusy(false); setOperation(null) } }
  }
  const prepare = async (draft: Draft) => {
    setBusy(true); setError(''); setNotice(''); setOperation({ message: 'Reserving this draft in ELIS…', started: Date.now() })
    let claimed = false
    try {
      if (!await ping()) throw new Error(`Reload bank assistant ${REQUIRED_EXTENSION_VERSION} before preparing a form.`)
      const result = await bankMonitorApi.prepareDraft(tenantId, draft.id); claimed = true
      if (!active.current) throw new Error('Business changed. Preparation stopped.')
      setOperation({ message: 'Waiting for your approval in the extension review tab…', started: Date.now() })
      await send<ExtensionResponse>(extension, { type: 'ELIS_PREPARE', draft: result.data })
      setOperation({ message: 'Saving the prepared-form status…', started: Date.now() })
      await bankMonitorApi.draftOutcome(tenantId, draft.id, 'prepared_awaiting_submission')
      if (active.current) setNotice('Form prepared in Chrome. Review and submit it in Truliant; ELIS has not confirmed a transfer.')
    } catch (error: unknown) {
      const code = error instanceof Error && 'code' in error ? (error as Error & { code?: string }).code : undefined
      const notStarted = claimed && code === 'PREPARATION_NOT_STARTED'
      let restored = false
      if (claimed) { try { await bankMonitorApi.draftOutcome(tenantId, draft.id, notStarted ? 'preparation_not_started' : 'preparation_failed'); restored = notStarted } catch { /* Keep locked if outcome cannot be saved. */ } }
      if (active.current) { setNotice(restored ? 'Approval expired or was canceled. No bank form opened; the draft is ready again.' : ''); if (!restored) setError(errorMessage(error, 'Preparation failed. Review the bank tab before continuing.')) }
    } finally { if (active.current) { await reload().catch(() => undefined); setBusy(false); setOperation(null) } }
  }
  const verify = async (draft: Draft) => {
    setBusy(true); setError(''); setNotice(''); setOperation({ message: 'Checking both account histories…', started: Date.now() })
    let polling = true
    const poll = async () => {
      if (!polling) return
      try { const status = await send<ExtensionResponse>(extension, { type: 'ELIS_STATUS', id: draft.id }); if (active.current && status.progress?.message) setOperation(current => ({ message: status.progress?.message || '', started: current?.started || Date.now() })) } catch { /* Main request reports failures. */ }
      if (polling) window.setTimeout(() => void poll(), 900)
    }
    void poll()
    try {
      if (!await ping()) throw new Error(`Reload bank assistant ${REQUIRED_EXTENSION_VERSION} before checking histories.`)
      let result: ExtensionResponse
      try { result = await send<ExtensionResponse>(extension, { type: 'ELIS_VERIFY', draft }) }
      catch (error: unknown) {
        const code = error instanceof Error && 'code' in error ? (error as Error & { code?: string }).code : undefined
        if (code !== 'VERIFICATION_REAUTH_REQUIRED') throw error
        setNotice('Approve the read-only history window. It cannot prepare or submit a transfer.')
        setOperation({ message: 'Waiting for read-only approval…', started: Date.now() })
        await send<ExtensionResponse>(extension, { type: 'ELIS_REAUTHORIZE_VERIFY', draft })
        result = await send<ExtensionResponse>(extension, { type: 'ELIS_VERIFY', draft })
      }
      setOperation({ message: 'Saving the matched entries in ELIS…', started: Date.now() })
      await bankMonitorApi.draftHistoryMatch(tenantId, draft.id, result.evidence)
      await send<ExtensionResponse>(extension, { type: 'ELIS_ACK', id: draft.id })
      if (active.current) setNotice('Confirmed: one matching posted entry was found in each account history.')
    } catch (error: unknown) { fail(error, 'Bank verification failed. Completion remains unconfirmed.') }
    finally { polling = false; if (active.current) { await reload().catch(() => undefined); setBusy(false); setOperation(null) } }
  }

  const checkedRows = balanceCheck ? checking.map(account => ({ account, balance: balanceCheck.accounts.find(item => item.last4 === account.last4) })) : []
  const negativePosted = checkedRows.reduce((sum, row) => sum + Math.max(0, -(row.balance?.current_cents ?? 0)), 0)
  const actionableDrafts = drafts.filter(draft => statusMeta(draft.status).action !== 'done')
  const completedDrafts = drafts.filter(draft => statusMeta(draft.status).action === 'done')

  return <div className="space-y-5">
    <section className="overflow-hidden rounded-2xl bg-slate-950 text-white shadow-sm ring-1 ring-slate-900/10">
      <div className="grid gap-6 p-5 sm:p-7 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="min-w-0">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-300"><Icon name="clock" className="h-4 w-4" /> Current funding status</div>
          {!balanceCheck ? <><h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Are your checking accounts covered?</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">Run a read-only check for the current posted balance in each monitored checking account.</p></> : <>
            <div className="flex items-start gap-3"><span className={`mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full ${negativePosted ? 'bg-red-500/15 text-red-300' : 'bg-emerald-500/15 text-emerald-300'}`}><Icon name={negativePosted ? 'alert' : 'check'} /></span><div><h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{negativePosted ? `${money(negativePosted)} negative posted balance` : 'Checking accounts are positive'}</h2><p className="mt-2 text-sm text-slate-300">Checked {new Date(balanceCheck.checked_at).toLocaleString()} · Read-only; no transfer submitted.</p></div></div>
            <div className="mt-6 grid gap-2 sm:grid-cols-2">{checkedRows.map(({ account, balance }) => <div key={account.last4} className="rounded-xl bg-white/5 px-4 py-3 ring-1 ring-white/10"><p className="truncate text-sm text-slate-300">{account.nickname} · ••{account.last4}</p><p className={`mt-1 text-xl font-semibold tabular-nums ${balance?.current_cents != null && balance.current_cents < 0 ? 'text-red-300' : 'text-white'}`}>{balance?.current_cents == null ? 'Unavailable' : money(balance.current_cents)}</p></div>)}</div>
          </>}
        </div>
        <button type="button" disabled={busy || !connected} onClick={checkBalances} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-blue-500 px-5 py-3 font-semibold text-white shadow-sm transition duration-150 hover:bg-blue-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 motion-reduce:transition-none sm:w-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"><Icon name="refresh" className={`h-4 w-4 ${operation?.message.startsWith('Reading current') ? 'animate-spin motion-reduce:animate-none' : ''}`} />{operation?.message.startsWith('Reading current') ? 'Checking bank…' : 'Check bank now'}</button>
      </div>
      <div className="flex flex-col gap-3 border-t border-white/10 bg-white/[0.03] px-5 py-3 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-7"><div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-amber-400'}`} /><span className="text-slate-300">{connected ? 'Bank assistant connected' : 'Connect the bank assistant to check balances'}</span></div>{!connected && <button type="button" onClick={() => setEditingConnection(true)} className="min-h-11 self-start font-medium text-blue-300 hover:text-blue-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 sm:min-h-0">Connect assistant</button>}</div>
    </section>

    {(error || notice || operation) && <div className="space-y-2" aria-live="polite">{error && <div role="alert" className="flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900"><Icon name="alert" className="h-5 w-5 shrink-0" /><span>{error}</span></div>}{notice && <div role="status" className="flex gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"><Icon name="check" className="h-5 w-5 shrink-0" /><span>{notice}</span></div>}{operation && <div role="status" className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950"><span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-blue-700 border-t-transparent motion-reduce:animate-none" /><span>{operation.message} <span className="tabular-nums text-blue-700">{Math.max(0, Math.floor((clock - operation.started) / 1000))}s</span></span></div>}</div>}

    {(editingConnection || (!connected && !extension)) && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700"><Icon name="link" /></span><div><h2 className="font-semibold text-slate-950">Connect bank assistant</h2><p className="mt-1 text-sm text-slate-600">Saved only in this Chrome profile. Connecting also imports account names and masked last four digits.</p></div></div><label className="mt-4 block text-sm font-medium text-slate-700">Chrome extension ID<input className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3 text-slate-950 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" value={draftExtension} maxLength={32} onChange={e => setDraftExtension(e.target.value.trim())} placeholder="32-letter extension ID" /></label><div className="mt-4 flex flex-col gap-2 sm:flex-row"><button type="button" disabled={busy || !/^[a-p]{32}$/.test(draftExtension)} onClick={connect} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-blue-700 px-4 font-semibold text-white transition hover:bg-blue-800 active:scale-[0.98] disabled:opacity-45 motion-reduce:transition-none">{busy ? 'Connecting…' : connected ? 'Save replacement' : 'Connect and import'}</button>{connected && <button type="button" disabled={busy} onClick={() => { setDraftExtension(extension); setEditingConnection(false); setError('') }} className="min-h-11 rounded-xl px-4 font-medium text-slate-700 hover:bg-slate-100">Cancel</button>}</div></section>}

    {connected && <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Action queue</p><h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">Transfers to prepare</h2><p className="mt-1 text-sm text-slate-600">{actionableDrafts.length ? `${actionableDrafts.length} transfer${actionableDrafts.length === 1 ? '' : 's'} need attention.` : 'No transfers need attention.'}</p></div><button type="button" disabled={busy} onClick={discoverAccounts} className="min-h-11 self-start rounded-xl px-3 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-45">Refresh accounts</button></div>
      <div className="divide-y divide-slate-200">{actionableDrafts.length === 0 && <div className="p-8 text-center"><span className="mx-auto grid h-10 w-10 place-items-center rounded-full bg-emerald-50 text-emerald-700"><Icon name="check" /></span><p className="mt-3 font-medium text-slate-900">Queue is clear</p><p className="mt-1 text-sm text-slate-600">New reviewed charges will appear here.</p></div>}{actionableDrafts.map(draft => { const meta = statusMeta(draft.status); return <article key={draft.id} className="grid gap-4 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="text-lg font-semibold tabular-nums text-slate-950">{money(draft.amount_cents)}</p><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${meta.tone}`}>{meta.label}</span></div><p className="mt-1 truncate font-medium text-slate-800">{draft.memo}</p><p className="mt-1 text-sm text-slate-500">••{draft.from_last4} <span aria-hidden="true">→</span> ••{draft.to_last4} · {draft.charge_reference}</p></div>{meta.action === 'prepare' && <button disabled={busy} onClick={() => prepare(draft)} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 font-semibold text-white transition hover:bg-blue-800 active:scale-[0.98] disabled:opacity-45 motion-reduce:transition-none sm:w-auto">Prepare in Truliant <Icon name="arrow" className="h-4 w-4" /></button>}{meta.action === 'verify' && <button disabled={busy} onClick={() => verify(draft)} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-45 sm:w-auto">Verify bank histories <Icon name="arrow" className="h-4 w-4" /></button>}{meta.action === 'blocked' && <p className="max-w-xs text-sm text-red-700">Review both bank histories before attempting this draft again.</p>}</article> })}</div>
      <div className="border-t border-slate-200 p-4"><button type="button" onClick={() => { setManualOpen(value => !value); setError('') }} className="min-h-11 rounded-xl px-3 text-sm font-semibold text-blue-700 hover:bg-blue-50">{manualOpen ? 'Close manual entry' : 'Add a charge manually'}</button></div>
      {manualOpen && <form onSubmit={create} className="border-t border-slate-200 bg-slate-50/70 p-5"><div className="mb-5"><h3 className="font-semibold text-slate-950">Add an individual charge</h3><p className="mt-1 text-sm text-slate-600">Use one draft for one full posted charge. No transfer is submitted when you add it.</p></div><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-3">Unique charge reference<input required maxLength={120} pattern="[A-Za-z0-9 .:_\-]+" className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" value={reference} onChange={e => { setReference(e.target.value); setReviewed(false) }} /></label><label className="text-sm font-medium text-slate-700">Full amount<input required inputMode="decimal" className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" placeholder="118.20" value={amount} onChange={e => { setAmount(e.target.value); setReviewed(false) }} /></label><label className="min-w-0 text-sm font-medium text-slate-700">From<select required className="mt-2 block min-h-11 w-full min-w-0 rounded-xl border border-slate-300 bg-white px-3" value={from} onChange={e => { setFrom(e.target.value); setReviewed(false) }}><option value="">Select source</option>{sources.map(a => <option key={a.last4} value={a.last4}>{a.nickname} · {a.last4}</option>)}</select></label><label className="min-w-0 text-sm font-medium text-slate-700">To<select required className="mt-2 block min-h-11 w-full min-w-0 rounded-xl border border-slate-300 bg-white px-3" value={to} onChange={e => { setTo(e.target.value); setReviewed(false) }}><option value="">Select checking</option>{checking.map(a => <option key={a.last4} value={a.last4}>{a.nickname} · {a.last4}</option>)}</select></label><label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-3">Memo<input required maxLength={34} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" value={memo} onChange={e => { setMemo(e.target.value); setReviewed(false) }} /><span className="mt-1 block text-xs font-normal text-slate-500">Starts with Cvr · 34 characters maximum</span></label></div><label className="mt-5 flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700"><input type="checkbox" className="mt-0.5 h-4 w-4" checked={reviewed} onChange={e => setReviewed(e.target.checked)} /><span>I checked the bank history. This charge needs funding and has no matching transfer or unresolved submission.</span></label><div className="mt-4 flex flex-col gap-2 sm:flex-row"><button disabled={busy || !reviewed} className="min-h-11 rounded-xl bg-blue-700 px-4 font-semibold text-white hover:bg-blue-800 disabled:opacity-45">Add reviewed transfer</button><button type="button" disabled={busy} onClick={() => { setManualOpen(false); setError('') }} className="min-h-11 rounded-xl px-4 font-medium text-slate-700 hover:bg-slate-200">Cancel</button></div></form>}
      {completedDrafts.length > 0 && <details className="border-t border-slate-200"><summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500">Completed transfers ({completedDrafts.length})</summary><div className="divide-y divide-slate-200 border-t border-slate-200">{completedDrafts.map(draft => <div key={draft.id} className="flex flex-col gap-1 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="font-medium text-slate-800">{money(draft.amount_cents)} · {draft.memo}</span><span className="text-emerald-700">Matched in both histories</span></div>)}</div></details>}
    </section>}
  </div>
}
