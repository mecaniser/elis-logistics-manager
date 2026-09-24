import { useEffect, useRef, useState } from 'react'
import { bankMonitorApi } from '../services/api'
import BankTransferQueue from './BankTransferQueue'
import BankSelect from '../components/BankSelect'
import MoneyInput from '../components/MoneyInput'
import { centsFromMoneyInput, incomeExceedsCash } from '../components/moneyAmount'
import { useTenant } from '../contexts/TenantContext'

type Account = { nickname: string; last4: string; kind?: 'checking' | 'credit' | 'other' }
type Repayment = { enabled: boolean; priority: string[]; reserve_cents: number | null }
type Rules = { repayment: Repayment; enabled: boolean; checking: Account[]; sources: Account[]; basis: string; buffer_cents: number }
type Run = { id: number; scheduled_date: string; started_at: string; status: string; result: {
  credit_accounts?: { last4: string; nickname: string; outstanding_cents: number | null; accrued_interest_cents: number | null }[];
  repayment?: { status: string; proposals: { from_last4: string; to_last4: string; amount_cents: number }[] };
  observed_at?: string; uncovered_cents?: number; message?: string;
  accounts?: { last4: string; nickname: string; current_cents: number; available_cents: number | null; needed_cents: number }[];
  proposals?: { from_last4: string; to_last4: string; amount_cents: number }[];
} }
type RepaymentRun = { id: number; started_at: string; status: string; result: {
  proposals: { from_last4: string; to_last4: string; amount_cents: number }[];
  observed_at: string; transfers_executed: false; drafts_created?: boolean;
} }
type ConnectionCheck = { id: number; status: string; requested_at: string; finished_at: string | null; result: { observed_at?: string; account_count?: number } }
type BrowserCheck = { id: number; status: string; observed_at: string; result: { source: string; repayment?: { status: string } } }
type Dashboard = { rules: Rules; reader_mode: 'private_worker' | 'signed_in_chrome'; next_check: string; worker: { status: 'online' | 'offline'; last_seen_at: string | null }; connection_check: ConnectionCheck | null; browser_check: BrowserCheck | null; runs: Run[]; repayment_runs: RepaymentRun[] }
type CheckingEvidence = { current: string; pending: string; settled: string; income: string; incomeDate: string }
type BankRead = {
  checked_at: string;
  accounts: { last4: string; current_cents: number | null; available_cents: number | null; available_credit_cents: number | null }[];
  coverage: { last4: string; transactions: { amount_cents: number; pending?: boolean }[] }[];
}

const dollars = (cents: number) => (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const label = (status: string) => status.replace(/_/g, ' ')
const scheduledIssue = (status: string) => {
  if (status === 'chrome_check_missed') return {
    title: 'Chrome check missed',
    detail: 'No complete signed-in Chrome bank read reached ELIS during the 5:30–5:45 p.m. Eastern window. Open Chrome and sign in to Truliant, then run Check bank now. No balance or repayment was inferred for the missed slot.',
  }
  if (status === 'bank_security_challenge') return {
    title: 'Bank blocked the server browser',
    detail: 'Truliant showed a security challenge before the worker could reach its sign-in form. No accounts were read and no login was submitted. Use the signed-in Chrome assistant for a current check; server scheduling cannot be considered verified.',
  }
  if (status === 'profile_setup_required') return {
    title: 'Bank access not set up',
    detail: 'The scheduled worker has no private Truliant browser profile. This check did not read any accounts. A Chrome extension connection does not connect the server worker; a system administrator must set up and verify its separate bank access.',
  }
  if (status === 'connection_required') return {
    title: 'Worker bank connection missing',
    detail: 'The scheduled worker has no bank profile configured. This check did not read any accounts. A system administrator must configure and verify the worker connection.',
  }
  if (status === 'credentials_required') return {
    title: 'Worker sign-in not configured',
    detail: 'The worker reached the bank sign-in step but has no worker-only credentials. This check did not read any accounts. A system administrator must configure secure worker credentials and verify sign-in.',
  }
  if (status === 'profile_permissions_required') return {
    title: 'Worker profile access blocked',
    detail: 'The worker cannot safely use its private browser profile. This check did not read any accounts. A system administrator must correct its profile permissions.',
  }
  if (['mfa_required', 'login_review_required', 'sign_in_required', 'unexpected_login_page'].includes(status)) return {
    title: 'Worker bank sign-in needs review',
    detail: 'The scheduled worker could not complete Truliant sign-in. This check did not read any accounts. An operator must review the separate worker session and any bank verification step.',
  }
  if (status === 'check_interrupted') return {
    title: 'Worker bank check interrupted',
    detail: 'The private worker stopped before confirming the bank read. No automatic retry was made; an operator must inspect the worker session before another sign-in attempt.',
  }
  return null
}
const defaults: Rules = { repayment: { enabled: false, priority: [], reserve_cents: 0 }, enabled: false, checking: [], sources: [], basis: 'posted', buffer_cents: 0 }
const apiError = (error: unknown, fallback: string) => {
  if (typeof error === 'object' && error && 'response' in error) {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response
    if (typeof response?.data?.detail === 'string') return response.data.detail
  }
  return fallback
}
const easternDate = () => {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date())
  const value = Object.fromEntries(parts.map(part => [part.type, part.value]))
  return `${value.year}-${value.month}-${value.day}`
}
const dollarsInput = (cents: number | null | undefined) => cents == null ? '' : (cents / 100).toFixed(2)

