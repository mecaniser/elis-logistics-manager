const {approval}=await chrome.storage.session.get('approval');
if(approval) {
  const d=approval.draft;
  document.querySelector('#details').textContent=`From: ••${d.from_last4}\nTo: ••${d.to_last4}\nAmount: $${(d.amount_cents/100).toFixed(2)}\nMemo: ${d.memo}`;
  document.querySelector('#approve').disabled=false;
  for(const action of ['approve','cancel']) document.querySelector(`#${action}`).addEventListener('click',()=>{
    document.querySelector('#approve').disabled=true;
    chrome.runtime.sendMessage({action,nonce:approval.nonce});
  });
} else document.querySelector('#details').textContent='This preparation request has expired. Return to ELIS.';
