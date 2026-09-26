import { createPortal } from 'react-dom'
import { useEffect, useRef, useState } from 'react'
import { bankProfilesApi } from '../services/api'
import { loadPlaidLink } from '../services/plaidLink'
import BankSelect from '../components/BankSelect'
import MoneyInput from '../components/MoneyInput'
import { centsFromMoneyInput } from '../components/moneyAmount'

type Account = { id: string; account_id: string | null; name: string; last4: string; kind: string; subtype: string; reserve_cents: number; balance: { current_cents?: number | null; available_cents?: number | null; pending_debit_cents?: number | null; currency?: string }; overlap_candidates: { id: string; name: string; last4: string; profiles?: string[] }[] }
type Profile = { id: string; name: string; institution_id: string; status: string; last_error: string | null; last_checked_at: string | null; accounts: Account[] }
type Route = { id: string; profile_id: string; source_id: string; destination_id: string; enabled: boolean }
type Data = { profiles: Profile[]; routes: Route[]; runs: { profile_id: string; date: string; status: string }[] }
type Review = { id: number; profile_name: string; source_name: string; destination_name: string; from_last4: string; to_last4: string; limit_cents: number; reserve_cents: number; reserved_draft_cents: number; pending_debit_cents: number | null; observed_at: string }
const money = (value?: number | null) => value == null ? 'Unavailable' : (value / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const button = 'min-h-11 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-45'
const primary = 'min-h-11 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-45'
const errorText = (e: unknown) => (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || (e instanceof Error ? e.message : 'Banking profile request failed.')

export default function BankProfiles({ tenantId, onMode, onDraft, settingsTarget, openSettings }: { settingsTarget: HTMLElement | null; openSettings: () => void; tenantId: number; onMode: (value: boolean) => void; onDraft: () => void }) {
  const [data, setData] = useState<Data>({ profiles: [], routes: [], runs: [] })
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [name, setName] = useState('Truliant — Main Business')
  const [source, setSource] = useState('')
  const [destination, setDestination] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [review, setReview] = useState<Review | null>(null)
  const [amount, setAmount] = useState('')
  const alive = useRef(true)
  const resumed = useRef(false)
  const active = data.profiles.find(p => p.id === selected) || data.profiles[0]
  const mode = data.profiles.length > 1 || data.routes.length > 0
  const update = (value: Data) => { if (alive.current) { setData(value); onMode(value.profiles.length > 1 || value.routes.length > 0) } }
  const request = async (path: string, method: 'post' | 'put' = 'post', body?: unknown) => {
    setBusy(true); setError(''); setNotice('')
    try { const response = await bankProfilesApi.request<Data>(tenantId, path, method, body); update(response.data) }
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
    void bankProfilesApi.request<Data>(tenantId).then(response => update(response.data)).catch(e => { if (alive.current) setError(errorText(e)) })
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
    return () => { alive.current = false }
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
    setBusy(true); setError(''); setReview(null)
    try {
      const response = await bankProfilesApi.request<Review>(tenantId, `/routes/${route.id}/review`, 'post')
      if (alive.current) { setReview(response.data); setAmount((response.data.limit_cents / 100).toFixed(2)) }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  let cents = 0
  try { cents = centsFromMoneyInput(amount) } catch { /* Invalid input cannot create a draft. */ }
  const create = async () => {
    if (!review) return
    setBusy(true); setError('')
    try {
      await bankProfilesApi.request(tenantId, `/reviews/${review.id}/draft`, 'post', { amount_cents: cents })
      if (alive.current) { setReview(null); setNotice('Draft added to the transfer queue. Prepare it using the bank login shown on the draft.'); onDraft() }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  return <section aria-label="Banking profiles" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Banking profiles</p><h2 className="mt-1 text-xl font-semibold text-slate-950">{mode ? 'Accounts and transfer routes' : 'Connect separate bank logins'}</h2><p className="mt-2 text-sm text-slate-600">Each profile keeps its own bank access. Transfers use the login assigned to their route.</p></div></header>
    {settingsTarget && createPortal(<section aria-label="Manage bank connections" className="space-y-4 rounded-xl border border-slate-200 p-4">
      <h3 className="font-semibold text-slate-950">Manage bank connections</h3>
      <p className="text-sm text-slate-600">Each connection uses its own bank login. Adding one preserves your existing connections.</p>
      {error && <p role="alert" className="text-sm text-red-900">{error}</p>}
      {data.profiles.map(profile => <div key={profile.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3"><div><p className="text-sm font-semibold">{profile.name}</p><p className="text-xs text-slate-500">{profile.accounts.map(account => `••${account.last4}`).join(' · ')}</p></div><button type="button" disabled={busy} onClick={() => void connect(profile)} className={button}>Renew access for {profile.name}</button></div>)}
      {!data.profiles.length && <button type="button" disabled={busy} onClick={() => void request('/initialize')} className={button}>Use existing bank connection</button>}
      <label className="block text-sm text-slate-700">New banking profile name<input value={name} maxLength={80} onChange={e => setName(e.target.value)} className="mt-1 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label>
      <p className="text-xs leading-5 text-slate-500">For a separate bank login, choose different credentials in Plaid instead of reusing a saved connection. Other institutions can be monitored; form preparation currently supports Truliant only.</p>
      <button type="button" disabled={busy || !name.trim()} onClick={() => void connect()} className={primary}>{busy ? 'Working…' : 'Connect another bank login'}</button>
    </section>, settingsTarget)}
    {error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
    {notice && <p role="status" className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</p>}
    {!data.profiles.length ? <div><button type="button" onClick={openSettings} className={`${primary} mt-4`}>Set up in Monitoring settings</button></div> : <>
      <div className="mt-5 flex flex-wrap gap-2" aria-label="Choose banking profile">{data.profiles.map(p => <button key={p.id} type="button" aria-pressed={active?.id === p.id} disabled={busy} onClick={() => { setSelected(p.id); setSource(''); setDestination(''); setConfirmed(false); setReview(null) }} className={active?.id === p.id ? primary : button}>{p.name}</button>)}</div>

      {active && <>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-600">{active.status === 'synced' ? 'Synced' : active.status.replace(/_/g, ' ')}{active.last_checked_at && ` · Last successful read ${new Date(active.last_checked_at).toLocaleString()}`}</p><div className="flex gap-2"><button disabled={busy} onClick={() => { setReview(null); void request(`/${active.id}/sync`) }} className={primary}>{busy ? 'Working…' : 'Refresh profile'}</button></div></div>
        {active.last_error && <p role="status" className="mt-3 text-sm text-amber-900">{active.last_error.replace(/_/g, ' ')}. Previously read balances may be stale.</p>}
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{active.accounts.map(a => <article key={a.id} className={`rounded-xl border p-4 ${a.kind === 'checking' ? 'border-emerald-200 bg-emerald-50/50' : 'border-indigo-200 bg-indigo-50/50'}`}><p className="text-xs font-semibold uppercase text-slate-500">{a.kind} · ••{a.last4}</p><h3 className="mt-2 font-semibold text-slate-950">{a.name}</h3>{a.account_id ? <><p className="mt-3 text-2xl font-semibold tabular-nums text-slate-950">{money(a.balance.available_cents)}</p><p className="text-xs text-slate-600">{a.kind === 'checking' ? 'Bank available cash' : 'Available credit'}</p><p className="mt-3 text-sm text-slate-700">{a.kind === 'checking' ? 'Posted' : 'Balance owed'}: {money(a.balance.current_cents)}</p><p className="mt-1 text-sm text-slate-700">Pending debits reported: {money(a.balance.pending_debit_cents)}</p>{data.profiles.filter(p => p.accounts.some(other => other.account_id === a.account_id)).length > 1 && <p className="mt-2 text-xs font-medium text-blue-800">Shared account identity across banking profiles. Reserved drafts apply across all logins.</p>}{a.kind === 'checking' && <details className="mt-3 text-sm"><summary className="cursor-pointer">Keep in checking: {money(a.reserve_cents)}</summary><Reserve key={`${a.account_id}-${a.reserve_cents}`} account={a} busy={busy} save={value => request(`/accounts/${a.account_id}/reserve`, 'put', { reserve_cents: value })} /></details>}</> : <div className="mt-3 space-y-2"><p className="text-sm text-amber-900">Possible overlapping account. Identify it before using its balance or creating a route.</p>{a.overlap_candidates.map(c => <button key={c.id} disabled={busy} className={`${button} w-full`} onClick={() => void request(`/${active.id}/accounts/${a.id}/resolve`, 'post', { account_id: c.id })}>Same account as {c.name} · ••{c.last4}{c.profiles?.length ? ` (${c.profiles.join(', ')})` : ''}</button>)}<button disabled={busy} className={`${button} w-full`} onClick={() => void request(`/${active.id}/accounts/${a.id}/resolve`, 'post', { separate_account: true })}>This is a different account</button></div>}</article>)}</div>
        <p className="mt-3 text-xs leading-5 text-slate-500">Profiles show their own bank-reported balances; do not add overlapping profiles together. Pending feeds can omit payments. Keep a reserve for upcoming bills.</p>
        <div className="mt-6 border-t border-slate-200 pt-5"><h3 className="font-semibold text-slate-950">Transfer routes · {active.name}</h3><div className="mt-3 space-y-3">{data.routes.filter(r => r.profile_id === active.id).map(r => { const from = active.accounts.find(a => a.account_id === r.source_id); const to = active.accounts.find(a => a.account_id === r.destination_id); return <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 p-4"><div><p className="text-sm font-semibold text-slate-900">{from?.name || 'Unavailable account'} · ••{from?.last4} → {to?.name || 'Unavailable account'} · ••{to?.last4}</p><p className="mt-1 text-xs text-slate-500">Login: {active.name}{!r.enabled && ' · Disabled'}</p></div><div className="flex gap-2"><button disabled={busy || !r.enabled} onClick={() => void startReview(r)} className={primary}>Review transfer</button><button disabled={busy} onClick={() => { setReview(null); void request(`/routes/${r.id}`, 'put', { enabled: !r.enabled }) }} className={button}>{r.enabled ? 'Disable' : 'Enable'}</button></div></div> })}</div>
        {active.institution_id === 'ins_109917' && <details className="mt-4 rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-semibold">Add a permitted transfer route</summary><div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="text-sm text-slate-700">From<BankSelect ariaLabel="Route source" value={source} onChange={v => { setSource(v); setConfirmed(false) }} options={[{ value: '', label: 'Choose source account' }, ...active.accounts.filter(a => a.account_id && (a.kind === 'checking' || ['line of credit', 'home equity'].includes(a.subtype))).map(a => ({ value: a.account_id!, label: `${a.name} · ••${a.last4}` }))]} /></label><label className="text-sm text-slate-700">To<BankSelect ariaLabel="Route destination" value={destination} onChange={v => { setDestination(v); setConfirmed(false) }} options={[{ value: '', label: 'Choose destination account' }, ...active.accounts.filter(a => a.account_id && a.account_id !== source).map(a => ({ value: a.account_id!, label: `${a.name} · ••${a.last4}` }))]} /></label></div><label className="mt-4 flex gap-3 text-sm text-slate-700"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />This route is available in Truliant under the {active.name} login.</label><button disabled={busy || !source || !destination || source === destination || !confirmed} onClick={() => { void request('/routes', 'post', { profile_id: active.id, source_id: source, destination_id: destination, bank_route_confirmed: confirmed }); setConfirmed(false) }} className={`${primary} mt-4`}>Save transfer route</button></details>}
        </div>
        {review && <section aria-label="Review profile transfer" className="mt-5 space-y-4 rounded-xl border border-blue-200 bg-blue-50 p-5"><h3 className="font-semibold text-slate-950">{review.source_name} · ••{review.from_last4} → {review.destination_name} · ••{review.to_last4}</h3><p className="text-sm text-slate-600">Required bank login: {review.profile_name}. Bank data read {new Date(review.observed_at).toLocaleTimeString()}.</p><label className="block text-sm font-medium">Transfer amount<MoneyInput value={amount} onChange={setAmount} className="block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3" /></label><p className="text-sm text-slate-600">Maximum {money(review.limit_cents)} after reserve {money(review.reserve_cents)} and unfinished drafts {money(review.reserved_draft_cents)}. This is an estimate, not a payoff quote.</p><div className="flex gap-2"><button disabled={busy || cents <= 0 || cents > review.limit_cents} onClick={() => void create()} className={primary}>Create reviewed draft</button><button disabled={busy} onClick={() => setReview(null)} className={button}>Cancel</button></div><p className="text-xs text-slate-500">No money moves here. You sign in to the required bank profile, review the prepared form, and submit it yourself.</p></section>}
        {!!data.runs.length && <details className="mt-5 text-sm"><summary className="cursor-pointer font-semibold">Profile check history</summary>{data.runs.filter(r => r.profile_id === active.id).map(r => <p key={r.date} className="mt-2 text-slate-600">{r.date} · {r.status.replace(/_/g, ' ')}</p>)}</details>}
      </>}
    </>}
  </section>
}

function Reserve({ account, busy, save }: { account: Account; busy: boolean; save: (value: number) => Promise<void> }) {
  const [value, setValue] = useState((account.reserve_cents / 100).toFixed(2))
  let cents = -1
  try { cents = centsFromMoneyInput(value) } catch { /* invalid */ }
  return <div className="mt-2 space-y-2"><MoneyInput value={value} onChange={setValue} className="block min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3" /><button disabled={busy || cents < 0} onClick={() => void save(cents)} className={button}>Save reserve</button></div>
}
