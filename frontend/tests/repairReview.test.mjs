import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const source = readFileSync(new URL('../src/components/repairs/repairReview.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022}}).outputText
const { matchesReview, repairMoney } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)

test('unknown vendor and owner balances stay unknown while confirmed zero remains zero', () => {
  assert.equal(repairMoney(null), 'Not established')
  assert.equal(repairMoney('0.00'), '$0.00')
  assert.equal(repairMoney('238.86'), '$238.86')
})
test('invoice evidence cannot remove an unverified payment from the review queue', () => {
  const row = {issues: [], evidence: [{id: 'receipt'}], payment_status: 'unverified'}
  assert.equal(matchesReview(row, 'payment'), true)
  assert.equal(matchesReview({...row, payment_status: 'linked_activity'}, 'payment'), false)
})
test('amount conflicts and free-work treatment remain independently filterable', () => {
  assert.equal(matchesReview({issues: ['invoice_amount_difference']}, 'amount'), true)
  assert.equal(matchesReview({issues: ['conflicting_invoice_totals']}, 'amount'), true)
  assert.equal(matchesReview({issues: ['cost_or_recovery_treatment_review']}, 'treatment'), true)
  assert.equal(matchesReview({issues: ['legacy_reserve_flag_needs_funding_evidence']}, 'amount'), false)
})
test('records absent from the selected as-of report are not invented as missing documents', () => {
  assert.equal(matchesReview(undefined, 'all'), true)
  assert.equal(matchesReview(undefined, 'documents'), false)
})

test('owner confirmation answers payment questions without claiming a ledger payment', () => {
  const row = {issues: [], payment_status: 'unverified', confirmation: {status: 'paid', stale: false}}
  assert.equal(matchesReview(row, 'payment'), false)
  assert.equal(matchesReview({...row, confirmation: {...row.confirmation, stale: true}}, 'payment'), true)
  assert.equal(matchesReview({...row, confirmation: {...row.confirmation, status: 'unknown'}}, 'payment'), true)
})
