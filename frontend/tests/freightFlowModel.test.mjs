import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const source = readFileSync(new URL('../src/components/finance/freightFlowModel.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022}}).outputText
const {freightFlowModel} = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const model = (gross, remainder, rows) => freightFlowModel({freight_gross:gross, settlement_remainder:remainder, rows:rows.map(([category,amount])=>({category,amount}))})

test('September 21 preserves the source remainder and groups smaller deductions once',()=>{
  const m=model('23700.00','5836.92',[['carrier','2844.00'],['fuel','6844.83'],['driver_pay','7110.00'],['insurance','600.00'],['tolls','264.25'],['support','200.00']])
  assert.equal(m.reconciled,true); assert.equal(m.canFlow,true)
  assert.equal(m.flows.find(r=>r.key==='other').cents,106425)
  assert.equal(m.flows.reduce((s,r)=>s+r.cents,0),2370000)
  assert.equal(m.steps.at(-1).after,583692)
  assert.equal(m.details.length,6)
})
test('a loss keeps the negative endpoint inside the signed waterfall domain',()=>{
  const m=model('100.00','-20.00',[['fuel','120.00']])
  assert.equal(m.reconciled,true);assert.equal(m.canFlow,false);assert.equal(m.min,-2000);assert.equal(m.steps[0].after,-2000)
})
test('refunds add to the running balance instead of disappearing',()=>{
  const m=model('100.00','110.00',[['fuel','-10.00']])
  assert.equal(m.reconciled,true);assert.equal(m.canFlow,false);assert.equal(m.steps[0].after,11000);assert.equal(m.max,11000)
})
test('offsetting other costs and credits retain exact source details',()=>{
  const m=model('100.00','100.00',[['tolls','20.00'],['refund','-20.00']])
  assert.equal(m.canFlow,false);assert.equal(m.others.length,2);assert.equal(m.steps[0].cents,0)
})
test('a nonreconciling report cannot be drawn as a balanced allocation',()=>{
  assert.equal(model('100.00','85.00',[['fuel','20.00']]).reconciled,false)
})
test('zero freight never produces percentage division or a positive flow',()=>{
  const m=model('0.00','-10.00',[['insurance','10.00']])
  assert.equal(m.reconciled,true);assert.equal(m.canFlow,false);assert.equal(m.min,-1000)
})
test('a zero remainder remains explicitly labeled',()=>{
  const m=model('100.00','0.00',[['fuel','100.00']])
  assert.equal(m.canFlow,true);assert.equal(m.flows.at(-1).key,'remainder');assert.equal(m.flows.at(-1).cents,0)
})
test('duplicate category amounts aggregate with cent precision',()=>{
  const m=model('0.30','0.00',[['fuel','0.10'],['fuel','0.20']])
  assert.equal(m.reconciled,true);assert.equal(m.flows[0].cents,30)
})
test('invalid or unsafe amounts do not become a plausible chart',()=>{
  assert.equal(model('100.00','90.00',[['fuel','unknown'],['fuel','10.00']]).reconciled,false)
  assert.equal(model('9999999999999999.00','9999999999999999.00',[]).reconciled,false)
})
