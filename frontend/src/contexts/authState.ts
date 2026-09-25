import { createContext, useContext } from 'react'

interface AuthContextType {
  authenticated: boolean
  loading: boolean
  login: (username: string, password: string, remember: boolean, mfaCode?: string) => Promise<boolean>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
