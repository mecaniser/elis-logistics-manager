"""
Auth router for session-based login/logout.
"""
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel
import os

from app.auth_utils import (
    SESSION_COOKIE_NAME,
    SESSION_DURATION_SECONDS,
    create_session_token,
    verify_session_token,
)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(data: LoginRequest, response: Response):
    """
    Validate credentials and issue a signed session cookie.
    """
    expected_user = os.getenv("APP_AUTH_USERNAME")
    expected_pass = os.getenv("APP_AUTH_PASSWORD")

    if not (expected_user and expected_pass):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured on the server.",
        )

    if data.username != expected_user or data.password != expected_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_session_token(data.username)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to issue session token.",
        )

    secure_cookie = os.getenv("APP_AUTH_COOKIE_SECURE", "false").lower() == "true"

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=secure_cookie,
        max_age=SESSION_DURATION_SECONDS,
        path="/",
    )
    return {"message": "Login successful"}


@router.post("/logout")
async def logout(response: Response):
    """
    Clear session cookie.
    """
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )
    return {"message": "Logged out"}


@router.get("/me")
async def me(request: Request):
    """
    Return authenticated user based on session cookie.
    """
    # The API middleware deliberately allows unauthenticated local development
    # when credentials have not been configured.  Return the same state here
    # so the frontend does not strand local users on the login screen.
    if not (os.getenv("APP_AUTH_USERNAME") and os.getenv("APP_AUTH_PASSWORD")):
        return {"username": "local-dev", "authentication_enabled": False}

    token = request.cookies.get(SESSION_COOKIE_NAME)
    valid, username = verify_session_token(token) if token else (False, None)

    if not valid or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return {"username": username}
