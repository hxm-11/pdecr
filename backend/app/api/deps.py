from collections.abc import Generator
from typing import Annotated, Optional
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[Optional[str], Depends(reusable_oauth2)]


def _get_default_user(session: Session) -> User | None:
    """Look up the default system user (FIRST_SUPERUSER) when no auth token is provided."""
    return session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    if token is None:
        user = _get_default_user(session)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No default user found — please run init_db first",
            )
        return user

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        # Fall back to default user on invalid token
        user = _get_default_user(session)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No default user found — please run init_db first",
            )
        return user

    user = session.get(User, uuid.UUID(token_data.sub))
    if not user:
        user = _get_default_user(session)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
