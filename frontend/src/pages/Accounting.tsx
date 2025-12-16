import { Link } from 'react-router-dom'

const accountingLinks = [
  { 
    path: '/accounting/chart-of-accounts', 
    label: 'Chart of Accounts',
    description: 'View and manage your chart of accounts',
    info: 'A complete list of all accounts (Assets, Liabilities, Equity, Revenue, Expenses) used to categorize financial transactions. Think of it as a filing system for your money.',
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
    info: 'Records of every financial transaction using double-entry bookkeeping. Each entry has debits and credits that must balance. Automatically created from settlements and repairs, or manually entered.',
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
    info: 'A snapshot of your business\'s financial position at a specific date. Shows what you own (Assets), what you owe (Liabilities), and your ownership stake (Equity). Always balances: Assets = Liabilities + Equity.',
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
    info: 'Shows your business\'s financial performance over a period (month, quarter, or year). Displays Revenue (money in), Expenses (money out), and Net Income (profit or loss). Essential for tracking profitability.',
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
          <div
            key={link.path}
            className="bg-white rounded-lg shadow-sm border border-gray-200 hover:shadow-md hover:border-blue-300 transition-all duration-200"
          >
            <Link
              to={link.path}
              className="block p-6 group"
            >
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0 text-blue-600 group-hover:text-blue-700">
                  {link.icon}
                </div>
                <div className="flex-1 min-w-0">
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
            <div className="border-t border-gray-100 px-6 py-4">
              <p className="text-xs text-gray-600 leading-relaxed">
                {link.info}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

