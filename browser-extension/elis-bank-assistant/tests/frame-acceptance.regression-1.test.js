import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

// Regression: ISSUE-002 — unrelated and not-yet-rendered Truliant frames won the account-selection response race
// Found by /qa on 2026-09-14
// Report: .gstack/qa-reports/qa-report-bank-monitor-2026-09-14.md
const source=readFileSync(new URL('../bank-history-content.js',import.meta.url),'utf8');

function frame(links) {
  let listener;
  const context={
    window:{}, location:{origin:'https://www.truliantfcuonline.org'},
    document:{
      querySelector:()=>null,
      querySelectorAll:selector=>selector==='[id^="account-link-"]' ? links : []
    },
    chrome:{runtime:{onMessage:{addListener:value=>{listener=value;}}}}
  };
  context.window.top={};
  vm.runInNewContext(source,context);
  return message=>{
    let response;
    listener(message,{},value=>{response=value;});
    return response;
  };
}

test('multi-frame account selection waits through empty frames and delayed account cards', () => {
  const emptyFrame=frame([]);
  const unrelatedFrame=frame([{textContent:'Advertisement',click:()=>assert.fail('unrelated frame clicked')}]);
  const delayedLinks=[];
  const accountFrame=frame(delayedLinks);
  const message={type:'ELIS_OPEN_ACCOUNT',suffix:'3304'};

  assert.equal(emptyFrame(message),undefined);
  assert.equal(unrelatedFrame(message),undefined);
  assert.equal(accountFrame(message),undefined);

  let clicked=0;
  delayedLinks.push({textContent:'Main Business Checking ********3304 Available -$968.10',click:()=>{clicked++;}});
  const broadcast=[emptyFrame(message),unrelatedFrame(message),accountFrame(message)].filter(Boolean);
  assert.equal(broadcast.filter(value=>value.opened).length,1);
  assert.equal(clicked,1);
});
