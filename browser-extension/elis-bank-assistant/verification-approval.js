// In-page approval authorizes only a read-only history check. Bank preparation
// still requires the private extension-owned approval window.
let pending = null;
const ownsReview = (review, id, sender) => review?.draft.id === id
  && sender.frameId === 0 && review.tabId === sender.tab?.id
  && review.origin === new URL(sender.url).origin;

export function verificationReview(id, sender) {
  if (!ownsReview(pending, id, sender)) return null;
  return {draft:pending.draft, nonce:pending.nonce, expires_at:pending.expiresAt};
}

export function cancelVerificationReview(id, sender) {
  if (!ownsReview(pending, id, sender)) return false;
  pending.finish(false);
  return true;
}

export function confirmVerificationReview(id, nonce, sender) {
  if (!ownsReview(pending, id, sender) || nonce !== pending.nonce) return false;
  if (Date.now() >= pending.expiresAt) { pending.finish(false); return false; }
  pending.finish(true);
  return true;
}

export function approveVerification(draft, sender) {
  if (pending) return Promise.reject(new Error('Another history review is open.'));
  return new Promise((resolve, reject) => {
    let finished = false;
    function finish(approved) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      pending = null;
      approved ? resolve() : reject(Object.assign(new Error('History review canceled or expired. Select Check completion to try again.'), {code:'VERIFICATION_REVIEW_CANCELED'}));
    }
    const timer = setTimeout(() => finish(false), 120000);
    pending = {draft, nonce:crypto.randomUUID(), expiresAt:Date.now()+120000,
      tabId:sender.tab.id, origin:new URL(sender.url).origin, finish};
  });
}
