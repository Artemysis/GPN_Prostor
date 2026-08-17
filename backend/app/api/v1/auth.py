from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.db.models import User
from app.schemas.analytics import AuthLoginRequest, AuthLoginResponse, MeResponse, UserOut

router = APIRouter()


@router.post("/auth/login", response_model=AuthLoginResponse)
async def login(body: AuthLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(username=body.username, full_name=body.username, role="customer")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id, user.username, user.role)
    return AuthLoginResponse(
        access_token=token,
        user=UserOut(id=str(user.id), username=user.username, role=user.role),
    )


@router.get("/auth/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    return MeResponse(user=UserOut(id=str(user.id), username=user.username, role=user.role))
