import { useState } from 'react'
import { centsFromMoneyInput, editableMoney, formattedMoney, groupedMoneyDraft, moneyCaretPosition, plainMoney } from './moneyAmount'

export default function MoneyInput({ value, onChange, allowNegative = false, className = '', placeholder = '0.00', required = false }: {
  value: string
  onChange: (value: string) => void
  allowNegative?: boolean
  className?: string
  placeholder?: string
  required?: boolean
}) {
  const [focused, setFocused] = useState(false)
  let display = focused ? groupedMoneyDraft(value) : value
  if (!focused && value.trim()) {
    try { display = formattedMoney(centsFromMoneyInput(value, allowNegative)) }
    catch { display = value }
  }

  const restoreCaret = (input: HTMLInputElement, logicalOffset: number) => {
    window.requestAnimationFrame(() => {
      if (document.activeElement !== input) return
      const position = moneyCaretPosition(input.value, logicalOffset)
      input.setSelectionRange(position, position)
    })
  }

  return <span className="relative mt-2 block">
    {(!value || focused) && <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500">$</span>}
    <input
      type="text"
      inputMode="decimal"
      required={required}
      placeholder={placeholder}
      value={display}
      onFocus={event => {
        const input = event.currentTarget
        const logicalOffset = input.value.slice(0, input.selectionStart ?? input.value.length).replace(/[$,]/g, '').length
        setFocused(true)
        restoreCaret(input, logicalOffset)
      }}
      onChange={event => {
        const input = event.currentTarget
        const logicalOffset = input.value.slice(0, input.selectionStart ?? input.value.length).replace(/[$,]/g, '').length
        const pasted = (event.nativeEvent as InputEvent).inputType === 'insertFromPaste'
        onChange(editableMoney(input.value, pasted))
        restoreCaret(input, logicalOffset)
      }}
      onBlur={() => {
        if (value.trim()) {
          try { onChange(plainMoney(centsFromMoneyInput(value, allowNegative))) }
          catch { /* Keep invalid input visible for correction. */ }
        }
        setFocused(false)
      }}
      className={`${className} ${!value || focused ? 'pl-7' : ''}`}
    />
  </span>
}
