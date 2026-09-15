import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

export type BankSelectOption = { value: string; label: string }

export default function BankSelect({ value, options, onChange, ariaLabel, required = false }: {
  value: string
  options: BankSelectOption[]
  onChange: (value: string) => void
  ariaLabel: string
  required?: boolean
}) {
  const [open, setOpen] = useState(false)
  const selectedIndex = Math.max(0, options.findIndex(option => option.value === value))
  const [highlighted, setHighlighted] = useState(selectedIndex)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [open])

  const choose = (index: number) => {
    const option = options[index]
    if (!option) return
    onChange(option.value)
    setHighlighted(index)
    setOpen(false)
  }

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && open) { event.preventDefault(); event.stopPropagation(); setOpen(false); return }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      if (!open) { setOpen(true); setHighlighted(selectedIndex); return }
      setHighlighted(current => (current + direction + options.length) % options.length)
      return
    }
    if ((event.key === 'Enter' || event.key === ' ') && open) {
      event.preventDefault(); choose(highlighted)
    }
  }

  const selected = options[selectedIndex] || options[0]
  return <div ref={root} className="relative mt-1 min-w-0" onKeyDown={onKeyDown}>
    <button
      type="button"
      aria-label={`${ariaLabel}: ${selected?.label || 'Select'}`}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-required={required}
      onClick={() => { setHighlighted(selectedIndex); setOpen(current => !current) }}
      className={`flex min-h-11 w-full min-w-0 items-center justify-between gap-3 rounded-lg border bg-white py-2 pl-3 pr-3 text-left text-sm text-slate-900 outline-none transition-[border-color,box-shadow,transform] duration-150 active:scale-[0.99] focus-visible:border-blue-500 focus-visible:ring-4 focus-visible:ring-blue-100 ${open ? 'border-blue-600 ring-4 ring-blue-100' : 'border-slate-300 hover:border-slate-400'}`}
    >
      <span className={`min-w-0 truncate ${value ? '' : 'text-slate-500'}`}>{selected?.label || 'Select'}</span>
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-150 motion-reduce:transition-none ${open ? 'rotate-180' : ''}`}><path d="m7 9 5 5 5-5" /></svg>
    </button>
    {open && <div role="listbox" aria-label={ariaLabel} className="absolute inset-x-0 top-full z-50 mt-1 max-h-64 overflow-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-[0_16px_40px_-12px_rgba(15,23,42,0.35)]">
      {options.map((option, index) => <button
        type="button"
        role="option"
        aria-selected={option.value === value}
        key={option.value || '__empty'}
        onPointerMove={() => setHighlighted(index)}
        onClick={() => choose(index)}
        className={`flex min-h-10 w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-left text-sm outline-none ${highlighted === index ? 'bg-blue-50 text-blue-950' : 'text-slate-700 hover:bg-slate-50'} ${option.value === value ? 'font-semibold' : ''}`}
      >
        <span className="min-w-0 truncate">{option.label}</span>
        {option.value === value && <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-4 w-4 shrink-0 text-blue-700"><path d="m5 12 4 4L19 6" /></svg>}
      </button>)}
    </div>}
  </div>
}
