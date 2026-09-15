import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

const source = readFileSync(new URL('../bank-history-content.js', import.meta.url), 'utf8');

function listenerFor(links) {
  let listener;
  const context = {
    window: {},
    location: {origin: 'https://www.truliantfcuonline.org'},
    document: {
      querySelector: () => null,
      querySelectorAll: selector => selector === '[id^="account-link-"]' ? links : []
    },
    chrome: {runtime: {onMessage: {addListener: fn => { listener = fn; }}}}
  };
  context.window.top = {};
  vm.runInNewContext(source, context);
  return listener;
}

test('empty Truliant child frames stay silent during account selection', () => {
  const listener = listenerFor([]);
  let replied = false;
  listener({type:'ELIS_OPEN_ACCOUNT',suffix:'3304'}, {}, () => { replied = true; });
  assert.equal(replied, false);
});

test('only the child frame containing account cards answers and opens the exact suffix', () => {
  let clicked = false;
  const link = {textContent:'Main Business Checking********3304Available Balance$0.00',click:()=>{clicked=true;}};
  const listener = listenerFor([link]);
  let response;
  listener({type:'ELIS_OPEN_ACCOUNT',suffix:'3304'}, {}, value => { response = value; });
  assert.equal(response.ready, true);
  assert.equal(response.opened, true);
  assert.equal(clicked, true);
});
