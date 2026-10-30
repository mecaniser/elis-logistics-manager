import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const transpile = path => ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
const dataUrl = text => `data:text/javascript;base64,${Buffer.from(text).toString('base64')}`
const core = dataUrl(transpile('../src/components/repairs/dieselBridgeFinancial.ts'))
const js = transpile('../src/components/repairs/dieselBridgeSettlement.ts').replace(/from ['"]\.\/dieselBridgeFinancial['"]/, `from ${JSON.stringify(core)}`)
const { sourceReceiptAmount, sourceAppliedFees, actualSourcePaidDate, eligibleSourceReceipts, sourceAttemptKey, sourceSettlementNeedsReview } = await import(dataUrl(js))

const attempt = (changes = {}) => ({ attempt_id: 'source-cash', revision: 'a'.repeat(64), rail: 'cash', state: 'confirmed', principal_amount: '4886.38', received_amount: '4886.38', gross_received_amount: '4886.38', applied_principal_amount: '4886.38', applied_card_fee_amount: '0.00', applied_card_fee_tax_amount: '0.00', unapplied_amount: '0.00', confirmed_at: '2026-09-10T23:45:00Z', actual_paid_date: null, paid_date_basis: 'unknown', ...changes })
const state = (changes = {}) => ({ state: 'active', source_invoice_total: '5057.40', booked_cost: '4886.38', recorded_balance_due: '4886.38', payments: [], source_claims: [], source_payment_review_required: false, source_settlement: { settlement_id: 'settlement-17', revision: 'b'.repeat(64), status: 'available', review_reasons: [], principal_total: '4886.38', max_card_fee: '167.38', max_card_fee_tax: '3.64', confirmed_principal: '4886.38', pending_principal: '0.00', unapplied_credit: '0.00', refund_pending: '0.00', payments: [attempt()] }, ...changes })

test('cash settlement selects4886.38 actual principal without copying5057.40 quote or quoted card fees', () => {
  const facts = state()
  assert.equal(sourceReceiptAmount(attempt()), '4886.38')
  assert.deepEqual(eligibleSourceReceipts(facts), [attempt()])
  assert.equal(facts.source_invoice_total, '5057.40')
  assert.equal(facts.booked_cost, '4886.38')
  assert.equal(facts.source_settlement.max_card_fee, '167.38')
})

test('card receipt uses actual gross, received principal alone cannot hide actual fee and fee tax', () => {
  const card = attempt({ rail: 'card', principal_amount: '100.00', received_amount: '100.00', gross_received_amount: '103.08', applied_principal_amount: '100.00', applied_card_fee_amount: '3.00', applied_card_fee_tax_amount: '0.08' })
  assert.equal(sourceReceiptAmount(card), '103.08')
  assert.equal(sourceReceiptAmount({ ...card, gross_received_amount: '100.00' }), null)
  assert.equal(sourceReceiptAmount({ ...card, gross_received_amount: null }), null)
})

test('source confirmation timestamp never substitutes for an unknown actual payment date', () => {
  assert.equal(actualSourcePaidDate(attempt()), '')
  assert.equal(actualSourcePaidDate(attempt({ actual_paid_date: '2026-09-09', paid_date_basis: 'unknown' })), '')
  assert.equal(actualSourcePaidDate(attempt({ actual_paid_date: '2026-09-09', paid_date_basis: 'explicit_verified_date' })), '2026-09-09')
  assert.equal(actualSourcePaidDate(attempt({ actual_paid_date: '2026-02-30', paid_date_basis: 'explicit_verified_date' })), '')
})

test('only full confirmed receipts are eligible; pending, unapplied, ambiguous fees and mismatched totals are blocked', () => {
  for (const stage of ['pending', 'failed', 'expired', 'refunded', 'reversed']) assert.equal(sourceReceiptAmount(attempt({ state: stage })), null)
  for (const changes of [{ unapplied_amount: '0.01' }, { gross_received_amount: '4886.39' }, { applied_card_fee_amount: '1.00', gross_received_amount: '4887.38' }, { applied_principal_amount: '1e3' }, { gross_received_amount: 'NaN' }]) assert.equal(sourceReceiptAmount(attempt(changes)), null)
})

test('active claims cannot be linked a second time and source/payment review preserves the existing ledger', () => {
  assert.deepEqual(eligibleSourceReceipts(state({ source_claims: [{ source_attempt_id: 'source-cash', payment_id: 9, reversed: false }] })), [])
  assert.equal(eligibleSourceReceipts(state({ source_claims: [{ source_attempt_id: 'source-cash', payment_id: 9, reversed: true }] })).length, 1)
  assert.deepEqual(eligibleSourceReceipts(state({ payments: [{ source_attempt_id: 'source-cash', reversed: false }] })), [])
  assert.deepEqual(eligibleSourceReceipts(state({ recorded_balance_due: '4000.00' })), [])
  for (const changes of [{ state: 'review_required' }, { source_payment_review_required: true }, { source_settlement: { ...state().source_settlement, status: 'review_required' } }, { source_settlement: { ...state().source_settlement, refund_pending: '1.00' } }, { source_settlement: { ...state().source_settlement, unapplied_credit: '1.00' } }]) assert.deepEqual(eligibleSourceReceipts(state(changes)), [])
  assert.equal(sourceSettlementNeedsReview(state({ source_payment_review_required: true })), true)
})

test('attempt selection identifies the exact revision so changed source evidence cannot retain an old selection', () => {
  assert.notEqual(sourceAttemptKey(attempt()), sourceAttemptKey(attempt({ revision: 'c'.repeat(64) })))
  assert.notEqual(sourceAttemptKey(attempt()), sourceAttemptKey(attempt({ attempt_id: 'other-cash' })))
})


test('actual fee summary uses confirmed applied fees, preserving full principal and ignoring maximum or pending fees', () => {
  const settlement = state().source_settlement
  assert.deepEqual(sourceAppliedFees(settlement), { fee: '0.00', feeTax: '0.00' })
  const card = attempt({ rail: 'card', applied_card_fee_amount: '3.00', applied_card_fee_tax_amount: '0.08' })
  assert.deepEqual(sourceAppliedFees({ ...settlement, payments: [attempt(), card, { ...card, state: 'pending', applied_card_fee_amount: '100.00' }] }), { fee: '3.00', feeTax: '0.08' })
  assert.equal(sourceAppliedFees({ ...settlement, payments: [{ ...card, applied_card_fee_amount: 'bad' }] }), null)
})
