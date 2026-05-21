"""Authentication: Databricks Apps forwards user identity headers (X-Forwarded-Email, X-Forwarded-User, X-Forwarded-Preferred-Username).

Resolves the request to a User row in Lakebase, auto-provisioning on first sight. Falls back to a dev user when running locally without the headers.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Role, RoleKey, User, UserRole

log = logging.getLogger(__name__)

DEV_EMAIL = os.environ.get("RCW_DEV_EMAIL", "drew.triplett@databricks.com")
DEV_NAME = os.environ.get("RCW_DEV_NAME", "Drew Triplett (Dev)")


ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("RCW_ADMIN_EMAILS", "drew.triplett@databricks.com").split(",")
    if e.strip()
}


async def get_or_create_user(
    session: AsyncSession,
    email: str,
    display_name: Optional[str] = None,
) -> User:
    from .models import Role, RoleKey, UserRole

    res = await session.execute(select(User).where(User.email == email))
    user = res.scalar_one_or_none()
    if user is not None:
        return user
    user = User(email=email, display_name=display_name or email.split("@")[0])
    session.add(user)
    await session.flush()
    log.info("Auto-provisioned user %s", email)

    # Grant admin if email is in the allowlist
    if email.lower() in ADMIN_EMAILS:
        rres = await session.execute(select(Role).where(Role.key == RoleKey.admin))
        role = rres.scalar_one_or_none()
        if role:
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.flush()
            log.info("Granted admin to %s", email)
    return user


def _email_to_display_name(email: str) -> str:
    local = email.split("@")[0]
    # turn "drew.triplett" into "Drew Triplett"
    return " ".join(p.capitalize() for p in local.replace("_", ".").split(".") if p)


def _looks_like_uuid(value: str) -> bool:
    import re
    return bool(re.fullmatch(r"[0-9a-fA-F-]{32,40}", value))


def _extract_identity(
    x_forwarded_email: Optional[str],
    x_forwarded_user: Optional[str],
    x_forwarded_preferred_username: Optional[str],
) -> tuple[str, str]:
    email = x_forwarded_email or x_forwarded_preferred_username
    if not email and not os.environ.get("DATABRICKS_APP_NAME"):
        # local dev fallback
        return DEV_EMAIL, DEV_NAME
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No user identity")
    # If x_forwarded_user is a UUID (which Databricks Apps sometimes provides),
    # derive a friendly name from the email instead.
    if x_forwarded_user and not _looks_like_uuid(x_forwarded_user):
        name = x_forwarded_user
    else:
        name = _email_to_display_name(email)
    return email, name


async def resolve_current_user(
    session: AsyncSession,
    x_forwarded_email: Optional[str] = Header(default=None),
    x_forwarded_user: Optional[str] = Header(default=None),
    x_forwarded_preferred_username: Optional[str] = Header(default=None),
) -> User:
    email, name = _extract_identity(x_forwarded_email, x_forwarded_user, x_forwarded_preferred_username)
    return await get_or_create_user(session, email, name)


async def get_user_roles(session: AsyncSession, user: User) -> dict[str, list[str]]:
    """Returns {"global": [...role keys], "<case_id>": [...]}"""
    res = await session.execute(
        select(UserRole, Role).join(Role, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)
    )
    out: dict[str, list[str]] = {"global": []}
    for ur, role in res.all():
        bucket = str(ur.case_id) if ur.case_id else "global"
        out.setdefault(bucket, []).append(role.key.value)
    return out


def has_role(role_map: dict[str, list[str]], required: RoleKey, case_id: Optional[str] = None) -> bool:
    if required.value in role_map.get("global", []):
        return True
    if RoleKey.admin.value in role_map.get("global", []):
        return True
    if case_id and required.value in role_map.get(case_id, []):
        return True
    return False
