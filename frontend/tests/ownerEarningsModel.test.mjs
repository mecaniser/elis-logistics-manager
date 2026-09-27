import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const js=ts.transpileModule(readFileSync(new URL('../src/components/finance/ownerEarningsModel.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {ownerEarningsModel}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const plan=()=>({planning_subtotal:'4946.15',unassigned_result:'0.00',pairs:[{repair_target:'600.00',capital_target:'290.77',additional_protection:'890.77',capital_complete:false,bridge:[{label:'Statement remainder',amount:'3677.34'},{label:'Saved settlements not yet posted (unverified)',amount:'2159.58'}],allocation_split:{trailer_allocation:'800.00',trailer_capital_target:'290.77'}}]})
test('full fleet bridge retains trailer earnings and matches existing planning subtotal',()=>{
 const result=ownerEarningsModel(plan());assert.equal(result.start,583692);assert.equal(result.end,494615);assert.equal(result.reconciled,true);assert.equal(result.allocation,80000);assert.equal(result.trailerRecovery,29077)
})
test('reserve-covered repair is offset once, principal deducted once',()=>{
 const p=plan();p.pairs[0].additional_protection='390.77';p.pairs[0].bridge.push({label:'New repair and capital funding',amount:'-500.00'},{label:'Historical repairs not yet posted to Accounting',amount:'-500.00'},{label:'Repair costs covered by protected funds',amount:'500.00'},{label:'Business-paid equipment obligations',amount:'-100.00'});p.planning_subtotal='4846.15';assert.equal(ownerEarningsModel(p).end,484615);assert.equal(ownerEarningsModel(p).reconciled,true)
})
test('unassigned losses enter company result without hiding a shortfall',()=>{
 const p=plan();p.unassigned_result='-6000.00';const r=ownerEarningsModel(p);assert.equal(r.end,-105385);assert.equal(r.reconciled,true);assert.equal(r.min,-105385)
})
test('unexpected bridge entries remain visible and reconciliation rejects mismatches',()=>{
 const p=plan();p.pairs[0].bridge.push({label:'Correction',amount:'-1.00'});assert.equal(ownerEarningsModel(p).reconciled,false);p.planning_subtotal='4945.15';assert.equal(ownerEarningsModel(p).reconciled,true);p.pairs[0].bridge[0].amount='invalid';assert.equal(ownerEarningsModel(p).reconciled,false)
})
