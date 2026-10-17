"""Account registration, verification, password access, and identity tokens."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import case, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from fashion_search.catalog.models import AuthRateLimit, AuthToken, User
from fashion_search.config.settings import Settings, get_settings
from fashion_search.core.db import get_engine

router = APIRouter(prefix="/auth", tags=["authentication"])


class Credentials(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class EmailRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    email: EmailStr


class TokenRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    token: str = Field(min_length=32, max_length=256)


class PasswordReset(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=256)


class GoogleIdentity(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    subject: str = Field(min_length=1, max_length=255)
    email: EmailStr


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        hashlib.scrypt(
            password.encode(), salt=b"vastraai-dummy-salt", n=2**14, r=8, p=1
        )
        return False
    try:
        algorithm, salt, expected = stored.split("$", 2)
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=2**14, r=8, p=1
        )
        return algorithm == "scrypt" and hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _rate_limit(action: str, email: str, *, limit: int, minutes: int) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=minutes)
    key = _token_hash(f"{action}:{email}")
    statement = insert(AuthRateLimit).values(key=key, attempts=1, window_start=now)
    statement = statement.on_conflict_do_update(
        index_elements=[AuthRateLimit.key],
        set_={
            "attempts": case(
                (AuthRateLimit.window_start < cutoff, 1),
                else_=AuthRateLimit.attempts + 1,
            ),
            "window_start": case(
                (AuthRateLimit.window_start < cutoff, now),
                else_=AuthRateLimit.window_start,
            ),
        },
    ).returning(AuthRateLimit.attempts)
    with Session(get_engine()) as session, session.begin():
        attempts = session.execute(statement).scalar_one()
    if attempts > limit:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(minutes * 60)},
        )


def _send_email(settings: Settings, *, recipient: str, subject: str, body: str) -> None:
    if not settings.auth_smtp_host or not settings.auth_email_from:
        raise HTTPException(status_code=503, detail="Email delivery is not configured")
    message = EmailMessage()
    message["From"] = settings.auth_email_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(
        settings.auth_smtp_host, settings.auth_smtp_port, timeout=10
    ) as smtp:
        if settings.auth_smtp_starttls:
            smtp.starttls()
        if settings.auth_smtp_username:
            smtp.login(settings.auth_smtp_username, settings.auth_smtp_password)
        smtp.send_message(message)


def _public_user(user: User) -> dict[str, str | int]:
    return {"id": user.id, "email": user.email, "auth_version": user.auth_version}


@router.post("/register", status_code=202)
def register(body: Credentials, settings: Settings = Depends(get_settings)):
    email = _normalize_email(str(body.email))
    _rate_limit("register", email, limit=3, minutes=60)
    raw_token = secrets.token_urlsafe(32)
    with Session(get_engine()) as session, session.begin():
        if session.scalar(select(User).where(User.email == email)) is not None:
            return {
                "message": "If this address can be registered, a verification email will be sent."
            }
        user = User(email=email, password_hash=_hash_password(body.password))
        session.add(user)
        session.flush()
        session.add(
            AuthToken(
                user_id=user.id,
                token_hash=_token_hash(raw_token),
                purpose="verify_email",
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )
        link = (
            f"{settings.auth_frontend_url.rstrip('/')}/verify-email?token={raw_token}"
        )
        _send_email(
            settings,
            recipient=email,
            subject="Verify your VastraAI account",
            body=f"Verify your email: {link}\nThis link expires in 24 hours.",
        )
    return {
        "message": "If this address can be registered, a verification email will be sent."
    }


@router.post("/verify-email")
def verify_email(body: TokenRequest):
    now = datetime.now(UTC)
    with Session(get_engine()) as session, session.begin():
        row = session.scalar(
            select(AuthToken)
            .where(
                AuthToken.token_hash == _token_hash(body.token),
                AuthToken.purpose == "verify_email",
                AuthToken.expires_at > now,
            )
            .with_for_update()
        )
        if row is None:
            raise HTTPException(
                status_code=400, detail="Verification link is invalid or expired"
            )
        user = session.get(User, row.user_id)
        if user is None:
            raise HTTPException(
                status_code=400, detail="Verification link is invalid or expired"
            )
        user.email_verified_at = now
        session.delete(row)
    return {"message": "Email verified. You can now sign in."}


@router.post("/verification/request", status_code=202)
def resend_verification(body: EmailRequest, settings: Settings = Depends(get_settings)):
    email = _normalize_email(str(body.email))
    _rate_limit("verify_request", email, limit=3, minutes=60)
    with Session(get_engine()) as session, session.begin():
        user = session.scalar(
            select(User).where(User.email == email, User.email_verified_at.is_(None))
        )
        if user is not None:
            session.execute(
                delete(AuthToken).where(
                    AuthToken.user_id == user.id, AuthToken.purpose == "verify_email"
                )
            )
            raw_token = secrets.token_urlsafe(32)
            session.add(
                AuthToken(
                    user_id=user.id,
                    token_hash=_token_hash(raw_token),
                    purpose="verify_email",
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
            )
            link = f"{settings.auth_frontend_url.rstrip('/')}/verify-email?token={raw_token}"
            _send_email(
                settings,
                recipient=email,
                subject="Verify your VastraAI account",
                body=f"Verify your email: {link}\nThis link expires in 24 hours.",
            )
    return {"message": "If this address needs verification, an email will be sent."}


@router.post("/login")
def login(body: Credentials, settings: Settings = Depends(get_settings)):
    email = _normalize_email(str(body.email))
    _rate_limit("login", email, limit=10, minutes=15)
    with Session(get_engine()) as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None or not _verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if user.email_verified_at is None:
            raise HTTPException(
                status_code=403, detail="Verify your email before signing in"
            )
        return _public_user(user)


@router.post("/password-reset/request", status_code=202)
def request_password_reset(
    body: EmailRequest, settings: Settings = Depends(get_settings)
):
    email = _normalize_email(str(body.email))
    _rate_limit("password_reset", email, limit=3, minutes=60)
    with Session(get_engine()) as session, session.begin():
        user = session.scalar(
            select(User).where(User.email == email, User.email_verified_at.is_not(None))
        )
        if user is not None:
            session.execute(
                delete(AuthToken).where(
                    AuthToken.user_id == user.id, AuthToken.purpose == "reset_password"
                )
            )
            raw_token = secrets.token_urlsafe(32)
            session.add(
                AuthToken(
                    user_id=user.id,
                    token_hash=_token_hash(raw_token),
                    purpose="reset_password",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            link = f"{settings.auth_frontend_url.rstrip('/')}/reset-password?token={raw_token}"
            _send_email(
                settings,
                recipient=email,
                subject="Reset your VastraAI password",
                body=f"Reset your password: {link}\nThis link expires in one hour.",
            )
    return {
        "message": "If the address has an eligible account, a reset email will be sent."
    }


@router.post("/password-reset/confirm")
def reset_password(body: PasswordReset):
    now = datetime.now(UTC)
    with Session(get_engine()) as session, session.begin():
        row = session.scalar(
            select(AuthToken)
            .where(
                AuthToken.token_hash == _token_hash(body.token),
                AuthToken.purpose == "reset_password",
                AuthToken.expires_at > now,
            )
            .with_for_update()
        )
        if row is None:
            raise HTTPException(
                status_code=400, detail="Reset link is invalid or expired"
            )
        user = session.get(User, row.user_id)
        if user is None or user.email_verified_at is None:
            raise HTTPException(
                status_code=400, detail="Reset link is invalid or expired"
            )
        user.password_hash = _hash_password(body.password)
        user.auth_version += 1
        session.execute(
            delete(AuthToken).where(
                AuthToken.user_id == user.id, AuthToken.purpose == "reset_password"
            )
        )
    return {"message": "Password reset. You can now sign in."}


@router.post("/google")
def google_account(
    body: GoogleIdentity,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
):
    if (
        not settings.auth_jwt_secret
        or not authorization
        or not authorization.startswith("Bearer ")
    ):
        raise HTTPException(status_code=401, detail="Invalid service identity")
    try:
        claims = jwt.decode(
            authorization[7:],
            settings.auth_jwt_secret,
            algorithms=["HS256"],
            audience=settings.auth_jwt_audience,
            issuer=settings.auth_jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid service identity") from exc
    if claims.get("scope") != "account:sync" or claims.get("sub") != "nextauth":
        raise HTTPException(status_code=403, detail="Invalid service identity")
    email = _normalize_email(str(body.email))
    with Session(get_engine()) as session, session.begin():
        user = session.scalar(
            select(User).where(User.google_subject == body.subject).with_for_update()
        )
        if user is None:
            user = session.scalar(
                select(User).where(User.email == email).with_for_update()
            )
        if user is not None and user.email != email:
            raise HTTPException(
                status_code=409,
                detail="This Google account is linked to a different email",
            )
        if user is None:
            user = User(
                email=email,
                google_subject=body.subject,
                email_verified_at=datetime.now(UTC),
            )
            session.add(user)
        elif user.google_subject not in (None, body.subject):
            raise HTTPException(
                status_code=409, detail="This email is linked to another Google account"
            )
        else:
            user.google_subject = body.subject
            user.email_verified_at = user.email_verified_at or datetime.now(UTC)
        session.flush()
        return _public_user(user)
