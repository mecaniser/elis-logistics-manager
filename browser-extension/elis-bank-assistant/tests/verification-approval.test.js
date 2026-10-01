import test from 'node:test';
import assert from 'node:assert/strict';
import {approveVerification, verificationReviewUrl, cancelVerificationReview} from '../verification-approval.js';
const draft={id:'draft-id',amount_cents:12345,from_last4:'2829',to_last4:'3304'};
const sender={tab:{id:81},url:'https://www.elisprotech.com/bank-monitor'};
function setup() {
 let listener;
 const chrome={runtime:{id:'extension',getURL:p=>'chrome-extension://extension/'+p,
 onMessage:{addListener:f=>{listener=f},removeListener:f=>{if(f===listener) listener=null}}}};
 const approval=approveVerification(chrome,draft,sender);
 const url=verificationReviewUrl(chrome,draft.id,sender);
 const nonce=new URL(url).searchParams.get('nonce');
 const frame={id:'extension',frameId:3,tab:{id:81},url};
 return {chrome,approval,url,nonce,frame,get listener(){return listener}};
}
test('review data and approval are bound to extension frame, tab, URL and one-use nonce',async()=>{
 const h=setup(); let replies=[];
 assert.equal(verificationReviewUrl(h.chrome,draft.id,{...sender,tab:{id:82}}),null);
 assert.equal(verificationReviewUrl(h.chrome,draft.id,{...sender,url:'https://evil.example/'}),null);
 const callback=h.listener;
 for(const frame of [{...h.frame,id:undefined},{...h.frame,frameId:0},{...h.frame,tab:{id:82}},{...h.frame,url:sender.url}]) {
   callback({action:'approve',nonce:h.nonce},frame,r=>replies.push(r));
   callback({action:'read-verification-review',nonce:h.nonce},frame,r=>replies.push(r));
 }
 callback({action:'approve',nonce:'wrong'},h.frame,r=>replies.push(r));
 assert.equal(replies.length,0);
 callback({action:'read-verification-review',nonce:h.nonce},h.frame,r=>replies.push(r));
 assert.equal(replies[0].draft,draft);
 callback({action:'approve',nonce:h.nonce},h.frame,r=>replies.push(r));
 await h.approval;
 assert.equal(h.listener,null);
 assert.equal(verificationReviewUrl(h.chrome,draft.id,sender),null);
 callback({action:'approve',nonce:h.nonce},h.frame,r=>replies.push(r));
 assert.equal(replies.length,2,'replayed approval ignored');
});
test('only initiating page can cancel; cancellation never authorizes',async()=>{
 const h=setup();
 assert.equal(cancelVerificationReview(draft.id,{...sender,tab:{id:82}}),false);
 assert.equal(cancelVerificationReview('other',sender),false);
 const rejection=assert.rejects(h.approval,{code:'VERIFICATION_REVIEW_CANCELED'});
 assert.equal(cancelVerificationReview(draft.id,sender),true);
 await rejection;
});
test('expired review cannot authorize even if timeout callback has not run',async t=>{
 const h=setup();
 t.mock.method(Date,'now',()=>Number.MAX_SAFE_INTEGER);
 const rejection=assert.rejects(h.approval,{code:'VERIFICATION_REVIEW_CANCELED'});
 let response;
 h.listener({action:'approve',nonce:h.nonce},h.frame,r=>{response=r});
 await rejection;
 assert.deepEqual(response,{ok:false});
});
