import { createPortal } from 'react-dom'
import { useEffect, useRef, useState } from 'react'
import { bankProfilesApi } from '../services/api'
import { loadPlaidLink } from '../services/plaidLink'
import BankDialog from '../components/BankDialog'
import BankSelect from '../components/BankSelect'
import MoneyInput from '../components/MoneyInput'
import { centsFromMoneyInput } from '../components/moneyAmount'

type Account = { id: string; account_id: string | null; name: string; last4: string; kind: string; subtype: string; reserve_cents: number; balance: { current_cents?: number | null; available_cents?: number | null; pending_debit_cents?: number | null; currency?: string }; overlap_candidates: { id: string; name: string; last4: string; profiles?: string[] }[] }
type Profile = { id: string; name: string; institution_id: string; status: string; last_error: string | null; last_checked_at: string | null; accounts: Account[] }
type Route = { id: string; profile_id: string; source_id: string; destination_id: string; enabled: boolean }
type Transfer = { id: string; source_id: string; destination_id: string; profile_id: string; amount_cents: number; status: string; from_last4: string; to_last4: string; kind: string }
type Data = { drafts?: Transfer[]; profiles: Profile[]; routes: Route[]; runs: { profile_id: string; date: string; status: string }[] }
type Review = { kind: string; id: number; profile_name: string; source_name: string; destination_name: string; from_last4: string; to_last4: string; limit_cents: number; reserve_cents: number; reserved_draft_cents: number; pending_debit_cents: number | null; observed_at: string }
const money = (value?: number | null) => value == null ? 'Unavailable' : (value / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
const button = 'min-h-11 rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:opacity-45'
const primary = 'min-h-11 rounded-xl bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:opacity-45'
const errorText = (e: unknown) => (e as { response?: { data?: { detail?: string } } }).response?.data?.detail || (e instanceof Error ? e.message : 'Banking profile request failed.')

export default function BankProfiles({ tenantId, onMode, onDraft, onOpenTransfer, settingsTarget, openSettings }: { settingsTarget: HTMLElement | null; openSettings: () => void; tenantId: number; onMode: (value: boolean) => void; onDraft: () => void; onOpenTransfer: (id: string) => void }) {
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
  const [accountId, setAccountId] = useState('')
  const [intent, setIntent] = useState<'payment' | 'full_payoff'>('payment')
  const [amount, setAmount] = useState('')
  const alive = useRef(true)
  const resumed = useRef(false)
  const active = data.profiles.find(p => p.id === selected) || data.profiles[0]
  const account = active?.accounts.find(a => a.id === accountId)
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
    setBusy(true); setError(''); setReview(null); setIntent('payment')
    try {
      const response = await bankProfilesApi.request<Review & { existing_draft?: { id: string } }>(tenantId, `/routes/${route.id}/review`, 'post')
      if (alive.current && response.data.existing_draft) { setAccountId(''); onOpenTransfer(response.data.existing_draft.id); return }
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
      const response = await bankProfilesApi.request<{ draft: { id: string } }>(tenantId, `/reviews/${review.id}/draft`, 'post', { amount_cents: cents, intent })
      if (alive.current) { setReview(null); setAccountId(''); setNotice('Transfer saved. Continue below to prepare the bank form.'); onDraft(); onOpenTransfer(response.data.draft.id) }
    } catch (e) { if (alive.current) setError(errorText(e)) }
    finally { if (alive.current) setBusy(false) }
  }
  return <section aria-label="Banking profiles" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-wider text-blue-700">Banking profiles</p><h2 className="mt-1 text-xl font-semibold text-slate-950">{mode ? 'Your accounts' : 'Connect separate bank logins'}</h2><p className="mt-2 text-sm text-slate-600">Select an account to make a payment, move funds, or view its transfers.</p></div></header>
    {settingsTarget && createPortal(<section aria-label="Manage bank connections" className="space-y-4 rounded-xl border border-slate-200 p-4">
      <h3 className="font-semibold text-slate-950">Manage bank connections</h3>
      <p className="text-sm text-slate-600">Each connection uses its own bank login. Adding one preserves your existing connections.</p>
      {error && <p role="alert" className="text-sm text-red-900">{error}</p>}
      {data.profiles.map(profile => <div key={profile.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3"><div><p className="text-sm font-semibold">{profile.name}</p><p className="text-xs text-slate-500">{profile.accounts.map(account => `••${account.last4}`).join(' · ')}</p></div><button type="button" disabled={busy} onClick={() => void connect(profile)} className={button}>Renew access for {profile.name}</button></div>)}
      {!data.profiles.length && <button type="button" disabled={busy} onClick={() => void request('/initialize')} className={button}>Use existing bank connection</button>}
      <label className="block text-sm text-slate-700">New banking profile name<input value={name} maxLength={80} onChange={e => setName(e.target.value)} className="mt-1 block min-h-11 w-full rounded-xl border border-slate-300 px-3" /></label>
      <p className="text-xs leading-5 text-slate-500">For a separate bank login, choose different credentials in Plaid instead of reusing a saved connection. Other institutions can be monitored; form preparation currently supports Truliant only.</p>
      <button type="button" disabled={busy || !name.trim()} onClick={() => void connect()} className={primary}>{busy ? 'Working…' : 'Connect another bank login'}</button>

      {active && <section aria-label="Transfer and reserve settings" className="space-y-4 border-t border-slate-200 pt-4">
        <h3 className="font-semibold">Transfer routes and reserves</h3>
        <BankSelect ariaLabel="Configure banking profile" value={active.id} onChange={value => { setSelected(value); setSource(''); setDestination(''); setConfirmed(false); setReview(null) }} options={data.profiles.map(profile => ({ value: profile.id, label: profile.name }))} />
        {active.accounts.filter(account => account.kind === 'checking' && account.account_id).map(account => <details key={account.id} className="rounded-xl border border-slate-200 p-3"><summary className="cursor-pointer text-sm font-medium">{account.name} · ••{account.last4} · Reserve {money(account.reserve_cents)}</summary><Reserve key={`${account.account_id}-${account.reserve_cents}`} account={account} busy={busy} save={value => request(`/accounts/${account.account_id}/reserve`, 'put', { reserve_cents: value })} /></details>)}
        {data.routes.filter(route => route.profile_id === active.id).map(route => <div key={route.id} className="flex flex-wrap items-center justify-between gap-3 text-sm"><p>{active.accounts.find(account => account.account_id === route.source_id)?.name || 'Unavailable account'} → {active.accounts.find(account => account.account_id === route.destination_id)?.name || 'Unavailable account'}</p><button type="button" disabled={busy} onClick={() => { setReview(null); void request(`/routes/${route.id}`, 'put', { enabled: !route.enabled }) }} className={button}>{route.enabled ? 'Disable' : 'Enable'}</button></div>)}
        {active.institution_id === 'ins_109917' && <details className="mt-4 rounded-xl border border-slate-200 p-4"><summary className="cursor-pointer text-sm font-semibold">Add a permitted transfer route</summary><div className="mt-4 grid gap-4 sm:grid-cols-2"><label className="text-sm text-slate-700">From<BankSelect ariaLabel="Route source" value={source} onChange={v => { setSource(v); setConfirmed(false) }} options={[{ value: '', label: 'Choose source account' }, ...active.accounts.filter(a => a.account_id && (a.kind === 'checking' || ['line of credit', 'home equity'].includes(a.subtype))).map(a => ({ value: a.account_id!, label: `${a.name} · ••${a.last4}` }))]} /></label><label className="text-sm text-slate-700">To<BankSelect ariaLabel="Route destination" value={destination} onChange={v => { setDestination(v); setConfirmed(false) }} options={[{ value: '', label: 'Choose destination account' }, ...active.accounts.filter(a => a.account_id && a.account_id !== source).map(a => ({ value: a.account_id!, label: `${a.name} · ••${a.last4}` }))]} /></label></div><label className="mt-4 flex gap-3 text-sm text-slate-700"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />This route is available in Truliant under the {active.name} login.</label><button type="button" disabled={busy || !source || !destination || source === destination || !confirmed} onClick={() => { void request('/routes', 'post', { profile_id: active.id, source_id: source, destination_id: destination, bank_route_confirmed: confirmed }); setConfirmed(false) }} className={`${primary} mt-4`}>Save transfer route</button></details>}
      </section>}
    </section>, settingsTarget)}
    {error && <p role="alert" className="mt-4 rounded-xl bg-red-50 p-3 text-sm text-red-900">{error}</p>}
    {notice && <p role="status" className="mt-4 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</p>}
    {!data.profiles.length ? <div><button type="button" onClick={openSettings} className={`${primary} mt-4`}>Set up in Monitoring settings</button></div> : <>
      <div className="mt-5 flex flex-wrap gap-2" aria-label="Choose banking profile">{data.profiles.map(p => <button key={p.id} type="button" aria-pressed={active?.id === p.id} disabled={busy} onClick={() => { setSelected(p.id); setSource(''); setDestination(''); setConfirmed(false); setReview(null) }} className={active?.id === p.id ? primary : button}>{p.name}</button>)}</div>

      {active && <>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-600">{active.status === 'synced' ? 'Synced' : active.status.replace(/_/g, ' ')}{active.last_checked_at && ` · Last successful read ${new Date(active.last_checked_at).toLocaleString()}`}</p><div className="flex gap-2"><button disabled={busy} onClick={() => { setReview(null); void request(`/${active.id}/sync`) }} className={primary}>{busy ? 'Working…' : 'Refresh profile'}</button></div></div>
        {active.last_error && <p role="status" className="mt-3 text-sm text-amber-900">{active.last_error.replace(/_/g, ' ')}. Previously read balances may be stale.</p>}
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{active.accounts.map(a => <article key={a.id} className={`relative rounded-xl border p-4 ${a.kind === 'checking' ? 'border-emerald-200 bg-emerald-50/50' : 'border-indigo-200 bg-indigo-50/50'}`}><p className="text-xs font-semibold uppercase text-slate-500">{a.kind} · ••{a.last4}</p><h3 className="mt-2 font-semibold text-slate-950">{a.account_id ? <button type="button" aria-label={`Manage ${a.name} ending ${a.last4}`} onClick={() => { setAccountId(a.id); setReview(null); setError(''); void bankProfilesApi.request<Data>(tenantId).then(r => update(r.data)).catch(e => setError(errorText(e))) }} className="text-left after:absolute after:inset-0 after:rounded-xl hover:text-blue-700 focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-blue-600">{a.name}</button> : a.name}</h3>{a.account_id ? <><p className="mt-3 text-2xl font-semibold tabular-nums text-slate-950">{money(a.balance.available_cents)}</p><p className="text-xs text-slate-600">{a.kind === 'checking' ? 'Bank available cash' : 'Available credit'}</p><p className="mt-3 text-sm text-slate-700">{a.kind === 'checking' ? 'Posted' : 'Balance owed'}: {money(a.balance.current_cents)}</p><p className="mt-1 text-sm text-slate-700">Pending debits reported: {money(a.balance.pending_debit_cents)}</p>{data.profiles.filter(p => p.accounts.some(other => other.account_id === a.account_id)).length > 1 && <p className="mt-2 text-xs font-medium text-blue-800">Shared account identity across banking profiles. Reserved drafts apply across all logins.</p>}{a.kind === 'checking' && <p className="mt-3 text-sm text-slate-600">Protected reserve: {money(a.reserve_cents)}</p>}<p className="mt-4 text-sm font-semibold text-blue-700">Manage account →</p></> : <div className="mt-3 space-y-2"><p className="text-sm text-amber-900">Possible overlapping account. Identify it before using its balance or creating a route.</p>{a.overlap_candidates.map(c => <button key={c.id} disabled={busy} className={`${button} w-full`} onClick={() => void request(`/${active.id}/accounts/${a.id}/resolve`, 'post', { account_id: c.id })}>Same account as {c.name} · ••{c.last4}{c.profiles?.length ? ` (${c.profiles.join(', ')})` : ''}</button>)}<button disabled={busy} className={`${button} w-full`} onClick={() => void request(`/${active.id}/accounts/${a.id}/resolve`, 'post', { separate_account: true })}>This is a different account</button></div>}</article>)}</div>
        <p className="mt-3 text-xs leading-5 text-slate-500">Profiles show their own bank-reported balances; do not add overlapping profiles together. Pending feeds can omit payments. Keep a reserve for upcoming bills.</p>
        {account && <BankDialog title={`${account.name} · ••${account.last4}`} onClose={() => { setAccountId(''); setReview(null) }}>
          <p className="text-sm text-slate-600">Bank login: {active.name}</p>
          {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-red-900">{error}</p>}
          <div className="grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-4"><div><p className="text-xs text-slate-600">{account.kind === 'checking' ? 'Bank available cash' : 'Balance owed'}</p><p className="text-xl font-semibold">{money(account.kind === 'checking' ? account.balance.available_cents : account.balance.current_cents)}</p></div><div><p className="text-xs text-slate-600">{account.kind === 'checking' ? 'Protected reserve' : 'Available credit'}</p><p className="text-xl font-semibold">{money(account.kind === 'checking' ? account.reserve_cents : account.balance.available_cents)}</p></div></div>
          {!review && <>
            <section className="space-y-3"><h3 className="font-semibold">What would you like to do?</h3>
              {data.routes.filter(r => r.profile_id === active.id && r.enabled && (r.source_id === account.account_id || (account.kind === 'credit' && r.destination_id === account.account_id))).map(r => {
                const from = active.accounts.find(a => a.account_id === r.source_id)
                const to = active.accounts.find(a => a.account_id === r.destination_id)
                const existing = data.drafts?.find(d => d.source_id === r.source_id && d.destination_id === r.destination_id && d.status !== 'bank_history_matched')
                const action = to?.kind === 'credit' ? 'Make a payment' : from?.kind === 'credit' ? 'Transfer credit to checking' : 'Transfer to checking'
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
              <label className="block text-sm font-medium">{review.kind === 'repayment' ? 'Payment amount' : 'Transfer amount'}<MoneyInput value={amount} onChange={setAmount} className="mt-1 block min-h-11 w-full rounded-xl border border-slate-300 bg-white px-3" /></label>
              <p className="text-sm text-slate-600">Planning limit {money(review.limit_cents)} after reserve {money(review.reserve_cents)}, reported pending debits {money(review.pending_debit_cents)}, and unfinished transfers {money(review.reserved_draft_cents)}.</p>
              <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-950">Pending transactions may be missing from the feed. Confirm current bank cash before submitting.{review.kind === 'repayment' && ' Interest may be deducted from your payment. Paying the displayed balance does not guarantee a zero balance.'}</p>
              <button disabled={busy || cents <= 0 || cents > review.limit_cents} onClick={() => void create()} className={primary}>{busy ? 'Saving…' : 'Continue to preparation'}</button>
            </>}
            <p className="text-xs text-slate-500">No money moves here. Required login: {review.profile_name}. Bank data read {new Date(review.observed_at).toLocaleTimeString()}.</p>
          </section>}
        </BankDialog>}
        {!!data.runs.length && <details className="mt-5 text-sm"><summary className="cursor-pointer font-semibold">Profile check history</summary>{data.runs.filter(r => r.profile_id === active.id).map(r => <p key={r.date} className="mt-2 text-slate-600">{r.date} · {r.status.replace(/_/g, ' ')}</p>)}</details>}
      </>}
    </>}
  </section>
}

function Reserve({ account, busy, save }: { account: Account; busy: boolean; save: (value: number) => Promise<void> }) {
  const [value, setValue] = useState((account.reserve_cents / 100).toFixed(2))
  let cents = -1
  try { cents = centsFromMoneyInput(value) } catch { /* invalid */ }
  return <div className="mt-2 space-y-2"><MoneyInput value={value} onChange={setValue} className="block min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3" /><button type="button" disabled={busy || cents < 0} onClick={() => void save(cents)} className={button}>Save reserve</button></div>
}
