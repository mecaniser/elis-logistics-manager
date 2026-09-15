import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';

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
    setTimeout,
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

test('only the child frame containing account cards answers and opens the exact suffix', async () => {
  let clicked = false;
  const link = {textContent:'Main Business Checking********3304Available Balance$0.00',click:()=>{clicked=true;}};
  const listener = listenerFor([link]);
  let response;
  listener({type:'ELIS_OPEN_ACCOUNT',suffix:'3304'}, {}, value => { response = value; });
  assert.equal(response.ready, true);
  assert.equal(response.opened, true);
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(clicked, true);
});

test('lists only underlying posted debits with stable references and row balances', async () => {
  let listener;
  const cell = (id, textContent) => ({id, textContent});
  const row = ({amount, description, date='Sep 14, 2026', balance='-$968.10', id='charge-1'}) => ({
    getAttribute: () => null,
    querySelector: selector => selector.includes('amount-') ? cell(id, amount) :
      selector.includes('description-') ? cell('description', description) :
      selector.includes('transactionDate-') ? cell('date', date) :
      selector.includes('balance-') ? cell('balance', balance) : null
  });
  const section = {getAttribute: () => 'posted transactions section', querySelector: () => null};
  const rows = [section,
    row({amount:'-$118.20',description:'Union County / utilities',id:'charge-1'}),
    row({amount:'-$35.00',description:'Overdraft Fee',id:'fee'}),
    row({amount:'$118.20',description:'Deposit Cvr Union County utilities 0914',id:'deposit'}),
    row({amount:'-$42.15',description:'Fuel stop',balance:'$10.00',id:'old-positive'})
  ];
  const table = {querySelectorAll: selector => selector === 'tbody tr' ? rows : []};
  const context = {
    window: {}, location: {origin:'https://www.truliantfcuonline.org'}, setTimeout,
    TextEncoder, crypto:webcrypto,
    document:{
      querySelector: selector => selector === 'table[aria-label="account transactions"]' ? table : null,
      querySelectorAll: selector => selector === 'h2' ? [{textContent:'Main Business Checking 3304'}] : []
    },
    chrome:{runtime:{onMessage:{addListener: fn => {listener=fn;}}}}
  };
  context.window.top = {};
  vm.runInNewContext(source, context);
  const result = await new Promise(resolve => listener({type:'ELIS_LIST_POSTED_DEBITS',suffix:'3304'}, {}, resolve));
  assert.equal(result.ready, true);
  assert.deepEqual(JSON.parse(JSON.stringify(result.transactions.map(item => ({description:item.description,amount:item.amount_cents,balance:item.balance_cents})))), [
    {description:'Union County utilities',amount:11820,balance:-96810},
    {description:'Fuel stop',amount:4215,balance:1000}
  ]);
  assert.match(result.transactions[0].reference,/^[a-f0-9]{64}$/);
});
