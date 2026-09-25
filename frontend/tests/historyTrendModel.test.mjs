import test from 'node:test'
import assert from 'node:assert/strict'
import { trendSegments, monthBuckets } from '../src/components/finance/historyTrendModel.ts'

const settlement = (asset_id, date, status = 'arithmetic_matched') => ({asset_id,date,status,remainder:'1000.00',rolling_fuel_per_mile:'0.850',driver_percent:'30.0'})

test('different truck statement days do not break either series; unavailable originals and long gaps do', () => {
  const range={start:'2026-04-01',end:'2026-07-31'}
  const rows=[settlement(1,'2026-04-06'),settlement(2,'2026-04-04'),settlement(1,'2026-04-13'),settlement(2,'2026-04-11'),
    settlement(1,'2026-04-20','missing_source'),settlement(1,'2026-04-27'),settlement(1,'2026-05-04'),settlement(2,'2026-06-23')]
  assert.deepEqual(trendSegments(rows,range,'remainder').map(({assetId,dates})=>[assetId,dates]), [
    [1,['2026-04-06','2026-04-13']],[1,['2026-04-27','2026-05-04']],[2,['2026-04-04','2026-04-11']],[2,['2026-06-23']]
  ])
})

test('monthly coverage keeps saved records visible without inventing plotted amounts', () => {
  const range={start:'2026-01-01',end:'2026-03-31'}
  const rows=[settlement(2,'2026-01-10','missing_source'),settlement(2,'2026-02-07','needs_review'),settlement(2,'2026-03-07')]
  assert.deepEqual(monthBuckets(rows,range,2),[
    {month:'2026-01',matched:0,needsReview:0,missingOriginal:1},
    {month:'2026-02',matched:0,needsReview:1,missingOriginal:0},
    {month:'2026-03',matched:1,needsReview:0,missingOriginal:0}
  ])
})
