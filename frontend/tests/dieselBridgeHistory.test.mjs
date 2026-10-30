import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const source = readFileSync(new URL('../src/components/repairs/dieselBridgeHistory.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
const { historyDate, historyTitle, historyReviewMessage, sortHistory } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)

test('service dates remain the same calendar day in different browser timezones', () => {
  const prior = process.env.TZ
  try {
    for (const timezone of ['America/Los_Angeles', 'UTC', 'Pacific/Auckland']) {
      process.env.TZ = timezone
      assert.equal(historyDate('2026-10-08'), '10/08/2026')
      assert.equal(historyDate('2026-10-01'), '10/01/2026')
    }
  } finally {
    if (prior === undefined) delete process.env.TZ
    else process.env.TZ = prior
  }
})

test('unavailable source rows display only their retained order reference', () => {
  assert.equal(historyTitle({ repair_order_id: 'source-ro-42', service: null, order_number: 'cached old title' }), 'Repair order source-ro-42')
})

test('history ordering uses the service date rather than a newer invoice date and preserves input', () => {
  const rows = [
    { id: 1, repair_order_id: 'older', service: { order_number: 'RO-55', service_date: '2026-10-08', invoice_date: '2026-10-19' } },
    { id: 2, repair_order_id: 'newer', service: { order_number: 'RO-58', service_date: '2026-10-19', invoice_date: '2026-10-19' } },
    { id: 3, repair_order_id: 'removed', service: null },
  ]
  assert.deepEqual(sortHistory(rows).map(row => row.id), [2, 1, 3])
  assert.deepEqual(rows.map(row => row.id), [1, 2, 3])
})

test('changed truck identities remain a review action instead of showing an automatic reassignment', () => {
  assert.match(historyReviewMessage('truck_identity_changed'), /Review the existing truck assignment/)
  assert.match(historyReviewMessage('duplicate_vin'), /More than one EDG truck/)
})
