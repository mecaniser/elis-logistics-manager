import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const source=readFileSync(new URL('../src/components/finance/fuelMileageModel.ts',import.meta.url),'utf8')
const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {summarizeFuel,fuelMileageReport}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const item=(miles='700',gallons='100')=>({miles,basis:'reported',amount:'400',reviewed:true,rows:[{amount:'400',gallons,product:'diesel'}]})
test('diesel comparison excludes DEF and uses reported miles',()=>{
 const row=item();row.amount='420';row.rows.push({amount:'20',gallons:'5',product:'def'})
 const result=summarizeFuel([row]);assert.equal(result.mpg,7);assert.equal(result.purchased,105);assert.deepEqual(result.expected,[100,700/6])
})
test('unknown product, estimated miles, incomplete volumes and credits block MPG',()=>{
 const cases=[{...item(),basis:'estimated'},{...item(),reviewed:false},{...item(),amount:'401'}]
 for(const value of ['unknown','def'])cases.push({...item(),rows:[{amount:'400',gallons:'100',product:value}]})
 cases.push({...item(),rows:[{amount:'400',gallons:null,product:'diesel'}]})
 cases.push({...item(),amount:'-400',rows:[{amount:'-400',gallons:'100',product:'diesel'}]})
 for(const row of cases)assert.equal(summarizeFuel([row]).mpg,null)
})
test('rolling comparison is weighted and excludes dates outside 28 days',()=>{
 const rows=[['2026-09-27','700','100'],['2026-08-31','600','100'],['2026-08-30','1','100']].map(([date,miles,gallons],id)=>({id,asset_id:1,date,miles,mileage_basis:'reported',fuel:'400',fuel_rows:item(miles,gallons).rows,status:'arithmetic_matched'}))
 const report=fuelMileageReport([{id:'s',legacy_id:0,asset_id:1,date:'2026-09-27',name:'Truck',basis:'posted',miles:'650',mileage_basis:'independent',amount:'400',rows:item().rows}],{rows})
 assert.equal(report.selected[0].mpg,6.5);assert.equal(report.rolling[0].count,2);assert.equal(report.rolling[0].mpg,6.5)
 rows[1].status='missing_source';assert.equal(fuelMileageReport([{id:'s',asset_id:1,date:'2026-09-27',rows:[],amount:'400'}],{rows}).rolling[0].mpg,null)
})
