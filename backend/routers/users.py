from fastapi import APIRouter
from sqlalchemy import select

from ..auth import get_user_roles
from ..deps import CurrentUser, DBSession
from ..models import User
from ..schemas import UserMeOut, UserOut

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=UserMeOut)
async def me(session: DBSession, user: CurrentUser) -> UserMeOut:
    role_map = await get_user_roles(session, user)
    global_roles = role_map.pop("global", [])
    return UserMeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=global_roles,
        case_roles=role_map,
    )


@router.get("/users", response_model=list[UserOut])
async def list_users(session: DBSession, _: CurrentUser) -> list[UserOut]:
    res = await session.execute(select(User).order_by(User.created_at.desc()).limit(500))
    return [UserOut.model_validate(u) for u in res.scalars().all()]
