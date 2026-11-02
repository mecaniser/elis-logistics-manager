async (page) => {
 await page.unrouteAll();
 const business=page.getByRole('button',{name:/Current business:.*Switch business/});
 if(!(await business.getAttribute('aria-label')).includes('October synthetic')){
  await business.click();await page.getByText('October synthetic',{exact:true}).click();
 }

 const results=[]; const writes=[]; const external=[]; const errors=[];
 page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.method()+' '+r.url())});
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!=='http://127.0.0.1:8766'){external.push(u.origin);return route.abort()}return route.continue()});
 const before=await (await page.request.get('http://127.0.0.1:8766/api/qa/invariants')).json();
 const check=(ok,name)=>{if(!ok)throw Error(name);results.push(name)};
 await page.setViewportSize({width:1440,height:1000});
 await page.reload();
 await page.getByRole('button',{name:'Monthly',exact:true}).first().click();
 await page.getByText('$10,357.46',{exact:true}).waitFor();
 let body=await page.locator('main').innerText();
 check(body.includes('$7,478.78')&&body.includes('$2,878.68')&&body.includes('$52,873.98'),'October monthly reconciliation');
 check(body.includes('Fleet Manager Support')&&body.includes('$400.00')&&body.includes('Custom Expenses')&&body.includes('$100.00'),'support and custom already deducted, visible in breakdown');
 await page.getByText('Settlements Included (this month): 1',{exact:false}).click();
 body=await page.locator('main').innerText();
 check(body.includes('9/28/2026')&&!body.includes('9/27/2026'),'date-only September 28 remains September 28');
 await page.screenshot({path:'output/playwright/october-desktop.png',fullPage:true});
 for(const view of ['Yearly','All Time','Monthly']){
  await page.getByRole('button',{name:view,exact:true}).first().click();
  await page.getByText('$10,357.46',{exact:true}).waitFor();
  check((await page.locator('main').innerText()).includes('$7,478.78'),view+' remaining consistent');
 }
 const scenarios=[['Unpaid synthetic','$3,200.00','$0.00'],['Partial synthetic','$3,000.00','$200.00'],['Non-reserve synthetic','$3,200.00','$0.00'],['Negative reserve synthetic','$-800.00','$4,000.00']];
 for(const [name,balance,withdrawal] of scenarios){
  await page.getByRole('button',{name:/Current business:.*Switch business/}).click();
  await page.getByText(name,{exact:true}).click();
  await page.getByRole('button',{name:'Monthly',exact:true}).first().click();
  await page.getByText('$10,357.46',{exact:true}).waitFor();
  await page.getByText(balance,{exact:true}).first().waitFor();
  const reserve=await page.getByRole('region',{name:'Recorded reserve withdrawals'}).count();
  body=await page.locator('main').innerText();
  check(body.includes(balance)&&body.includes(withdrawal)&&body.includes('$8,056.76'),name+' balances, invoice visibility and unchanged remaining');
 }
 await page.setViewportSize({width:390,height:844});
 await page.reload();
 await page.getByRole('button',{name:'Monthly',exact:true}).first().click();
 await page.getByText('$10,357.46',{exact:true}).waitFor();
 check(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),'mobile no horizontal page overflow');
 await page.screenshot({path:'output/playwright/negative-mobile.png',fullPage:true});
 for(let i=0;i<3;i++){
  await page.getByRole('button',{name:'Yearly',exact:true}).first().click();
  await page.getByText('$10,357.46',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Monthly',exact:true}).first().click();
  await page.getByText('$10,357.46',{exact:true}).waitFor();
 }
 check((await page.locator('main').innerText()).includes('$-800.00'),'repeated mobile period navigation preserves negative reserve');
 const after=await (await page.request.get('http://127.0.0.1:8766/api/qa/invariants')).json();
 check(JSON.stringify(before)===JSON.stringify(after),'synthetic record counts unchanged');
 check(writes.length===0,'no HTTP writes');check(external.length===0,'no external requests');check(errors.length===0,'no uncaught browser errors');
 return {results,before,after,writes,external,errors};
}
