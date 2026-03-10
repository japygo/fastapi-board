# app/domain/user.py
# 사용자 엔티티 (Spring Security의 UserDetails 역할)

from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """
    사용자 엔티티

    [Spring Security 비교]
    Spring Security: UserDetails 인터페이스를 구현한 User 엔티티
    FastAPI:         이 SQLAlchemy 모델을 직접 사용

    Spring 예시:
        @Entity
        public class User implements UserDetails {
            private String username;
            private String password;  // BCrypt 해시된 비밀번호
            private boolean enabled;
        }
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 로그인 ID (Spring Security의 username 역할)
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,       # UNIQUE 제약 (@Column(unique=true))
        nullable=False,
        index=True,        # 로그인 시 빠른 조회를 위한 인덱스
        comment="사용자 아이디",
    )

    # BCrypt 해시된 비밀번호
    # Spring Security: passwordEncoder.encode(rawPassword) 와 동일
    # 절대 평문(raw) 비밀번호를 저장하지 않습니다!
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="BCrypt 해시 비밀번호",
    )

    # 사용자 활성화 여부 (Spring Security의 isEnabled() 역할)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        nullable=False,
        comment="계정 활성화 여부",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="가입일시",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' active={self.is_active}>"
