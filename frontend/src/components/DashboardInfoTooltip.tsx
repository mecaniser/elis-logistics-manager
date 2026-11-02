import { useCallback, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

/** Small report explanations available to pointer, keyboard and touch users. */
export default function DashboardInfoTooltip({ label, children }: { label: string; children: React.ReactNode }) {
  const id = useId()
  const button = useRef<HTMLButtonElement>(null)
  const popup = useRef<HTMLDivElement>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()
  const pinned = useRef(false)
  const focused = useRef(false)
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null)
  const cancelClose = useCallback(() => clearTimeout(timer.current), [])
  const dismiss = useCallback(() => { cancelClose(); pinned.current = false; setOpen(false); setPosition(null) }, [cancelClose])
  const leave = () => {
    cancelClose()
    timer.current = setTimeout(() => { if (!pinned.current && !focused.current) { setOpen(false); setPosition(null) } }, 150)
  }

  useLayoutEffect(() => {
    if (!open) return
    const place = () => {
      if (!button.current || !popup.current) return
      const anchor = button.current.getBoundingClientRect()
      const box = popup.current.getBoundingClientRect()
      setPosition({
        left: Math.max(12, Math.min(anchor.left, document.documentElement.clientWidth - box.width - 12)),
        top: anchor.bottom + box.height + 8 < window.innerHeight ? anchor.bottom + 8 : Math.max(12, anchor.top - box.height - 8),
      })
    }
    const outside = (event: PointerEvent) => {
      if (!button.current?.contains(event.target as Node) && !popup.current?.contains(event.target as Node)) dismiss()
    }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.preventDefault(); dismiss() } }
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      cancelClose()
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open, cancelClose, dismiss])

  return <>
    <button ref={button} type="button" aria-label={`About ${label}`} aria-expanded={open}
      aria-describedby={open ? id : undefined} aria-controls={open ? id : undefined}
      className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
      onPointerEnter={event => { if (event.pointerType === 'mouse') { cancelClose(); setOpen(true) } }}
      onPointerLeave={leave}
      onFocus={() => { focused.current = true; cancelClose(); setOpen(true) }}
      onBlur={() => { focused.current = false; dismiss() }}
      onClick={() => { pinned.current = !pinned.current; setOpen(pinned.current); if (!pinned.current) setPosition(null) }}>
      <svg aria-hidden="true" width="15" height="15" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.5"/><path d="M10 9v5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><circle cx="10" cy="6" r="1" fill="currentColor"/></svg>
    </button>
    {open && createPortal(<div ref={popup} id={id} role="tooltip"
      onPointerEnter={cancelClose} onPointerLeave={leave}
      className="fixed z-50 rounded-lg border border-slate-200 bg-white p-3 text-left text-sm font-normal leading-5 text-slate-700 shadow-lg"
      style={{ width: 'min(18rem, calc(100vw - 24px))', left: position?.left ?? 0, top: position?.top ?? 0, visibility: position ? 'visible' : 'hidden' }}>
      {children}
    </div>, document.body)}
  </>
}
