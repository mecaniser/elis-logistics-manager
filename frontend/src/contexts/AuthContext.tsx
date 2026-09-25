import { AuthContext } from './authState'
import { useEffect, useState, ReactNode } from 'react'
import { authApi } from '../services/api'


export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [authenticated, setAuthenticated] = useState(false)
  const [loading, setLoading] = useState(true)

  const checkAuth = async () => {
    try {
      await authApi.me()
      setAuthenticated(true)
    } catch {
      setAuthenticated(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    checkAuth()
  }, [])

  const login = async (username: string, password: string, remember: boolean, mfaCode?: string) => {
    const response = await authApi.login(username, password, remember, mfaCode)
    if (response.data.mfa_required) return false
    setAuthenticated(true)
    return true
  }

  const logout = async () => {
    await authApi.logout()
    // The server remains authoritative: a local preview without configured
    // authentication must not strand the user on an unusable login form.
    await checkAuth()
  }

  return (
    <AuthContext.Provider value={{ authenticated, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
