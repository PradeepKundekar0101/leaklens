from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import LOGIN_LIMIT, limiter
from app.core.security import ANY_ROLE, COOKIE_NAME, CurrentUser, create_token, verify_password
from app.db.models import User
from app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    # Plain string: internal domains like .local are valid accounts here, and lookup is exact anyway.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def _normalise(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str


def _user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, name=user.name, role=user.role)


@router.post("/login", response_model=UserOut)
@limiter.limit(LOGIN_LIMIT)
async def login(
    request: Request, body: LoginIn, response: Response, session: Annotated[AsyncSession, Depends(get_session)]
) -> UserOut:
    user = (await session.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Invalid email or password")
    settings = get_settings()
    response.set_cookie(
        COOKIE_NAME,
        create_token(user),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    await audit.log(session, user, "login", "user", user.id)
    await session.commit()
    return _user_out(user)


@router.post("/logout", dependencies=[Depends(ANY_ROLE)])
async def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return _user_out(user)
