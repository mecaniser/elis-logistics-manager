import { FormEvent, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { authApi } from '../services/api'

const field = 'w-full rounded-lg border border-slate-600 bg-slate-800 text-white px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-400'

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4">
    <div className="w-full max-w-md bg-white/10 rounded-xl p-8 shadow-xl border border-white/10 text-slate-200">
      <h1 className="text-2xl font-bold text-white text-center mb-6">{title}</h1>
      {children}
      <p className="mt-6 text-center"><Link to="/login" className="text-sm text-emerald-300 underline">Back to sign in</Link></p>
    </div>
  </div>
}

function errorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : 'The request could not be completed. Please try again.'
}

export function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [available, setAvailable] = useState<boolean | null>(null)
  const [emailHint, setEmailHint] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    authApi.capabilities().then(({ data }) => {
      setAvailable(data.password_recovery)
      setEmailHint(data.recovery_email_hint)
    }).catch(() => setAvailable(false))
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setMessage('')
    try {
      const { data } = await authApi.requestReset(email)
      setMessage(data.message)
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return <Shell title="Reset your password">
    {available === false ? <p role="status">Email recovery is not configured yet. Contact the account administrator to restore access.</p> :
      <form onSubmit={submit} autoComplete="off" className="space-y-4">
        <p>Enter the recovery email for your account. If it matches, we’ll send a link that works for 20 minutes.</p>
        {emailHint && <p className="text-sm text-slate-300">Recovery email on file: <span className="font-medium text-white">{emailHint}</span></p>}
        <div><label htmlFor="recovery-email" className="block text-sm mb-1">Recovery email</label>
          <input id="recovery-email" name="recovery-address" type="email" autoComplete="off" required value={email} onChange={(e) => setEmail(e.target.value)} className={field} /></div>
        <button disabled={busy || available === null} className="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-semibold py-2 rounded-lg disabled:opacity-60">
          {busy ? 'Sending...' : 'Send reset link'}
        </button>
      </form>}
    {message && <p role="status" className="mt-4">{message}</p>}
  </Shell>
}

export function ResetPassword() {
  const location = useLocation()
  const [token] = useState(() => new URLSearchParams(location.search).get('token') || '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [message, setMessage] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    // Remove the single-use token from the visible URL and browser history.
    if (token) window.history.replaceState(window.history.state, '', '/reset-password')
  }, [token])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (password !== confirm) { setMessage('Passwords do not match.'); return }
    setBusy(true)
    setMessage('')
    try {
      const { data } = await authApi.resetPassword(token, password)
      setMessage(data.message)
      setDone(true)
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return <Shell title="Choose a new password">
    {!token && <p role="alert">This reset link is missing its token. Request a new link.</p>}
    {token && !done && <form onSubmit={submit} className="space-y-4">
      <div><label htmlFor="new-password" className="block text-sm mb-1">New password</label>
        <input id="new-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={password} onChange={(e) => setPassword(e.target.value)} className={field} /></div>
      <div><label htmlFor="confirm-password" className="block text-sm mb-1">Confirm new password</label>
        <input id="confirm-password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required value={confirm} onChange={(e) => setConfirm(e.target.value)} className={field} /></div>
      <button disabled={busy} className="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-semibold py-2 rounded-lg disabled:opacity-60">
        {busy ? 'Updating...' : 'Update password'}
      </button>
    </form>}
    {message && <p role={done ? 'status' : 'alert'} className="mt-4">{message}</p>}
  </Shell>
}

export function VerifyRecoveryEmail() {
  const location = useLocation()
  const [token] = useState(() => new URLSearchParams(location.search).get('token') || '')
  const [message, setMessage] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (token) window.history.replaceState(window.history.state, '', '/verify-recovery-email')
  }, [token])

  const confirm = async () => {
    setBusy(true)
    setMessage('')
    try {
      const { data } = await authApi.confirmRecoveryEmail(token)
      setMessage(data.message)
      setDone(true)
    } catch (error) {
      setMessage(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return <Shell title="Confirm recovery email">
    {!token && <p role="alert">This verification link is missing its token. Request a new link from Account security.</p>}
    {token && !done && <>
      <p className="mb-5">Confirm this address as your account’s recovery email. Your current address stays active until you confirm.</p>
      <button onClick={confirm} disabled={busy} className="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-semibold py-2 rounded-lg disabled:opacity-60">
        {busy ? 'Confirming...' : 'Confirm recovery email'}
      </button>
    </>}
    {message && <p role="status">{message}</p>}
    {done && <p className="mt-4 text-center"><Link to="/account/security" className="text-sm text-emerald-300 underline">Return to Account security</Link></p>}
  </Shell>
}
