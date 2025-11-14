import { useEffect } from 'react'

interface ToastProps {
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  isVisible: boolean
  onClose: () => void
  duration?: number
}

export default function Toast({ message, type, isVisible, onClose, duration = 3000 }: ToastProps) {
  useEffect(() => {
    if (isVisible) {
      const timer = setTimeout(() => {
        onClose()
      }, duration)
      return () => clearTimeout(timer)
    }
  }, [isVisible, duration, onClose])

  if (!isVisible) return null

  const typeStyles = {
    success: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      text: 'text-green-800',
      icon: '✓',
      iconBg: 'bg-green-100',
    },
    error: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-800',
      icon: '✕',
      iconBg: 'bg-red-100',
    },
    warning: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      text: 'text-yellow-800',
      icon: '⚠',
      iconBg: 'bg-yellow-100',
    },
    info: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-800',
      icon: 'ℹ',
      iconBg: 'bg-blue-100',
    },
  }

  const styles = typeStyles[type]

  return (
    <div className="fixed top-4 right-4 z-[70] animate-slide-in">
      <div className={`${styles.bg} ${styles.border} border rounded-lg shadow-lg p-4 min-w-[300px] max-w-[500px] flex items-center gap-3`}>
        <div className={`${styles.iconBg} rounded-full p-1.5 flex-shrink-0 flex items-center justify-center w-6 h-6`}>
          <span className={`${styles.text} text-xs font-bold leading-none`}>{styles.icon}</span>
        </div>
        <div className="flex-1">
          <p className={`${styles.text} text-sm font-medium`}>{message}</p>
        </div>
        <button
          onClick={onClose}
          className={`${styles.text} hover:opacity-70 flex-shrink-0`}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  )
}

