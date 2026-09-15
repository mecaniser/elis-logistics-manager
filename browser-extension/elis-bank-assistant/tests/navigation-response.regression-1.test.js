import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

// Regression: ISSUE-003 — account navigation destroyed the frame before Chrome received the opened response
// Found by /qa on 2026-09-14
// Report: .gstack/qa-reports/qa-report-bank-monitor-2026-09-14.md
const source=readFileSync(new URL('../bank-history-content.js',import.meta.url),'utf8');

test('account-open response is delivered before the click navigates its frame', () => {
  let listener;
  let delivered=false;
  let navigated=false;
  const context={
    window:{}, location:{origin:'https://www.truliantfcuonline.org'},
    document:{
      querySelector:()=>null,
      querySelectorAll:selector=>selector==='[id^="account-link-"]' ? [{
        textContent:'Main Business Checking ********3304',
        click:()=>{navigated=true;assert.equal(delivered,true,'reply must be delivered before navigation');}
      }] : []
    },
    setTimeout:callback=>{callback();return 1;},
    chrome:{runtime:{onMessage:{addListener:value=>{listener=value;}}}}
  };
  context.window.top={};
  vm.runInNewContext(source,context);
  listener({type:'ELIS_OPEN_ACCOUNT',suffix:'3304'}, {}, response=>{
    assert.deepEqual({...response},{ready:true,opened:true});
    delivered=true;
  });
  assert.equal(navigated,true);
});
