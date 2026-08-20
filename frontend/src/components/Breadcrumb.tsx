import { Link, useLocation, useParams } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'

interface BreadcrumbItem {
  label: string
  path: string
}

const routeLabels: Record<string, string> = {
  '/': 'Dashboard',
  '/trucks': 'Vehicles',
  '/settlements': 'Settlements',
  '/repairs': 'Maintenance & Repairs',
  '/accounting': 'Accounting',
  '/accounting/chart-of-accounts': 'Chart of Accounts',
  '/accounting/journal-entries': 'Journal Entries',
  '/accounting/balance-sheet': 'Balance Sheet',
  '/accounting/income-statement': 'Income Statement',
  '/businesses': 'Businesses',
}

const accountingLinks = [
  { path: '/accounting/income-statement', label: 'Income Statement' },
  { path: '/accounting/balance-sheet', label: 'Balance Sheet' },
  { path: '/accounting/journal-entries', label: 'Journal Entries' },
  { path: '/accounting/general-ledger', label: 'General Ledger' },
  { path: '/accounting/tax-year-summary', label: 'Tax Year Summary' },
  { path: '/accounting/schedule-c', label: 'Schedule C Report' },
  { path: '/accounting/chart-of-accounts', label: 'Chart of Accounts' },
]

export default function Breadcrumb() {
  const location = useLocation()
  const params = useParams()
  const pathnames = location.pathname.split('/').filter((x) => x)
  const [showAccountingMenu, setShowAccountingMenu] = useState(false)
  const accountingMenuRef = useRef<HTMLDivElement>(null)

  // Close accounting menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (accountingMenuRef.current && !accountingMenuRef.current.contains(event.target as Node)) {
        setShowAccountingMenu(false)
      }
    }

    if (showAccountingMenu) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showAccountingMenu])

  const breadcrumbs: BreadcrumbItem[] = [
    { label: 'Dashboard', path: '/' },
  ]

  // Build breadcrumb items from path
  let currentPath = ''
  pathnames.forEach((pathname) => {
    // Handle dynamic routes like /vehicles/:id
    if (pathname === 'vehicles' && params.id) {
          breadcrumbs.push({
            label: 'Vehicles',
            path: '/trucks',
          })
      currentPath += `/${pathname}/${params.id}`
      breadcrumbs.push({
        label: `Vehicle Details`,
        path: currentPath,
      })
      return
    }
    
    currentPath += `/${pathname}`
    const label = routeLabels[currentPath] || pathname.charAt(0).toUpperCase() + pathname.slice(1).replace(/-/g, ' ')
    
    breadcrumbs.push({
      label,
      path: currentPath,
    })
  })

  // Don't show breadcrumb on dashboard
  if (location.pathname === '/') {
    return null
  }

  return (
    <nav className="flex mb-4" aria-label="Breadcrumb">
      <ol className="flex items-center space-x-2 text-sm">
        {breadcrumbs.map((crumb, index) => {
          const isLast = index === breadcrumbs.length - 1
          
          return (
            <li key={crumb.path} className="flex items-center">
              {index > 0 && (
                <svg
                  className="w-4 h-4 text-gray-400 mx-2"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                    clipRule="evenodd"
                  />
                </svg>
              )}
              {isLast ? (
                <span className="text-gray-900 font-medium">{crumb.label}</span>
              ) : crumb.path === '/accounting' ? (
                <div 
                  className="relative"
                  ref={accountingMenuRef}
                  onMouseEnter={() => setShowAccountingMenu(true)}
                  onMouseLeave={() => setShowAccountingMenu(false)}
                >
                  <Link
                    to={crumb.path}
                    className="text-gray-500 hover:text-gray-700 transition-colors inline-flex items-center"
                  >
                    {crumb.label}
                    <svg className="ml-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </Link>
                  {showAccountingMenu && (
                    <div className="absolute left-0 top-full pt-1 w-56 z-50">
                      <div className="rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5">
                        <div className="py-1">
                          <Link
                            to="/accounting"
                            onClick={() => setShowAccountingMenu(false)}
                            className={`block px-4 py-2 text-sm ${
                              location.pathname === '/accounting'
                                ? 'bg-blue-50 text-blue-700 font-medium'
                                : 'text-gray-700 hover:bg-gray-100'
                            }`}
                          >
                            Overview
                          </Link>
                          {accountingLinks.map((link) => (
                            <Link
                              key={link.path}
                              to={link.path}
                              onClick={() => setShowAccountingMenu(false)}
                              className={`block px-4 py-2 text-sm ${
                                location.pathname === link.path
                                  ? 'bg-blue-50 text-blue-700 font-medium'
                                  : 'text-gray-700 hover:bg-gray-100'
                              }`}
                            >
                              {link.label}
                            </Link>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <Link
                  to={crumb.path}
                  className="text-gray-500 hover:text-gray-700 transition-colors"
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

