import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const source=readFileSync(new URL('../src/pages/Dashboard.tsx',import.meta.url),'utf8')
const helper=readFileSync(new URL('../src/utils/reporting.ts',import.meta.url),'utf8').replaceAll('export function','function')
const start=source.indexOf('  const getSelectedPeriodData = () => {')
const end=source.indexOf('\n  const selectedPeriodData =',start)
assert.ok(start>0 && end>start)
const js=ts.transpileModule(helper+'\n'+source.slice(start,end)+'\nreturn getSelectedPeriodData()', {compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
const compute=new Function('expenseAnalysisView','data','vehicleTypeFilter','timeSeriesData','selectedExpensePeriod',js)
const data={trucks:{total_revenue:2000,net_profit:800,total_expenses:1200,expense_categories:{},truck_profits:[],operational_metrics:{settlement_expenses:900,repair_costs:300}}}
test('failed time-series with repair activity leaves all-time detail unavailable',()=>{
 // A failed read is null, never an apparently successful empty result.
 // Existing repair activity keeps hasAnyTimeSeriesPeriods true (Dashboard:1001).
 const result=compute('all_time',data,'trucks',null,'')
 assert.equal(result,null)
})
test('successful series preserves exact zero and negative all-time remaining',()=>{
 for(const amount of [0,-125,1100]) {
  const result=compute('all_time',data,'trucks',{by_year:[{settlement_remainder:amount}]},'')
  assert.equal(result.settlement_remainder,amount)
 }
})
test('late business-series success cannot replace the latest request',async()=>{
 const a=source.indexOf('  const loadBusinessTimeSeries = useEventCallback(async () => {')
 const b=source.indexOf('\n  useEffect(',a)
 const loader=source.slice(a,b)
 const code=ts.transpileModule(loader+'\nreturn loadBusinessTimeSeries',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 let resolvers=[],state
 const api={getTimeSeries:()=>new Promise(resolve=>resolvers.push(resolve))}
 const load=new Function('useEventCallback','analyticsApi','setBusinessTimeSeries','normalizeTimeSeries','businessTimeSeriesRequestRef','setBusinessTimeSeriesError',code)(fn=>fn,api,s=>{state=s},x=>x,{current:0},()=>{})
 const oldTenant=load(); const newTenant=load()
 resolvers[2]({data:{tenant:'B'}});resolvers[3]({data:{tenant:'B'}});await newTenant
 assert.equal(state.truck.tenant,'B')
 resolvers[0]({data:{tenant:'A'}});resolvers[1]({data:{tenant:'A'}});await oldTenant
 assert.equal(state.truck.tenant,'B')

})

test('late business-series failure cannot clear the latest successful request',async()=>{
 const a=source.indexOf('  const loadBusinessTimeSeries = useEventCallback(async () => {')
 const b=source.indexOf('\n  useEffect(',a)
 const loader=source.slice(a,b)
 const code=ts.transpileModule(loader+'\nreturn loadBusinessTimeSeries',{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
 let resolvers=[],rejecters=[],state
 const api={getTimeSeries:()=>new Promise((resolve,reject)=>{resolvers.push(resolve);rejecters.push(reject)})}
 const load=new Function('useEventCallback','analyticsApi','setBusinessTimeSeries','normalizeTimeSeries','businessTimeSeriesRequestRef','setBusinessTimeSeriesError',code)(fn=>fn,api,s=>{state=s},x=>x,{current:0},()=>{})
 const oldTenant=load(); const newTenant=load()
 resolvers[2]({data:{tenant:'B'}});resolvers[3]({data:{tenant:'B'}});await newTenant
 assert.equal(state.truck.tenant,'B')
 rejecters[0](new Error('old failed'));rejecters[1](new Error('old failed'));await oldTenant
 assert.equal(state.truck.tenant,'B')

})
