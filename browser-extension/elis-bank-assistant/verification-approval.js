// Only read-only history authorization can be embedded. Preparation approval
// remains in the private, top-level extension window.
let pending = null;

const ownsReview = (review, id, sender) => review?.draft.id === id
  && review.tabId === sender.tab?.id && review.origin === new URL(sender.url).origin;

export function verificationReviewUrl(chrome, id, sender) {
  return ownsReview(pending, id, sender) ? pending.url : null;
}

export function cancelVerificationReview(id, sender) {
  if (!ownsReview(pending, id, sender)) return false;
  pending.finish(false);
  return true;
}

export function approveVerification(chrome, draft, sender) {
  if (pending) return Promise.reject(new Error('Another history review is open.'));
  return new Promise((resolve, reject) => {
    const nonce = crypto.randomUUID();
    const url = `${chrome.runtime.getURL('verify.html')}?nonce=${nonce}`;
    const expiresAt = Date.now() + 120000;
    let finished = false;
    const review = { draft, tabId: sender.tab.id, origin: new URL(sender.url).origin, url, finish };
    function finish(approved) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      chrome.runtime.onMessage.removeListener(listener);
      pending = null;
      approved ? resolve() : reject(Object.assign(new Error('History review canceled or expired. Select Check completion to try again.'), { code: 'VERIFICATION_REVIEW_CANCELED' }));
    }
    function listener(message, frame, reply) {
      // An ELIS page cannot send an approval. It must come from this extension's
      // isolated review frame, in the initiating tab, with the one-use nonce.
      if (finished || frame.id !== chrome.runtime.id || frame.tab?.id !== review.tabId
        || !(frame.frameId > 0) || frame.url !== url || message?.nonce !== nonce) return;
      if (Date.now() >= expiresAt) { reply({ ok: false }); finish(false); return; }
      if (message.action === 'read-verification-review') {
        reply({ ok: true, draft, expiresAt });
      } else if (['approve', 'cancel'].includes(message.action)) {
        reply({ ok: true });
        finish(message.action === 'approve');
      }
    }
    const timer = setTimeout(() => finish(false), 120000);
    pending = review;
    chrome.runtime.onMessage.addListener(listener);
  });
}
