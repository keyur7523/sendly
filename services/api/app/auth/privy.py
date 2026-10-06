"""Privy access-token verification (PRD Section 11.2, AUTH-01).

Privy access tokens are ES256 JWTs with iss "privy.io", aud = app ID, sub = Privy DID.
"""

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings

ISSUER = "privy.io"
ALGORITHMS = ["ES256"]


@dataclass(frozen=True)
class AuthenticatedUser:
    privy_did: str
    session_id: str | None


class InvalidToken(Exception):
    pass


def verify_access_token(token: str, *, app_id: str, verification_key: str) -> AuthenticatedUser:
    try:
        claims = jwt.decode(
            token,
            verification_key,
            algorithms=ALGORITHMS,
            audience=app_id,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    return AuthenticatedUser(privy_did=claims["sub"], session_id=claims.get("sid"))


def current_user(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "AUTH_REQUIRED"})
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return verify_access_token(
            token, app_id=settings.privy_app_id, verification_key=settings.privy_verification_key
        )
    except InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={"code": "AUTH_REQUIRED"}) from None


CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]
