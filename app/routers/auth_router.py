# app/routers/auth_router.py
# 인증 API 라우터 (비동기 버전)
#
# [Before → After]
# Before: def register(..., db: Session = Depends(get_db))
# After:  async def register(..., db: AsyncSession = Depends(get_db))
#
# Spring Security 비교:
#   - /api/auth/register → 회원가입
#   - /api/auth/login    → 로그인 (JWT 발급)
#   - /api/auth/me       → 내 정보 조회 (인증 필요)

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # Session → AsyncSession

from app.database import get_db
from app.domain.user import User
from app.auth.password import hash_password, verify_password
from app.auth.jwt import create_access_token
from app.auth.dependencies import get_current_active_user
from app.schemas.auth import UserRegisterRequest, UserResponse, TokenResponse

router = APIRouter(
    prefix="/api/auth",
    tags=["인증"],
)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="회원가입")
async def register(  # def → async def
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),  # Session → AsyncSession
):
    """
    새 사용자를 등록합니다.

    [Before → After]
    Before: def register(...): existing = db.execute(...).scalar_one_or_none()
    After:  async def register(...):
                result = await db.execute(...)    ← await
                existing = result.scalar_one_or_none()
    """
    result = await db.execute(  # ← await
        select(User).where(User.username == request.username)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 사용 중인 아이디입니다: {request.username}",
        )

    user = User(
        username=request.username,
        hashed_password=hash_password(request.password),
    )
    db.add(user)
    await db.commit()   # ← await
    await db.refresh(user)  # ← await
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="로그인 (JWT 발급)")
async def login(  # def → async def
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),  # Session → AsyncSession
):
    """
    아이디/비밀번호로 로그인하여 JWT 토큰을 발급받습니다.

    [Before → After]
    Before: user = db.execute(...).scalar_one_or_none()
    After:  result = await db.execute(...)    ← await
            user = result.scalar_one_or_none()
    """
    result = await db.execute(  # ← await
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    access_token = create_access_token(data={"sub": user.username})
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse, summary="내 정보 조회 (인증 필요)")
async def get_me(  # def → async def
    current_user: User = Depends(get_current_active_user),
):
    """
    현재 로그인된 사용자 정보를 반환합니다.
    Authorization: Bearer <token> 헤더가 필요합니다.

    Spring Security 비교:
        @PreAuthorize("isAuthenticated()")
        public UserResponse getMe(@AuthenticationPrincipal UserDetails user)
    """
    return UserResponse.model_validate(current_user)
