import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
const js=ts.transpileModule(readFileSync(new URL('../src/components/investmentPlanModel.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ES2022,target:ts.ScriptTarget.ES2022}}).outputText
const {investmentPayload,savedInvestmentDraft,formatInvestmentAmount}=await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const saved={funding:'heloc',effective:'2026-05-15',start:'2026-05-15',acquisition_cost:'72129.69',financed:'68099.00',initial_cash:'4030.69',annual_rate:'0.065',balance_at_sale:'40000',quoted_monthly_payment:null}
test('opening a saved investment retains its effective date and all financing terms',()=>{
 const draft=savedInvestmentDraft(saved);assert.deepEqual(draft,saved);draft.effective='2026-09-28';assert.equal(saved.effective,'2026-05-15')
})
test('cash preview normalizes loan fields without destroying the HELOC draft when toggling back',()=>{
 const draft={...saved,funding:'cash'};const cash=investmentPayload(draft);assert.equal(cash.financed,0);assert.equal(cash.initial_cash,'72129.69');assert.equal(cash.balance_at_sale,0);assert.deepEqual(investmentPayload({...draft,funding:'heloc'}),saved)
})
test('money fields format cents and grouping while optional payment stays blank',()=>{
 assert.equal(formatInvestmentAmount('68099.00'),'68,099.00');assert.equal(formatInvestmentAmount('4030.69'),'4,030.69');assert.equal(formatInvestmentAmount(0),'0.00');assert.equal(formatInvestmentAmount(null),'');assert.equal(formatInvestmentAmount(''),'')
})
