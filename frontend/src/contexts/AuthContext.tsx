import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { authApi } from '../services/api'

interface AuthContextType {
  authenticated: boolean
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

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

  const login = async (username: string, password: string) => {
    await authApi.login(username, password)
    setAuthenticated(true)
  }

  const logout = async () => {
    await authApi.logout()
    setAuthenticated(false)
  }

  return (
    <AuthContext.Provider value={{ authenticated, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
