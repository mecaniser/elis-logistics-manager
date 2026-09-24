import test from 'node:test';
import assert from 'node:assert/strict';

const draft = {id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', amount_cents:11820, from_last4:'2829',to_last4:'3304',memo:'Cvr Test'};
const sender = {frameId:0,tab:{id:1},url:'http://127.0.0.1:18081/bank-monitor'};

test('approval timeout reports no preparation and opens only the dedicated review popup', async t => {
  let external;
  const created = [], removed = [], stored = [];
  t.mock.method(globalThis, 'setTimeout', fn => { queueMicrotask(fn); return 0; });
  globalThis.chrome = {
    runtime: {id:'test',getURL:p=>'chrome-extension://test/'+p,
      onMessageExternal:{addListener:f=>{external=f;}},onMessage:{addListener(){},removeListener(){}}},
    storage:{session:{get:async()=>({}),set:async v=>stored.push(v),remove:async()=>{}}},
    tabs:{query:async()=>[]},
    windows:{
      create:async args=>{created.push(args);return {id:20,tabs:[{id:2}]};},
      remove:async id=>removed.push(id),
      onRemoved:{addListener(){},removeListener(){}}
    },
    scripting:{executeScript:async()=>assert.fail('Must not script a bank tab before approval')}
  };
  await import('../background.js?timeout-test');
  const result = await new Promise(resolve=>external({type:'ELIS_PREPARE',draft},sender,resolve));
  assert.equal(result.code,'PREPARATION_NOT_STARTED');
  assert.equal(result.ok,false);
  assert.deepEqual(created,[{url:'chrome-extension://test/approve.html',type:'popup',focused:true,width:520,height:650}]);
  assert.deepEqual(removed,[20]);
  assert.ok(stored.every(v=>!v.activeDraft));
  delete globalThis.chrome;
});

test('unknown approval infrastructure failure stays locked', async () => {
  let external;
  globalThis.chrome = {
    runtime:{onMessageExternal:{addListener:f=>{external=f;}}},
    storage:{session:{get:async()=>({}),set:async()=>{throw new Error('storage unavailable');}}}
  };
  await import('../background.js?unknown-test');
  const result = await new Promise(resolve=>external({type:'ELIS_PREPARE',draft},sender,resolve));
  assert.equal(result.ok,false);
  assert.equal(result.code,undefined);
  delete globalThis.chrome;
});

test('login redirect releases the draft because the bank form was never reached', async () => {
  let external, internal, approval;
  const stored = [], removed = [];
  globalThis.chrome = {
    runtime: {id:'test',getURL:p=>'chrome-extension://test/'+p,
      onMessageExternal:{addListener:f=>{external=f;}},onMessage:{addListener:f=>{internal=f;},removeListener(){}}},
    storage:{session:{get:async()=>({}),set:async value=>{stored.push(value);if(value.approval) approval=value.approval;},remove:async key=>removed.push(key)}},
    tabs:{query:async()=>[],create:async()=>({id:3}),get:async()=>({id:3,status:'complete'})},
    windows:{
      create:async()=>({id:20,tabs:[{id:2}]}),remove:async()=>{},
      onRemoved:{addListener(){},removeListener(){}}
    },
    scripting:{executeScript:async()=>[{result:{ok:false,code:'LOGIN_REQUIRED',error:'Sign in to Truliant, then return to ELIS and resume this draft.'}}]}
  };
  await import('../background.js?login-redirect-test');
  const preparation = new Promise(resolve=>external({type:'ELIS_PREPARE',draft},sender,resolve));
  await new Promise(resolve=>setImmediate(resolve));
  internal({action:'approve',nonce:approval.nonce},{id:'test',tab:{id:2},url:'chrome-extension://test/approve.html'},()=>{});
  assert.deepEqual(await preparation,{ok:false,code:'PREPARATION_NOT_STARTED',error:'Sign in to Truliant, then return to ELIS and resume this draft.'});
  assert.equal(stored.some(value=>value.activeDraft?.status==='requested'),true);
  assert.equal(removed.includes('activeDraft'),true);
  delete globalThis.chrome;
});

test('extension reload can reauthorize read-only verification without opening a bank tab', async () => {
  let external, internal, approval;
  const created = [], stored = [];
  globalThis.chrome = {
    runtime: {id:'test',getURL:p=>'chrome-extension://test/'+p,getManifest:()=>({version:'test'}),
      onMessageExternal:{addListener:f=>{external=f;}},
      onMessage:{addListener:f=>{internal=f;},removeListener(){}}},
    storage:{session:{get:async()=>({}),set:async value=>{stored.push(value);if(value.approval) approval=value.approval;},remove:async()=>{}}},
    tabs:{query:async()=>[]},
    windows:{
      create:async args=>{created.push(args);return {id:20,tabs:[{id:2}]};},
      remove:async()=>{},onRemoved:{addListener(){},removeListener(){}}
    },
    scripting:{executeScript:async()=>assert.fail('Reauthorization must not inspect history until ELIS_VERIFY')}
  };
  await import('../background.js?reauthorize-test');
  const reauth = new Promise(resolve=>external({type:'ELIS_REAUTHORIZE_VERIFY',draft:{...draft,bank_date:'2026-09-14'}},sender,resolve));
  await new Promise(resolve=>setImmediate(resolve));
  internal({action:'approve',nonce:approval.nonce},{id:'test',tab:{id:2},url:'chrome-extension://test/approve.html'},()=>{});
  assert.deepEqual(await reauth,{ok:true});
  assert.deepEqual(created.map(item=>item.type),['popup']);
  assert.equal(stored.at(-1).activeDraft.bankDate,'Sep 14, 2026');
  delete globalThis.chrome;
});
