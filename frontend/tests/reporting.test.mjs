import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const source=readFileSync(new URL('../src/utils/reporting.ts',import.meta.url),'utf8')
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022}}).outputText
const {reportRemaining,reportExpenseTotal,formatReportDate}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
test('October remaining preserves allocations and does not subtract invoices or payments again',()=>{
 const truck={settlement_remainder:7478.78,net_profit:-577.98,repairs:8056.76}
 assert.equal(reportRemaining(truck)+reportRemaining({settlement_remainder:2878.68}),10357.46)
 for(const paid of [0,200,8056.76]) assert.equal(reportRemaining({...truck,paid}),7478.78)
})
test('zero and negative remaining are retained',()=>{
 assert.equal(reportRemaining({settlement_remainder:0,net_profit:900}),0)
 assert.equal(reportRemaining({settlement_remainder:-200}),-200)
})
test('expenses retain support, custom costs and credits from the authoritative settlement total',()=>{
 assert.equal(Math.round(reportExpenseTotal({expenses:44817.22,repairs:8056.76},true)*100),5287398)
 assert.equal(reportExpenseTotal({expenses:44817.22,repairs:8056.76},false),44817.22)
 assert.equal(reportExpenseTotal({total_expenses:-20},true),-20)
})
test('date-only dates retain the accounting day in western and eastern zones',()=>{
 const prior=process.env.TZ
 try { for(const zone of ['America/New_York','America/Los_Angeles','Asia/Tokyo']) {
 process.env.TZ=zone
 assert.equal(formatReportDate('2026-09-28'),new Date('2026-09-28T12:00:00Z').toLocaleDateString(undefined,{timeZone:'UTC'}))
 }} finally {process.env.TZ=prior}
})
