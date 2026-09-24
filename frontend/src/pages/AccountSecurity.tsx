import { FormEvent, useEffect, useState } from 'react'
import { authApi } from '../services/api'

const inputClass = 'w-full max-w-md rounded-lg border border-gray-300 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500'

function detail(error: unknown): string {
  const value = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return typeof value === 'string' ? value : 'Could not complete the request. Try again.'
}

export default function AccountSecurity() {
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [password, setPassword] = useState('')
  const [secret, setSecret] = useState('')
  const [uri, setUri] = useState('')
  const [code, setCode] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    authApi.mfaStatus().then(({ data }) => setEnabled(data.enabled)).catch((error) => setMessage(detail(error)))
  }, [])

  const begin = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true); setMessage('')
    try {
      const { data } = await authApi.mfaSetup(password)
      setSecret(data.secret)
      setUri(data.uri)
      setPassword('')
    } catch (error) { setMessage(detail(error)) }
    finally { setBusy(false) }
  }

  const confirm = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true); setMessage('')
    try {
      const { data } = await authApi.mfaConfirm(code)
      setRecoveryCodes(data.recovery_codes)
      setEnabled(true)
      setSecret(''); setUri(''); setCode('')
      setMessage('Authenticator enabled. Save your recovery codes now; they will not be shown again.')
    } catch (error) { setMessage(detail(error)) }
    finally { setBusy(false) }
  }

  return <section className="max-w-2xl space-y-6">
    <header><h2 className="text-2xl font-bold text-gray-900">Account security</h2>
      <p className="mt-2 text-gray-600">Add an authenticator app to protect sign in.</p></header>
    {message && <p role="status" className="rounded-lg bg-blue-50 border border-blue-200 px-4 py-3">{message}</p>}
    {enabled === true && recoveryCodes.length === 0 && <p className="rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3">Authenticator is enabled. Sign in with a six-digit code or one of your saved recovery codes.</p>}
    {recoveryCodes.length > 0 && <div className="rounded-lg bg-amber-50 border border-amber-300 p-4">
      <h3 className="font-semibold">Save these one-time recovery codes</h3>
      <p className="mt-1 text-sm">Store them somewhere private. Each code works once if you lose your authenticator.</p>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4 font-mono text-sm">{recoveryCodes.map((item) => <li key={item}>{item}</li>)}</ul>
      <button type="button" onClick={() => setRecoveryCodes([])} className="mt-4 text-sm underline">I have saved these codes</button>
    </div>}
    {enabled === false && !secret && <form onSubmit={begin} className="space-y-3 rounded-lg border bg-white p-5">
      <h3 className="font-semibold">Set up an authenticator</h3>
      <p className="text-sm text-gray-600">Confirm your current password to begin.</p>
      <label htmlFor="security-password" className="block text-sm font-medium">Current password</label>
      <input id="security-password" className={inputClass} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      <div><button disabled={busy} className="rounded-lg bg-emerald-600 text-white px-4 py-2 disabled:opacity-60">Continue</button></div>
    </form>}
    {secret && <form onSubmit={confirm} className="space-y-3 rounded-lg border bg-white p-5">
      <h3 className="font-semibold">Add Elis Group Hub to your authenticator app</h3>
      <p className="text-sm">Enter this setup key in your authenticator app, then enter its six-digit code below.</p>
      <code className="block rounded bg-gray-100 p-3 break-all select-all">{secret}</code>
      <a href={uri} className="text-sm text-blue-700 underline">Open in authenticator app</a>
      <label htmlFor="security-code" className="block text-sm font-medium">Six-digit code</label>
      <input id="security-code" className={inputClass} inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value)} />
      <div><button disabled={busy} className="rounded-lg bg-emerald-600 text-white px-4 py-2 disabled:opacity-60">Enable authenticator</button></div>
    </form>}
  </section>
}
