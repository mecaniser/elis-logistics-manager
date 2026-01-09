import { Navigate, useLocation } from 'react-router-dom'
import { ReactNode } from 'react'
import { useAuth } from '../contexts/AuthContext'

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
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

export default RequireAuth
