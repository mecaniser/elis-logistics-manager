import test from 'node:test';
import assert from 'node:assert/strict';
import {easternScheduleWindow, startScheduledChromeRead} from '../scheduled-check.js';

test('daily Chrome check uses Eastern time across daylight saving changes', () => {
  assert.deepEqual(easternScheduleWindow(new Date('2026-07-01T21:29:00Z')),
    {date:'2026-07-01',due:false});
  assert.deepEqual(easternScheduleWindow(new Date('2026-07-01T21:30:00Z')),
    {date:'2026-07-01',due:true});
  assert.deepEqual(easternScheduleWindow(new Date('2026-12-01T22:30:00Z')),
    {date:'2026-12-01',due:true});
  assert.deepEqual(easternScheduleWindow(new Date('2026-12-01T22:45:00Z')),
    {date:'2026-12-01',due:false});
});

test('scheduled Chrome read opens one inactive ELIS tab and dispatches once', async () => {
  const saved = {};
  const tabs = [];
  const api = {
    storage: {
      local: {get: async key => ({[key]: saved[key]}), set: async value => Object.assign(saved,value)},
      session: {set: async value => Object.assign(saved,value)},
    },
    tabs: {create: async options => {tabs.push(options); return {id: 7};}},
    alarms: {create: () => {}},
    scripting: {executeScript: async options => {
      assert.equal(options.target.tabId, 7);
      assert.equal(options.world, 'MAIN');
      return [{result:true}];
    }},
  };
  const now = new Date('2026-07-01T21:30:00Z');
  assert.equal(await startScheduledChromeRead(api,now,async()=>{}),'dispatched');
  assert.deepEqual(tabs,[{url:'https://www.elisprotech.com/bank-monitor',active:false}]);
  assert.equal(await startScheduledChromeRead(api,now,async()=>{}),'already_attempted');
  assert.equal(tabs.length,1);
});
