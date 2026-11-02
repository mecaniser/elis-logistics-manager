import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const js=ts.transpileModule(readFileSync(new URL('../src/utils/reporting.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {awaitingWeeklySettlements:pending}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const period={week_start:'2026-10-26',week_end:'2026-11-01'}
test('latest completed week awaits normal Tuesday/Wednesday arrival through Wednesday',()=>{
 for(const day of [2,3,4])assert.equal(pending('weekly',period,false,new Date(2026,10,day,12)),true)
 assert.equal(pending('weekly',period,false,new Date(2026,10,5,0)),false)
})
test('current run, future and historical weeks do not claim statements are awaiting arrival',()=>{
 assert.equal(pending('weekly',period,false,new Date(2026,9,29,12)),false)
 assert.equal(pending('weekly',period,false,new Date(2026,9,25,12)),false)
 assert.equal(pending('weekly',period,false,new Date(2026,10,9,12)),false)
})
test('any recorded settlement including a genuine zero prevents pending claim',()=>{
 assert.equal(pending('weekly',period,true,new Date(2026,10,2,12)),false)
})
test('nonweekly, invalid, missing or noncalendar intervals do not assert expected settlements',()=>{
 for(const view of ['monthly','yearly','all_time'])assert.equal(pending(view,period,false,new Date(2026,10,2)),false)
 for(const p of [null,{}, {week_start:'2026-02-30',week_end:'2026-03-08'},{week_start:'2026-10-27',week_end:'2026-11-02'}])assert.equal(pending('weekly',p,false,new Date(2026,10,2)),false)
})
test('local date semantics handle DST and year rollover without shifting date-only bounds',()=>{
 assert.equal(pending('weekly',{week_start:'2025-12-29',week_end:'2026-01-04'},false,new Date(2026,0,7,23,59)),true)
 assert.equal(pending('weekly',{week_start:'2025-12-29',week_end:'2026-01-04'},false,new Date(2026,0,8,0)),false)
})

test('different pay-date key and vehicle filter cannot assert that all business settlements are pending',async()=>{
 const {hasRecordedSettlementForRun:recorded}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
 const businessRows=[{week_key:'2026-11-03',week_start:'2026-10-26',week_end:'2026-11-01',settlement_remainder:1200}]
 const selectedTruckActivity={...period,week_key:'activity-week:2026-10-26'}
 assert.notEqual(businessRows[0].week_key,selectedTruckActivity.week_key)
 assert.equal(recorded(selectedTruckActivity,businessRows),true)
 assert.equal(pending('weekly',selectedTruckActivity,recorded(selectedTruckActivity,businessRows),new Date(2026,10,3)),false)
 assert.equal(recorded(period,[{week_key:'2026-10-26',week_start:'2026-10-19',week_end:'2026-10-26'}]),false)
 assert.equal(recorded(period,[{week_key:'2026-11-03'}]),true)
})

test('actual dashboard status expression suppresses pending for a different vehicle already settled',()=>{
 const dashboard=readFileSync(new URL('../src/pages/Dashboard.tsx',import.meta.url),'utf8')
 const a=dashboard.indexOf('  const recordedBusinessWeeks ='),b=dashboard.indexOf('  const businessPeriodSectionLabel =',a)
 assert.ok(a>0&&b>a)
 const helper=readFileSync(new URL('../src/utils/reporting.ts',import.meta.url),'utf8').replaceAll('export function','function')
 const compiled=ts.transpileModule(helper+'\n'+dashboard.slice(a,b)+'\nreturn emptySettlementLabel',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 const status=new Function('businessTimeSeries','expenseAnalysisView','selectedActivityPeriod','businessTimeSeriesError','businessResultAvailable',compiled)
 const row={week_key:'2026-11-03',week_start:'2026-10-26',week_end:'2026-11-01',settlement_remainder:1200}
 assert.equal(status({truck:{by_week:[row]},trailer:{by_week:[]}},'weekly',{...period,week_key:'activity-week:2026-10-26'},false,false),'No result for this selection')
})

test('backend synthesized and partially missing service bounds cannot falsely claim an arrival is pending',async()=>{
 const {hasRecordedSettlementForRun:recorded}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
 for(const bounds of [
  {week_start:'2026-11-03',week_end:'2026-11-03'},
  {week_start:'2026-11-03',week_end:'2026-11-01'},
  {week_start:'2026-10-26',week_end:'2026-11-03'},
  {week_start:null,week_end:'2026-11-03'},
 ]){
  const exists=recorded(period,[{week_key:'2026-11-03',...bounds}])
  assert.equal(exists,true);assert.equal(pending('weekly',period,exists,new Date(2026,10,3)),false)
 }
})
