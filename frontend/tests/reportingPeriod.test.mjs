import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const js=ts.transpileModule(readFileSync(new URL('../src/components/finance/reportingPeriod.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {reportingRange,validRange}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
test('current periods remain to-date, previous week is complete Monday to Sunday',()=>{
 const d=new Date(2026,8,28,12)
 assert.deepEqual(reportingRange('week',d),{start:'2026-09-28',end:'2026-09-28'})
 assert.deepEqual(reportingRange('previous-week',d),{start:'2026-09-21',end:'2026-09-27'})
 assert.deepEqual(reportingRange('month',d),{start:'2026-09-01',end:'2026-09-28'})
 assert.deepEqual(reportingRange('previous-month',d),{start:'2026-08-01',end:'2026-08-31'})
})
test('year and quarter rollover and leap month are calendar-safe',()=>{
 const d=new Date(2026,0,5,12)
 assert.deepEqual(reportingRange('previous-year',d),{start:'2025-01-01',end:'2025-12-31'})
 assert.deepEqual(reportingRange('previous-quarter',d),{start:'2025-10-01',end:'2025-12-31'})
 assert.deepEqual(reportingRange('previous-month',new Date(2024,2,31,12)),{start:'2024-02-01',end:'2024-02-29'})
 assert.deepEqual(reportingRange('previous-week',new Date(2026,0,1,12)),{start:'2025-12-22',end:'2025-12-28'})
})
test('rolling dates include today and work across DST',()=>{
 assert.deepEqual(reportingRange('30-days',new Date(2026,2,15,12)),{start:'2026-02-14',end:'2026-03-15'})
 assert.deepEqual(reportingRange('90-days',new Date(2026,0,1,12)),{start:'2025-10-04',end:'2026-01-01'})
})
test('invalid and reversed ranges are blocked; single days are allowed',()=>{
 assert.equal(validRange('2026-02-30','2026-03-01'),false)
 assert.equal(validRange('','2026-03-01'),false)
 assert.equal(validRange('2026-04-02','2026-04-01'),false)
 assert.equal(validRange('2024-02-29','2024-02-29'),true)
})
