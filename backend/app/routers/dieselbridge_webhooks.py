"""Public URL with its own HMAC boundary; it never accepts a tenant selector."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from app.database import get_db
from app.services import dieselbridge_financial_events as events

router = APIRouter()


def _commit(db,slug,body,headers):
    try:
        result = events.receive_event(db,slug,body,headers)
        from app.services.dieselbridge_signal import notify
        notify(db)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.post('/webhooks/{slug}',status_code=202)
async def financial_wakeup(slug: str,request: Request,db: Session=Depends(get_db)):
    if request.query_params or 'x-tenant-id' in request.headers:
        events.fail(400,'INVALID_EVENT','Notification scope is server configured.')
    if request.headers.get('content-type','').split(';',1)[0].strip().lower() != 'application/json':
        events.fail(415,'INVALID_EVENT','Use application/json for notifications.')
    headers = {}
    for name in ('x-dbn-event-id','x-dbn-timestamp','x-dbn-signature'):
        values = request.headers.getlist(name)
        if len(values) != 1 or len(values[0]) > 128:
            events.fail(400,'INVALID_EVENT','Provide one notification authentication header of each type.')
        headers[name] = values[0]
    lengths = request.headers.getlist('content-length')
    if len(lengths) > 1:
        events.fail(400,'INVALID_EVENT','Provide one notification length.')
    length = lengths[0] if lengths else None
    if length and (not length.isascii() or not length.isdigit()):
        events.fail(400,'INVALID_EVENT','Invalid notification length.')
    if length and (len(length) > 8 or int(length) > events.MAX_BODY_BYTES):
        events.fail(413,'EVENT_TOO_LARGE','Notification exceeds the supported size.')
    body = bytearray()
    async for chunk in request.stream():
        if len(body)+len(chunk) > events.MAX_BODY_BYTES:
            events.fail(413,'EVENT_TOO_LARGE','Notification exceeds the supported size.')
        body.extend(chunk)
    result = await run_in_threadpool(_commit,db,slug,bytes(body),headers)
    # Wake only after durable commit and successful HMAC/scope validation.
    wake = getattr(request.app.state,'dbn_financial_worker_wake',None)
    if wake is not None:wake.set()
    return result
