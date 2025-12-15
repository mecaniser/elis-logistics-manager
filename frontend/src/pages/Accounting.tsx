import { Link } from 'react-router-dom'

const accountingLinks = [
  { 
    path: '/accounting/chart-of-accounts', 
    label: 'Chart of Accounts',
    description: 'View and manage your chart of accounts',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )
  },
  { 
    path: '/accounting/journal-entries', 
    label: 'Journal Entries',
    description: 'Create and manage journal entries',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )
  },
  { 
    path: '/accounting/balance-sheet', 
    label: 'Balance Sheet',
    description: 'View your balance sheet',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    )
  },
  { 
    path: '/accounting/income-statement', 
    label: 'Income Statement',
    description: 'View your income statement',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    )
  },
]

export default function Accounting() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Accounting</h1>
        <p className="mt-2 text-sm text-gray-600">Manage your accounting and financial records</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {accountingLinks.map((link) => (
          <Link
            key={link.path}
            to={link.path}
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-blue-300 transition-all duration-200 group"
          >
            <div className="flex items-start space-x-4">
              <div className="flex-shrink-0 text-blue-600 group-hover:text-blue-700">
                {link.icon}
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 group-hover:text-blue-600">
                  {link.label}
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                  {link.description}
                </p>
              </div>
              <div className="flex-shrink-0">
                <svg className="w-5 h-5 text-gray-400 group-hover:text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  )
}

