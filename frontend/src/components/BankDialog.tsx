import { type ReactNode, useEffect, useId, useRef } from 'react'

import { lockPageScroll } from './lockPageScroll'

/** Native modal keeps keyboard focus inside and restores focus to its opener. */
export default function BankDialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const label = useId()
  useEffect(() => {
    const element = dialog.current!
    const opener = document.activeElement as HTMLElement | null
    element.showModal()
    const unlockScroll = lockPageScroll()
    return () => { element.close(); unlockScroll(); opener?.focus({ preventScroll: true }) }
  }, [])
  return <dialog ref={dialog} aria-labelledby={label} onCancel={onClose} className="m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-2xl overflow-y-auto overscroll-contain rounded-2xl bg-white p-0 text-slate-900 shadow-xl backdrop:bg-slate-950/50">
    <header className="sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-slate-200 bg-white p-5"><h2 id={label} className="text-xl font-semibold">{title}</h2><button type="button" aria-label="Close account panel" onClick={onClose} className="min-h-11 min-w-11 rounded-lg text-xl hover:bg-slate-100">×</button></header>
    <div className="space-y-5 p-5">{children}</div>
  </dialog>
}
