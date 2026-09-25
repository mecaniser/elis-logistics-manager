import { Navigate, useLocation } from 'react-router-dom'
import { ReactNode } from 'react'
import { useAuth } from '../contexts/authState'

const RequireAuth = ({ children }: { children: ReactNode }) => {
  const { authenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-600">Checking access...</p>
      </div>
    )
  }

  if (!authenticated) {
    return <Navigate to="/login" state={{ from: location, reason: 'session-required' }} replace />
  }

  return <>{children}</>
}

export default RequireAuth
