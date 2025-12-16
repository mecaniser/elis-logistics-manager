import { useState } from 'react'

interface InfoPanelProps {
  title: string
  content: React.ReactNode
  defaultExpanded?: boolean
}

export default function InfoPanel({ title, content, defaultExpanded = false }: InfoPanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)

  return (
    <div className="bg-blue-50 border border-blue-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-blue-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-blue-600"
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
          <span className="font-semibold text-blue-900">{title}</span>
        </div>
        <svg
          className={`w-5 h-5 text-blue-600 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isExpanded && (
        <div className="px-4 py-3 text-sm text-blue-800 border-t border-blue-200">
          {content}
        </div>
      )}
    </div>
  )
}

