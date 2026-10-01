import test from 'node:test';
import assert from 'node:assert/strict';
import {approveVerification, verificationReview, confirmVerificationReview, cancelVerificationReview} from '../verification-approval.js';
const draft={id:'draft-id',amount_cents:12345,from_last4:'2829',to_last4:'3304'};
const sender={frameId:0,tab:{id:81},url:'https://www.elisprotech.com/bank-monitor'};
function setup() {
 const approval=approveVerification(draft,sender);
 const review=verificationReview(draft.id,sender);
 return {approval,review};
}
test('read-only confirmation is bound to top-level origin, tab, draft and one-use nonce',async()=>{
 const h=setup();
 for(const other of [{...sender,tab:{id:82}},{...sender,frameId:2},{...sender,url:'https://evil.example/'}]) {
   assert.equal(verificationReview(draft.id,other),null);
   assert.equal(confirmVerificationReview(draft.id,h.review.nonce,other),false);
 }
 assert.equal(confirmVerificationReview('other',h.review.nonce,sender),false);
 assert.equal(confirmVerificationReview(draft.id,'wrong',sender),false);
 assert.equal(verificationReview(draft.id,sender).draft,draft);
 assert.equal(confirmVerificationReview(draft.id,h.review.nonce,sender),true);
 await h.approval;
 assert.equal(verificationReview(draft.id,sender),null);
 assert.equal(confirmVerificationReview(draft.id,h.review.nonce,sender),false);
});
test('only initiating page can cancel; cancellation never authorizes',async()=>{
 const h=setup();
 assert.equal(cancelVerificationReview(draft.id,{...sender,tab:{id:82}}),false);
 assert.equal(cancelVerificationReview('other',sender),false);
 const rejection=assert.rejects(h.approval,{code:'VERIFICATION_REVIEW_CANCELED'});
 assert.equal(cancelVerificationReview(draft.id,sender),true);
 await rejection;
});
test('expired review cannot authorize even before its timeout callback runs',async t=>{
 const h=setup();
 t.mock.method(Date,'now',()=>Number.MAX_SAFE_INTEGER);
 const rejection=assert.rejects(h.approval,{code:'VERIFICATION_REVIEW_CANCELED'});
 assert.equal(confirmVerificationReview(draft.id,h.review.nonce,sender),false);
 await rejection;
});
