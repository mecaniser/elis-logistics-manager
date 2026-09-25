import assert from 'node:assert/strict'
import test from 'node:test'
import { apiError } from '../src/utils/apiError.ts'

test('preserves server error text and serializes structured validation details', () => {
  const result = apiError({ isAxiosError: true, message: 'Request failed', response: { status: 422, data: { detail: [{ msg: 'Invalid amount' }] } } })
  assert.equal(result.response.status, 422)
  assert.equal(result.response.data.detail, '[{"msg":"Invalid amount"}]')
  assert.equal(apiError({ isAxiosError: true, response: { status: 400, data: { detail: 'Already recorded' } } }).response.data.detail, 'Already recorded')
})

test('handles network failures and arbitrary thrown values without masking the error', () => {
  assert.equal(apiError(new Error('Offline')).message, 'Offline')
  assert.equal(apiError('Cancelled').message, 'Cancelled')
  assert.deepEqual(apiError(null), { message: '', response: undefined })
  assert.equal(apiError({ isAxiosError: true, message: 'Timeout' }).response, undefined)
})
