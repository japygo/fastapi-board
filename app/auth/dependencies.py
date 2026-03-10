# app/auth/dependencies.py
# 인증 의존성 (Dependency) 정의
#
# [Spring Security 비교]
# Spring: SecurityFilterChain + JwtAuthenticationFilter
#   → 모든 요청에서 헤더를 파싱하고, UserDetails 를 SecurityContext에 저장
#
# FastAPI: Depends(get_current_user) 로 라우터에 선택적으로 인증 적용
#   → @PreAuthorize, @Secured 와 유사한 방식으로 엔드포인트별 보호 가능

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain.user import User
from app.auth.jwt import decode_access_token

# OAuth2PasswordBearer: Authorization: Bearer <token> 헤더에서 토큰을 추출
# tokenUrl: 토큰을 발급받는 엔드포인트 URL (Swagger UI에서 자동으로 로그인 버튼 생성)
# Spring Security의 UsernamePasswordAuthenticationFilter 와 유사한 역할
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),  # Authorization 헤더에서 토큰 자동 추출
    db: Session = Depends(get_db),
) -> User:
    """
    현재 인증된 사용자를 반환하는 의존성 함수

    [Spring Security 비교]
    @PreAuthorize("isAuthenticated()") 를 붙인 것과 동일한 효과입니다.
    이 함수를 Depends() 로 주입받는 라우터는 자동으로 JWT 인증이 필요합니다.

    Spring 예시:
        // SecurityContext에서 사용자 꺼내기
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        UserDetails user = (UserDetails) auth.getPrincipal();

    FastAPI 사용 예시:
        @router.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"user": current_user.username}

    인증 실패 시 자동으로 401 Unauthorized 반환합니다.
    """
    # 토큰 디코딩 및 검증 (실패 시 401 자동 발생)
    payload = decode_access_token(token)
    username: str = payload.get("sub")

    # DB에서 사용자 조회
    from sqlalchemy import select
    user = db.execute(
        select(User).where(User.username == username)
    ).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 비활성화된 계정 차단
    # Spring Security의 UserDetails.isEnabled() 검사와 동일
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다.",
        )

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    활성화된 사용자만 허용하는 의존성 (get_current_user의 별칭)

    Spring Security의 @PreAuthorize("isAuthenticated() and principal.enabled") 와 유사.
    get_current_user 에 이미 is_active 검사가 포함되어 있어 현재는 동일하지만,
    역할(Role) 기반 접근 제어를 추가할 때 이 함수를 확장할 수 있습니다.

    Spring Security 역할 제어 예시 (확장 방향):
        @PreAuthorize("hasRole('ADMIN')")
        → if "ADMIN" not in current_user.roles: raise 403
    """
    return current_user
