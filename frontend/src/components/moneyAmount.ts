export const centsFromMoneyInput = (value: string, allowNegative = false): number => {
  const typed = value.trim().replace(/^(-?)\$/, '$1').replace(/^\$(-?)/, '$1')
  const pattern = allowNegative ? /^-?(?:(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{0,2})?|\.\d{1,2})$/ : /^(?:(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{0,2})?|\.\d{1,2})$/
  if (!pattern.test(typed)) throw new Error('Enter an amount in dollars with no more than two decimal places.')
  const plain = typed.replace(/,/g, '')
  const negative = plain.startsWith('-')
  const [whole = '0', fraction = ''] = plain.replace('-', '').split('.')
  const cents = Number(whole || '0') * 100 + Number(fraction.padEnd(2, '0'))
  if (!Number.isSafeInteger(cents)) throw new Error('The dollar amount is too large.')
  return negative ? -cents : cents
}

export const editableMoney = (value: string, preserveBadGrouping = false) => {
  const typed = value.replace(/^(-?)\$/, '$1').replace(/^\$(-?)/, '$1').replace(/\s/g, '')
  if (preserveBadGrouping && typed.includes(',') && !/^-?\d{1,3}(?:,\d{3})+(?:\.\d*)?$/.test(typed)) return typed
  return typed.replace(/,/g, '')
}

export const groupedMoneyDraft = (value: string) => {
  if (!/^-?\d*(?:\.\d*)?$/.test(value)) return value
  const negative = value.startsWith('-')
  const unsigned = negative ? value.slice(1) : value
  const dot = unsigned.indexOf('.')
  const whole = dot < 0 ? unsigned : unsigned.slice(0, dot)
  const fractional = dot < 0 ? '' : unsigned.slice(dot)
  return `${negative ? '-' : ''}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fractional}`
}

export const moneyCaretPosition = (display: string, logicalOffset: number) => {
  if (logicalOffset <= 0) return 0
  let count = 0
  for (let index = 0; index < display.length; index += 1) {
    if (display[index] !== ',' && display[index] !== '$') count += 1
    if (count === logicalOffset) return index + 1
  }
  return display.length
}

export const plainMoney = (cents: number) => `${cents < 0 ? '-' : ''}${Math.trunc(Math.abs(cents) / 100)}.${String(Math.abs(cents) % 100).padStart(2, '0')}`
export const formattedMoney = (cents: number) => `${cents < 0 ? '-$' : '$'}${Math.trunc(Math.abs(cents) / 100).toLocaleString('en-US')}.${String(Math.abs(cents) % 100).padStart(2, '0')}`

export const incomeExceedsCash = (income: string, cash: string) => {
  try { return centsFromMoneyInput(income) > centsFromMoneyInput(cash) }
  catch { return false }
}
