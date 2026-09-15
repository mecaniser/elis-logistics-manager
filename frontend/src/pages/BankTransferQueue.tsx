import { useCallback, useEffect, useRef, useState } from 'react'
import { bankMonitorApi } from '../services/api'
import BankSelect from '../components/BankSelect'

type Account = { nickname: string; last4: string; kind?: 'checking' | 'credit' | 'other' }
type Draft = { id: string; charge_reference: string; amount_cents: number; from_last4: string; to_last4: string; memo: string; status: string; bank_date: string }
type ExtensionResponse = { ok: boolean; error?: string; code?: string; version?: string; accounts?: Account[]; progress?: { message?: string }; evidence?: unknown; checked_at?: string; [key: string]: unknown }
type ChromeRuntime = { sendMessage: (extension: string, message: unknown, callback: (response?: ExtensionResponse) => void) => void; lastError?: unknown }
type BalanceAccount = { last4: string; current_cents: number | null; available_cents: number | null; available_credit_cents: number | null }
type PostedDebit = { reference: string; date: string; description: string; amount_cents: number; balance_cents: number | null; pending?: boolean }
type BalanceCheck = { checked_at: string; accounts: BalanceAccount[]; coverage: { last4: string; transactions: PostedDebit[]; overdraft_detected?: boolean; error?: string | null }[] }
type BalanceResponse = { ok: boolean; error?: string; code?: string } & BalanceCheck

