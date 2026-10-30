"""Password hashing, JWT session cookie and role dependencies."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import User
from app.db.session import get_session

COOKIE_NAME = "leaklens_session"
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])


async def current_user(request: Request, session: Annotated[AsyncSession, Depends(get_session)]) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise AppError(401, "unauthorized", "Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.PyJWTError as exc:
        raise AppError(401, "unauthorized", "Invalid or expired session") from exc
    user = await session.get(User, int(payload["sub"]))
    if user is None:
        raise AppError(401, "unauthorized", "User no longer exists")
    return user


def require_role(*roles: str):
    """Dependency factory. With no roles, any authenticated user passes."""

    async def _dep(user: Annotated[User, Depends(current_user)]) -> User:
        if roles and user.role not in roles:
            raise AppError(403, "forbidden", f"Requires role: {', '.join(roles)}")
        return user

    _dep.required_roles = roles  # type: ignore[attr-defined]
    return _dep


ANY_ROLE = require_role()
CurrentUser = Annotated[User, Depends(ANY_ROLE)]
