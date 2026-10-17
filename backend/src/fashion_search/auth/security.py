"""Verification of short-lived identity tokens issued by the Next.js BFF."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from fashion_search.catalog.models import User
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.db import get_engine

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    if credentials is None or not settings.auth_jwt_secret:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.auth_jwt_secret,
            algorithms=["HS256"],
            audience=settings.auth_jwt_audience,
            issuer=settings.auth_jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired identity"
        ) from exc
    if claims.get("scope") is not None:
        raise HTTPException(status_code=401, detail="Invalid user identity")
    with Session(get_engine()) as session:
        user = session.get(User, claims.get("sub"))
        if (
            user is None
            or user.email_verified_at is None
            or claims.get("sv") != user.auth_version
        ):
            raise HTTPException(status_code=401, detail="Account is unavailable")
        user_data = User(
            id=user.id,
            email=user.email,
            email_verified_at=user.email_verified_at,
        )
    return user_data


def admin_user(
    user: Annotated[User, Depends(current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    allowlist = {
        item.strip().casefold()
        for item in settings.auth_admin_emails.split(",")
        if item.strip()
    }
    if user.email.casefold() not in allowlist:
        raise HTTPException(status_code=404, detail="Not found")
    return user
