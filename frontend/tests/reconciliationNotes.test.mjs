import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const source = readFileSync(new URL('../src/components/repairs/reconciliationNotes.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText
const { emptyReconciliationDraft, reconciliationInput, mergeReconciliationNotes, nextReconciliationCursor } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)

test('confirmed job reconciliation preserves references, independent date decisions and unexplained amount difference', () => {
  assert.deepEqual(reconciliationInput({ ...emptyReconciliationDraft(), note: ' Owner confirms one job. ', references: ' DBN invoice000021\nETSINV-1183\n ', serviceDate: '2026-07-13', invoiceDate: '2026-08-04', discrepancy: ' DBN1072.05 vs ETS1089.21;17.16 unresolved. ' }), {
    note: 'Owner confirms one job.', source_references: ['DBN invoice000021', 'ETSINV-1183'], confirmed_service_date: '2026-07-13', original_invoice_date: '2026-08-04', amount_discrepancy: 'DBN1072.05 vs ETS1089.21;17.16 unresolved.',
  })
})

test('informational notes never emit payment, cost, author or repair-date mutations', () => {
  const input = reconciliationInput({ ...emptyReconciliationDraft(), note: 'Cash statement not yet verified.' })
  assert.deepEqual(Object.keys(input).sort(), ['note', 'source_references'])
  assert.equal(reconciliationInput(emptyReconciliationDraft()), null)
})

test('bounded input refuses invalid dates, oversized references and unsafe correction identifiers', () => {
  const valid = { ...emptyReconciliationDraft(), note: 'Review' }
  for (const changes of [ { note: '  x ' }, { note: 'x'.repeat(4001) }, { references: Array(11).fill('reference').join('\n') }, { references: 'x'.repeat(301) }, { discrepancy: 'x'.repeat(1001) }, { serviceDate: '2026-02-30' }, { invoiceDate: '2026-2-1' }, { supersedes: '-1' }, { supersedes: '1.5' }, { supersedes: '9007199254740992' } ]) assert.equal(reconciliationInput({ ...valid, ...changes }), null)
  assert.equal(reconciliationInput({ ...valid, serviceDate: '2024-02-29', supersedes: '12' }).supersedes_note_id, 12)
})

const note = (id, changes = {}) => ({ id, note: `Original${id}`, source_references: [], confirmed_service_date: null, original_invoice_date: null, amount_discrepancy: null, supersedes_note_id: null, created_at: '2026-10-30T12:00:00Z', author: 'owner', repair_order_id: 'ro-21', ...changes })
test('sync refresh and correction append retain immutable originals with source-RO isolation', () => {
  const original = note(1)
  const correction = note(2, { note: 'Corrected date decision', supersedes_note_id: 1 })
  assert.deepEqual(mergeReconciliationNotes('ro-21', [correction, original], [note(1, { note: 'Overwrite attempt' }), note(3, { repair_order_id: 'another-ro' })]), [original, correction])
  assert.deepEqual(mergeReconciliationNotes('ro-21', [original], []), [original])
})

test('complete history pagination fails closed on repeated, backward and malformed cursors', () => {
  assert.equal(nextReconciliationCursor(0, 100, new Set()), 100)
  assert.equal(nextReconciliationCursor(100, null, new Set([100])), null)
  for (const next of [100, 99, 0, -1, '101', 100.5]) assert.throws(() => nextReconciliationCursor(100, next, new Set([100])))
  assert.throws(() => nextReconciliationCursor(100, 200, new Set([200])))
})
