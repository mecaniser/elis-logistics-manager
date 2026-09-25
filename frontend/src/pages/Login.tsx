import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const safeReturnPath = (value: string | null | undefined) => value?.startsWith('/') && !value.startsWith('//') ? value : '/'

const Login = () => {
  const { authenticated, login, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(false)
  const [mfaRequired, setMfaRequired] = useState(false)
  const [mfaCode, setMfaCode] = useState('')
  const [capsLock, setCapsLock] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const loginState = location.state as { from?: { pathname?: string }; reason?: string } | null
  const statePath = loginState?.from?.pathname
  const query = new URLSearchParams(location.search)
  const returnPath = safeReturnPath(statePath || query.get('from'))
  const sessionRecovery = loginState?.reason === 'session-required' || query.get('reason') === 'session-expired'
  const returnLabel = returnPath === '/bank-monitor' ? 'Bank Monitor' : 'the requested page'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const complete = await login(username, password, remember, mfaRequired ? mfaCode : undefined)
      if (complete) navigate(returnPath, { replace: true })
      else setMfaRequired(true)
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Unable to sign in. Check your connection and try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return null
  }

  // Local development can deliberately run with backend authentication
  // disabled.  When the auth check succeeds in that mode, do not leave the
  // user on a login form that cannot submit credentials.
  if (authenticated) {
    return <Navigate to={returnPath} replace />
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white/10 backdrop-blur rounded-xl p-8 shadow-xl border border-white/10">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-white">Elis Group Hub</h1>
          <p className="text-slate-300 mt-2">{sessionRecovery ? `Your ELIS session is no longer active. Sign in to return to ${returnLabel}.` : 'Sign in to continue'}</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-username" className="block text-sm text-slate-200 mb-1">Username</label>
            <input
              id="login-username"
              type="text"
              value={username}
              onChange={(e) => { setUsername(e.target.value); setMfaRequired(false); setMfaCode('') }}
              className="w-full rounded-lg border border-slate-600 bg-slate-800 text-white px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-400"
              autoComplete="username"
              required
            />
          </div>
          <div>
            <label htmlFor="login-password" className="block text-sm text-slate-200 mb-1">Password</label>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => { setPassword(e.target.value); setMfaRequired(false); setMfaCode('') }}
                onKeyDown={(e) => setCapsLock(e.getModifierState('CapsLock'))}
                onKeyUp={(e) => setCapsLock(e.getModifierState('CapsLock'))}
                onBlur={() => setCapsLock(false)}
                className="w-full rounded-lg border border-slate-600 bg-slate-800 text-white px-3 py-2 pr-16 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                autoComplete="current-password"
                required
              />
              {password && (
                <button
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded px-1 text-sm font-semibold text-white mix-blend-difference transition opacity-85 hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              )}
            </div>
            {capsLock && <p className="mt-1 text-sm text-amber-200" role="status">Caps Lock is on</p>}
          </div>
          {mfaRequired && (
            <div>
              <label htmlFor="login-mfa" className="block text-sm text-slate-200 mb-1">Authenticator or recovery code</label>
              <input id="login-mfa" value={mfaCode} onChange={(e) => setMfaCode(e.target.value.trim())}
                autoComplete="one-time-code" autoFocus required
                className="w-full rounded-lg border border-slate-600 bg-slate-800 text-white px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-400" />
            </div>
          )}
          <label className="flex items-center gap-2 text-sm text-slate-200">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)}
              className="h-4 w-4 accent-emerald-500" />
            Keep me signed in for up to 7 days on this device
          </label>
          {error && (
            <div role="alert" className="text-sm text-red-300 bg-red-900/40 border border-red-700 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-900 font-semibold py-2 rounded-lg transition disabled:opacity-60"
          >
            {submitting ? 'Signing in...' : mfaRequired ? 'Verify and sign in' : 'Sign In'}
          </button>
          <div className="text-center">
            <Link to="/forgot-password" className="text-sm text-emerald-300 underline underline-offset-2 hover:text-emerald-200">Forgot password?</Link>
          </div>
        </form>
      </div>
    </div>
  )
}

export default Login
