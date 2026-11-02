async (page) => {
 await page.unrouteAll();
 const results=[];const writes=[];const errors=[];
 page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.url())});
 page.on('pageerror',e=>errors.push(e.message));
 const check=(ok,name)=>{if(!ok)throw Error(name);results.push(name)};
 const switchTo=async name=>{
  const button=page.getByRole('button',{name:/Current business:.*Switch business/});
  await button.waitFor();if((await button.getAttribute('aria-label')).includes(name))return;
  await button.click();await page.getByText(name,{exact:true}).click();
  await page.getByRole('button',{name:`Current business: ${name}. Switch business`}).waitFor();
 };
 await switchTo('October synthetic');
 let failing=true;
 await page.route('**/api/analytics/time-series?**',r=>failing?r.fulfill({status:503,contentType:'application/json',body:'{"detail":"synthetic failure"}'}):r.continue());
 await page.reload();
 await page.getByRole('button',{name:'All Time',exact:true}).click();
 await page.getByRole('alert').filter({hasText:'Settlement results are unavailable'}).waitFor();
 check(await page.getByText('Settlement remaining after allocations',{exact:true}).count()===0,'failed all-time with repair activity suppresses remaining and allocations');
 check((await page.locator('main').innerText()).includes('Result unavailable'),'failed business results are unavailable, not zero');
 check((await page.locator('main').innerText()).includes('$8,056.76'),'failure retains independently loaded withdrawal activity');
 await page.screenshot({path:'output/playwright/failed-report.png',fullPage:false});
 failing=false;await page.getByRole('button',{name:'Retry report',exact:true}).click();
 await page.getByText('$10,357.46',{exact:true}).waitFor();
 check(await page.getByRole('alert').count()===0,'retry restores real remaining and clears error');
 await page.unroute('**/api/analytics/time-series?**');
 // Successful zero response must remain a real zero.
 await page.route('**/api/analytics/time-series?**',async route=>{
  const response=await route.fetch();const json=await response.json();
  for(const key of ['by_week','by_month','by_year'])for(const p of json[key])p.settlement_remainder=0;
  await route.fulfill({response,json});
 });
 await page.reload();await page.getByRole('button',{name:'All Time',exact:true}).click();
 await page.getByText('$0.00',{exact:true}).first().waitFor();
 check((await page.locator('main').innerText()).includes('Truck remaining\n$0.00'),'successful actual zero is displayed');
 check(await page.getByRole('alert').count()===0,'successful zero is not treated as failed');
 await page.unroute('**/api/analytics/time-series?**');
 // Delay all tenant A scoped reads; tenant B completes first with unique remaining.
 for(const oldFails of [false,true]){
  await switchTo('October synthetic');
  let release;let held=0;let completed=0;const gate=new Promise(resolve=>release=resolve);
  await page.route('**/api/**',async route=>{
   const req=route.request(),tenant=req.headers()['x-tenant-id'];
   if(tenant==='1'){
    held++;const response=await route.fetch();await gate;
    if(oldFails)await route.fulfill({status:503,contentType:'application/json',body:'{"detail":"old tenant failed"}'});
    else await route.fulfill({response});
    completed++;return;
   }
   if(tenant==='2'&&req.url().includes('/analytics/time-series')){
    const response=await route.fetch(),json=await response.json();
    for(const key of ['by_week','by_month','by_year'])for(const p of json[key])p.settlement_remainder=111;
    return route.fulfill({response,json});
   }
   return route.continue();
  });
  await page.reload();await page.getByRole('button',{name:'Current business: October synthetic. Switch business'}).waitFor();
  await switchTo('Unpaid synthetic');
  await page.getByRole('button',{name:'Monthly',exact:true}).first().click();
  await page.getByText('$222.00',{exact:true}).waitFor();
  check(held>0,'old tenant requests held before '+(oldFails?'failure':'success'));
  release();
  for(let i=0;i<100&&completed<held;i++)await new Promise(resolve=>setTimeout(resolve,20));
  await page.getByText('$222.00',{exact:true}).waitFor();
  check(!(await page.locator('main').innerText()).includes('$10,357.46'),'late old-tenant '+(oldFails?'failure':'success')+' cannot overwrite selected business');
  check((await page.locator('main').innerText()).includes('$3,200.00'),'old reserve response cannot overwrite tenant B reserve');
  await page.unroute('**/api/**');
 }
 await switchTo('Non-reserve synthetic');
 await page.getByRole('button',{name:'Monthly',exact:true}).first().click();
 await page.getByText('$10,357.46',{exact:true}).waitFor();
 let body=await page.locator('main').innerText();
 check(body.includes('$-100.00')&&body.includes('$52,873.98'),'negative custom credit visible while authoritative expense total reconciles');
 await page.getByRole('button',{name:'All Time',exact:true}).click();
 body=await page.locator('main').innerText();
 check(body.includes('$-100.00'),'negative custom credit remains visible all-time');
 check(writes.length===0,'error and race testing made no HTTP writes');
 check(errors.length===0,'failed report and diesel requests cause no uncaught browser errors');
 return {results,writes,errors};
}
