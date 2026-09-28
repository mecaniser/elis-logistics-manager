import { createPortal } from 'react-dom'
import { useEffect, useRef, useState } from 'react'
import { bankProfilesApi } from '../services/api'
import { loadPlaidLink } from '../services/plaidLink'
import BankDialog from '../components/BankDialog'
import BankSelect from '../components/BankSelect'
import MoneyInput from '../components/MoneyInput'
import { centsFromMoneyInput } from '../components/moneyAmount'

type Account = { id: string; account_id: string | null; name: string; last4: string; kind: string; subtype: string; reserve_cents: number; balance: { current_cents?: number | null; available_cents?: number | null; pending_debit_cents?: number | null; currency?: string }; overlap_candidates: { id: string; name: string; last4: string; profiles?: string[] }[] }
type ReviewItem = { id: string; kind: 'funding' | 'repayment'; route_id: string | null; last4: string | null; label: string; message: string }
type Preferences = { review_items?: ReviewItem[]; migration_pending?: boolean; monitor: boolean; repayment: boolean; funding_order: string[]; repayment_order: string[]; review_required: string[]; last_evaluation?: { status: string } }
type Coverage = { account_id: string; name: string; last4: string; status: string; minimum_cents?: number; possible_cents?: number; pending_debit_cents?: number | null; pending_review_required?: boolean; observed_at?: string; uncovered_cents?: number; routes: { route_id: string; source_name: string; source_last4: string; amount_cents: number; limit_cents: number }[] }
type Profile = { coverage?: Coverage[]; preferences: Preferences; id: string; name: string; institution_id: string; status: string; last_error: string | null; last_checked_at: string | null; accounts: Account[] }
type Route = { id: string; profile_id: string; source_id: string; destination_id: string; enabled: boolean }
type Transfer = { id: string; source_id: string; destination_id: string; profile_id: string; amount_cents: number; status: string; from_last4: string; to_last4: string; kind: string }
type Data = { unified?: boolean; drafts?: Transfer[]; profiles: Profile[]; routes: Route[]; runs: { profile_id: string; date: string; status: string }[] }
type Review = { coverage?: Coverage | null; route_id: string; kind: string; id: number; profile_name: string; source_name: string; destination_name: string; from_last4: string; to_last4: string; limit_cents: number; reserve_cents: number; reserved_draft_cents: number; pending_debit_cents: number | null; observed_at: string }
const money = (value?: number | null) => value == null ? 'Unavailable' : (value / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const button = 'min-h-11 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-45'
const primary = 'min-h-11 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-45'
const errorText = (e: unknown) => (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || (e instanceof Error ? e.message : 'Banking profile request failed.')

export default function BankProfiles({ tenantId, onUnified, onMode, onDraft, onOpenTransfer, settingsTarget, openSettings }: { onUnified: (value: boolean) => void; settingsTarget: HTMLElement | null; openSettings: () => void; tenantId: number; onMode: (value: boolean) => void; onDraft: () => void; onOpenTransfer: (id: string) => void }) {
  const [data, setData] = useState<Data>({ profiles: [], routes: [], runs: [] })
  const [selected, setSelected] = useState('')
  const [settingsProfile, setSettingsProfile] = useState('')
  const [editingName, setEditingName] = useState('')
  const [addingBank, setAddingBank] = useState(false)
  const [busy, setBusy] = useState(false)
  const [refreshingProfile, setRefreshingProfile] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [name, setName] = useState('Truliant — Main Business')
  const [source, setSource] = useState('')
  const [destination, setDestination] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [coverageConfirmed, setCoverageConfirmed] = useState(false)
  const [review, setReview] = useState<Review | null>(null)
  const [accountId, setAccountId] = useState('')
  const [intent, setIntent] = useState<'payment' | 'full_payoff'>('payment')
  const [amount, setAmount] = useState('')
  const alive = useRef(true)
  const resumed = useRef(false)
  const active = data.profiles.find(p => p.id === selected) || data.profiles[0]
  const account = active?.accounts.find(a => a.id === accountId)
  const mode = data.profiles.length > 1 || data.routes.length > 0
  const update = (value: Data) => { if (alive.current) { setData(value); onUnified(Boolean(value.unified)); setLoading(false); onMode(value.profiles.length > 1 || value.routes.length > 0) } }
  const request = async (path: string, method: 'post' | 'put' = 'post', body?: unknown, onSuccess?: () => void) => {
    setBusy(true); setError(''); setNotice('')
    try { const response = await bankProfilesApi.request<Data>(tenantId, path, method, body); update(response.data); if (alive.current) onSuccess?.(); if (path.endsWith('/preferences')) setNotice('Profile preferences saved.'); if (path.endsWith('/name')) { setNotice('Connection name saved.'); setEditingName('') } }
    catch (e) { if (alive.current) { setError(errorText(e)); try { update((await bankProfilesApi.request<Data>(tenantId)).data) } catch { /* Keep the original actionable error. */ } } }
    finally { if (alive.current) setBusy(false) }
  }
  const finishLink = () => {
    sessionStorage.removeItem('elis-bank-profile-link')
    const url = new URL(window.location.href); url.searchParams.delete('oauth_state_id')
    window.history.replaceState(null, '', url.pathname + url.search + url.hash)
  }
  const launch = async (saved: { token: string; attempt: string }, redirect?: string) => {
    await loadPlaidLink()
    if (!alive.current) return
    const handler = window.Plaid!.create({ token: saved.token, receivedRedirectUri: redirect,
      onSuccess: token => { void request('/exchange', 'post', { attempt_id: saved.attempt, link_token: saved.token, public_token: token }).finally(() => { finishLink(); handler.destroy() }) },
      onExit: () => { finishLink(); if (alive.current) setBusy(false); handler.destroy() },
    }); handler.open()
  }
  useEffect(() => {
    alive.current = true
    void bankProfilesApi.request<Data>(tenantId).then(response => update(response.data)).catch(e => { if (alive.current) { setError(errorText(e)); setLoading(false) } })
    const raw = sessionStorage.getItem('elis-bank-profile-link')
    if (raw && window.location.search.includes('oauth_state_id=') && !resumed.current) {
      resumed.current = true
      try {
        const saved = JSON.parse(raw)
        if (saved.tenantId !== tenantId || Date.now() - saved.started > 3600000) throw new Error('Bank profile sign-in expired. Start again.')
        setBusy(true)
        void launch(saved, window.location.href).catch(e => { if (alive.current) { setError(errorText(e)); setBusy(false) } })
      } catch (e) { setError(errorText(e)); finishLink() }
    }
    const timer = window.setInterval(() => { if (!document.hidden) void bankProfilesApi.request<Data>(tenantId).then(r => update(r.data)).catch(() => {}) }, 60000)
    return () => { alive.current = false; window.clearInterval(timer) }
    // A tenant switch remounts this component and discards all profile state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId])
  const connect = async (profile?: Profile) => {
    setBusy(true); setError('')
    try {
      const response = await bankProfilesApi.request<{ link_token: string; attempt_id: string }>(tenantId, '/link', 'post', { name: profile?.name || name, profile_id: profile?.id || null })
      const saved = { tenantId, token: response.data.link_token, attempt: response.data.attempt_id, started: Date.now() }
      sessionStorage.setItem('elis-bank-profile-link', JSON.stringify(saved)); await launch(saved)
    } catch (e) { setError(errorText(e)); setBusy(false) }
  }
  const startReview = async (route: Route) => {
    setBusy(true); setError(''); setReview(null); setIntent('payment'); setCoverageConfirmed(false)
    try {
      const response = await bankProfilesApi.request<Review & { existing_draft?: { id: string } }>(tenantId, `/routes/${route.id}/review`, 'post')
      if (alive.current && response.data.existing_draft) { setAccountId(''); onOpenTransfer(response.data.existing_draft.id); return }
      if (alive.current) { setReview(response.data); setAmount(response.data.coverage?.pending_review_required ? '' : ((response.data.coverage?.routes.find(r => r.route_id === route.id)?.amount_cents ?? response.data.limit_cents) / 100).toFixed(2)) }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  let cents = 0
  try { cents = centsFromMoneyInput(amount) } catch { /* Invalid input cannot create a draft. */ }
  const create = async () => {
    if (!review) return
    setBusy(true); setError('')
    try {
      const response = await bankProfilesApi.request<{ draft: { id: string } }>(tenantId, `/reviews/${review.id}/draft`, 'post', { amount_cents: cents, intent, coverage_confirmed: coverageConfirmed })
      if (alive.current) { setReview(null); setAccountId(''); setNotice('Transfer saved. Continue below to prepare the bank form.'); onDraft(); onOpenTransfer(response.data.draft.id) }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  return <section aria-label="Banking profiles" className="rounded-2xl border border-slate-800 bg-slate-950 p-5 text-white shadow-sm sm:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-blue-300">Banking profiles</p><h2 className="mt-1 text-xl font-semibold text-white">{loading || mode ? 'Your accounts' : 'Connect separate bank logins'}</h2><p className="mt-2 text-sm text-slate-300">Choose a profile to view its accounts. Select an account to make a payment, move funds, or view its transfers.</p></div></header>
    {settingsTarget && createPortal(<section aria-label="Manage bank connections" className="bank-profile-settings space-y-4 rounded-xl border border-slate-200 p-4">
      {error && <p role="alert" className="text-sm text-red-800">{error}</p>}{notice && <p role="status" className="text-sm text-emerald-800">{notice}</p>}<div className="flex items-center justify-between"><h3 className="font-semibold text-slate-950">Bank connections</h3><button type="button" aria-label="Add bank connection" aria-expanded={addingBank} onClick={() => setAddingBank(v => !v)} className="grid h-9 w-9 place-items-center rounded-lg text-2xl text-blue-700 hover:bg-blue-50">{addingBank ? '−' : '+'}</button></div>
      {!data.profiles.length && <button type="button" disabled={busy} onClick={() => void request('/initialize')} className={button}>Use existing bank connection</button>}
      {addingBank && <div className="space-y-3 rounded-xl border border-slate-200 p-3">      <label className="block text-sm text-slate-700">New banking profile name<input value={name} maxLength={80} onChange={e => setName(e.target.value)} className="mt-1 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label>
      <p className="text-xs leading-5 text-slate-500">For a separate bank login, choose different credentials in Plaid instead of reusing a saved connection. Other institutions can be monitored; form preparation currently supports Truliant only.</p>
      <button type="button" disabled={busy || !name.trim()} onClick={() => void connect()} className={primary}>{busy ? 'Working…' : 'Connect bank'}</button></div>}

      {data.profiles.map(active => <div key={active.id} className="border-t border-slate-200 pt-3">
        <div className="flex items-center justify-between gap-2"><div className="min-w-0 flex-1"><div className="flex items-center gap-1"><button type="button" aria-expanded={settingsProfile === active.id} onClick={() => { setSettingsProfile(settingsProfile === active.id ? '' : active.id); setSource(''); setDestination(''); setConfirmed(false) }} className="min-h-9 min-w-0 text-left text-sm font-semibold"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={`mr-1 inline h-4 w-4 transition-transform ${settingsProfile === active.id ? 'rotate-90' : ''}`}><path d="m9 18 6-6-6-6" /></svg>{active.name}</button><button type="button" disabled={busy} aria-label={`Edit ${active.name} connection name`} title="Edit connection name" onClick={() => setEditingName(active.id)} className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-slate-500 hover:bg-slate-100 hover:text-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4"><path d="m16 3 5 5M4 20l4-1L21 6a2.1 2.1 0 0 0-3-3L5 16l-1 4Z" /></svg></button></div><span className="block text-xs text-slate-500">{active.accounts.map(a => `••${a.last4}`).join(' · ')}</span></div><button type="button" disabled={busy} onClick={() => void connect(active)} aria-label={`Renew Access for ${active.name}`} className={button}>Renew Access</button></div>
        {editingName === active.id && <ConnectionName key={`${active.id}-${active.name}`} profile={active} busy={busy} cancel={() => setEditingName('')} save={name => request(`/${active.id}/name`, 'put', { name })} />}
        {settingsProfile === active.id && <section aria-label={`Settings for ${active.name}`} className="mt-3 space-y-3">
        {active.accounts.filter(account => account.kind === 'checking' && account.account_id).map(account => <Reserve key={account.id} account={account} busy={busy} save={(value, onSuccess) => request(`/accounts/${account.account_id}/reserve`, 'put', { reserve_cents: value }, onSuccess)} />)}

        <ProfilePreferences key={JSON.stringify(active.preferences)} profile={active} routes={data.routes.filter(r => r.profile_id === active.id)} busy={busy} toggle={route => { setReview(null); return request(`/routes/${route.id}`, 'put', { enabled: !route.enabled }) }} save={value => request(`/${active.id}/preferences`, 'put', value)} />
        {active.institution_id === 'ins_109917' && <details className="mt-4 rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-semibold">Add a permitted transfer route</summary><div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="text-sm text-slate-700">From<BankSelect ariaLabel="Route source" value={source} onChange={v => { setSource(v); setConfirmed(false) }} options={[{ value: '', label: 'Choose source account' }, ...active.accounts.filter(a => a.account_id && (a.kind === 'checking' || ['line of credit', 'home equity'].includes(a.subtype))).map(a => ({ value: a.account_id!, label: `${a.name} · ••${a.last4}` }))]} /></label><label className="text-sm text-slate-700">To<BankSelect ariaLabel="Route destination" value={destination} onChange={v => { setDestination(v); setConfirmed(false) }} options={[{ value: '', label: 'Choose destination account' }, ...active.accounts.filter(a => a.account_id && a.account_id !== source).map(a => ({ value: a.account_id!, label: `${a.name} · ••${a.last4}` }))]} /></label></div><label className="mt-4 flex gap-3 text-sm text-slate-700"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />This route is available in Truliant under the {active.name} login.</label><button type="button" disabled={busy || !source || !destination || source === destination || !confirmed} onClick={() => { void request('/routes', 'post', { profile_id: active.id, source_id: source, destination_id: destination, bank_route_confirmed: confirmed }); setConfirmed(false) }} className={`${primary} mt-4`}>Save transfer route</button></details>}
      </section>}</div>)}
    </section>, settingsTarget)}
    {error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
    {notice && <p role="status" className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</p>}
    {loading ? <div role="status" className="mt-5 rounded-2xl border border-slate-700 bg-slate-900 p-6 text-slate-300">Loading your accounts…<div aria-hidden="true" className="mt-4 grid gap-4 md:grid-cols-2"><div className="h-56 rounded-xl bg-slate-800" /><div className="h-56 rounded-xl bg-slate-800" /></div></div> : !data.profiles.length ? <div><button type="button" onClick={openSettings} className={`${primary} mt-4`}>Set up in Monitoring settings</button></div> : <>
      <div className="mt-5 flex flex-wrap gap-2" aria-label="Choose banking profile">{data.profiles.map(p => {
        const isActive = active?.id === p.id
        const refreshing = refreshingProfile === p.id
        return <div key={p.id} className={`inline-flex max-w-full items-stretch overflow-hidden rounded-xl border text-sm font-semibold ${isActive ? 'border-blue-500 bg-blue-600 text-white' : 'border-slate-600 bg-slate-900 text-slate-200'}`}>
          <button type="button" aria-pressed={isActive} disabled={busy} onClick={() => { setSelected(p.id); setSource(''); setDestination(''); setConfirmed(false); setReview(null) }} className="min-h-11 min-w-0 px-4 text-left hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-300 disabled:opacity-45">{p.name}</button>
          {isActive && <button type="button" aria-label={`Refresh ${p.name}`} title={`Refresh ${p.name}`} aria-busy={refreshing} disabled={busy} onClick={() => {
            setReview(null); setRefreshingProfile(p.id)
            void request(`/${p.id}/sync`).finally(() => { if (alive.current) setRefreshingProfile('') })
          }} className="grid min-h-11 w-11 shrink-0 place-items-center border-l border-blue-400/60 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-blue-300 disabled:opacity-45">
            <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`h-4 w-4 ${refreshing ? 'animate-spin motion-reduce:animate-none' : ''}`}><path d="M20 7v5h-5M4 17v-5h5" /><path d="M6.1 7a7 7 0 0 1 11.6-1L20 9M4 15l2.3 3A7 7 0 0 0 17.9 17" /></svg>
          </button>}
        </div>
      })}</div>

      {active && <>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-300">{active.status === 'synced' ? 'Synced' : active.status.replace(/_/g, ' ')}{active.last_checked_at && ` · Last successful read ${new Date(active.last_checked_at).toLocaleString()}`}</p></div>
        {active.last_error && <p role="status" className="mt-3 text-sm text-amber-200">{active.last_error.replace(/_/g, ' ')}. Previously read balances may be stale.</p>}
        {!!active.coverage?.length && <section aria-label="Coverage proposals" className="mt-5 border-t border-slate-700 pt-4"><h3 className="font-semibold text-amber-200">Checking needs attention</h3>{active.coverage.map(c => <div key={c.account_id} className="mt-3 space-y-2 text-sm">
          <div className="flex flex-wrap items-center justify-between gap-2"><strong>{c.name} · ••{c.last4}</strong><span className="font-semibold tabular-nums">{c.minimum_cents == null ? 'Balance unavailable' : c.pending_review_required ? `${money(c.minimum_cents)}–${money(c.possible_cents)} to review` : `${money(c.minimum_cents)} to cover`}</span></div>
          <p className="text-xs text-slate-300">{c.pending_review_required ? 'Pending debits may already affect the balance. Confirm the amount before creating a draft.' : 'Includes your protected reserve and accounts for unfinished incoming transfers.'}{c.observed_at && ` Based on ${new Date(c.observed_at).toLocaleString()}.`}</p>
          <div className="flex flex-wrap gap-2">{c.routes.map(option => { const route = data.routes.find(r => r.id === option.route_id); return route && <button key={option.route_id} disabled={busy} className={button} onClick={() => { const target = active.accounts.find(a => a.account_id === c.account_id); setAccountId(target?.id || ''); void startReview(route) }}>Review funding from ••{option.source_last4}</button> })}{!c.routes.length && <button type="button" className={button} onClick={openSettings}>Review funding settings</button>}</div>
          {!!c.uncovered_cents && <p className="text-xs text-amber-200">Enabled funding can leave up to {money(c.uncovered_cents)} uncovered.</p>}
        </div>)}</section>}
        {[{ key: 'checking', label: 'Checking accounts', description: 'Cash available at the bank' }, { key: 'line', label: 'Credit lines', description: 'Available borrowing and balances owed' }, { key: 'card', label: 'Credit cards', description: 'Available credit and card balances' }].map(group => {
          const accounts = active.accounts.filter(a => (a.kind === 'checking' ? 'checking' : a.subtype === 'credit card' ? 'card' : 'line') === group.key)
          if (!accounts.length) return null
          return <section key={group.key} aria-label={group.label} className="mt-6"><div className="mb-3 flex flex-wrap items-baseline justify-between gap-2"><h3 className="font-semibold text-slate-100">{group.label}</h3><p className="text-xs text-slate-400">{group.description}</p></div><div className={`grid gap-3 ${accounts.length === 1 ? 'grid-cols-1' : accounts.length === 2 ? 'md:grid-cols-2' : 'md:grid-cols-2 xl:grid-cols-3'}`}>{accounts.map(a => {
          const checking = a.kind === 'checking'
          const shared = data.profiles.filter(p => p.accounts.some(other => other.account_id === a.account_id)).length > 1
          return <article key={a.id} className={`relative flex min-w-0 flex-col rounded-2xl border p-4 ${checking ? 'border-emerald-700/70 bg-gradient-to-br from-emerald-950 to-slate-900' : 'border-blue-700/70 bg-gradient-to-br from-blue-950 to-slate-900'}`}>
            <div className="flex items-center justify-between gap-3"><span className={`rounded-md px-2.5 py-1 text-xs font-semibold ${checking ? 'bg-emerald-400/15 text-emerald-200' : 'bg-blue-400/15 text-blue-200'}`}>{checking ? 'Checking' : a.subtype === 'credit card' ? 'Credit card' : 'Credit line'}</span><span className="font-mono text-sm tracking-widest text-slate-300">•• {a.last4}</span></div>
            <h3 className="mt-3 text-base font-semibold text-white">{a.account_id ? <button type="button" aria-label={`Manage ${a.name} ending ${a.last4}`} onClick={() => { setAccountId(a.id); setReview(null); setError(''); void bankProfilesApi.request<Data>(tenantId).then(r => update(r.data)).catch(e => setError(errorText(e))) }} className="text-left after:absolute after:inset-0 after:rounded-2xl hover:text-blue-200 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-blue-300">{a.name}</button> : a.name}</h3>
            {a.account_id ? <>
              <div className="my-4 grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] gap-4">
                <div><p className="text-xs text-slate-300">{checking ? 'Bank available cash' : 'Available credit'}</p><p className="mt-1 break-words text-2xl font-semibold tabular-nums tracking-tight text-white">{money(a.balance.available_cents)}</p></div>
                <div className="border-l border-white/15 pl-4"><p className="text-xs text-slate-300">Pending debits reported</p><p className={`mt-1 break-words text-xl font-semibold tabular-nums ${a.balance.pending_debit_cents ? 'text-amber-200' : 'text-slate-100'}`}>{money(a.balance.pending_debit_cents)}</p></div>
              </div>
              <dl className="mt-auto flex flex-wrap justify-between gap-x-5 gap-y-2 border-t border-white/15 pt-3 text-sm"><div><dt className="text-xs text-slate-300">{checking ? 'Posted balance' : 'Balance owed'}</dt><dd className="mt-1 font-medium tabular-nums text-white">{money(a.balance.current_cents)}</dd></div>{checking && <div><dt className="text-xs text-slate-300">Protected reserve</dt><dd className="mt-1 font-medium tabular-nums text-white">{money(a.reserve_cents)}</dd></div>}</dl>
              <div className="mt-4 flex items-center justify-between gap-3 text-xs"><span className="text-slate-300">{shared ? 'Shared across profiles' : ''}</span><span className={`font-semibold ${checking ? 'text-emerald-200' : 'text-blue-200'}`}>Manage account →</span></div>
            </> : <div className="mt-3 space-y-2"><p className="text-sm text-amber-200">Possible overlapping account. Identify it before using its balance or creating a route.</p>{a.overlap_candidates.map(c => <button key={c.id} disabled={busy} className={`${button} w-full`} onClick={() => void request(`/${active.id}/accounts/${a.id}/resolve`, 'post', { account_id: c.id })}>Same account as {c.name} · ••{c.last4}{c.profiles?.length ? ` (${c.profiles.join(', ')})` : ''}</button>)}<button disabled={busy} className={`${button} w-full`} onClick={() => void request(`/${active.id}/accounts/${a.id}/resolve`, 'post', { separate_account: true })}>This is a different account</button></div>}
          </article>
        })}</div></section>
        })}
        <p className="mt-4 text-xs leading-5 text-slate-400">Shared accounts use the same reserves and drafts across profiles. Pending feeds can omit payments; keep a reserve for upcoming bills.</p>
        {account && <BankDialog title={`${account.name} · ••${account.last4}`} onClose={() => { setAccountId(''); setReview(null) }}>
          <p className="text-sm text-slate-600">Bank login: {active.name}</p>
          {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-900">{error}</p>}
          <div className="grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-4"><div><p className="text-xs text-slate-600">{account.kind === 'checking' ? 'Bank available cash' : 'Balance owed'}</p><p className="text-xl font-semibold">{money(account.kind === 'checking' ? account.balance.available_cents : account.balance.current_cents)}</p></div><div><p className="text-xs text-slate-600">{account.kind === 'checking' ? 'Protected reserve' : 'Available credit'}</p><p className="text-xl font-semibold">{money(account.kind === 'checking' ? account.reserve_cents : account.balance.available_cents)}</p></div></div>
          {!review && <>
            <section className="space-y-3"><h3 className="font-semibold">What would you like to do?</h3>
              {data.routes.filter(r => r.profile_id === active.id && r.enabled && (r.source_id === account.account_id || r.destination_id === account.account_id)).map(r => {
                const from = active.accounts.find(a => a.account_id === r.source_id)
                const to = active.accounts.find(a => a.account_id === r.destination_id)
                const existing = data.drafts?.find(d => d.source_id === r.source_id && d.destination_id === r.destination_id && d.status !== 'bank_history_matched')
                const action = operationLabel(from, to)
                return <button key={r.id} type="button" disabled={busy} onClick={() => { if (existing) { setAccountId(''); onOpenTransfer(existing.id) } else void startReview(r) }} className="block min-h-16 w-full rounded-xl border border-slate-200 p-4 text-left hover:border-blue-500 hover:bg-blue-50 disabled:opacity-50"><span className="block font-semibold text-blue-800">{existing ? 'Continue existing transfer' : action}</span><span className="mt-1 block text-sm text-slate-600">{from?.name} · ••{from?.last4} → {to?.name} · ••{to?.last4}{existing && ` · ${money(existing.amount_cents)}`}</span></button>
              })}
              <p className="text-xs text-slate-500">Only permitted routes for this bank login appear. <button type="button" onClick={() => { setAccountId(''); openSettings() }} className="font-semibold text-blue-700">Manage routes in settings</button></p>
            </section>
            <section className="space-y-3 border-t border-slate-200 pt-4"><h3 className="font-semibold">Transfers involving this account</h3>
              {!data.drafts?.some(d => d.source_id === account.account_id || d.destination_id === account.account_id) && <p className="text-sm text-slate-600">No transfers yet.</p>}
              {data.drafts?.filter(d => d.source_id === account.account_id || d.destination_id === account.account_id).map(d => <div key={d.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-3"><div><p className="font-semibold">{money(d.amount_cents)} · ••{d.from_last4} → ••{d.to_last4}</p><p className="text-sm text-slate-600">{d.status === 'bank_history_matched' ? d.kind === 'repayment' ? 'Payment posted · full payoff not verified' : 'Transfer completed' : d.status === 'reviewed' ? 'Ready to prepare' : 'Needs verification'}</p></div>{d.status !== 'bank_history_matched' && <button type="button" className={button} onClick={() => { setAccountId(''); onOpenTransfer(d.id) }}>Continue transfer</button>}</div>)}
            </section>
          </>}
          {review && <section aria-label="Review account transfer" className="space-y-4">
            <button type="button" onClick={() => setReview(null)} className="min-h-11 text-sm font-semibold text-blue-700">← Account actions</button>
            <h3 className="font-semibold">{review.source_name} · ••{review.from_last4} → {review.destination_name} · ••{review.to_last4}</h3>
            <p className="text-sm text-slate-600">1. Set amount → 2. Prepare in Truliant → 3. You approve in the bank</p>
            {review.kind === 'repayment' && <fieldset><legend className="mb-2 font-semibold">Payment goal</legend><div className="flex flex-wrap gap-3">{(['payment', 'full_payoff'] as const).map(value => <label key={value} className="flex min-h-11 items-center gap-2 rounded-xl border border-slate-300 p-3"><input type="radio" name="payment-goal" checked={intent === value} onChange={() => setIntent(value)} />{value === 'payment' ? 'Make a payment' : 'Pay off in full'}</label>)}</div></fieldset>}
            {intent === 'full_payoff' ? <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-4"><h4 className="font-semibold">Full payoff is not verified</h4><p className="mt-2 text-sm">This connection reports the balance owed, but does not supply a current payoff quote including accrued interest. ELIS cannot prepare a full payoff from that balance. Check the payoff amount in Truliant, or choose Make a payment for a partial payment.</p></div> : <>
              {review.coverage && <div className="space-y-3 rounded-xl bg-blue-50 p-3 text-sm"><dl className="grid grid-cols-2 gap-2"><dt>Balance shortfall + reserve</dt><dd className="text-right font-semibold">{money(review.coverage.minimum_cents)}</dd><dt>If reported pending debits are additional</dt><dd className="text-right font-semibold">{money(review.coverage.possible_cents)}</dd></dl><p>Pending debits are not automatically added to the bank balance. Check Truliant for debits that have already posted, then enter the amount to cover.</p><label className="flex items-start gap-2"><input type="checkbox" checked={coverageConfirmed} onChange={e => setCoverageConfirmed(e.target.checked)} className="mt-1" />I checked the bank balance and pending debits and approve this coverage amount.</label></div>}
              <label className="block text-sm font-medium">{review.kind === 'repayment' ? 'Payment amount' : 'Transfer amount'}<MoneyInput value={amount} onChange={value => { setAmount(value); setCoverageConfirmed(false) }} className="mt-1 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3" /></label>
              <p className="text-sm text-slate-600">Planning limit {money(review.limit_cents)} after reserve {money(review.reserve_cents)}, reported pending debits {money(review.pending_debit_cents)}, and unfinished transfers {money(review.reserved_draft_cents)}.</p>
              <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-950">Pending transactions may be missing from the feed. Confirm current bank cash before submitting.{review.kind === 'repayment' && ' Interest may be deducted from your payment. Paying the displayed balance does not guarantee a zero balance.'}</p>
              <button disabled={busy || cents <= 0 || cents > Math.min(review.limit_cents, review.coverage?.possible_cents ?? review.limit_cents) || Boolean(review.coverage && !coverageConfirmed)} onClick={() => void create()} className={primary}>{busy ? 'Saving…' : 'Continue to preparation'}</button>
            </>}
            <p className="text-xs text-slate-500">No money moves here. Required login: {review.profile_name}. Bank data read {new Date(review.observed_at).toLocaleTimeString()}.</p>
          </section>}
        </BankDialog>}
        {!!data.runs.length && <details className="mt-5 text-sm"><summary className="cursor-pointer font-semibold">Profile check history</summary>{data.runs.filter(r => r.profile_id === active.id).map(r => <p key={r.date} className="mt-2 text-slate-600">{r.date} · {r.status.replace(/_/g, ' ')}</p>)}</details>}
      </>}
    </>}
  </section>
}

function Reserve({ account, busy, save }: { account: Account; busy: boolean; save: (value: number, onSuccess: () => void) => Promise<void> }) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState((account.reserve_cents / 100).toFixed(2))
  const editor = useRef<HTMLLabelElement>(null)
  const control = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    if (editing) { const input = editor.current?.querySelector('input'); input?.focus(); input?.select() }
  }, [editing])
  let cents = -1
  try { cents = centsFromMoneyInput(value) } catch { /* invalid */ }
  const close = () => { setEditing(false); control.current?.focus() }
  const submit = () => {
    if (busy || cents < 0) return
    if (cents === account.reserve_cents) { close(); return }
    void save(cents, close)
  }
  const action = editing ? 'Save' : 'Edit'
  return <div className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm">
    <span className="flex min-w-0 flex-1 items-center gap-1 font-medium" title={`${account.name} · ••${account.last4}`}><span className="truncate">{account.name}</span><span className="shrink-0">· ••{account.last4}</span></span>
    <div className="flex shrink-0 items-center gap-1">
      {editing ? <label ref={editor} className="flex items-center gap-2 whitespace-nowrap text-slate-600 [&>span.relative]:mt-0 [&>span.relative]:w-20" onKeyDown={event => {
        if (event.key === 'Enter') { event.preventDefault(); submit() }
        if (event.key === 'Escape' && !busy) { event.preventDefault(); event.stopPropagation(); close() }
      }}>Reserve<span className="sr-only"> for {account.name} ••{account.last4}</span><MoneyInput value={value} onChange={setValue} invalid={cents < 0} className="min-h-9 w-full rounded-lg border border-slate-300 bg-white px-2 text-slate-900" /></label> : <span className="flex items-center gap-2 whitespace-nowrap text-slate-600">Reserve <span className="inline-flex min-h-9 w-20 items-center justify-end px-2 font-medium tabular-nums text-slate-900">{money(account.reserve_cents)}</span></span>}
      <button ref={control} type="button" disabled={busy || (editing && cents < 0)} aria-label={`${action} reserve for ${account.name} ••${account.last4}`} title={`${action} reserve`} onClick={() => {
        if (editing) submit()
        else { setValue((account.reserve_cents / 100).toFixed(2)); setEditing(true) }
      }} className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-blue-700 hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:opacity-45">
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4">{editing ? <path d="m5 12 4 4L19 6" /> : <path d="m16 3 5 5M4 20l4-1L21 6a2.1 2.1 0 0 0-3-3L5 16l-1 4Z" />}</svg>
      </button>
    </div>
  </div>
}

function operationLabel(from?: Account, to?: Account) {
  return to?.kind === 'credit' ? to.subtype === 'credit card' ? 'Pay credit card from checking' : 'Pay credit line from checking' : from?.kind === 'credit' ? 'Draw to checking' : `Move funds to checking ••${to?.last4 || 'unknown'}`
}

function ConnectionName({ profile, busy, save, cancel }: { profile: Profile; busy: boolean; save: (name: string) => Promise<void>; cancel: () => void }) {
  const [name, setName] = useState(profile.name)
  return <div className="space-y-2"><label className="block text-sm">Connection name<input autoFocus maxLength={80} value={name} disabled={busy} onChange={e => setName(e.target.value)} className="mt-1 min-h-11 w-full rounded-lg border border-slate-300 px-3" /></label><div className="flex gap-2"><button type="button" disabled={busy || !name.trim() || name.trim() === profile.name} className={primary} onClick={() => void save(name.trim())}>Save name</button><button type="button" disabled={busy} className={button} onClick={cancel}>Cancel</button></div><p className="text-xs text-slate-500">Changes the label in ELIS. Bank access and accounts stay connected.</p></div>
}

function ProfilePreferences({ profile, routes, busy, save, toggle }: { profile: Profile; routes: Route[]; busy: boolean; save: (value: unknown) => Promise<void>; toggle: (route: Route) => Promise<void> }) {
  const [value, setValue] = useState(profile.preferences)
  const [removed, setRemoved] = useState<string[]>([])
  const issues = value.review_items || []
  const pairs = new Map<string, Route[]>()
  for (const route of routes) {
    const key = [route.source_id, route.destination_id].sort().join(':')
    pairs.set(key, [...(pairs.get(key) || []), route])
  }
  return <div className="space-y-3 border-t border-slate-200 pt-3 text-sm">
    {[...pairs.entries()].map(([key, pair]) => {
      const accounts = [pair[0].source_id, pair[0].destination_id].map(id => profile.accounts.find(a => a.account_id === id)).sort((a, b) => (a?.kind === 'checking' ? 0 : 1) - (b?.kind === 'checking' ? 0 : 1) || (a?.last4 || '').localeCompare(b?.last4 || ''))
      const twoWay = pair.some(route => route.enabled && route.source_id === accounts[0]?.account_id && route.destination_id === accounts[1]?.account_id) && pair.some(route => route.enabled && route.source_id === accounts[1]?.account_id && route.destination_id === accounts[0]?.account_id)
      return <section key={key} aria-label={`Transfer relationship ${accounts.map(a => a?.last4 || 'unavailable').join(' and ')}`} className="rounded-xl border border-slate-200 p-3">
        <h4 className="mb-2 font-semibold text-slate-900">{accounts[0]?.name || 'Unavailable account'} · ••{accounts[0]?.last4}<span className="mx-2 font-normal text-slate-500" title={twoWay ? 'Transfers enabled in both directions' : undefined}>{twoWay ? <><span aria-hidden="true">↔</span><span className="sr-only">two-way transfers with</span></> : 'and'}</span>{accounts[1]?.name || 'Unavailable account'} · ••{accounts[1]?.last4}</h4>
        {pair.sort((a,b) => a.source_id === accounts[0]?.account_id ? -1 : b.source_id === accounts[0]?.account_id ? 1 : a.id.localeCompare(b.id)).map(route => {
          const from = profile.accounts.find(a => a.account_id === route.source_id)
          const to = profile.accounts.find(a => a.account_id === route.destination_id)
          const action = operationLabel(from, to)
          const kind = from?.kind === 'credit' && to?.kind === 'checking' ? 'funding' : from?.kind === 'checking' && to?.kind === 'credit' ? 'repayment' : null
          const orderKey = kind === 'funding' ? 'funding_order' : 'repayment_order'
          const index = value[orderKey].indexOf(route.id)
          return <div key={route.id} className="border-t border-slate-100 py-2">
            <div className="flex items-center justify-between gap-3"><span>{action}</span><button type="button" role="switch" aria-checked={route.enabled} aria-label={`${action}: ${from?.last4} to ${to?.last4}`} disabled={busy} onClick={() => void toggle(route)} className={`relative h-6 w-11 shrink-0 rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:opacity-50 ${route.enabled ? 'bg-blue-600' : 'bg-slate-300'}`}><span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${route.enabled ? 'left-0.5 translate-x-5' : 'left-0.5'}`} /></button></div>
            {kind && <details className="mt-1 text-xs text-slate-600"><summary className="cursor-pointer py-1">{kind === 'funding' ? 'Funding' : 'Repayment'} checks{index >= 0 ? ` · Priority ${index + 1}` : ' · Not included'}</summary><div className="flex flex-wrap items-center gap-2 py-2"><label className="flex items-center gap-2"><input type="checkbox" checked={index >= 0} disabled={busy || (!route.enabled && index < 0)} onChange={e => setValue({ ...value, [orderKey]: e.target.checked ? [...value[orderKey], route.id] : value[orderKey].filter(id => id !== route.id) })} />Include this operation</label>{index >= 0 && <button type="button" disabled={busy || index === 0} aria-label={`Move ${action} from ${from?.last4} priority up`} className="min-h-9 px-2 font-semibold text-blue-700 disabled:opacity-40" onClick={() => { const order = [...value[orderKey]]; [order[index - 1], order[index]] = [order[index], order[index - 1]]; setValue({ ...value, [orderKey]: order }) }}>Move up</button>}</div></details>}
          </div>
        })}
      </section>
    })}
    <p className="text-xs text-slate-500">Transfer switches save as you change them. Use Save changes for the check settings.</p>
    <label className="flex gap-2"><input type="checkbox" checked={value.monitor} onChange={e => setValue({ ...value, monitor: e.target.checked })} />Check these accounts daily</label>
    <label className="flex gap-2"><input type="checkbox" checked={value.repayment} onChange={e => setValue({ ...value, repayment: e.target.checked })} />Check for possible payments on Fridays</label>
    {!!issues.length && <div className="space-y-3 rounded-lg bg-amber-50 p-3 text-amber-950"><h4 className="font-semibold">Some saved transfer settings need updating</h4>{issues.map(item => {
      const removedItem = removed.includes(item.id)
      const possible = routes.filter(route => !route.enabled && (item.route_id ? route.id === item.route_id : profile.accounts.some(a => a.account_id === (item.kind === 'funding' ? route.source_id : route.destination_id) && a.last4 === item.last4)))
      return <div key={item.id} className="border-t border-amber-200 pt-2"><p className="font-medium">{item.label}</p><p className="mt-1 text-xs">{removedItem ? (item.kind === 'funding' ? 'After saving, ELIS will no longer consider this account as a source of money for checking.' : 'After saving, ELIS will no longer include this transfer in payment checks.') : item.message}</p><div className="mt-1 flex flex-wrap gap-2">{removedItem ? <button type="button" className="min-h-9 font-semibold text-blue-800" onClick={() => { setRemoved(removed.filter(id => id !== item.id)); if (item.route_id) { const key = item.kind === 'funding' ? 'funding_order' : 'repayment_order'; setValue({ ...value, [key]: [...value[key], item.route_id] }) } }}>Undo change</button> : <>
      {possible.map(route => <button key={route.id} type="button" disabled={busy} className="min-h-9 font-semibold text-blue-800" onClick={() => void toggle(route)}>Enable {item.kind === 'funding' ? 'transfer to checking' : 'payment'} ••{profile.accounts.find(a => a.account_id === route.source_id)?.last4} → ••{profile.accounts.find(a => a.account_id === route.destination_id)?.last4}</button>)}
      <button type="button" disabled={busy} className="min-h-9 font-semibold text-red-800" onClick={() => { setRemoved([...removed, item.id]); const key = item.kind === 'funding' ? 'funding_order' : 'repayment_order'; setValue({ ...value, [key]: value[key].filter(id => id !== item.route_id) }) }}>{item.kind === 'funding' ? 'Don’t use this account to fund checking' : 'Don’t include this transfer in payment checks'}</button></>}</div>{!removedItem && !possible.length && <p className="mt-1 text-xs">If this bank connection supports the transfer, add it using “Add a permitted transfer route” below.</p>}</div>
    })}<p className="text-xs">You can save one change at a time. Other flagged transfers stay in your plan for later review. These changes do not disconnect accounts, stop balance monitoring, or change manual transfer permissions.</p></div>}
    {value.migration_pending && <p className="text-xs text-slate-600">Saving will use the accounts and cash reserves shown above for future checks. Your accounts stay connected.</p>}
    {!!removed.length && <p className="text-sm text-slate-700">After saving: {issues.filter(item => removed.includes(item.id)).map(item => `${item.label} — ${item.kind === 'funding' ? 'will not be considered for funding checking' : 'will not be included in payment checks'}`).join('; ')}.</p>}
    {value.repayment && !value.repayment_order.length && <p className="text-sm text-amber-900">Choose a payment above for Friday checks, or turn Friday payment checks off.</p>}
    <p className="text-xs text-slate-500">ELIS checks balances and money set aside for bills before suggesting a payment. You review and submit transfers in Truliant.</p>
    {value.last_evaluation?.status && <p className="text-xs text-slate-600">Last route check: {value.last_evaluation.status.replace(/_/g, ' ')}</p>}
    <button type="button" disabled={busy || (value.repayment && !value.repayment_order.length)} className={primary} onClick={() => void save({ monitor: value.monitor, repayment: value.repayment, funding_order: value.funding_order, repayment_order: value.repayment_order, confirm_migration: true, removed_review_items: removed })}>Save changes</button>
  </div>
}
