const {approval}=await chrome.storage.session.get('approval');
const approve=document.querySelector('#approve');
const cancel=document.querySelector('#cancel');
const status=document.querySelector('#status');

function setText(selector,value) { document.querySelector(selector).textContent=value; }
function finish(action) {
  approve.disabled=true;
  cancel.disabled=true;
  setText('#approve-label',action==='approve' ? 'Opening Truliant…' : 'Canceling…');
  status.textContent=action==='approve' ? 'Approval recorded. Preparing the bank form…' : '';
  chrome.runtime.sendMessage({action,nonce:approval.nonce},response=>{
    if(chrome.runtime.lastError || !response?.ok) {
      status.textContent='The request could not be completed. Return to ELIS and try again.';
      cancel.disabled=false;
    }
  });
}

if(approval?.draft) {
  const d=approval.draft;
  if(approval.mode==='verify') {
    setText('#heading','Review transfer verification');
    setText('#intro','This approval opens both transaction histories.');
    setText('#safety-copy','The check is read-only. It cannot prepare, submit, or schedule a transfer.');
    setText('#approve-label','Approve history check');
    document.querySelector('.current-label').textContent='Approve verification';
    document.querySelector('.final-label').textContent='Confirm posted entries';
  }
  setText('#from',`••${d.from_last4}`);
  setText('#to',`••${d.to_last4}`);
  setText('#amount',(d.amount_cents/100).toLocaleString('en-US',{style:'currency',currency:'USD'}));
  setText('#memo',d.memo);
  approve.disabled=false;
  const expiresAt=approval.expires_at || Date.now()+120000;
  const tick=()=>{
    const remaining=Math.max(0,Math.ceil((expiresAt-Date.now())/1000));
    setText('#countdown',`${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}`);
    if(!remaining) {
      clearInterval(timer);
      approve.disabled=true;
      setText('#expiry','This review expired. Return to ELIS and prepare the draft again.');
      status.textContent='No bank form was opened.';
    }
  };
  const timer=setInterval(tick,1000);
  tick();
  approve.addEventListener('click',()=>finish('approve'));
  cancel.addEventListener('click',()=>finish('cancel'));
} else {
  setText('#heading','Review expired');
  setText('#intro','This approval request is no longer active.');
  setText('#safety-copy','Return to ELIS and select Prepare in Truliant again.');
  setText('#expiry','No bank form was opened.');
  status.textContent='You can close this window.';
  cancel.textContent='Close';
  cancel.addEventListener('click',()=>window.close());
}
