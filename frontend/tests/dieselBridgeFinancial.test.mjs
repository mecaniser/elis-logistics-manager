import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
async function load(path) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}
const { moneyCents, validPaymentAmount, canonicalPaymentAmount, paymentSummary, paymentTransactions, previewCounts, financialReviewMessage, sourceReviewAllowsApply } = await load('../src/components/repairs/dieselBridgeFinancial.ts')

test('accepted whole and single-decimal payment inputs serialize as exact API cents', () => {
  assert.equal(canonicalPaymentAmount('200'), '200.00')
  assert.equal(canonicalPaymentAmount('200.5'), '200.50')
  assert.equal(canonicalPaymentAmount('000200.05'), '200.05')
  assert.equal(canonicalPaymentAmount('0.01'), '0.01')
  for (const value of ['0', '-1', '0.001', '1e2', 'NaN', '9007199254740991']) assert.equal(canonicalPaymentAmount(value), null)
})
const { matchesReview, repairMethod, repairDocumentType, eligibleBatchRepairs } = await load('../src/components/repairs/repairReview.ts')

test('payment amounts retain cents and reject overpayment, rounding and ambiguous formats', () => {
  assert.equal(moneyCents('134.60'), 13460)
  assert.equal(moneyCents('200'), 20000)
  assert.equal(moneyCents('0.01'), 1)
  assert.equal(validPaymentAmount('200.00', '1000.00'), true)
  assert.equal(validPaymentAmount('1000', '1000.00'), true)
  for (const value of ['0', '-1', '200.001', '1e2', '1,000.00', 'NaN', 'Infinity', '9007199254740991']) assert.equal(validPaymentAmount(value, '1000.00'), false)
  assert.equal(validPaymentAmount('1000.01', '1000.00'), false)
})

test('a source paid status never replaces unconfirmed EDG payment history', () => {
  const state = { payment_status: 'unconfirmed', recorded_paid_amount: '0.00', recorded_balance_due: '1000.00', source_status: 'paid' }
  assert.match(paymentSummary(state), /has not been confirmed/)
  assert.match(paymentSummary(state), /does not establish a payment/)
  assert.match(paymentSummary({ ...state, payment_status: 'partial', recorded_paid_amount: '200.00', recorded_balance_due: '800.00' }), /Partly paid/)
})

test('payment choices only offer unmatched outgoing transactions for the selected funding type', () => {
  const workspace = { accounts: [{ id: 'bank', name: 'Checking', account_type: 'bank' }, { id: 'card', name: 'Card', account_type: 'card' }, { id: 'cash', name: 'Cashbook', account_type: 'cash' }], transactions: [
    { id: 'bank-out', account_id: 'bank', amount: '-200.00', matched: false },
    { id: 'bank-in', account_id: 'bank', amount: '200.00', matched: false },
    { id: 'bank-matched', account_id: 'bank', amount: '-100.00', matched: true },
    { id: 'card-out', account_id: 'card', amount: '-50.00', matched: false },
    { id: 'cash-out', account_id: 'cash', amount: '-20.00', matched: false },
    { id: 'unknown', account_id: 'other-business', amount: '-20.00', matched: false },
  ] }
  assert.deepEqual(paymentTransactions(workspace, 'business').map(t => t.id), ['bank-out'])
  assert.deepEqual(paymentTransactions(workspace, 'card').map(t => t.id), ['card-out'])
  assert.deepEqual(paymentTransactions(workspace, 'cash').map(t => t.id), ['cash-out'])
})

test('preview counts do not invent amounts for unauthorized historical invoices', () => {
  const rows = [...Array(7)].map((_, i) => ({ repair_order_id: `ready-${i}`, action: 'create', invoice_total: '100.00', blockers: [] })).concat([...Array(8)].map((_, i) => ({ repair_order_id: `held-${i}`, action: 'blocked', invoice_total: null, blockers: ['attribution_required'] })))
  assert.deepEqual(previewCounts({ rows }), { create: 7, unchanged: 0, review_required: 0, blocked: 8 })
  assert.equal(rows.filter(r => r.invoice_total === null).length, 8)
  assert.match(financialReviewMessage('attribution_required'), /approved before this invoice can be imported/)
})

test('changed and cancelled invoice messages preserve accepted costs for review', () => {
  assert.match(financialReviewMessage('invoice_changed'), /accepted cost is preserved/)
  assert.match(financialReviewMessage('invoice_cancelled'), /Review its existing expense and payments/)
  assert.match(financialReviewMessage('source_access_removed'), /preserved for review/)
})

test('normal invoice review filters use canonical financial state instead of stale legacy answers', () => {
  const row = { issues: [], payment_status: 'linked_activity', confirmation: { status: 'paid', stale: false }, evidence: [], dieselbridge_financial: { state: 'active', payment_status: 'unconfirmed', payments: [] } }
  assert.equal(matchesReview(row, 'payment'), true)
  assert.equal(repairMethod(row), 'unknown')
  assert.equal(repairDocumentType(row), 'DBN finalized invoice')
  row.dieselbridge_financial = { state: 'review_required', payment_status: 'partial', payments: [{ payer: 'card', reversed: false }] }
  assert.equal(matchesReview(row, 'treatment'), true)
  assert.equal(matchesReview(row, 'payment'), false)
  assert.equal(repairMethod(row), 'credit_card')
})


test('legacy matching batch confirmation cannot record payments on managed DBN invoices', () => {
  const legacy = { legacy_id: 1, batch_eligible: true }
  const managed = { legacy_id: 2, batch_eligible: true, dieselbridge_financial: { payment_status: 'unconfirmed' } }
  const notReady = { legacy_id: 3, batch_eligible: false }
  assert.deepEqual(eligibleBatchRepairs([legacy, managed, notReady]).map(row => row.legacy_id), [1])
})


test('financial source corrections require no active paid amount; status-only restoration preserves payments', () => {
  const proposal = { action: 'replace_unpaid_invoice', can_apply: true, recorded_paid_amount: '0.00' }
  assert.equal(sourceReviewAllowsApply(proposal), true)
  assert.equal(sourceReviewAllowsApply({ ...proposal, recorded_paid_amount: '200.00' }), false)
  assert.equal(sourceReviewAllowsApply({ ...proposal, can_apply: false }), false)
  assert.equal(sourceReviewAllowsApply({ ...proposal, action: 'unrecognized_change' }), false)
  assert.equal(sourceReviewAllowsApply({ ...proposal, action: 'no_change', recorded_paid_amount: '200.00' }), true)
  assert.match(financialReviewMessage('PAYMENT_CORRECTION_REQUIRED'), /payment or refund corrections/)
})
