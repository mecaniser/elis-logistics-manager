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

export const editableMoney = (value: string) => {
  const typed = value.replace(/^(-?)\$/, '$1').replace(/^\$(-?)/, '$1')
  return /^-?\d{1,3}(?:,\d{3})+(?:\.\d{0,2})?$/.test(typed) ? typed.replace(/,/g, '') : typed
}

export const plainMoney = (cents: number) => `${cents < 0 ? '-' : ''}${Math.trunc(Math.abs(cents) / 100)}.${String(Math.abs(cents) % 100).padStart(2, '0')}`
export const formattedMoney = (cents: number) => `${cents < 0 ? '-$' : '$'}${Math.trunc(Math.abs(cents) / 100).toLocaleString('en-US')}.${String(Math.abs(cents) % 100).padStart(2, '0')}`
