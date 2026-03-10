# app/routers/auth_router.py
# 인증 API 라우터
#
# [Spring Security 비교]
# Spring: SecurityFilterChain 설정 + AuthController
#   - /api/auth/register → 회원가입
#   - /api/auth/login    → 로그인 (JWT 발급)
#   - /api/auth/me       → 내 정보 조회 (인증 필요)
#
# [인증 흐름]
# 1. POST /api/auth/register → 회원가입 (비밀번호 BCrypt 해싱 후 저장)
# 2. POST /api/auth/login    → 로그인 성공 시 JWT 발급
# 3. GET  /api/posts/        → Authorization: Bearer <token> 헤더로 요청
# 4. get_current_user()      → 토큰 검증 후 User 객체 반환

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import select

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


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    """
    새 사용자를 등록합니다.

    [Spring Security 비교]
    @PostMapping("/register")
    public ResponseEntity<UserResponse> register(@RequestBody @Valid UserRegisterRequest request) {
        String hashedPassword = passwordEncoder.encode(request.password());
        User user = new User(request.username(), hashedPassword);
        userRepository.save(user);
        return ResponseEntity.status(201).body(UserResponse.from(user));
    }
    """
    # 중복 아이디 검사
    existing = db.execute(
        select(User).where(User.username == request.username)
    ).scalar_one_or_none()

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 사용 중인 아이디입니다: {request.username}",
        )

    # 비밀번호 BCrypt 해싱 후 저장
    # Spring의 passwordEncoder.encode(rawPassword) 와 동일
    user = User(
        username=request.username,
        hashed_password=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="로그인 (JWT 발급)",
)
def login(
    # OAuth2PasswordRequestForm: username/password 폼 데이터를 자동으로 파싱
    # Swagger UI에서 자동으로 로그인 폼을 생성합니다
    # Spring의 UsernamePasswordAuthenticationToken 과 동일한 역할
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    아이디/비밀번호로 로그인하여 JWT 토큰을 발급받습니다.

    [Spring Security 비교]
    AuthenticationManager.authenticate(
        new UsernamePasswordAuthenticationToken(username, password)
    )
    → 성공 시 JWT 토큰 생성하여 반환

    Swagger UI에서 직접 테스트:
    1. /docs 접속
    2. 우상단 'Authorize' 버튼 클릭 (또는 /api/auth/login 엔드포인트 직접 실행)
    3. 발급받은 토큰을 'Bearer <token>' 형태로 입력
    """
    # 사용자 조회
    user = db.execute(
        select(User).where(User.username == form_data.username)
    ).scalar_one_or_none()

    # 사용자 없거나 비밀번호 불일치 → 401
    # 보안상 "사용자 없음"과 "비밀번호 틀림"을 같은 메시지로 처리합니다
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

    # JWT 토큰 생성
    # "sub" (subject): JWT 표준 클레임, 사용자 식별자를 저장합니다
    # Spring의 Jwts.builder().setSubject(username) 과 동일
    access_token = create_access_token(data={"sub": user.username})

    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="내 정보 조회 (인증 필요)",
)
def get_me(
    # Depends(get_current_active_user): 이 엔드포인트에 인증 적용
    # Spring의 @PreAuthorize("isAuthenticated()") 와 동일한 효과
    current_user: User = Depends(get_current_active_user),
):
    """
    현재 로그인된 사용자의 정보를 반환합니다.

    Authorization: Bearer <token> 헤더가 필요합니다.

    [Spring Security 비교]
    @GetMapping("/me")
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<UserResponse> getMe(@AuthenticationPrincipal UserDetails user) {
        return ResponseEntity.ok(UserResponse.from(user));
    }
    """
    return UserResponse.model_validate(current_user)