function Icon({ name, className = 'h-5 w-5' }: { name: 'calendar' | 'shield' | 'settings' | 'history' | 'check' | 'pause' | 'close'; className?: string }) {
  const paths = {
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
    history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5M12 7v5l3 2" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    pause: <><path d="M9 5v14M15 5v14" /></>,
    close: <><path d="m6 6 12 12" /><path d="M18 6 6 18" /></>,
  }
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>{paths[name]}</svg>
}

export default function BankMonitor() {
  const { currentTenant } = useTenant()
  const currentTenantId = currentTenant?.id
  const tenantRef = useRef(currentTenantId)
  tenantRef.current = currentTenantId
  const [loadedTenant, setLoadedTenant] = useState<number | null>(null)
  const [data, setData] = useState<Dashboard | null>(null)
  const [rules, setRules] = useState<Rules>(defaults)
  const [error, setError] = useState('')
  const [settingsError, setSettingsError] = useState('')
  const [settingsNotice, setSettingsNotice] = useState('')
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)
  const [verifyingWorker, setVerifyingWorker] = useState(false)
  const [verificationError, setVerificationError] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [repaymentOpen, setRepaymentOpen] = useState(false)
  const [repaying, setRepaying] = useState(false)
  const [repaymentError, setRepaymentError] = useState('')
  const [repaymentNotice, setRepaymentNotice] = useState('')
  const [evidenceConfirmed, setEvidenceConfirmed] = useState(false)
  const [checkingEvidence, setCheckingEvidence] = useState<Record<string, CheckingEvidence>>({})
  const [sourceEvidence, setSourceEvidence] = useState<Record<string, string>>({})
  const [latestBankRead, setLatestBankRead] = useState<BankRead | null>(null)
  const [queueVersion, setQueueVersion] = useState(0)
  const settingsButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!settingsOpen && !repaymentOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSettingsOpen(false)
        setRepaymentOpen(false)
        window.setTimeout(() => settingsButtonRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [settingsOpen, repaymentOpen])

  useEffect(() => {
    if (!currentTenantId) return
    const tenantId = currentTenantId
    let active = true
    setData(null); setError(''); setLoading(true)
    bankMonitorApi.get(tenantId).then(({ data: value }) => {
      if (active) { setData(value); setRules({ ...value.rules, repayment: value.rules.repayment || defaults.repayment }); setLoadedTenant(tenantId) }
    }).catch(error => { if (active) setError(apiError(error, 'Unable to load bank monitoring.')) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [currentTenantId])

  useEffect(() => {
    const status = data?.connection_check?.status
    if (!currentTenantId || loadedTenant !== currentTenantId || (status !== 'pending' && status !== 'running')) return
    let active = true
    const timer = window.setInterval(() => {
      bankMonitorApi.get(currentTenantId).then(({ data: value }) => {
        if (active && tenantRef.current === currentTenantId) setData(value)
      }).catch(() => { if (active) setVerificationError('Unable to refresh the worker check. Reload the page to see its result.') })
    }, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [currentTenantId, loadedTenant, data?.connection_check?.status])

  const verifyWorkerConnection = async () => {
    if (!currentTenantId || loadedTenant !== currentTenantId) return
    const tenantId = currentTenantId
    setVerifyingWorker(true); setVerificationError('')
    try {
      await bankMonitorApi.verifyWorkerConnection(tenantId)
      const response = await bankMonitorApi.get(tenantId)
      if (tenantRef.current === tenantId) setData(response.data)
    } catch (error: unknown) {
      if (tenantRef.current === tenantId) setVerificationError(apiError(error, 'Unable to start the worker bank check.'))
    } finally { setVerifyingWorker(false) }
  }

  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!currentTenantId || loadedTenant !== currentTenantId) return
    const tenantId = currentTenantId
    setSaving(true); setSettingsError(''); setSettingsNotice('')
    try {
      await bankMonitorApi.save(tenantId, rules)
      if (tenantRef.current !== tenantId) return
      const response = await bankMonitorApi.get(tenantId)
      if (tenantRef.current !== tenantId) return
      setData(response.data)
      setRules({ ...response.data.rules, repayment: response.data.rules.repayment || defaults.repayment })
      setSettingsNotice(response.data.rules.enabled ? 'Schedule saved. Bank access must be verified before automated checks can be relied on.' : 'Settings saved. Scheduled checks are paused.')
    } catch (error: unknown) {
      if (tenantRef.current === tenantId) setSettingsError(apiError(error, 'Check the account suffixes and ensure each account appears only once.'))
    } finally { setSaving(false) }
  }
  const editAccount = (group: 'checking' | 'sources', index: number, key: keyof Account, value: string) => setRules(current => ({ ...current, [group]: current[group].map((account, itemIndex) => itemIndex === index ? { ...account, [key]: value } : account) }))
  const importAccounts = async (accounts: Account[]) => {
    if (!currentTenantId || loadedTenant !== currentTenantId || !data) return { checking: rules.checking, sources: rules.sources }
    const tenantId = currentTenantId
    const checking = accounts.filter(account => account.kind === 'checking' || (!account.kind && /checking/i.test(account.nickname))).map(({ nickname, last4 }) => ({ nickname, last4 }))
    const sources = accounts.filter(account => /(line of credit|heloc|home equity)/i.test(account.nickname)).map(({ nickname, last4 }) => ({ nickname, last4 }))
    const saved = { ...data.rules, repayment: data.rules.repayment || defaults.repayment }
    const configured = new Set([...saved.checking, ...saved.sources].map(account => account.last4))
    const newChecking = checking.filter(account => !configured.has(account.last4))
    newChecking.forEach(account => configured.add(account.last4))
    const newSources = sources.filter(account => !configured.has(account.last4))
    const next = { ...saved, checking: [...saved.checking, ...newChecking], sources: [...saved.sources, ...newSources] }
    if (!newChecking.length && !newSources.length) return { checking: next.checking, sources: next.sources }
    await bankMonitorApi.save(tenantId, next)
    const response = await bankMonitorApi.get(tenantId)
    if (tenantRef.current !== tenantId) return { checking: next.checking, sources: next.sources }
    setData(response.data)
    setRules({ ...response.data.rules, repayment: response.data.rules.repayment || defaults.repayment })
    const added = [...newChecking, ...newSources].map(account => `${account.nickname} · ••${account.last4}`).join(', ')
    setSettingsNotice(`Added and saved ${added}.`)
    return { checking: response.data.rules.checking, sources: response.data.rules.sources }
  }

  const openRepayment = () => {
    const today = easternDate()
    const balances = new Map((latestBankRead?.accounts || []).map(account => [account.last4, account]))
    const pending = new Map((latestBankRead?.coverage || []).map(account => [account.last4, account.transactions.filter(transaction => transaction.pending).reduce((sum, transaction) => sum + transaction.amount_cents, 0)]))
    setCheckingEvidence(Object.fromEntries(savedRules.checking.map(account => {
      const current = balances.get(account.last4)?.current_cents
      const pendingDebits = pending.get(account.last4)
      const settled = current == null || pendingDebits == null ? null : Math.max(0, current - pendingDebits)
      return [account.last4, { current: dollarsInput(current), pending: dollarsInput(pendingDebits), settled: dollarsInput(settled), income: '', incomeDate: today }]
    })))
    setSourceEvidence(Object.fromEntries(savedRules.repayment.priority.map(last4 => [last4, ''])))
    setEvidenceConfirmed(false); setRepaymentError(''); setRepaymentNotice(''); setRepaymentOpen(true)
  }
  const runRepayment = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!currentTenantId || loadedTenant !== currentTenantId) return
    const tenantId = currentTenantId
    setRepaying(true); setRepaymentError(''); setRepaymentNotice('')
    try {
      const checking = savedRules.checking.map(account => {
        const values = checkingEvidence[account.last4]
        if (!values) throw new Error(`Evidence for ••${account.last4} is missing.`)
        const settledCash = centsFromMoneyInput(values.settled)
        const eligibleIncome = centsFromMoneyInput(values.income)
        if (eligibleIncome > settledCash) throw new Error(`Incoming funds for ${account.nickname} cannot exceed ${dollars(settledCash)} cash available after pending debits.`)
        return { last4: account.last4, current_cents: centsFromMoneyInput(values.current, true), pending_debits_cents: centsFromMoneyInput(values.pending), settled_cash_cents: settledCash, eligible_income_cents: eligibleIncome, income_date: values.incomeDate }
      })
      const sources = savedRules.repayment.priority.map(last4 => ({ last4, payoff_cents: centsFromMoneyInput(sourceEvidence[last4] || '') }))
      const response = await bankMonitorApi.runRepayment(tenantId, { checking, sources, evidence_confirmed: evidenceConfirmed })
      if (tenantRef.current !== tenantId) return
      const refreshed = await bankMonitorApi.get(tenantId)
      if (tenantRef.current !== tenantId) return
      setData(refreshed.data); setRepaymentOpen(false)
      setRepaymentNotice(response.data.status === 'review_required' ? 'Repayment proposal created. Review the exact route and amount below.' : `Manual repayment check completed: ${label(response.data.status)}.`)
    } catch (error: unknown) {
      if (tenantRef.current === tenantId) setRepaymentError(apiError(error, error instanceof Error ? error.message : 'Unable to run the repayment check.'))
    } finally { setRepaying(false) }
  }
  const addRepaymentToQueue = async (run: RepaymentRun) => {
    if (!currentTenantId || loadedTenant !== currentTenantId) return
    const tenantId = currentTenantId
    setRepaying(true); setRepaymentError(''); setRepaymentNotice('')
    try {
      const response = await bankMonitorApi.createRepaymentDrafts(tenantId, run.id)
      const refreshed = await bankMonitorApi.get(tenantId)
      if (tenantRef.current !== tenantId) return
      setData(refreshed.data); setQueueVersion(value => value + 1)
      setRepaymentNotice(`${response.data.created} repayment transfer${response.data.created === 1 ? '' : 's'} added to the queue. Prepare and approve each form in Truliant.`)
    } catch (error: unknown) {
      if (tenantRef.current === tenantId) setRepaymentNotice('')
      setRepaymentError(apiError(error, 'Unable to add this repayment proposal to the queue.'))
    } finally { setRepaying(false) }
  }

  const latest = data?.runs[0]
  const latestIssue = latest ? scheduledIssue(latest.status) : null
  const latestRepayment = data?.repayment_runs?.[0]
  const stale = Boolean(latest?.result.observed_at && Date.now() - Date.parse(latest.result.observed_at) > 300000)
  const savedRules = data ? { ...data.rules, repayment: data.rules.repayment || defaults.repayment } : defaults
  const settingsDirty = JSON.stringify(rules) !== JSON.stringify(savedRules)
  const incomeOverLimit = Object.values(checkingEvidence).some(values => incomeExceedsCash(values.income, values.settled))
  const accountsConfigured = savedRules.checking.length > 0 && savedRules.sources.length > 0
  const scheduleActive = savedRules.enabled && accountsConfigured
  const workerOnline = data?.worker.status === 'online'
  const connectionCheck = data?.connection_check
  const connectionPending = connectionCheck?.status === 'pending' || connectionCheck?.status === 'running'
  const connectionVerified = Boolean(connectionCheck?.status === 'verified' && connectionCheck.finished_at &&
    Date.now() - Date.parse(connectionCheck.finished_at) < 86400000 &&
    (!latest || !latestIssue || Date.parse(connectionCheck.finished_at) > Date.parse(latest.started_at)))

  return <div className="mx-auto max-w-7xl space-y-6 pb-12">
    <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-sm font-semibold text-blue-700">Cash protection</p><h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">Bank Monitor</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Check business balances, prepare exact coverage transfers, and verify each result.</p></div>
      <div className="flex items-center gap-2 text-sm text-slate-600"><Icon name="shield" className="h-4 w-4 text-emerald-700" /><span>You approve every transfer in Truliant</span></div>
    </header>

    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">{error}</div>}
    {loading && <div role="status" className="flex min-h-48 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-600"><span className="mr-3 h-5 w-5 animate-spin rounded-full border-2 border-blue-700 border-t-transparent motion-reduce:animate-none" />Loading bank monitor…</div>}

    {data && loadedTenant === currentTenantId && <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <main className="min-w-0 space-y-6">
        <BankTransferQueue key={`${currentTenantId}-${queueVersion}`} tenantId={currentTenantId} checking={rules.checking} sources={rules.sources} basis={rules.basis} onAccountsDiscovered={importAccounts} onBalanceObserved={setLatestBankRead} onBrowserCheckRecorded={() => {
          if (!currentTenantId) return
          const tenantId = currentTenantId
          void bankMonitorApi.get(tenantId).then(response => { if (tenantRef.current === tenantId) setData(response.data) })
        }} />

        {data.browser_check && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-950">Chrome bank read saved in ELIS at {new Date(data.browser_check.observed_at).toLocaleString()}. Result: {label(data.browser_check.status)}. {data.browser_check.result.repayment?.status === 'repayment_data_required' ? 'Friday repayment remains blocked until income, usable cash, pending debits, and full payoff are verified.' : ''}</div>}

        {repaymentNotice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">{repaymentNotice}</div>}
        {repaymentError && !repaymentOpen && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{repaymentError}</div>}
        {latestRepayment && <section className="rounded-2xl border border-violet-200 bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-violet-100 p-5 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-violet-700">Manual repayment check</p><h2 className="mt-1 text-xl font-semibold text-slate-950">{latestRepayment.status === 'review_required' ? 'Repayment proposal ready for review' : label(latestRepayment.status)}</h2><p className="mt-1 text-sm text-slate-600">Checked {new Date(latestRepayment.started_at).toLocaleString()} · No transfer submitted.</p></div><span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold capitalize text-violet-800 ring-1 ring-inset ring-violet-200">{label(latestRepayment.status)}</span></div>
          <div className="p-5">{latestRepayment.result.proposals.length ? <div className="space-y-3">{latestRepayment.result.proposals.map((proposal, index) => <div key={`${proposal.from_last4}-${proposal.to_last4}-${index}`} className="flex flex-col gap-1 rounded-xl bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between"><span className="text-sm text-slate-700">Checking ••{proposal.from_last4} <span aria-hidden="true">→</span> credit ••{proposal.to_last4}</span><strong className="text-lg tabular-nums text-slate-950">{dollars(proposal.amount_cents)}</strong></div>)}</div> : <p className="text-sm text-slate-700">No repayment is available from the evidence entered. Nothing was sent to Truliant.</p>}{latestRepayment.result.proposals.length > 0 && <div className="mt-5 flex flex-col gap-2 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs leading-5 text-slate-500">Creating drafts adds these exact routes to the queue. You still approve and submit each transfer in Truliant.</p><button type="button" disabled={repaying || latestRepayment.result.drafts_created} onClick={() => addRepaymentToQueue(latestRepayment)} className="min-h-11 shrink-0 rounded-xl bg-violet-700 px-4 font-semibold text-white hover:bg-violet-800 disabled:cursor-not-allowed disabled:opacity-45">{latestRepayment.result.drafts_created ? 'Added to transfer queue' : repaying ? 'Adding…' : 'Add to transfer queue'}</button></div>}</div>
        </section>}

        {latest && <details className="group rounded-2xl border border-slate-200 bg-white shadow-sm">
          <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500">
            <span className="flex min-w-0 items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-700"><Icon name="history" /></span><span className="min-w-0"><span className="block font-semibold text-slate-950">Latest scheduled check</span><span className={`block text-sm ${latestIssue ? 'font-medium text-amber-800' : 'text-slate-500'}`}>{latest.scheduled_date} · {latestIssue?.title || label(latest.status)}</span></span></span><span className="text-sm font-semibold text-blue-700 group-open:hidden">View details</span><span className="hidden text-sm font-semibold text-blue-700 group-open:inline">Hide details</span>
          </summary>
          <div className="space-y-5 border-t border-slate-200 p-5">
            {latest.status === 'running' && <p className="text-sm text-amber-800">This check is still running. No outcome is confirmed.</p>}
            {latestIssue && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">{latestIssue.detail}</p>}
            {stale && <p className="text-sm text-amber-800">Historical snapshot. Use Check bank now before preparing a transfer.</p>}
            {latest.result.message && <p className="text-sm text-slate-700">{latest.result.message}</p>}
            {latest.result.accounts && <div role="region" aria-label="Latest scheduled account balances" tabIndex={0} className="overflow-x-auto"><table className="w-full min-w-[34rem] text-left text-sm"><caption className="sr-only">Balances from the latest scheduled bank check</caption><thead className="text-xs uppercase tracking-wide text-slate-500"><tr><th scope="col" className="pb-2 font-semibold">Checking</th><th scope="col" className="pb-2 font-semibold">Current</th><th scope="col" className="pb-2 font-semibold">Available</th><th scope="col" className="pb-2 font-semibold">Needed</th></tr></thead><tbody>{latest.result.accounts.map(account => <tr key={account.last4} className="border-t border-slate-200"><td className="py-3 font-medium text-slate-800">{account.nickname} · ••{account.last4}</td><td className="tabular-nums">{dollars(account.current_cents)}</td><td className="tabular-nums">{account.available_cents === null ? 'Unknown' : dollars(account.available_cents)}</td><td className="tabular-nums">{dollars(account.needed_cents)}</td></tr>)}</tbody></table></div>}
            {latest.result.credit_accounts?.some(account => account.outstanding_cents !== null) && <div className="border-t border-slate-200 pt-4"><h3 className="font-semibold text-slate-900">Credit balances</h3>{latest.result.credit_accounts.map(account => <p key={account.last4} className="mt-2 text-sm text-slate-700">{account.nickname} · ••{account.last4}: {account.outstanding_cents === null ? 'unknown' : dollars(account.outstanding_cents)}</p>)}</div>}
            {latest.result.repayment && <div className="border-t border-slate-200 pt-4"><h3 className="font-semibold text-slate-900">Friday repayment</h3><p className="mt-1 text-sm capitalize text-slate-700">{label(latest.result.repayment.status)}</p>{latest.result.repayment.proposals.map((proposal, index) => <p key={`${proposal.from_last4}-${proposal.to_last4}-${index}`} className="mt-2 text-sm text-slate-700">{dollars(proposal.amount_cents)} from ••{proposal.from_last4} to ••{proposal.to_last4}</p>)}</div>}
            {!!latest.result.uncovered_cents && <p className="rounded-xl bg-red-50 p-3 text-sm font-medium text-red-800">Uncovered shortfall: {dollars(latest.result.uncovered_cents)}</p>}
          </div>
        </details>}

        <details className="group rounded-2xl border border-slate-200 bg-white shadow-sm">
          <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500"><span className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-lg bg-slate-100 text-slate-700"><Icon name="history" /></span><span><span className="block font-semibold text-slate-950">Run history</span><span className="block text-sm text-slate-500">{data.runs.length} scheduled · {data.repayment_runs.length} manual</span></span></span><span className="text-sm font-semibold text-blue-700 group-open:hidden">View</span><span className="hidden text-sm font-semibold text-blue-700 group-open:inline">Hide</span></summary>
          <div className="divide-y divide-slate-200 border-t border-slate-200">{data.repayment_runs.map(run => <div key={`repayment-${run.id}`} className="flex flex-col gap-1 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="font-medium text-slate-800">{new Date(run.started_at).toLocaleString()} · Manual repayment</span><span className="capitalize text-slate-600">{label(run.status)} · No transfer executed</span></div>)}{data.runs.map(run => <div key={`scheduled-${run.id}`} className="flex flex-col gap-1 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="font-medium text-slate-800">{run.scheduled_date} · Scheduled</span><span className="text-slate-600">{scheduledIssue(run.status)?.title || label(run.status)} · No transfers executed</span></div>)}{!data.runs.length && !data.repayment_runs.length && <p className="px-5 py-6 text-sm text-slate-600">No scheduled check has completed. The next attempt is {new Date(data.next_check).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} Eastern. Bank access is not yet verified.</p>}</div>
        </details>
      </main>

      <aside className="space-y-5 lg:sticky lg:top-5">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between"><span className={`grid h-10 w-10 place-items-center rounded-xl ${scheduleActive && latestIssue && !connectionVerified ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}><Icon name={scheduleActive ? 'calendar' : 'pause'} /></span><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${scheduleActive && latestIssue && !connectionVerified ? 'bg-amber-50 text-amber-900 ring-amber-200' : 'bg-slate-100 text-slate-700 ring-slate-200'}`}>{!scheduleActive ? 'Setup needed' : !workerOnline ? 'Worker offline' : data.reader_mode === 'signed_in_chrome' ? (data.browser_check ? 'Chrome reader active' : 'Chrome check needed') : connectionVerified ? 'Access verified' : latestIssue ? 'Last check blocked' : 'Worker running'}</span></div>
          <h2 className="mt-4 text-lg font-semibold text-slate-950">Daily 5:30 p.m. attempt</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{!accountsConfigured ? 'Import and save the accounts to enable scheduled checks.' : !savedRules.enabled ? 'Scheduled checks are paused.' : !workerOnline ? 'Scheduled checks are enabled, but the monitoring worker is not reporting.' : data.reader_mode === 'signed_in_chrome' ? `The Chrome assistant will attempt a bank read at 5:30 p.m. Eastern while Chrome is running. A complete result must reach ELIS by 5:45; otherwise the scheduled run is marked missed. Next attempt: ${new Date(data.next_check).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} Eastern.` : connectionVerified ? `The worker completed a read-only bank verification. Next scheduled attempt: ${new Date(data.next_check).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} Eastern.` : latestIssue ? `The last scheduled attempt did not read the bank: ${latestIssue.title.toLowerCase()}. See its details for the required setup. Next attempt: ${new Date(data.next_check).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} Eastern.` : `Worker is running; bank access is only confirmed by a completed check. Next attempt: ${new Date(data.next_check).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} Eastern.`}</p>
          {savedRules.repayment.enabled && <p className="mt-3 rounded-xl bg-violet-50 p-3 text-xs leading-5 text-violet-900">Friday repayment can be evaluated during a completed 5:30 p.m. bank check. A proposal appears only when Friday income, settled cash, pending debits, and payoff balances are all verified.</p>}
          <button type="button" disabled={!savedRules.repayment.enabled || !accountsConfigured} onClick={openRepayment} className="mt-4 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-violet-700 px-4 font-semibold text-white transition hover:bg-violet-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 motion-reduce:transition-none">Run repayment check now</button>
          <div className="mt-4 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-500">The server worker records proposals only. It does not submit transfers.</div>
        </section>

        {data.reader_mode === 'signed_in_chrome' ? <section aria-labelledby="chrome-access-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 id="chrome-access-title" className="text-lg font-semibold text-slate-950">Chrome bank access</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">The bank assistant checks Truliant in your signed-in Chrome profile at 5:30 p.m. Eastern when Chrome is running. ELIS records a complete result; if Chrome or bank sign-in is unavailable, the check is marked missed at 5:45. No password is sent from Chrome to ELIS.</p>
          {data.browser_check ? <p className="mt-4 text-sm font-medium text-emerald-800">Last complete browser read: {new Date(data.browser_check.observed_at).toLocaleString()}</p> : <p className="mt-4 text-sm text-amber-800">No complete browser read has been recorded yet.</p>}
          <p className="mt-2 text-xs leading-5 text-slate-500">The bank may require you to sign in again when its session expires. Transfers still require your approval in Truliant.</p>
        </section> : <section aria-labelledby="worker-access-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 id="worker-access-title" className="text-lg font-semibold text-slate-950">Server bank access</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">The worker creates a private browser profile on its persistent volume. Its Truliant username and password must be set as worker-only Railway secrets. Do not enter them on this page or in chat.</p>
          {connectionCheck?.status === 'verified' && <p role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm leading-6 text-emerald-900">Read-only sign-in verified {connectionCheck.finished_at ? new Date(connectionCheck.finished_at).toLocaleString() : ''}. {connectionCheck.result.account_count} configured accounts were read. No transfer was submitted.</p>}
          {connectionPending && <p role="status" className="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">Checking the private worker’s bank session…</p>}
          {connectionCheck && !connectionPending && connectionCheck.status !== 'verified' && <p role="alert" className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">{connectionCheck.status === 'mfa_required' || connectionCheck.status === 'login_review_required' ? 'Truliant requested sign-in review. The worker stopped after one attempt; an operator must recover the private session before another sign-in.' : scheduledIssue(connectionCheck.status)?.detail || `The worker check stopped: ${label(connectionCheck.status)}. No bank access was verified.`}</p>}
          {verificationError && <p role="alert" className="mt-4 text-sm text-red-800">{verificationError}</p>}
          <button type="button" disabled={!workerOnline || !accountsConfigured || connectionPending || verifyingWorker} onClick={verifyWorkerConnection} className="mt-4 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-blue-700 px-4 font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-45">{connectionPending || verifyingWorker ? 'Verifying bank access…' : 'Verify worker bank access'}</button>
          <p className="mt-2 text-xs leading-5 text-slate-500">This opens a read-only worker check. It never prepares or submits a transfer.</p>
        </section>}

        <button ref={settingsButtonRef} type="button" aria-expanded={settingsOpen} aria-controls="monitoring-settings-drawer" onClick={() => setSettingsOpen(true)} className="flex min-h-16 w-full items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 text-left shadow-sm transition hover:border-blue-200 hover:shadow-md active:scale-[0.99] motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500">
          <span className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-lg bg-blue-50 text-blue-700"><Icon name="settings" /></span><span><span className="block font-semibold text-slate-950">Monitoring settings</span><span className="block text-xs text-slate-500">Accounts, rules and schedule</span></span></span><span className="text-sm font-semibold text-blue-700">Edit</span>
        </button>

        {settingsOpen && <>
          <button type="button" aria-label="Close monitoring settings" onClick={() => setSettingsOpen(false)} className="fixed inset-0 z-40 cursor-default bg-slate-950/45 backdrop-blur-[1px]" />
          <section id="monitoring-settings-drawer" role="dialog" aria-modal="true" aria-labelledby="monitoring-settings-title" className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col bg-white shadow-2xl ring-1 ring-slate-900/10">
            <header className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-6">
              <div><p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Bank Monitor</p><h2 id="monitoring-settings-title" className="mt-1 text-xl font-semibold tracking-tight text-slate-950">Monitoring settings</h2><p className="mt-1 text-sm text-slate-600">Manage accounts, coverage rules, repayment priority, and schedule.</p></div>
              <button type="button" autoFocus onClick={() => { setSettingsOpen(false); window.setTimeout(() => settingsButtonRef.current?.focus(), 0) }} aria-label="Close monitoring settings" className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-slate-600 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"><Icon name="close" /></button>
            </header>
          <form onSubmit={save} className="flex-1 space-y-6 overflow-y-auto p-5 sm:p-6">
            {(['checking', 'sources'] as const).map(group => <fieldset key={group} className="space-y-3"><legend className="text-sm font-semibold text-slate-950">{group === 'checking' ? 'Checking accounts' : 'Funding priority'}</legend>{rules[group].map((account, index) => <div key={`${group}-${account.last4 || 'new'}-${index}`} className="rounded-xl border border-slate-200 bg-slate-50 p-3"><label className="block text-xs font-medium text-slate-600">{group === 'sources' ? `Priority ${index + 1}` : `Account ${index + 1}`}<input required maxLength={80} value={account.nickname} onChange={event => editAccount(group, index, 'nickname', event.target.value)} className="mt-1 block min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900" /></label><div className="mt-2 flex items-end gap-2"><label className="min-w-0 flex-1 text-xs font-medium text-slate-600">Last four<input required inputMode="numeric" pattern="[0-9]{4}" maxLength={4} value={account.last4} onChange={event => editAccount(group, index, 'last4', event.target.value)} className="mt-1 block min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-900" /></label><button type="button" className="min-h-11 rounded-lg px-3 text-sm font-semibold text-red-700 hover:bg-red-50" onClick={() => setRules(current => ({ ...current, [group]: current[group].filter((_, itemIndex) => itemIndex !== index) }))} aria-label={`Remove ${account.nickname || group}`}>Remove</button></div></div>)}<button type="button" disabled={rules[group].length >= (group === 'checking' ? 10 : 5)} className="min-h-11 rounded-lg px-2 text-sm font-semibold text-blue-700 hover:bg-blue-50 disabled:opacity-45" onClick={() => setRules(current => ({ ...current, [group]: [...current[group], { nickname: '', last4: '' }] }))}>Add {group === 'checking' ? 'checking account' : 'funding source'}</button></fieldset>)}

            <fieldset className="space-y-3 border-t border-slate-200 pt-5"><legend className="text-sm font-semibold text-slate-950">Coverage rule</legend><label className="block text-xs font-medium text-slate-600">Calculate from<BankSelect ariaLabel="Calculate coverage from" value={rules.basis} options={[{ value: 'posted', label: 'Posted balance only' }, { value: 'posted_and_pending', label: 'Posted plus verified pending debits' }]} onChange={value => setRules(current => ({ ...current, basis: value }))} /></label></fieldset>

            <fieldset className="space-y-3 border-t border-slate-200 pt-5"><legend className="text-sm font-semibold text-slate-950">Friday repayment</legend>{[0, 1].map(index => <label key={index} className="block text-xs font-medium text-slate-600">{index === 0 ? 'Repay first' : 'Repay second'}<BankSelect ariaLabel={index === 0 ? 'Repay first' : 'Repay second'} value={rules.repayment.priority[index] || ''} options={[{ value: '', label: 'Select source' }, ...rules.sources.filter(account => /^[0-9]{4}$/.test(account.last4)).map(account => ({ value: account.last4, label: `${account.nickname} · ••${account.last4}` }))]} onChange={value => { const priority = [...rules.repayment.priority]; priority[index] = value; setRules(current => ({ ...current, repayment: { ...current.repayment, priority } })) }} /></label>)}<label className="flex items-start gap-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-700"><input type="checkbox" className="mt-0.5 h-4 w-4" checked={rules.repayment.enabled} onChange={event => { setSettingsNotice(''); setRules(current => ({ ...current, repayment: { ...current.repayment, enabled: event.target.checked, reserve_cents: 0 } })) }} /><span>Include verified Friday income repayment proposals</span></label></fieldset>

            <fieldset className="space-y-3 border-t border-slate-200 pt-5"><legend className="text-sm font-semibold text-slate-950">Schedule</legend><label className="flex items-start gap-3 rounded-xl bg-slate-50 p-3 text-sm text-slate-700"><input type="checkbox" className="mt-0.5 h-4 w-4" checked={rules.enabled} onChange={event => { setSettingsNotice(''); setRules(current => ({ ...current, enabled: event.target.checked })) }} /><span>Run daily at 5:30 p.m. Eastern, including weekends</span></label></fieldset>

            {settingsDirty && <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Unsaved changes</div>}
            {!settingsDirty && settingsNotice && <div role="status" className="flex gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900"><Icon name="check" className="h-4 w-4 shrink-0" />{settingsNotice}</div>}
            {settingsError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900">{settingsError}</div>}
            <button disabled={saving || !settingsDirty} className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 font-semibold text-white transition hover:bg-blue-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 motion-reduce:transition-none">{saving && <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent motion-reduce:animate-none" />}{saving ? 'Saving…' : settingsDirty ? 'Save settings' : 'Settings saved'}</button>
          </form>
          </section>
        </>}

        {repaymentOpen && <>
          <button type="button" aria-label="Close manual repayment check" onClick={() => setRepaymentOpen(false)} className="fixed inset-0 z-40 cursor-default bg-slate-950/45 backdrop-blur-[1px]" />
          <section role="dialog" aria-modal="true" aria-labelledby="manual-repayment-title" className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col bg-white shadow-2xl ring-1 ring-slate-900/10">
            <header className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-5 py-5 sm:px-6"><div><p className="text-xs font-semibold uppercase tracking-wider text-violet-700">On-demand check</p><h2 id="manual-repayment-title" className="mt-1 text-xl font-semibold text-slate-950">Calculate repayment available now</h2><p className="mt-1 text-sm leading-6 text-slate-600">Enter values you just verified in Truliant. ELIS will protect pending debits and calculate the repayment order; it will not move money.</p></div><button type="button" onClick={() => setRepaymentOpen(false)} aria-label="Close manual repayment check" className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-slate-600 hover:bg-slate-100"><Icon name="close" /></button></header>
            <form onSubmit={runRepayment} className="flex-1 space-y-6 overflow-y-auto p-5 sm:p-6">
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><strong>Each checking account funds its own repayments.</strong> ELIS prefills the posted balance and pending debits from the latest bank check, protects those debits, and applies confirmed incoming funds to the credit lines in your repayment priority.</div>
              {savedRules.checking.map(account => {
                const values = checkingEvidence[account.last4]
                if (!values) return null
                const prefilled = Boolean(latestBankRead?.accounts.some(item => item.last4 === account.last4))
                const overLimit = incomeExceedsCash(values.income, values.settled)
                let cashLimit: number | null = null
                try { cashLimit = centsFromMoneyInput(values.settled) } catch { /* Wait for a valid cash amount. */ }
                const incomeHelpId = `repayment-income-limit-${account.last4}`
                return <fieldset key={account.last4} className="rounded-xl border border-slate-200 p-4">
                  <legend className="px-1 font-semibold text-slate-950">{account.nickname} · ••{account.last4}</legend>
                  {prefilled && <p className="mb-3 text-xs font-medium text-emerald-700">Balance and pending debits prefilled from the latest bank check.</p>}
                  <div className="mt-2 grid gap-4 sm:grid-cols-2">
                    <label className="text-sm font-medium text-slate-700">Current posted balance
                      <MoneyInput required allowNegative value={values.current} onChange={value => setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], current: value } }))} className="block min-h-11 w-full rounded-xl border border-slate-300 px-3" />
                      <span className="mt-1 block text-xs font-normal text-slate-500">Use a minus sign if negative.</span>
                    </label>
                    <label className="text-sm font-medium text-slate-700">Pending debits
                      <MoneyInput required value={values.pending} onChange={value => setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], pending: value } }))} className="block min-h-11 w-full rounded-xl border border-slate-300 px-3" />
                    </label>
                    <label className="text-sm font-medium text-slate-700">Cash available after pending debits
                      <MoneyInput required value={values.settled} onChange={value => { setRepaymentError(''); setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], settled: value } })) }} className="block min-h-11 w-full rounded-xl border border-slate-300 px-3" />
                      <span className="mt-1 block text-xs font-normal text-slate-500">Exclude any amount supplied by overdraft protection or a credit draw.</span>
                    </label>
                    <label className="text-sm font-medium text-slate-700">Incoming funds to reimburse credit
                      <MoneyInput required invalid={overLimit} describedBy={incomeHelpId} value={values.income} onChange={value => { setRepaymentError(''); setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], income: value } })) }} className={`block min-h-11 w-full rounded-xl border px-3 ${overLimit ? 'border-red-400 focus:border-red-500' : 'border-slate-300'}`} />
                      <span className="mt-1 block text-xs font-normal text-slate-500">Enter cleared income from this account that you want applied to the credit lines.</span>
                      <span id={incomeHelpId} role={overLimit ? 'alert' : undefined} className={`mt-1 block text-xs font-medium ${overLimit ? 'text-red-700' : 'text-slate-600'}`}>{overLimit ? `Reduce this amount to ${dollars(cashLimit ?? 0)} or less.` : cashLimit === null ? 'Cannot exceed cash available after pending debits.' : `Maximum ${dollars(cashLimit)}: cash available after pending debits in this account.`}</span>
                    </label>
                    <label className="text-sm font-medium text-slate-700 sm:col-span-2">Income received date
                      <input required type="date" value={values.incomeDate} onChange={event => setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], incomeDate: event.target.value } }))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3" />
                    </label>
                  </div>
                </fieldset>
              })}
              <fieldset className="space-y-4"><legend className="font-semibold text-slate-950">Full payoff amounts</legend>{savedRules.repayment.priority.map(last4 => { const account = savedRules.sources.find(item => item.last4 === last4); return <label key={last4} className="block text-sm font-medium text-slate-700">{account?.nickname || 'Credit source'} · ••{last4}<MoneyInput required value={sourceEvidence[last4] || ''} onChange={value => setSourceEvidence(current => ({ ...current, [last4]: value }))} className="block min-h-11 w-full rounded-xl border border-slate-300 px-3" /><span className="mt-1 block text-xs font-normal text-slate-500">Use the full verified payoff, including accrued interest—not amount due or available credit.</span></label> })}</fieldset>
              <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700"><input required type="checkbox" checked={evidenceConfirmed} onChange={event => setEvidenceConfirmed(event.target.checked)} className="mt-0.5 h-4 w-4" /><span>I verified these values in Truliant and understand this check records a proposal only.</span></label>
              {repaymentError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{repaymentError}</div>}
              <div className="flex flex-col gap-2 sm:flex-row"><button disabled={repaying || !evidenceConfirmed || incomeOverLimit} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-violet-700 px-5 font-semibold text-white hover:bg-violet-800 disabled:opacity-45">{repaying ? 'Calculating…' : 'Calculate repayment'}</button><button type="button" disabled={repaying} onClick={() => setRepaymentOpen(false)} className="min-h-11 rounded-xl px-4 font-medium text-slate-700 hover:bg-slate-100">Cancel</button></div>
            </form>
          </section>
        </>}
      </aside>
    </div>}
  </div>
}
