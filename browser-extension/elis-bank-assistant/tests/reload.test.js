import test from 'node:test';
import assert from 'node:assert/strict';

test('an allowed ELIS page can request a safe extension runtime reload', async t => {
  let external;
  let reloaded=false;
  t.mock.method(globalThis,'setTimeout',callback=>{queueMicrotask(callback);return 1;});
  globalThis.chrome={runtime:{
    id:'reload-extension',getManifest:()=>({version:'0.1.19'}),reload:()=>{reloaded=true;},
    onMessageExternal:{addListener:listener=>{external=listener;}},onMessage:{addListener(){},removeListener(){}}
  }};
  await import('../background.js?reload-test');
  let response;
  external({type:'ELIS_RELOAD'},{frameId:0,tab:{id:7},url:'https://www.elisprotech.com/bank-monitor'},value=>{response=value;});
  assert.deepEqual(response,{ok:true,version:'0.1.19'});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(reloaded,true);
  delete globalThis.chrome;
});
