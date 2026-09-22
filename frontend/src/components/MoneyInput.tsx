import { useState } from 'react'
import { centsFromMoneyInput, editableMoney, formattedMoney, plainMoney } from './moneyAmount'

export default function MoneyInput({ value, onChange, allowNegative = false, className = '', placeholder = '0.00', required = false }: {
  value: string
  onChange: (value: string) => void
  allowNegative?: boolean
  className?: string
  placeholder?: string
  required?: boolean
}) {
  const [focused, setFocused] = useState(false)
  let display = value
  if (!focused && value.trim()) {
    try { display = formattedMoney(centsFromMoneyInput(value, allowNegative)) }
    catch { display = value }
  }

  return <span className="relative mt-2 block">
    {(!value || focused) && <span aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-500">$</span>}
    <input
      type="text"
      inputMode="decimal"
      required={required}
      placeholder={placeholder}
      value={display}
      onFocus={() => setFocused(true)}
      onChange={event => onChange(editableMoney(event.target.value))}
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
