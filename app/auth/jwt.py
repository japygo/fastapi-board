# app/auth/jwt.py
# JWT 토큰 생성 및 검증 유틸리티
#
# [Spring Security 비교]
# Spring: JwtTokenProvider (또는 JwtUtil) 클래스
#   - generateToken(UserDetails userDetails) → create_access_token()
#   - validateToken(String token)            → decode_access_token()
#   - getUsernameFromToken(String token)     → decode 결과의 "sub" 필드
#
# FastAPI: python-jose 라이브러리로 JWT 처리

from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from fastapi import HTTPException, status

from app.config import settings


def create_access_token(data: dict) -> str:
    """
    JWT 액세스 토큰 생성

    [Spring Security 비교]
    Jwts.builder()
        .setSubject(username)
        .setIssuedAt(new Date())
        .setExpiration(new Date(System.currentTimeMillis() + expiration))
        .signWith(SignatureAlgorithm.HS256, secretKey)
        .compact()

    Args:
        data: 토큰에 담을 데이터 ({"sub": "username"} 형태)

    Returns:
        서명된 JWT 문자열 (Bearer 토큰으로 사용)
    """
    to_encode = data.copy()

    # 만료 시간 설정 (현재 시간 + ACCESS_TOKEN_EXPIRE_MINUTES 분)
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    # "exp" 클레임: JWT 표준 만료 시간 필드
    to_encode.update({"exp": expire})

    # 토큰 서명 및 인코딩
    # algorithm=HS256: HMAC-SHA256 서명 (대칭 키)
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    JWT 토큰 디코딩 및 검증

    [Spring Security 비교]
    JwtAuthenticationFilter.doFilterInternal() 에서:
        Claims claims = Jwts.parser()
            .setSigningKey(secretKey)
            .parseClaimsJws(token)
            .getBody();
        String username = claims.getSubject();

    Args:
        token: Authorization 헤더에서 추출한 JWT 문자열

    Returns:
        디코딩된 페이로드 딕셔너리

    Raises:
        HTTPException 401: 토큰이 유효하지 않거나 만료된 경우
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        # "sub" 클레임에 username이 저장됩니다
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="토큰에 사용자 정보가 없습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload

    except JWTError:
        # 서명 불일치, 만료, 형식 오류 모두 401로 처리
        # Spring Security의 AuthenticationException → 401 응답과 동일
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},  # RFC 6750 표준 헤더
        )
