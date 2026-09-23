"""Canonical accounting error envelopes and request correlation."""
from uuid import uuid4
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from starlette.exceptions import HTTPException


def is_accounting(request):
    return request.url.path.startswith(('/api/v1/accounting', '/api/accounting'))


def error_response(request, status, code, message, fields=None):
    trace = getattr(request.state, 'trace_id', str(uuid4()))
    return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message, 'status': status, 'trace_id': trace, 'field_errors': fields or [], 'meta': {}}}, headers={'X-Request-ID': trace})


def install(app):
    @app.middleware('http')
    async def trace(request: Request, call_next):
        request.state.trace_id = str(uuid4())
        response = await call_next(request)
        if is_accounting(request):
            response.headers['X-Request-ID'] = request.state.trace_id
            response.headers['Cache-Control'] = 'private, no-store'
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if not is_accounting(request): return await http_exception_handler(request, exc)
        detail = exc.detail
        code = detail.get('code', 'REQUEST_FAILED') if isinstance(detail, dict) else 'REQUEST_FAILED'
        message = detail.get('message', 'Request failed.') if isinstance(detail, dict) else str(detail)
        if exc.status_code == 404: code, message = 'RESOURCE_NOT_FOUND', 'Resource not found.'
        return error_response(request, exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if not is_accounting(request): return await request_validation_exception_handler(request, exc)
        invalid_tenant = any('tenant_id' in str(e['loc']) for e in exc.errors())
        fields = [{'field': '.'.join(str(x) for x in e['loc']), 'code': e['type'], 'message': e['msg']} for e in exc.errors()]
        return error_response(request, 400 if invalid_tenant else 422, 'TENANT_CONTEXT_INVALID' if invalid_tenant else 'VALIDATION_FAILED', 'Business scope cannot be supplied in the body.' if invalid_tenant else 'Check the indicated fields.', fields)
