import { useState } from 'react'

interface AccountingTooltipProps {
  term: string
  description: string
  children: React.ReactNode
}

export default function AccountingTooltip({ term, description, children }: AccountingTooltipProps) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div className="relative inline-flex items-center group">
      {children}
      <button
        type="button"
        className="ml-1.5 text-gray-400 hover:text-gray-600 focus:outline-none"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={() => setShowTooltip(!showTooltip)}
        aria-label={`Learn about ${term}`}
      >
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </button>
      {showTooltip && (
        <div className="absolute z-50 w-64 p-3 mb-2 text-xs text-gray-700 bg-white border border-gray-200 rounded-lg shadow-lg left-0 bottom-full">
          <div className="font-semibold text-gray-900 mb-1">{term}</div>
          <div className="text-gray-600">{description}</div>
        </div>
      )}
    </div>
  )
}

