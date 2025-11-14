import { ReactNode, useEffect } from 'react'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title: string
  children: ReactNode
  type?: 'success' | 'error' | 'warning' | 'info'
}

export default function Modal({ isOpen, onClose, title, children, type = 'info' }: ModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }

    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [isOpen])

  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleEscape)
    }

    return () => {
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen, onClose])

  if (!isOpen) return null

  const typeStyles = {
    success: {
      icon: '✓',
      iconBg: 'bg-green-100',
      iconText: 'text-green-600',
      titleText: 'text-green-900',
      border: 'border-green-200',
    },
    error: {
      icon: '✕',
      iconBg: 'bg-red-100',
      iconText: 'text-red-600',
      titleText: 'text-red-900',
      border: 'border-red-200',
    },
    warning: {
      icon: '⚠',
      iconBg: 'bg-yellow-100',
      iconText: 'text-yellow-600',
      titleText: 'text-yellow-900',
      border: 'border-yellow-200',
    },
    info: {
      icon: 'ℹ',
      iconBg: 'bg-blue-100',
      iconText: 'text-blue-600',
      titleText: 'text-blue-900',
      border: 'border-blue-200',
    },
  }

  const styles = typeStyles[type]

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div
        className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
        onClick={onClose}
      />
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className={`relative transform overflow-hidden rounded-lg bg-white shadow-xl transition-all w-full max-w-md mx-4 ${styles.border} border-2`}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 border-b border-gray-200">
            <div className="flex items-center space-x-2 sm:space-x-3 min-w-0 flex-1">
              <div className={`flex h-8 w-8 sm:h-10 sm:w-10 items-center justify-center rounded-full flex-shrink-0 ${styles.iconBg}`}>
                <span className={`text-lg sm:text-xl font-bold ${styles.iconText}`}>{styles.icon}</span>
              </div>
              <h3 className={`text-base sm:text-lg font-semibold ${styles.titleText} truncate`}>{title}</h3>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 focus:outline-none"
            >
              <span className="sr-only">Close</span>
              <svg
                className="h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
          <div className="px-4 sm:px-6 py-3 sm:py-4">
            <div className="text-sm text-gray-700 break-words">{children}</div>
          </div>
          <div className="bg-gray-50 px-4 sm:px-6 py-3 sm:py-4 border-t border-gray-200">
            <button
              onClick={onClose}
              className={`w-full rounded-md px-4 py-2.5 text-sm font-medium text-white ${
                type === 'error'
                  ? 'bg-red-600 hover:bg-red-700'
                  : type === 'warning'
                  ? 'bg-yellow-600 hover:bg-yellow-700'
                  : type === 'success'
                  ? 'bg-green-600 hover:bg-green-700'
                  : 'bg-blue-600 hover:bg-blue-700'
              } focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                type === 'error'
                  ? 'focus:ring-red-500'
                  : type === 'warning'
                  ? 'focus:ring-yellow-500'
                  : type === 'success'
                  ? 'focus:ring-green-500'
                  : 'focus:ring-blue-500'
              }`}
            >
              OK
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
