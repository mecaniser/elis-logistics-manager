export function easternScheduleWindow(now = new Date()) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(now).map(part => [part.type, part.value]));
  const date = `${parts.year}-${parts.month}-${parts.day}`;
  const minute = Number(parts.hour) * 60 + Number(parts.minute);
  return {date, due: minute >= 17 * 60 + 30 && minute < 17 * 60 + 45};
}

export async function startScheduledChromeRead(api, now = new Date(), pause = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  const slot = easternScheduleWindow(now);
  if (!slot.due) return 'outside_window';
  const key = `scheduledCheckAttempt:${slot.date}`;
  if ((await api.storage.local.get(key))[key]) return 'already_attempted';
  await api.storage.local.set({[key]: true}); // Never repeat a bank read blindly.
  const tab = await api.tabs.create({url:'https://www.elisprotech.com/bank-monitor',active:false});
  await api.storage.session.set({scheduledElisTabId:tab.id});
  api.alarms.create('elis-bank-monitor-cleanup', {when:Date.now()+5*60*1000});
  for (let attempt=0;attempt<50;attempt++) {
    await pause(500);
    const result=await api.scripting.executeScript({target:{tabId:tab.id},world:'MAIN',func:()=>{
      if (document.documentElement.dataset.elisBankMonitorReady !== 'true') return false;
      window.dispatchEvent(new Event('elis:scheduled-bank-check'));
      return true;
    }}).catch(()=>[]);
    if (result[0]?.result) return 'dispatched';
  }
  return 'page_unavailable';
}
