import { useEffect, useRef, useState } from 'react'
import { BankNumberField as NumberField, tenantsApi } from '../services/api'
import { copyText } from '../utils/copyText'

interface Props {
  tenantId: number
  accountIndex: number
  field: NumberField
  label: string
  maskedValue: string
  onCopied: (label: string, ok: boolean) => void
}

export default function BankNumberField({ tenantId, accountIndex, field, label, maskedValue, onCopied }: Props) {
  const [revealed, setRevealed] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const pending = useRef<AbortController | null>(null)

  useEffect(() => () => pending.current?.abort(), [])

  const access = async (action: 'show' | 'copy') => {
    if (pending.current) return
    const controller = new AbortController()
    pending.current = controller
    setBusy(true)
    setError(false)
    const value = tenantsApi.getBankNumber(tenantId, accountIndex, field, action, controller.signal)
      .then((response) => {
        controller.signal.throwIfAborted()
        return response.data.value
      })
    try {
      if (action === 'copy') {
        // Copy does not retain the number in component or tenant state.
        const ok = await copyText(value)
        if (!controller.signal.aborted) onCopied(label, ok)
      } else {
        const number = await value
        if (!controller.signal.aborted) setRevealed(number)
      }
    } catch {
      if (!controller.signal.aborted) setError(true)
    } finally {
      if (!controller.signal.aborted) {
        pending.current = null
        setBusy(false)
      }
    }
  }

  return (
    <div className="py-2.5 border-b border-gray-100 last:border-b-0">
      <dt className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">{label}</dt>
      <dd className="mt-0.5 flex items-start gap-2">
        {maskedValue ? <>
          <span className="flex-1 text-sm text-gray-900 break-all font-mono">{revealed ?? maskedValue}</span>
          <button type="button" disabled={busy} aria-label={`${revealed === null ? 'Show' : 'Hide'} ${label}`}
            onClick={() => revealed === null ? void access('show') : setRevealed(null)}
            className="flex-shrink-0 whitespace-nowrap text-xs font-medium text-gray-500 hover:text-gray-700 px-1.5 py-1 rounded hover:bg-gray-100 disabled:opacity-50">
            {revealed === null ? 'Show' : 'Hide'}
          </button>
          <button type="button" disabled={busy} aria-label={`Copy ${label}`} onClick={() => void access('copy')}
            className="flex-shrink-0 whitespace-nowrap text-xs font-medium px-1.5 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50 disabled:opacity-50">
            Copy
          </button>
        </> : <span className="text-sm text-gray-500 italic">Not set</span>}
      </dd>
      {busy && <p role="status" className="text-xs text-gray-500 mt-1">Loading…</p>}
      {error && <p role="alert" className="text-xs text-red-700 mt-1">Could not access this number. Try again.</p>}
    </div>
  )
}
