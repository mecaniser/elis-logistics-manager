import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {allowedSender,validDraft} from '../contract.js';
import {fillForm} from '../fill-form.js';
const draft={id:'12345678-1234-1234-1234-123456789012',amount_cents:11820,from_last4:'2222',to_last4:'1111',memo:'Cvr Utility 0914'};
test('only exact ELIS origins and bank-monitor route may request preparation',()=>{
  assert(allowedSender('https://www.elisprotech.com/bank-monitor'));
  assert(allowedSender('http://127.0.0.1:18081/bank-monitor'));
  for(const url of ['https://evil.test/bank-monitor','https://www.elisprotech.com.evil.test/bank-monitor','http://127.0.0.1:9999/bank-monitor','https://www.elisprotech.com/']) assert(!allowedSender(url));
});
test('reject malformed, fractional, same-account and oversized requests',()=>{
  assert(validDraft(draft));
  for(const change of [{amount_cents:1.1},{amount_cents:0},{to_last4:'2222'},{memo:'Missing prefix'},{memo:'Cvr '+'x'.repeat(31)}]) assert(!validDraft({...draft,...change}));
});
test('signed-out page receives no form writes',async()=>{
  globalThis.location={origin:'https://www.truliantfcuonline.org',pathname:'/dbank/live/app/login/consumer'};
  assert.equal((await fillForm(draft)).ok,false);
});
test('extension never receives cookies or broad host access',()=>{
  const manifest=JSON.parse(fs.readFileSync(new URL('../manifest.json',import.meta.url)));
  assert.deepEqual(manifest.permissions,['scripting','storage']);
  assert.deepEqual(manifest.host_permissions,['https://www.truliantfcuonline.org/*']);
});
test('an occupied form is not overwritten or submitted',async()=>{
  globalThis.location={origin:'https://www.truliantfcuonline.org',pathname:'/dbank/live/app/home/olb/transfers'};
  globalThis.document={querySelector:s=>s==='#amountInputField'?{value:'118.20'}:s==='#memoInputField'?{value:'Cvr Existing'}:null};
  const result=await fillForm(draft);
  assert.equal(result.ok,false);
  assert.match(result.error,/not overwritten/);
});

test('whole-charge funding check stops before amount entry when credit is insufficient',async()=>{
  globalThis.location={origin:'https://www.truliantfcuonline.org',pathname:'/dbank/live/app/home/olb/transfers'};
  const amount={value:''},memo={value:''};
  let accountChosen=false;
  const option={getClientRects:()=>[1],click:()=>{accountChosen=true;},querySelector:s=>s.includes('listAccountDescription')?{textContent:'Credit 2222'}:{textContent:'Available'},querySelectorAll:()=>[{id:'accountBalance-testFrom',textContent:'$26.29'}]};
  const label={textContent:'From',parentElement:{querySelectorAll:()=>[{getClientRects:()=>[1],click:()=>{}}]}};
  const today=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  globalThis.document={querySelector:s=>s==='#amountInputField'?amount:s==='#memoInputField'?memo:s==='#frequency'?{checked:false}:null,
    querySelectorAll:s=>s.includes('label')?[label]:s.includes('input')?[{value:today}]:s.includes('menuitem')?[option]:[]};
  const result=await fillForm(draft);
  assert.equal(result.ok,false); assert.match(result.error,/whole charge/);
  assert.equal(accountChosen,false); assert.equal(amount.value,''); assert.equal(memo.value,'');
});
