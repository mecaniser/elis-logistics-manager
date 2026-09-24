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
  const [recoveryEmail, setRecoveryEmail] = useState<string | null>(null)
  const [pendingEmailHint, setPendingEmailHint] = useState<string | null>(null)
  const [newRecoveryEmail, setNewRecoveryEmail] = useState('')
  const [recoveryPassword, setRecoveryPassword] = useState('')
  const [recoveryMessage, setRecoveryMessage] = useState('')
  const [recoveryBusy, setRecoveryBusy] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordMessage, setPasswordMessage] = useState('')
  const [passwordBusy, setPasswordBusy] = useState(false)

  useEffect(() => {
    authApi.mfaStatus().then(({ data }) => setEnabled(data.enabled)).catch((error) => setMessage(detail(error)))
    authApi.recoveryEmail().then(({ data }) => {
      setRecoveryEmail(data.email)
      setPendingEmailHint(data.pending_email_hint)
    }).catch((error) => setRecoveryMessage(detail(error)))
  }, [])

  const changePassword = async (event: FormEvent) => {
    event.preventDefault()
    if (newPassword !== confirmPassword) { setPasswordMessage('New passwords do not match.'); return }
    setPasswordBusy(true); setPasswordMessage('')
    try {
      const { data } = await authApi.changePassword(currentPassword, newPassword)
      setPasswordMessage(data.message)
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('')
    } catch (error) { setPasswordMessage(detail(error)) }
    finally { setPasswordBusy(false) }
  }

  const changeRecoveryEmail = async (event: FormEvent) => {
    event.preventDefault()
    setRecoveryBusy(true); setRecoveryMessage('')
    try {
      const { data } = await authApi.requestRecoveryEmailChange(recoveryPassword, newRecoveryEmail)
      setRecoveryMessage(data.message)
      setRecoveryPassword(''); setNewRecoveryEmail('')
      const status = await authApi.recoveryEmail()
      setPendingEmailHint(status.data.pending_email_hint)
    } catch (error) { setRecoveryMessage(detail(error)) }
    finally { setRecoveryBusy(false) }
  }

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
      <p className="mt-2 text-gray-600">Manage your password, recovery email, and authenticator.</p></header>
    <form onSubmit={changePassword} className="space-y-3 rounded-lg border bg-white p-5">
      <h3 className="font-semibold">Change password</h3>
      <p className="text-sm text-gray-600">Use at least 12 characters. Changing your password signs out other sessions.</p>
      <label htmlFor="current-account-password" className="block text-sm font-medium">Current password</label>
      <input id="current-account-password" className={inputClass} type="password" autoComplete="current-password" required value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} />
      <label htmlFor="new-account-password" className="block text-sm font-medium">New password</label>
      <input id="new-account-password" className={inputClass} type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
      <label htmlFor="confirm-account-password" className="block text-sm font-medium">Confirm new password</label>
      <input id="confirm-account-password" className={inputClass} type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
      <div><button disabled={passwordBusy} className="rounded-lg bg-emerald-600 text-white px-4 py-2 disabled:opacity-60">{passwordBusy ? 'Updating...' : 'Change password'}</button></div>
      {passwordMessage && <p role="status" className="text-sm">{passwordMessage}</p>}
    </form>
    <form onSubmit={changeRecoveryEmail} className="space-y-3 rounded-lg border bg-white p-5">
      <h3 className="font-semibold">Recovery email</h3>
      <p className="text-sm text-gray-600">Current address: <span className="font-medium text-gray-900">{recoveryEmail ?? 'Loading...'}</span></p>
      {pendingEmailHint && <p className="text-sm text-amber-800">Waiting for confirmation from {pendingEmailHint}. The current address still works.</p>}
      <p className="text-sm text-gray-600">We’ll send a verification link to the new address before using it for password resets.</p>
      <label htmlFor="new-recovery-email" className="block text-sm font-medium">New recovery email</label>
      <input id="new-recovery-email" className={inputClass} type="email" autoComplete="email" required value={newRecoveryEmail} onChange={(e) => setNewRecoveryEmail(e.target.value)} />
      <label htmlFor="recovery-current-password" className="block text-sm font-medium">Current password</label>
      <input id="recovery-current-password" className={inputClass} type="password" autoComplete="current-password" required value={recoveryPassword} onChange={(e) => setRecoveryPassword(e.target.value)} />
      <div><button disabled={recoveryBusy || recoveryEmail === null} className="rounded-lg bg-emerald-600 text-white px-4 py-2 disabled:opacity-60">{recoveryBusy ? 'Sending...' : 'Verify new email'}</button></div>
      {recoveryMessage && <p role="status" className="text-sm">{recoveryMessage}</p>}
    </form>
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