const REQUIRED_EXTENSION_VERSION = '0.1.18'
const SELF_RELOAD_VERSION = '0.1.19'
const versionAtLeast = (current: string | undefined, minimum: string) => {
  const parsed = (value: string | undefined) => String(value || '').split('.').map(part => Number(part))
  const left = parsed(current); const right = parsed(minimum)
  if (left.some(Number.isNaN) || right.some(Number.isNaN)) return false
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const difference = (left[index] || 0) - (right[index] || 0)
    if (difference) return difference > 0
  }
  return true
}
const runtime = () => (window as Window & { chrome?: { runtime?: ChromeRuntime } }).chrome?.runtime
const money = (cents: number) => (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback
const draftReference = (last4: string, transaction: PostedDebit) => `bank-${last4}-${transaction.reference.slice(0, 32)}`
const memoFor = (transaction: PostedDebit) => {
  const clean = transaction.description.replace(/[^A-Za-z0-9 ._-]+/g, ' ').replace(/\s+/g, ' ').trim()
  const parsed = new Date(transaction.date)
  const dateCode = Number.isNaN(parsed.valueOf()) ? '' : `${String(parsed.getMonth() + 1).padStart(2, '0')}${String(parsed.getDate()).padStart(2, '0')}`
  const available = dateCode ? 25 : 30
  const subject = clean.slice(0, available).trim().replace(/[ ._-]+$/, '') || 'posted charge'
  return `Cvr ${subject}${dateCode ? ` ${dateCode}` : ''}`
}
const coverageText = (value: string) => value.toLowerCase().replace(/^cvr\s+/, '').replace(/[^a-z0-9]+/g, '')
const matchesExistingDraft = (draft: Draft, destination: Account, transaction: PostedDebit, reference: string, memo: string) => {
  if (draft.charge_reference === reference) return true
  if (draft.to_last4 !== destination.last4 || draft.amount_cents !== transaction.amount_cents) return false
  const existing = coverageText(draft.memo)
  const proposed = coverageText(memo)
  return existing.length >= 5 && proposed.length >= 5 && (existing.startsWith(proposed) || proposed.startsWith(existing))
}
const send = <T extends { ok: boolean; error?: string; code?: string }>(extension: string, message: unknown): Promise<T> => new Promise((resolve, reject) => {
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

export default function BankTransferQueue({ tenantId, checking, sources, basis, onAccountsDiscovered }: { tenantId: number; checking: Account[]; sources: Account[]; basis: string; onAccountsDiscovered: (accounts: Account[]) => void }) {
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [extension, setExtension] = useState(localStorage.getItem('elis-bank-extension-id') || '')
  const [draftExtension, setDraftExtension] = useState(extension)
  const [connected, setConnected] = useState(false)
  const [connectionState, setConnectionState] = useState<'checking' | 'connected' | 'outdated' | 'unavailable' | 'unconfigured'>(extension ? 'checking' : 'unconfigured')
  const [detectedVersion, setDetectedVersion] = useState('')
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
  const [coverageIssue, setCoverageIssue] = useState('')
  const active = useRef(true)

  const markDisconnected = useCallback(() => { setConnected(false); setConnectionState(extension ? 'unavailable' : 'unconfigured') }, [extension])
  const ping = useCallback(async () => {
    if (!extension) { if (active.current) setConnectionState('unconfigured'); return false }
    try {
      const response = await send<ExtensionResponse>(extension, { type: 'ELIS_PING' })
      const valid = versionAtLeast(response.version, REQUIRED_EXTENSION_VERSION)
      if (active.current) { setDetectedVersion(response.version || 'unknown'); setConnected(valid); setConnectionState(valid ? 'connected' : 'outdated') }
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
      if (!from || !to) throw new Error('Select both the funding source and checking destination.')
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
      if (!versionAtLeast(response.version, REQUIRED_EXTENSION_VERSION)) throw new Error(`Extension ${response.version || 'version unknown'} is loaded. Reload version ${REQUIRED_EXTENSION_VERSION} or newer.`)
      localStorage.setItem('elis-bank-extension-id', candidate)
      if (active.current) { setExtension(candidate); setDraftExtension(candidate); setConnected(true); setConnectionState('connected'); setDetectedVersion(response.version || ''); setEditingConnection(false) }
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
  const reloadAssistant = async () => {
    if (!versionAtLeast(detectedVersion, SELF_RELOAD_VERSION)) { void ping(); return }
    setBusy(true); setError(''); setNotice(''); setOperation({ message: 'Reloading the saved bank assistant…', started: Date.now() })
    try {
      await send<ExtensionResponse>(extension, { type: 'ELIS_RELOAD' })
      for (let attempt = 0; attempt < 30; attempt += 1) {
        await new Promise(resolve => window.setTimeout(resolve, 300))
        try {
          const response = await send<ExtensionResponse>(extension, { type: 'ELIS_PING' })
          if (versionAtLeast(response.version, REQUIRED_EXTENSION_VERSION)) {
            if (active.current) { setDetectedVersion(response.version || ''); setConnected(true); setConnectionState('connected'); setNotice('Bank assistant reloaded and reconnected. Your saved accounts were preserved.') }
            return
          }
        } catch { /* The extension is briefly unavailable while Chrome reloads it. */ }
      }
      throw new Error('The extension reload started but did not reconnect. Reload it from chrome://extensions, then return here.')
    } catch (error: unknown) { if (active.current) setError(errorMessage(error, 'Unable to reload the bank assistant.')) }
    finally { if (active.current) { setBusy(false); setOperation(null) } }
  }
  const checkBalances = async () => {
    setBusy(true); setError(''); setNotice(''); setCoverageIssue(''); setOperation({ message: 'Reading balances and transaction histories from Truliant…', started: Date.now() })
    let bankRead = false
    try {
      if (!checking.length || !sources.length) throw new Error('Import and save the checking and credit accounts first.')
      const suffixes = [...checking, ...sources].map(account => account.last4)
      const result = await send<BalanceResponse>(extension, { type: 'ELIS_CHECK_BALANCES', suffixes, checking_suffixes: checking.map(account => account.last4), include_pending: basis === 'posted_and_pending' })
      bankRead = true
      if (!active.current) return
      setConnected(true); setBalanceCheck(result)
      setOperation({ message: 'Building the queue from uncovered posted and pending charges…', started: Date.now() })
      const existing = (await bankMonitorApi.drafts(tenantId)).data as Draft[]
      const accountBySuffix = new Map(result.accounts.map(account => [account.last4, account]))
      const sourceBalances = sources.map(source => ({ source, available: accountBySuffix.get(source.last4)?.available_credit_cents ?? null }))
      let created = 0
      let identified = 0
      const issues: string[] = []
      for (const destination of checking) {
        const balance = accountBySuffix.get(destination.last4)
        if (balance?.current_cents == null) { issues.push(`Posted balance for ••${destination.last4} was unavailable.`); continue }
        const history = result.coverage?.find(item => item.last4 === destination.last4)
        if (!history || history.error) {
          issues.push(history?.error || `Account history for ••${destination.last4} was unavailable.`)
          continue
        }
        const pendingCandidates = history.transactions.filter(transaction => transaction.pending)
        const postedCandidates = history.transactions.filter(transaction => !transaction.pending)
        if (balance.current_cents >= 0 && !history.overdraft_detected && pendingCandidates.length === 0) continue
        const pending = existing.filter(draft => draft.to_last4 === destination.last4 && statusMeta(draft.status).action !== 'done')
          .reduce((sum, draft) => sum + draft.amount_cents, 0)
        let remaining = Math.max(0, -balance.current_cents - pending)
        const candidates = [...pendingCandidates, ...postedCandidates]
        for (const transaction of candidates) {
          if (!transaction.pending && !history.overdraft_detected && remaining <= 0) break
          const chargeReference = draftReference(destination.last4, transaction)
          const transactionMemo = memoFor(transaction)
          if (existing.some(draft => matchesExistingDraft(draft, destination, transaction, chargeReference, transactionMemo))) continue
          const sourceRow = sourceBalances.find(row => (row.available ?? -1) >= transaction.amount_cents)
          if (!sourceRow) {
            issues.push(`${money(transaction.amount_cents)} ${transaction.description} cannot be covered in full by one funding source.`)
            continue
          }
          identified += 1
          try {
            await bankMonitorApi.createDraft(tenantId, { charge_reference: chargeReference, amount_cents: transaction.amount_cents, from_last4: sourceRow.source.last4, to_last4: destination.last4, memo: transactionMemo })
            created += 1
            sourceRow.available = (sourceRow.available ?? 0) - transaction.amount_cents
          } catch (error: unknown) {
            if ((error as { response?: { status?: number } })?.response?.status !== 409) throw error
          }
          remaining = Math.max(0, remaining - transaction.amount_cents)
        }
        if (balance.current_cents < 0 && remaining > 0) issues.push(`${money(remaining)} of the negative balance in ••${destination.last4} could not be tied to an uncovered posted charge.`)
      }
      await reload()
      if (issues.length) setCoverageIssue(issues.join(' '))
      const negative = result.accounts.filter(account => checking.some(item => item.last4 === account.last4) && (account.current_cents ?? 0) < 0)
      if (!negative.length && !created && !identified) setNotice('All configured accounts and transaction histories were checked. No new coverage transfer is needed.')
      else if (created) setNotice(`${created} coverage draft${created === 1 ? '' : 's'} created. Prepare each one in the action queue.`)
      else if (identified) setNotice('The coverage queue is already current for the posted charges found.')
      else if (!issues.length) setNotice('The negative balance is already covered by transfer drafts in the action queue.')
    } catch (error: unknown) {
      if (bankRead) { if (active.current) setError(errorMessage(error, 'Balances were read, but the coverage queue could not be updated.')) }
      else fail(error, 'Unable to check balances.')
    }
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
  const fundingRows = balanceCheck ? sources.map(account => ({ account, balance: balanceCheck.accounts.find(item => item.last4 === account.last4) })) : []
  const negativePosted = checkedRows.reduce((sum, row) => sum + Math.max(0, -(row.balance?.current_cents ?? 0)), 0)
  const actionableDrafts = drafts.filter(draft => statusMeta(draft.status).action !== 'done')
  const completedDrafts = drafts.filter(draft => statusMeta(draft.status).action === 'done')
  const connectionText = connected ? 'Bank assistant connected automatically' : connectionState === 'checking' ? 'Checking the saved bank assistant…' : connectionState === 'outdated' ? `Bank assistant update required · ${detectedVersion} loaded` : extension ? 'Saved bank assistant is temporarily unavailable' : 'Connect the bank assistant once to get started'

  return <div className="space-y-5">
    <section className="overflow-hidden rounded-2xl bg-slate-950 text-white shadow-sm ring-1 ring-slate-900/10">
      <div className="grid gap-6 p-5 sm:p-7 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="min-w-0">
          <div className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-300"><Icon name="clock" className="h-4 w-4" /> Current funding status</div>
          {!balanceCheck ? <><h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Are your checking accounts covered?</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">Check both business checking accounts and every funding source, then build the transfer queue from uncovered posted charges.</p></> : <>
            <div className="flex items-start gap-3"><span className={`mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full ${negativePosted ? 'bg-red-500/15 text-red-300' : 'bg-emerald-500/15 text-emerald-300'}`}><Icon name={negativePosted ? 'alert' : 'check'} /></span><div><h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">{negativePosted ? `${money(negativePosted)} negative posted balance` : 'Checking accounts are positive'}</h2><p className="mt-2 text-sm text-slate-300">Checked {new Date(balanceCheck.checked_at).toLocaleString()} · Read-only; no transfer submitted.</p></div></div>
            <div className="mt-6 grid gap-5 xl:grid-cols-2">
              <div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Checking</p><div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">{checkedRows.map(({ account, balance }) => <div key={account.last4} className="rounded-xl bg-white/5 px-4 py-3 ring-1 ring-white/10"><p className="truncate text-sm text-slate-300">{account.nickname} · ••{account.last4}</p><p className={`mt-1 text-xl font-semibold tabular-nums ${balance?.current_cents != null && balance.current_cents < 0 ? 'text-red-300' : 'text-white'}`}>{balance?.current_cents == null ? 'Unavailable' : money(balance.current_cents)}</p><p className="mt-1 text-xs text-slate-400">Posted balance{balance?.available_cents != null && balance.available_cents !== balance.current_cents ? ` · ${money(balance.available_cents)} available` : ''}</p></div>)}</div></div>
              <div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Funding sources</p><div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">{fundingRows.map(({ account, balance }) => <div key={account.last4} className="rounded-xl bg-white/5 px-4 py-3 ring-1 ring-white/10"><p className="truncate text-sm text-slate-300">{account.nickname} · ••{account.last4}</p><p className="mt-1 text-xl font-semibold tabular-nums text-white">{balance?.available_credit_cents == null ? 'Unavailable' : money(balance.available_credit_cents)}</p><p className="mt-1 text-xs text-slate-400">Available credit{balance?.current_cents != null ? ` · ${money(balance.current_cents)} outstanding` : ''}</p></div>)}</div></div>
            </div>
          </>}
        </div>
        <button type="button" disabled={busy || !connected} onClick={checkBalances} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-blue-500 px-5 py-3 font-semibold text-white shadow-sm transition duration-150 hover:bg-blue-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 motion-reduce:transition-none sm:w-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-300 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"><Icon name="refresh" className={`h-4 w-4 ${operation?.message.startsWith('Reading balances') ? 'animate-spin motion-reduce:animate-none' : ''}`} />{operation?.message.startsWith('Reading balances') ? 'Checking bank…' : 'Check bank now'}</button>
      </div>
      <div className="border-t border-white/10 bg-white/[0.03] px-5 py-3 text-sm sm:px-7"><div className="flex items-center gap-2"><span className={`h-2 w-2 rounded-full ${connected ? 'bg-emerald-400' : connectionState === 'checking' ? 'animate-pulse bg-blue-400 motion-reduce:animate-none' : 'bg-amber-400'}`} /><span className="text-slate-300">{connectionText}</span></div></div>
    </section>

    {(error || notice || coverageIssue || operation) && <div className="space-y-2" aria-live="polite">{error && <div role="alert" className="flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900"><Icon name="alert" className="h-5 w-5 shrink-0" /><span>{error}</span></div>}{coverageIssue && <div role="alert" className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"><Icon name="alert" className="h-5 w-5 shrink-0" /><span><strong>Coverage needs review.</strong> {coverageIssue}</span></div>}{notice && <div role="status" className="flex gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"><Icon name="check" className="h-5 w-5 shrink-0" /><span>{notice}</span></div>}{operation && <div role="status" className="flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-950"><span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-blue-700 border-t-transparent motion-reduce:animate-none" /><span>{operation.message} <span className="tabular-nums text-blue-700">{Math.max(0, Math.floor((clock - operation.started) / 1000))}s</span></span></div>}</div>}

    {!connected && extension && !editingConnection && connectionState !== 'checking' && <section className="flex flex-col gap-4 rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between"><div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white text-amber-700 ring-1 ring-amber-200"><Icon name="refresh" /></span><div><h2 className="font-semibold text-amber-950">{connectionState === 'outdated' ? 'Reload the saved bank assistant' : 'Bank assistant did not respond'}</h2><p className="mt-1 text-sm leading-6 text-amber-900">{connectionState === 'outdated' ? versionAtLeast(detectedVersion, SELF_RELOAD_VERSION) ? `Chrome has version ${detectedVersion}; ELIS needs ${REQUIRED_EXTENSION_VERSION}. Reload it here without changing the saved extension ID or accounts.` : `Chrome still has version ${detectedVersion}. Open chrome://extensions, reload ELIS Bank Form Assistant once, then return here. Your extension ID and imported accounts remain saved.` : 'The saved extension ID and account setup remain intact. Chrome may still be restarting the extension.'}</p></div></div><div className="flex shrink-0 gap-2"><button type="button" disabled={busy} onClick={() => connectionState === 'outdated' ? void reloadAssistant() : void ping()} className="min-h-11 rounded-xl bg-amber-900 px-4 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-50">{connectionState === 'outdated' ? versionAtLeast(detectedVersion, SELF_RELOAD_VERSION) ? 'Reload assistant now' : 'Check after reload' : 'Try reconnecting'}</button><button type="button" onClick={() => setEditingConnection(true)} className="min-h-11 rounded-xl px-3 text-sm font-semibold text-amber-900 hover:bg-amber-100">Change extension</button></div></section>}

    {(editingConnection || !extension) && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-start gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700"><Icon name="link" /></span><div><h2 className="font-semibold text-slate-950">{extension ? 'Change bank assistant' : 'Connect bank assistant'}</h2><p className="mt-1 text-sm text-slate-600">The extension ID is saved in this Chrome profile. Account import runs only when you connect a new extension.</p></div></div><label className="mt-4 block text-sm font-medium text-slate-700">Chrome extension ID<input className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3 text-slate-950 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" value={draftExtension} maxLength={32} onChange={e => setDraftExtension(e.target.value.trim())} placeholder="32-letter extension ID" /></label><div className="mt-4 flex flex-col gap-2 sm:flex-row"><button type="button" disabled={busy || !/^[a-p]{32}$/.test(draftExtension)} onClick={connect} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-blue-700 px-4 font-semibold text-white transition hover:bg-blue-800 active:scale-[0.98] disabled:opacity-45 motion-reduce:transition-none">{busy ? 'Connecting…' : extension ? 'Save replacement' : 'Connect and import'}</button>{extension && <button type="button" disabled={busy} onClick={() => { setDraftExtension(extension); setEditingConnection(false); setError('') }} className="min-h-11 rounded-xl px-4 font-medium text-slate-700 hover:bg-slate-100">Cancel</button>}</div></section>}

    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Action queue</p><h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">Transfers to prepare</h2><p className="mt-1 text-sm text-slate-600">{actionableDrafts.length ? `${actionableDrafts.length} transfer${actionableDrafts.length === 1 ? '' : 's'} need attention.` : 'No transfers need attention.'}</p></div><button type="button" disabled={busy || !connected} onClick={discoverAccounts} className="min-h-11 self-start rounded-xl px-3 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:cursor-not-allowed disabled:text-blue-300 disabled:hover:bg-transparent">Refresh accounts</button></div>
      <div className="divide-y divide-slate-200">{actionableDrafts.length === 0 && <div className="p-8 text-center"><span className="mx-auto grid h-10 w-10 place-items-center rounded-full bg-emerald-50 text-emerald-700"><Icon name="check" /></span><p className="mt-3 font-medium text-slate-900">Queue is clear</p><p className="mt-1 text-sm text-slate-600">New reviewed charges will appear here.</p></div>}{actionableDrafts.map(draft => { const meta = statusMeta(draft.status); return <article key={draft.id} className="grid gap-4 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><p className="text-lg font-semibold tabular-nums text-slate-950">{money(draft.amount_cents)}</p><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${meta.tone}`}>{meta.label}</span></div><p className="mt-1 truncate font-medium text-slate-800">{draft.memo}</p><p className="mt-1 text-sm text-slate-500">••{draft.from_last4} <span aria-hidden="true">→</span> ••{draft.to_last4} · {draft.charge_reference}</p></div>{meta.action === 'prepare' && <button disabled={busy || !connected} onClick={() => prepare(draft)} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 font-semibold text-white transition hover:bg-blue-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 motion-reduce:transition-none sm:w-auto">Prepare in Truliant <Icon name="arrow" className="h-4 w-4" /></button>}{meta.action === 'verify' && <button disabled={busy || !connected} onClick={() => verify(draft)} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-4 font-semibold text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-45 sm:w-auto">Verify bank histories <Icon name="arrow" className="h-4 w-4" /></button>}{meta.action === 'blocked' && <p className="max-w-xs text-sm text-red-700">Review both bank histories before attempting this draft again.</p>}</article> })}</div>
      <div className="border-t border-slate-200 p-4"><button type="button" onClick={() => { setManualOpen(value => !value); setError('') }} className="min-h-11 rounded-xl px-3 text-sm font-semibold text-blue-700 hover:bg-blue-50">{manualOpen ? 'Close manual entry' : 'Add a charge manually'}</button></div>
      {manualOpen && <form onSubmit={create} className="border-t border-slate-200 bg-slate-50/70 p-5"><div className="mb-5"><h3 className="font-semibold text-slate-950">Add an individual charge</h3><p className="mt-1 text-sm text-slate-600">Use one draft for one full posted charge. No transfer is submitted when you add it.</p></div><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"><label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-3">Unique charge reference<input required maxLength={120} pattern="[A-Za-z0-9 .:_\-]+" className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" value={reference} onChange={e => { setReference(e.target.value); setReviewed(false) }} /></label><label className="text-sm font-medium text-slate-700">Full amount<input required inputMode="decimal" className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" placeholder="118.20" value={amount} onChange={e => { setAmount(e.target.value); setReviewed(false) }} /></label><label className="min-w-0 text-sm font-medium text-slate-700">From<BankSelect required ariaLabel="Funding source" value={from} options={[{ value: '', label: 'Select source' }, ...sources.map(a => ({ value: a.last4, label: `${a.nickname} · ••${a.last4}` }))]} onChange={value => { setFrom(value); setReviewed(false) }} /></label><label className="min-w-0 text-sm font-medium text-slate-700">To<BankSelect required ariaLabel="Checking destination" value={to} options={[{ value: '', label: 'Select checking' }, ...checking.map(a => ({ value: a.last4, label: `${a.nickname} · ••${a.last4}` }))]} onChange={value => { setTo(value); setReviewed(false) }} /></label><label className="text-sm font-medium text-slate-700 sm:col-span-2 lg:col-span-3">Memo<input required maxLength={34} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-100" value={memo} onChange={e => { setMemo(e.target.value); setReviewed(false) }} /><span className="mt-1 block text-xs font-normal text-slate-500">Starts with Cvr · 34 characters maximum</span></label></div><label className="mt-5 flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700"><input type="checkbox" className="mt-0.5 h-4 w-4" checked={reviewed} onChange={e => setReviewed(e.target.checked)} /><span>I checked the bank history. This charge needs funding and has no matching transfer or unresolved submission.</span></label><div className="mt-4 flex flex-col gap-2 sm:flex-row"><button disabled={busy || !reviewed} className="min-h-11 rounded-xl bg-blue-700 px-4 font-semibold text-white hover:bg-blue-800 disabled:opacity-45">Add reviewed transfer</button><button type="button" disabled={busy} onClick={() => { setManualOpen(false); setError('') }} className="min-h-11 rounded-xl px-4 font-medium text-slate-700 hover:bg-slate-200">Cancel</button></div></form>}
      {completedDrafts.length > 0 && <details className="border-t border-slate-200"><summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500">Completed transfers ({completedDrafts.length})</summary><div className="divide-y divide-slate-200 border-t border-slate-200">{completedDrafts.map(draft => <div key={draft.id} className="flex flex-col gap-1 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="font-medium text-slate-800">{money(draft.amount_cents)} · {draft.memo}</span><span className="text-emerald-700">Matched in both histories</span></div>)}</div></details>}
    </section>
  </div>
}
