import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const source=readFileSync(new URL('../src/utils/latestReportPeriod.ts',import.meta.url),'utf8')
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022}}).outputText
const {resolveReportPeriod:resolve,recordedReportPeriods:recorded}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const old={week_key:'2026-10-20',week_end:'2026-10-25',has_settlement_data:true}
const empty={week_key:'activity-week:2026-10-26',week_end:'2026-11-01',has_settlement_data:false}
const fresh={week_key:'2026-11-03',week_end:'2026-11-01',has_settlement_data:true}
test('latest recorded defaults ahead of newer repair-only activity',()=>assert.equal(resolve('weekly',[old,empty],null,'a'),old.week_key))
test('new upload advances automatic selection, manual selection stays fixed',()=>{
 assert.equal(resolve('weekly',[old,empty,fresh],null,'a'),fresh.week_key)
 assert.equal(resolve('weekly',[old,empty,fresh],{scope:'a',key:old.week_key},'a'),old.week_key)
 assert.equal(resolve('weekly',[old,empty,fresh],{scope:'a',key:empty.week_key},'a'),empty.week_key)
})
test('tenant/filter/view scope change cannot inherit manual period',()=>assert.equal(resolve('weekly',[old,fresh],{scope:'a',key:old.week_key},'b'),fresh.week_key))
test('removed manual period falls back; no settlements preserves inspectable activity; no data empty',()=>{
 assert.equal(resolve('weekly',[old],{scope:'a',key:'gone'},'a'),old.week_key)
 assert.equal(resolve('weekly',[empty],null,'a'),empty.week_key)
 assert.equal(resolve('weekly',[],null,'a'),'')
 assert.equal(resolve('all_time',[old],null,'a'),'')
})
test('sort independent, date-only year boundary, zero or negative result counts as recorded',()=>{
 const jan={week_key:'2027-01-05',week_end:'2027-01-03',has_settlement_data:true,settlement_remainder:0}
 assert.equal(resolve('weekly',[jan,old],null,'a'),jan.week_key)
 assert.equal(resolve('monthly',[{month_key:'2026-12',has_settlement_data:true},{month_key:'2027-01',has_settlement_data:false}],null,'a'),'2026-12')
 assert.equal(resolve('yearly',[{year_key:'2027',has_settlement_data:false},{year_key:'2026',has_settlement_data:true,settlement_remainder:-100}],null,'a'),'2026')
})

test('actual monthly/yearly analytics repair-only rows are not recorded settlements',()=>{
 const series={by_week:[old],by_month:[{month_key:'2025-12',settlement_count:1,settlement_remainder:0},{month_key:'2026-01',settlement_count:0,settlement_remainder:0}],by_year:[{year_key:'2025'},{year_key:'2026'}]}
 assert.deepEqual(recorded('monthly',series).map(p=>p.month_key),['2025-12'])
 assert.deepEqual(recorded('yearly',series).map(p=>p.year_key),['2025'])
 assert.deepEqual(recorded('weekly',series),[old])
 assert.deepEqual(recorded('monthly',null),[])
})
