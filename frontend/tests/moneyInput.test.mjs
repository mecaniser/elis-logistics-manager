import assert from 'node:assert/strict'
import test from 'node:test'
import { centsFromMoneyInput, editableMoney, formattedMoney, groupedMoneyDraft, incomeExceedsCash, moneyCaretPosition, plainMoney } from '../src/components/moneyAmount.ts'

test('formats and parses whole, fractional, and grouped dollar amounts exactly', () => {
  assert.equal(centsFromMoneyInput('1180'), 118000)
  assert.equal(centsFromMoneyInput('$1,180.40'), 118040)
  assert.equal(editableMoney('$1,180.40'), '1180.40')
  assert.equal(centsFromMoneyInput('.05'), 5)
  assert.equal(formattedMoney(118040), '$1,180.40')
  assert.equal(plainMoney(118040), '1180.40')
})

test('groups digits as they are typed while keeping the caret by numeric position', () => {
  assert.equal(groupedMoneyDraft('1234'), '1,234')
  assert.equal(groupedMoneyDraft('1234.'), '1,234.')
  assert.equal(groupedMoneyDraft('1234.5'), '1,234.5')
  assert.equal(groupedMoneyDraft('-1234.5'), '-1,234.5')
  assert.equal(moneyCaretPosition('1,234.5', 2), 3)
  assert.equal(moneyCaretPosition('1,234.5', 6), 7)
  assert.equal(editableMoney('1,24'), '124')
  assert.equal(editableMoney('1,24', true), '1,24')
})

test('supports negative posted balances without allowing negative repayments', () => {
  assert.equal(centsFromMoneyInput('-$1,180.40', true), -118040)
  assert.equal(formattedMoney(-118040), '-$1,180.40')
  assert.equal(plainMoney(-5), '-0.05')
  assert.throws(() => centsFromMoneyInput('-1.00'))
})

test('rejects excess precision and nonnumeric values', () => {
  for (const value of ['1.234', '1.2.3', '1,23', '', '$', 'abc', '90071992547409.92']) {
    assert.throws(() => centsFromMoneyInput(value), value)
  }
})

test('incoming reimbursement cannot exceed cash available after pending debits', () => {
  assert.equal(incomeExceedsCash('1180.23', '1180.22'), true)
  assert.equal(incomeExceedsCash('1180.22', '1180.22'), false)
  assert.equal(incomeExceedsCash('0', '0'), false)
  assert.equal(incomeExceedsCash('', '1180.22'), false)
})
