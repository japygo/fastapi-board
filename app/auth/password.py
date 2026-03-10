# app/auth/password.py
# 비밀번호 해싱/검증 유틸리티
#
# [Spring Security 비교]
# Spring: PasswordEncoder (BCryptPasswordEncoder)
#   passwordEncoder.encode("rawPassword")      → 해시 생성
#   passwordEncoder.matches("raw", "hashed")   → 검증
#
# Python: passlib 라이브러리의 CryptContext
#   pwd_context.hash("rawPassword")            → 해시 생성
#   pwd_context.verify("raw", "hashed")        → 검증

from passlib.context import CryptContext

# BCrypt 해싱 설정
# Spring의 new BCryptPasswordEncoder() 와 동일
# schemes=["bcrypt"]: BCrypt 알고리즘 사용
# deprecated="auto": 오래된 해시는 자동으로 업그레이드 권장
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    평문 비밀번호를 BCrypt 해시로 변환

    Spring 비교: passwordEncoder.encode(rawPassword)
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    평문 비밀번호와 해시를 비교하여 일치 여부 반환

    Spring 비교: passwordEncoder.matches(rawPassword, encodedPassword)
    """
    return pwd_context.verify(plain_password, hashed_password)
