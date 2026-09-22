import { useEffect, useRef, useState } from 'react'
import { bankMonitorApi } from '../services/api'
import BankTransferQueue from './BankTransferQueue'
import BankSelect from '../components/BankSelect'
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
type Dashboard = { rules: Rules; next_check: string; worker: { status: 'online' | 'offline'; last_seen_at: string | null }; runs: Run[]; repayment_runs: RepaymentRun[] }
type CheckingEvidence = { current: string; pending: string; settled: string; income: string; incomeDate: string }

const dollars = (cents: number) => (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const label = (status: string) => status.replace(/_/g, ' ')
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
const centsFromInput = (value: string, allowNegative = false) => {
  const pattern = allowNegative ? /^-?(?:0|[1-9]\d*)(?:\.\d{1,2})?$/ : /^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/
  if (!pattern.test(value.trim())) throw new Error('Enter every amount in dollars, using no more than two decimal places.')
  return Math.round(Number(value) * 100)
}

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
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [repaymentOpen, setRepaymentOpen] = useState(false)
  const [repaying, setRepaying] = useState(false)
  const [repaymentError, setRepaymentError] = useState('')
  const [repaymentNotice, setRepaymentNotice] = useState('')
  const [evidenceConfirmed, setEvidenceConfirmed] = useState(false)
  const [checkingEvidence, setCheckingEvidence] = useState<Record<string, CheckingEvidence>>({})
  const [sourceEvidence, setSourceEvidence] = useState<Record<string, string>>({})
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
      setSettingsNotice(response.data.rules.enabled ? 'Settings saved. Daily checks are scheduled.' : 'Settings saved. Scheduled checks are paused.')
    } catch (error: unknown) {
      if (tenantRef.current === tenantId) setSettingsError(apiError(error, 'Check the account suffixes and ensure each account appears only once.'))
    } finally { setSaving(false) }
  }
  const editAccount = (group: 'checking' | 'sources', index: number, key: keyof Account, value: string) => setRules(current => ({ ...current, [group]: current[group].map((account, itemIndex) => itemIndex === index ? { ...account, [key]: value } : account) }))
  const importAccounts = (accounts: Account[]) => {
    const checking = accounts.filter(account => account.kind === 'checking' || (!account.kind && /checking/i.test(account.nickname)))
    const sources = accounts.filter(account => account.kind === 'credit' || (!account.kind && /(line of credit|heloc|home equity)/i.test(account.nickname)))
    setRules(current => ({ ...current, checking: checking.length ? checking : current.checking, sources: sources.length ? [...sources.filter(account => /(heloc|home equity)/i.test(account.nickname)), ...sources.filter(account => !/(heloc|home equity)/i.test(account.nickname))] : current.sources }))
  }

  const openRepayment = () => {
    const today = easternDate()
    setCheckingEvidence(Object.fromEntries(savedRules.checking.map(account => [account.last4, { current: '', pending: '', settled: '', income: '', incomeDate: today }])))
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
        return { last4: account.last4, current_cents: centsFromInput(values.current, true), pending_debits_cents: centsFromInput(values.pending), settled_cash_cents: centsFromInput(values.settled), eligible_income_cents: centsFromInput(values.income), income_date: values.incomeDate }
      })
      const sources = savedRules.repayment.priority.map(last4 => ({ last4, payoff_cents: centsFromInput(sourceEvidence[last4] || '') }))
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
  const latestRepayment = data?.repayment_runs?.[0]
  const stale = Boolean(latest?.result.observed_at && Date.now() - Date.parse(latest.result.observed_at) > 300000)
  const savedRules = data ? { ...data.rules, repayment: data.rules.repayment || defaults.repayment } : defaults
  const settingsDirty = JSON.stringify(rules) !== JSON.stringify(savedRules)
  const accountsConfigured = savedRules.checking.length > 0 && savedRules.sources.length > 0
  const scheduleActive = savedRules.enabled && accountsConfigured
  const workerOnline = data?.worker.status === 'online'

  return <div className="mx-auto max-w-7xl space-y-6 pb-12">
    <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-sm font-semibold text-blue-700">Cash protection</p><h1 className="mt-1 text-3xl font-semibold tracking-tight text-slate-950">Bank Monitor</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">Check business balances, prepare exact coverage transfers, and verify each result.</p></div>
      <div className="flex items-center gap-2 text-sm text-slate-600"><Icon name="shield" className="h-4 w-4 text-emerald-700" /><span>You approve every transfer in Truliant</span></div>
    </header>

    {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-900">{error}</div>}
    {loading && <div role="status" className="flex min-h-48 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-600"><span className="mr-3 h-5 w-5 animate-spin rounded-full border-2 border-blue-700 border-t-transparent motion-reduce:animate-none" />Loading bank monitor…</div>}

    {data && loadedTenant === currentTenantId && <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <main className="min-w-0 space-y-6">
        <BankTransferQueue key={`${currentTenantId}-${queueVersion}`} tenantId={currentTenantId} checking={rules.checking} sources={rules.sources} basis={rules.basis} onAccountsDiscovered={importAccounts} />

        {repaymentNotice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">{repaymentNotice}</div>}
        {repaymentError && !repaymentOpen && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{repaymentError}</div>}
        {latestRepayment && <section className="rounded-2xl border border-violet-200 bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-violet-100 p-5 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs font-semibold uppercase tracking-wider text-violet-700">Manual repayment check</p><h2 className="mt-1 text-xl font-semibold text-slate-950">{latestRepayment.status === 'review_required' ? 'Repayment proposal ready for review' : label(latestRepayment.status)}</h2><p className="mt-1 text-sm text-slate-600">Checked {new Date(latestRepayment.started_at).toLocaleString()} · No transfer submitted.</p></div><span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-semibold capitalize text-violet-800 ring-1 ring-inset ring-violet-200">{label(latestRepayment.status)}</span></div>
          <div className="p-5">{latestRepayment.result.proposals.length ? <div className="space-y-3">{latestRepayment.result.proposals.map((proposal, index) => <div key={`${proposal.from_last4}-${proposal.to_last4}-${index}`} className="flex flex-col gap-1 rounded-xl bg-slate-50 p-4 sm:flex-row sm:items-center sm:justify-between"><span className="text-sm text-slate-700">Checking ••{proposal.from_last4} <span aria-hidden="true">→</span> credit ••{proposal.to_last4}</span><strong className="text-lg tabular-nums text-slate-950">{dollars(proposal.amount_cents)}</strong></div>)}</div> : <p className="text-sm text-slate-700">No repayment is available from the evidence entered. Nothing was sent to Truliant.</p>}{latestRepayment.result.proposals.length > 0 && <div className="mt-5 flex flex-col gap-2 border-t border-slate-200 pt-5 sm:flex-row sm:items-center sm:justify-between"><p className="text-xs leading-5 text-slate-500">Creating drafts adds these exact routes to the queue. You still approve and submit each transfer in Truliant.</p><button type="button" disabled={repaying || latestRepayment.result.drafts_created} onClick={() => addRepaymentToQueue(latestRepayment)} className="min-h-11 shrink-0 rounded-xl bg-violet-700 px-4 font-semibold text-white hover:bg-violet-800 disabled:cursor-not-allowed disabled:opacity-45">{latestRepayment.result.drafts_created ? 'Added to transfer queue' : repaying ? 'Adding…' : 'Add to transfer queue'}</button></div>}</div>
        </section>}

        {latest && <details className="group rounded-2xl border border-slate-200 bg-white shadow-sm">
          <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-500">
            <span className="flex min-w-0 items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-slate-100 text-slate-700"><Icon name="history" /></span><span className="min-w-0"><span className="block font-semibold text-slate-950">Latest scheduled check</span><span className="block truncate text-sm capitalize text-slate-500">{latest.scheduled_date} · {label(latest.status)}</span></span></span><span className="text-sm font-semibold text-blue-700 group-open:hidden">View details</span><span className="hidden text-sm font-semibold text-blue-700 group-open:inline">Hide details</span>
          </summary>
          <div className="space-y-5 border-t border-slate-200 p-5">
            {latest.status === 'running' && <p className="text-sm text-amber-800">This check is still running. No outcome is confirmed.</p>}
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
          <div className="divide-y divide-slate-200 border-t border-slate-200">{data.repayment_runs.map(run => <div key={`repayment-${run.id}`} className="flex flex-col gap-1 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="font-medium text-slate-800">{new Date(run.started_at).toLocaleString()} · Manual repayment</span><span className="capitalize text-slate-600">{label(run.status)} · No transfer executed</span></div>)}{data.runs.map(run => <div key={`scheduled-${run.id}`} className="flex flex-col gap-1 px-5 py-4 text-sm sm:flex-row sm:items-center sm:justify-between"><span className="font-medium text-slate-800">{run.scheduled_date} · Scheduled</span><span className="capitalize text-slate-600">{label(run.status)} · No transfers executed</span></div>)}{!data.runs.length && !data.repayment_runs.length && <p className="px-5 py-6 text-sm text-slate-600">No check has completed. The next scheduled check is {new Date(data.next_check).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} Eastern.</p>}</div>
        </details>
      </main>

      <aside className="space-y-5 lg:sticky lg:top-5">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between"><span className={`grid h-10 w-10 place-items-center rounded-xl ${scheduleActive && workerOnline ? 'bg-emerald-50 text-emerald-700' : scheduleActive ? 'bg-amber-50 text-amber-700' : 'bg-slate-100 text-slate-600'}`}><Icon name={scheduleActive ? 'calendar' : 'pause'} /></span><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${scheduleActive && workerOnline ? 'bg-emerald-50 text-emerald-800 ring-emerald-200' : scheduleActive ? 'bg-amber-50 text-amber-900 ring-amber-200' : 'bg-slate-100 text-slate-700 ring-slate-200'}`}>{!scheduleActive ? 'Setup needed' : workerOnline ? 'Worker online' : 'Worker offline'}</span></div>
          <h2 className="mt-4 text-lg font-semibold text-slate-950">Daily 5:30 p.m. check</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">{!accountsConfigured ? 'Import and save the accounts to enable scheduled checks.' : !savedRules.enabled ? 'Scheduled checks are paused.' : !workerOnline ? 'Scheduled checks are enabled, but the monitoring worker is not reporting.' : `Worker connected. Next check: ${new Date(data.next_check).toLocaleString('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })} Eastern.`}</p>
          {savedRules.repayment.enabled && <p className="mt-3 rounded-xl bg-violet-50 p-3 text-xs leading-5 text-violet-900">Friday repayment is evaluated at the 5:30 p.m. check. A proposal appears only when Friday income, settled cash, pending debits, and payoff balances are all verified.</p>}
          <button type="button" disabled={!savedRules.repayment.enabled || !accountsConfigured} onClick={openRepayment} className="mt-4 inline-flex min-h-11 w-full items-center justify-center rounded-xl bg-violet-700 px-4 font-semibold text-white transition hover:bg-violet-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 motion-reduce:transition-none">Run repayment check now</button>
          <div className="mt-4 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-500">The server worker records proposals only. It does not submit transfers.</div>
        </section>

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
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950"><strong>Use current bank values.</strong> Settled cash means cash available without an overdraft or credit draw. Eligible income means cleared business or salary income received on the date entered.</div>
              {savedRules.checking.map(account => { const values = checkingEvidence[account.last4]; if (!values) return null; return <fieldset key={account.last4} className="rounded-xl border border-slate-200 p-4"><legend className="px-1 font-semibold text-slate-950">{account.nickname} · ••{account.last4}</legend><div className="mt-2 grid gap-4 sm:grid-cols-2"><label className="text-sm font-medium text-slate-700">Current posted balance<input required inputMode="decimal" placeholder="0.00" value={values.current} onChange={event => setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], current: event.target.value } }))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /><span className="mt-1 block text-xs font-normal text-slate-500">Use a minus sign if negative.</span></label><label className="text-sm font-medium text-slate-700">Pending debits<input required inputMode="decimal" placeholder="0.00" value={values.pending} onChange={event => setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], pending: event.target.value } }))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label><label className="text-sm font-medium text-slate-700">Settled cash without borrowing<input required inputMode="decimal" placeholder="0.00" value={values.settled} onChange={event => setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], settled: event.target.value } }))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label><label className="text-sm font-medium text-slate-700">Eligible cleared income<input required inputMode="decimal" placeholder="0.00" value={values.income} onChange={event => setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], income: event.target.value } }))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label><label className="text-sm font-medium text-slate-700 sm:col-span-2">Income received date<input required type="date" value={values.incomeDate} onChange={event => setCheckingEvidence(current => ({ ...current, [account.last4]: { ...current[account.last4], incomeDate: event.target.value } }))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label></div></fieldset> })}
              <fieldset className="space-y-4"><legend className="font-semibold text-slate-950">Full payoff amounts</legend>{savedRules.repayment.priority.map(last4 => { const account = savedRules.sources.find(item => item.last4 === last4); return <label key={last4} className="block text-sm font-medium text-slate-700">{account?.nickname || 'Credit source'} · ••{last4}<input required inputMode="decimal" placeholder="0.00" value={sourceEvidence[last4] || ''} onChange={event => setSourceEvidence(current => ({ ...current, [last4]: event.target.value }))} className="mt-2 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /><span className="mt-1 block text-xs font-normal text-slate-500">Use the full verified payoff, including accrued interest—not amount due or available credit.</span></label> })}</fieldset>
              <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700"><input required type="checkbox" checked={evidenceConfirmed} onChange={event => setEvidenceConfirmed(event.target.checked)} className="mt-0.5 h-4 w-4" /><span>I verified these values in Truliant and understand this check records a proposal only.</span></label>
              {repaymentError && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">{repaymentError}</div>}
              <div className="flex flex-col gap-2 sm:flex-row"><button disabled={repaying || !evidenceConfirmed} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-violet-700 px-5 font-semibold text-white hover:bg-violet-800 disabled:opacity-45">{repaying ? 'Calculating…' : 'Calculate repayment'}</button><button type="button" disabled={repaying} onClick={() => setRepaymentOpen(false)} className="min-h-11 rounded-xl px-4 font-medium text-slate-700 hover:bg-slate-100">Cancel</button></div>
            </form>
          </section>
        </>}
      </aside>
    </div>}
  </div>
}
