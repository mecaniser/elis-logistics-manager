import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {allowedSender,validDraft,parseAccountSummary} from '../contract.js';
import {fillForm} from '../fill-form.js';
const draft={id:'12345678-1234-1234-1234-123456789012',amount_cents:11820,from_last4:'2222',to_last4:'1111',memo:'Cvr Utility 0914'};
test('only exact ELIS origins and bank-monitor route may request preparation',()=>{
  assert(allowedSender('https://www.elisprotech.com/bank-monitor'));
  assert(allowedSender('http://127.0.0.1:18081/bank-monitor'));
  for(const url of ['https://evil.test/bank-monitor','https://www.elisprotech.com.evil.test/bank-monitor','http://127.0.0.1:9999/bank-monitor','https://www.elisprotech.com/','https://elisprotech.com/bank-monitor']) assert(!allowedSender(url));
});

test('parse only explicitly labeled account-card balances', () => {
  assert.deepEqual(parseAccountSummary('Main Business Checking **3304 Current Balance -$968.10 Available Balance -$968.10'), {nickname:'Main Business Checking',last4:'3304',kind:'checking',current_cents:-96810,available_cents:-96810,available_credit_cents:null});
  assert.deepEqual(parseAccountSummary('Preferred Line of Credit **2829 Current Balance $311.25 Available Credit $4,688.75'), {nickname:'Preferred Line of Credit',last4:'2829',kind:'credit',current_cents:31125,available_cents:null,available_credit_cents:468875});
  assert.equal(parseAccountSummary('Account without suffix Current Balance $1.00'), null);
});
test('reject malformed, fractional, same-account and oversized requests',()=>{
  assert(validDraft(draft));
  assert(validDraft({...draft,kind:'repayment',memo:'Rpy 2829 0922 1-1',from_last4:'1111',to_last4:'2829'}));
  assert(!validDraft({...draft,kind:'repayment'}));
  for(const change of [{amount_cents:1.1},{amount_cents:0},{to_last4:'2222'},{memo:'Missing prefix'},{memo:'Cvr '+'x'.repeat(31)}]) assert(!validDraft({...draft,...change}));
});
test('signed-out page receives no form writes',async()=>{
  globalThis.location={origin:'https://www.truliantfcuonline.org',pathname:'/dbank/live/app/login/consumer'};
  assert.deepEqual(await fillForm(draft),{ok:false,code:'LOGIN_REQUIRED',error:'Sign in to Truliant, then return to ELIS and resume this draft.'});
});
test('extension never receives cookies and limits access to bank and ELIS monitor',()=>{
  const manifest=JSON.parse(fs.readFileSync(new URL('../manifest.json',import.meta.url)));
  assert.deepEqual(manifest.permissions,['scripting','storage','alarms']);
  assert.deepEqual(manifest.host_permissions,['https://www.truliantfcuonline.org/*','https://www.elisprotech.com/bank-monitor']);
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


test('verification is bound to the original draft, origin and ELIS tab', async()=>{
  const {boundDraft}=await import('../contract.js');
  const sender={url:'http://127.0.0.1:18081/bank-monitor',tab:{id:7}};
  const active={draft,origin:'http://127.0.0.1:18081',elisTabId:7};
  assert(boundDraft(active,draft,sender));
  for(const change of [{memo:'Cvr Different'},{amount_cents:1},{from_last4:'9999'},{to_last4:'9999'}]) assert(!boundDraft(active,{...draft,...change},sender));
  assert(!boundDraft(active,draft,{...sender,tab:{id:8}}));
});

test('profile transfers bind the required login and reject other institutions', async()=>{
  const {boundDraft}=await import('../contract.js');
  const session={profile_id:'12345678-1234-1234-1234-123456789012',profile_name:'Main Business',institution_id:'ins_109917',source_name:'Business',destination_name:'Credit'};
  const d={...draft,bank_session:session};
  assert(validDraft(d));
  assert(!validDraft({...d,bank_session:{...session,institution_id:'other-bank'}}));
  const sender={url:'https://www.elisprotech.com/bank-monitor',tab:{id:7}};
  assert(!boundDraft({draft:d,origin:'https://www.elisprotech.com',elisTabId:7},{...d,bank_session:{...session,profile_name:'Other login'}},sender));
});

test('wrong profile account name stops before account selection or amount entry',async()=>{
  globalThis.location={origin:'https://www.truliantfcuonline.org',pathname:'/dbank/live/app/home/olb/transfers'};
  let chosen=false;
  const amount={value:''},memo={value:''};
  const label={textContent:'From',parentElement:{querySelectorAll:()=>[{getClientRects:()=>[1],click:()=>{}}]}};
  const option={getClientRects:()=>[1],querySelector:()=>({textContent:'Different business 2222'}),click:()=>{chosen=true}};
  const today=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  globalThis.document={querySelector:s=>s==='#amountInputField'?amount:s==='#memoInputField'?memo:s==='#frequency'?{checked:false}:null,
    querySelectorAll:s=>s.includes('label')?[label]:s.includes('input')?[{value:today}]:s.includes('menuitem')?[option]:[]};
  const result=await fillForm({...draft,bank_session:{profile_name:'Main Business',source_name:'Expected business'}});
  assert.equal(result.code,'PROFILE_SESSION_REQUIRED');
  assert.equal(chosen,false); assert.equal(amount.value,''); assert.equal(memo.value,'');
});

test('bank amount formatting is accepted without accepting a different amount', async()=>{
  const originalTimeout=globalThis.setTimeout;
  globalThis.setTimeout=fn=>{queueMicrotask(fn);return 1};
  globalThis.location={origin:'https://www.truliantfcuonline.org',pathname:'/dbank/live/app/home/olb/transfers'};
  class Input { get value(){return this.text||''} set value(v){this.text=v} dispatchEvent(){} focus(){} }
  globalThis.HTMLInputElement=Input;
  const amount=new Input(),memo=new Input();
  const today=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const option=side=>({getClientRects:()=>[1],querySelector:s=>({textContent:s.startsWith('[id^="accountBalanceLabel')?'Available':`${side==='From'?'2222':'1111'}`}),querySelectorAll:()=>[{id:'accountBalance1',textContent:'$5,000.00'}],click(){}});
  let side='From';
  globalThis.document={querySelector:s=>s==='#amountInputField'?amount:s==='#memoInputField'?memo:s==='#frequency'?{checked:false}:null,querySelectorAll:s=>s.includes(' label')?['From','To'].map(label=>({textContent:label,parentElement:{querySelectorAll:()=>[{getClientRects:()=>[1],click(){side=label}}]}})):s.includes(' input')?[{value:today}]:s.includes('menuitem')?[option(side)]:s.includes('accountDescription')?[{getClientRects:()=>[1],textContent:side==='From'?'2222':'1111'}]:[]};
  try {
    amount.dispatchEvent=()=>{amount.text='1,200.00'};
    assert.equal((await fillForm({...draft,amount_cents:120000})).ok,true);
    amount.text='';memo.text='';amount.dispatchEvent=()=>{amount.text='1,201.00'};
    assert.match((await fillForm({...draft,amount_cents:120000})).error,/Bank amount differs/);
    amount.text='';memo.text='';amount.dispatchEvent=()=>{amount.text='1,200.00'};memo.dispatchEvent=()=>{memo.text='Custom memo'};
    assert.match((await fillForm({...draft,amount_cents:120000})).error,/Bank memo differs/);
  } finally {globalThis.setTimeout=originalTimeout}
});
