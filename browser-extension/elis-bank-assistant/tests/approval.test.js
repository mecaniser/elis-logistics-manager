import test from 'node:test';
import assert from 'node:assert/strict';

const draft = {id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', amount_cents:11820, from_last4:'2829',to_last4:'3304',memo:'Cvr Test'};
const sender = {frameId:0,tab:{id:1},url:'http://127.0.0.1:18081/bank-monitor'};

test('approval timeout reports no preparation and never opens or scripts a bank tab', async t => {
  let external;
  const created = [], stored = [];
  t.mock.method(globalThis, 'setTimeout', fn => { queueMicrotask(fn); return 0; });
  globalThis.chrome = {
    runtime: {id:'test',getURL:p=>'chrome-extension://test/'+p,
      onMessageExternal:{addListener:f=>{external=f;}},onMessage:{addListener(){},removeListener(){}}},
    storage:{session:{get:async()=>({}),set:async v=>stored.push(v),remove:async()=>{}}},
    tabs:{create:async args=>{created.push(args);return {id:2};},remove:async()=>{}},
    scripting:{executeScript:async()=>assert.fail('Must not script a bank tab before approval')}
  };
  await import('../background.js?timeout-test');
  const result = await new Promise(resolve=>external({type:'ELIS_PREPARE',draft},sender,resolve));
  assert.equal(result.code,'PREPARATION_NOT_STARTED');
  assert.equal(result.ok,false);
  assert.deepEqual(created,[{url:'chrome-extension://test/approve.html',active:true}]);
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
