import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ReactNode, useState } from 'react'
import { useTenant } from '../contexts/TenantContext'
import Breadcrumb from './Breadcrumb'
import BusinessSwitcher from './BusinessSwitcher'
import AccountMenu from './AccountMenu'
import BusinessInfoDrawer from './BusinessInfoDrawer'
import Toast from './Toast'
import { useAuth } from '../contexts/AuthContext'
import { Tenant } from '../services/api'
import { getNavLinks, isRouteAvailable, sectionLabel } from '../utils/navigation'
import { businessTypeLabel } from '../utils/tenantAppearance'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showBusinessInfo, setShowBusinessInfo] = useState(false)
  const [toast, setToast] = useState<{ message: string; isVisible: boolean }>({
    message: '',
    isVisible: false,
  })
  const { currentTenant, tenants, setCurrentTenant, loading } = useTenant()
  const { logout } = useAuth()

  const navLinks = getNavLinks(currentTenant?.business_type)

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)

  /**
   * Switching is a state change, not a page load. The data pages already
   * depend on `currentTenant?.id`, so they refetch on their own and the
   * user's filters and date range survive the switch.
   */
  const handleSelectBusiness = (tenant: Tenant) => {
    setCurrentTenant(tenant)
    setMobileMenuOpen(false)

    // Never strand the user on a section the new business type does not have.
    if (!isRouteAvailable(location.pathname, tenant.business_type)) {
      const section = sectionLabel(location.pathname)
      const type = businessTypeLabel(tenant.business_type).toLowerCase()
      navigate('/')
      setToast({
        message: `Switched to ${tenant.name}. ${section} isn't available for ${type} businesses.`,
        isVisible: true,
      })
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar: app identity + business switcher on the left, account on the right */}
      <div className="bg-gray-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between gap-2 sm:gap-4 min-h-[3.5rem] py-2">
            <div className="flex items-center gap-2 sm:gap-4 min-w-0">
              {/* Mobile nav toggle lives up here so the bar below can disappear */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                aria-expanded={mobileMenuOpen}
                aria-controls="mobile-nav"
                aria-label="Main menu"
                className="sm:hidden inline-flex items-center justify-center h-11 w-11 -ml-2 rounded-md text-gray-200 hover:text-white hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-white flex-shrink-0"
              >
                {mobileMenuOpen ? (
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                )}
              </button>

              {/* The switcher carries identity on mobile, so the wordmark steps aside */}
              <h1 className="hidden lg:block text-lg font-bold whitespace-nowrap flex-shrink-0">
                Elis Group Manager
              </h1>

              {!loading && currentTenant && (
                <BusinessSwitcher
                  currentTenant={currentTenant}
                  tenants={tenants}
                  onSelect={handleSelectBusiness}
                  onOpenDetails={() => setShowBusinessInfo(true)}
                />
              )}
            </div>

            <AccountMenu
              onLogout={async () => {
                await logout()
                navigate('/login')
              }}
            />
          </div>
        </div>
      </div>

      {/* Desktop navigation */}
      <nav className="bg-white shadow-sm border-b hidden sm:block">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 space-x-8">
            {navLinks.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                className={`inline-flex items-center px-1 border-b-2 text-sm font-medium ${
                  isActive(link.path)
                    ? 'border-blue-500 text-gray-900'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </nav>

      {/* Mobile navigation */}
      {mobileMenuOpen && (
        <nav id="mobile-nav" className="sm:hidden bg-white shadow-sm border-b">
          <div className="py-2">
            {navLinks.map((link) => (
              <Link
                key={link.path}
                to={link.path}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center min-h-[44px] pl-3 pr-4 py-2 border-l-4 text-base font-medium ${
                  isActive(link.path)
                    ? 'bg-blue-50 border-blue-500 text-blue-700'
                    : 'border-transparent text-gray-600 hover:bg-gray-50 hover:border-gray-300 hover:text-gray-800'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </nav>
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
        <Breadcrumb />
        {children}
      </main>

      <BusinessInfoDrawer
        isOpen={showBusinessInfo}
        onClose={() => setShowBusinessInfo(false)}
        tenant={currentTenant}
      />

      <Toast
        message={toast.message}
        type="info"
        isVisible={toast.isVisible}
        duration={5000}
        onClose={() => setToast({ ...toast, isVisible: false })}
      />
    </div>
  )
}
