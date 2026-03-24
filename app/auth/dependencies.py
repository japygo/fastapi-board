# app/auth/dependencies.py
# 인증 의존성 (비동기 버전)
#
# [Spring Security 비교]
# Spring: SecurityFilterChain + JwtAuthenticationFilter
# FastAPI: Depends(get_current_user) 로 선택적으로 인증 적용
#
# [Before → After]
# Before: def get_current_user(..., db: Session = Depends(get_db))
#         user = db.execute(...).scalar_one_or_none()
# After:  async def get_current_user(..., db: AsyncSession = Depends(get_db))
#         user = await db.execute(...).scalar_one_or_none()   ← await

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # Session → AsyncSession

from app.database import get_db
from app.domain.user import User
from app.auth.jwt import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),  # Session → AsyncSession
) -> User:
    """
    현재 인증된 사용자를 반환하는 의존성 함수 (비동기 버전)

    [Before → After]
    Before: def get_current_user(...): user = db.execute(...).scalar_one_or_none()
    After:  async def get_current_user(...):
                result = await db.execute(...)    ← await
                user = result.scalar_one_or_none()

    Spring Security 비교:
        @PreAuthorize("isAuthenticated()") 와 동일한 효과
    """
    payload = decode_access_token(token)
    username: str = payload.get("sub")

    result = await db.execute(  # ← await
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """활성화된 사용자만 허용하는 의존성 (역할 기반 접근 제어 확장 지점)"""
    return current_user
