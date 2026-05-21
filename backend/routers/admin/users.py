from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ...auth import get_or_create_user
from ...deps import DBSession, RequireAdmin
from ...models import Role, RoleKey, User, UserRole
from ...schemas import UserOut

router = APIRouter(prefix="/users", tags=["admin-users"])


class InviteUser(BaseModel):
    email: str
    display_name: str


class GrantRole(BaseModel):
    role: str  # RoleKey value
    case_id: Optional[uuid.UUID] = None


@router.get("", response_model=list[UserOut])
async def list_all_users(session: DBSession, _: RequireAdmin) -> list[UserOut]:
    res = await session.execute(select(User).order_by(User.created_at.desc()))
    return [UserOut.model_validate(u) for u in res.scalars().all()]


@router.post("", response_model=UserOut, status_code=201)
async def invite_user(body: InviteUser, session: DBSession, _: RequireAdmin) -> UserOut:
    u = await get_or_create_user(session, body.email, body.display_name)
    return UserOut.model_validate(u)


@router.post("/{user_id}/roles")
async def grant_role(
    user_id: uuid.UUID, body: GrantRole, session: DBSession, _: RequireAdmin
) -> dict:
    rkres = await session.execute(select(Role).where(Role.key == RoleKey(body.role)))
    role = rkres.scalar_one_or_none()
    if not role:
        raise HTTPException(400, f"unknown role: {body.role}")
    existing = await session.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role.id,
            UserRole.case_id == body.case_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        session.add(UserRole(user_id=user_id, role_id=role.id, case_id=body.case_id))
        await session.flush()
    return {"granted": True, "role": body.role, "case_id": str(body.case_id) if body.case_id else None}


@router.delete("/{user_id}/roles/{role}")
async def revoke_role(
    user_id: uuid.UUID, role: str, session: DBSession, _: RequireAdmin, case_id: Optional[uuid.UUID] = None
) -> dict:
    rkres = await session.execute(select(Role).where(Role.key == RoleKey(role)))
    rec = rkres.scalar_one_or_none()
    if not rec:
        return {"revoked": False}
    res = await session.execute(
        select(UserRole).where(
            UserRole.user_id == user_id, UserRole.role_id == rec.id, UserRole.case_id == case_id
        )
    )
    ur = res.scalar_one_or_none()
    if ur:
        await session.delete(ur)
        await session.flush()
    return {"revoked": True}
