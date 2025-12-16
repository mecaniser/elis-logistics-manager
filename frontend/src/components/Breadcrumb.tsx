import { Link, useLocation, useParams } from 'react-router-dom'

interface BreadcrumbItem {
  label: string
  path: string
}

const routeLabels: Record<string, string> = {
  '/': 'Dashboard',
  '/trucks': 'Trucks',
  '/settlements': 'Settlements',
  '/repairs': 'Repairs',
  '/accounting': 'Accounting',
  '/accounting/chart-of-accounts': 'Chart of Accounts',
  '/accounting/journal-entries': 'Journal Entries',
  '/accounting/balance-sheet': 'Balance Sheet',
  '/accounting/income-statement': 'Income Statement',
  '/businesses': 'Businesses',
}

export default function Breadcrumb() {
  const location = useLocation()
  const params = useParams()
  const pathnames = location.pathname.split('/').filter((x) => x)

  const breadcrumbs: BreadcrumbItem[] = [
    { label: 'Dashboard', path: '/' },
  ]

  // Build breadcrumb items from path
  let currentPath = ''
  pathnames.forEach((pathname) => {
    // Handle dynamic routes like /vehicles/:id
    if (pathname === 'vehicles' && params.id) {
      breadcrumbs.push({
        label: 'Trucks',
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

