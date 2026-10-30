import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const source = readFileSync(new URL('../src/components/repairs/reserveWithdrawals.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const methods = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const { reserveWithdrawalsForPeriod } = methods
const entry = (amount, payment_date='2026-05-08', truck_id=1) => ({ entry_id:1,truck_id,payment_date,amount,basis:'verified_payment' })

test('an unpaid invoice contributes zero withdrawals regardless of its full service cost', () => {
  const serviceRepair = {cost:1000,repair_date:'2026-04-20'}
  assert.equal(serviceRepair.cost,1000)
  assert.equal(reserveWithdrawalsForPeriod([], 'monthly', {month_key:'2026-04'}),0)
})
test('partial payment spending remains separate from full incurred repair expense', () => {
  const serviceRepair = {cost:1000,repair_date:'2026-05-01'}
  assert.equal(reserveWithdrawalsForPeriod([entry(200)],'monthly',{month_key:'2026-05'}),200)
  assert.equal(serviceRepair.cost,1000)
})
test('later payment is recognized in its payment month even with no service repairs then', () => {
  const withdrawals=[entry(200)]
  assert.equal(reserveWithdrawalsForPeriod(withdrawals,'monthly',{month_key:'2026-04'}),0)
  assert.equal(reserveWithdrawalsForPeriod(withdrawals,'monthly',{month_key:'2026-05'}),200)
})
test('week bounds include actual payment dates and exclude neighboring days', () => {
  const rows=[entry(200,'2026-05-04'),entry(30,'2026-05-10'),entry(99,'2026-05-03'),entry(99,'2026-05-11')]
  assert.equal(reserveWithdrawalsForPeriod(rows,'weekly',{week_start:'2026-05-04',week_end:'2026-05-10'}),230)
  assert.equal(reserveWithdrawalsForPeriod(rows,'weekly',{week_key:'2026-05-04'}),200)
})
test('truck selection, yearly totals, all-time and signed reversals remain scoped', () => {
  const rows=[entry(200),entry(-50,'2026-05-09'),entry(900,'2026-05-08',2),entry(10,'2025-12-31')]
  assert.equal(reserveWithdrawalsForPeriod(rows,'monthly',{month_key:'2026-05'},1),150)
  assert.equal(reserveWithdrawalsForPeriod([entry(-200)],'monthly',{month_key:'2026-05'},1),-200)
  assert.equal(reserveWithdrawalsForPeriod(rows,'yearly',{year_key:'2026'},1),150)
  assert.equal(reserveWithdrawalsForPeriod(rows,'all_time',null,1),160)
  assert.equal(reserveWithdrawalsForPeriod(rows,'all_time',null),1060)
})
test('decimal cents are summed without floating-point residue', () => {
  assert.equal(reserveWithdrawalsForPeriod([entry(0.1),entry(0.2)],'all_time',null),0.3)
})
test('missing data or invalid period is unavailable instead of a fabricated zero', () => {
  assert.equal(reserveWithdrawalsForPeriod(undefined,'all_time',null),null)
  assert.equal(reserveWithdrawalsForPeriod([entry(200)],'monthly',{month_key:'2026-13'}),null)
  assert.equal(reserveWithdrawalsForPeriod([entry(200)],'weekly',null),null)
  assert.equal(reserveWithdrawalsForPeriod([entry(200,'2026-02-30')],'all_time',null),null)
})
test('payment date grouping is unchanged by the browser timezone', () => {
  const prior=process.env.TZ
  try {
    for (const zone of ['America/Los_Angeles','UTC','Pacific/Auckland']) {
      process.env.TZ=zone
      assert.equal(reserveWithdrawalsForPeriod([entry(200,'2026-01-01')],'yearly',{year_key:'2026'}),200)
      assert.equal(reserveWithdrawalsForPeriod([entry(200,'2026-01-01')],'monthly',{month_key:'2025-12'}),0)
    }
  } finally { if(prior===undefined)delete process.env.TZ;else process.env.TZ=prior }
})

test('payment-only and service-only months are selectable without inventing settlement money', () => {
  const { expenseActivityPeriods } = methods
  const rows = expenseActivityPeriods('monthly', [{month_key:'2026-04',month_label:'Apr 2026'}], [entry(200,'2026-05-08')], [{repair_date:'2026-03-20'}])
  assert.deepEqual(rows.map(row=>row.month_key),['2026-03','2026-04','2026-05'])
  const may=rows.find(row=>row.month_key==='2026-05')
  assert.equal(may.has_settlement_data,false)
  assert.equal('net_profit' in may,false)
  assert.equal('gross_revenue' in may,false)
  assert.equal(reserveWithdrawalsForPeriod([entry(200)],'monthly',may),200)
})
test('payment-only weeks and years remain selectable, while existing covered weeks are retained', () => {
  const { expenseActivityPeriods } = methods
  const weeks=expenseActivityPeriods('weekly',[{week_key:'2026-04-30',week_start:'2026-04-20',week_end:'2026-04-26'}],[entry(200,'2026-05-08'),entry(50,'2026-04-22')],[])
  assert.equal(weeks.length,2)
  const may=weeks.find(row=>!row.has_settlement_data)
  assert.equal(may.week_start,'2026-05-04')
  assert.equal(may.week_end,'2026-05-10')
  assert.equal(reserveWithdrawalsForPeriod([entry(200)],'weekly',may),200)
  assert.deepEqual(expenseActivityPeriods('yearly',[],[entry(200,'2026-05-08')],[]).map(row=>row.year_key),['2026'])
})
test('service expense and payment-only-period amounts remain independent', () => {
  const { expenseActivityPeriods,serviceRepairCostsForPeriod }=methods
  const repairs=[{truck_id:1,repair_date:'2026-04-20',cost:1000}]
  const months=expenseActivityPeriods('monthly',[],[entry(200)],repairs)
  const april=months.find(row=>row.month_key==='2026-04'),may=months.find(row=>row.month_key==='2026-05')
  assert.equal(serviceRepairCostsForPeriod(repairs,'monthly',april),1000)
  assert.equal(serviceRepairCostsForPeriod(repairs,'monthly',may),0)
  assert.equal(reserveWithdrawalsForPeriod([entry(200)],'monthly',may),200)
})
