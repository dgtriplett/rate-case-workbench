"""FastAPI dependencies."""
from typing import Annotated, AsyncIterator, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import get_user_roles, resolve_current_user
from .db import session_scope
from .models import RoleKey, User


async def db_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


DBSession = Annotated[AsyncSession, Depends(db_session)]


async def current_user(
    session: DBSession,
    x_forwarded_email: Optional[str] = Header(default=None),
    x_forwarded_user: Optional[str] = Header(default=None),
    x_forwarded_preferred_username: Optional[str] = Header(default=None),
) -> User:
    return await resolve_current_user(
        session, x_forwarded_email, x_forwarded_user, x_forwarded_preferred_username
    )


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(role: RoleKey):
    async def _inner(user: CurrentUser, session: DBSession) -> User:
        roles = await get_user_roles(session, user)
        if role.value in roles.get("global", []) or RoleKey.admin.value in roles.get("global", []):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires role: {role.value}",
        )

    return _inner


RequireAdmin = Annotated[User, Depends(require_role(RoleKey.admin))]
RequireCaseManager = Annotated[User, Depends(require_role(RoleKey.case_manager))]
RequireReviewer = Annotated[User, Depends(require_role(RoleKey.reviewer))]
RequireApprover = Annotated[User, Depends(require_role(RoleKey.approver))]
