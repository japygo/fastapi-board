# app/domain/post.py
# Spring의 @Entity 클래스 역할
# SQLAlchemy 모델 = 데이터베이스 테이블 정의

from datetime import datetime

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Post(Base):
    """
    게시글 엔티티

    Spring JPA 비교:
        @Entity
        @Table(name = "posts")
        public class Post { ... }

    SQLAlchemy 2.x 에서는 Mapped[타입] 과 mapped_column() 을 사용합니다.
    이전 방식(Column 직접 사용)보다 타입 안전성이 높습니다.
    """

    # 테이블 이름 지정 (Spring의 @Table(name="posts") 와 동일)
    __tablename__ = "posts"

    # ── 컬럼 정의 ────────────────────────────────────────────────────────────
    # Spring JPA 비교: @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    # Mapped[int]: 이 컬럼의 Python 타입이 int 임을 명시
    # primary_key=True: 기본 키
    # autoincrement=True: 자동 증가 (SQLite: ROWID, PostgreSQL: SERIAL)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # @Column(nullable = false, length = 200)
    # String(200): VARCHAR(200)
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="게시글 제목")

    # @Column(nullable = false, columnDefinition = "TEXT")
    # Text: TEXT 타입 (길이 제한 없는 문자열)
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="게시글 내용")

    # @Column(nullable = false, length = 50)
    author: Mapped[str] = mapped_column(String(50), nullable=False, comment="작성자")

    # 조회수 (기본값 0)
    # [Alembic 두 번째 마이그레이션 학습용]
    # 이 컬럼은 나중에 추가됩니다. 모델에 추가한 뒤:
    #   $ uv run alembic revision --autogenerate -m "add_view_count"
    #   $ uv run alembic upgrade head
    # Flyway 비교: V2__add_view_count_to_posts.sql 에 ALTER TABLE 작성하는 것과 동일
    view_count: Mapped[int] = mapped_column(
        default=0,
        server_default="0",
        nullable=False,
        comment="조회수",
    )

    # @CreatedDate (Spring Data JPA의 Auditing)
    # server_default=func.now(): DB 서버에서 현재 시간을 기본값으로 설정
    # INSERT 시 자동으로 현재 시간이 저장됩니다
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="작성일시",
    )

    # @LastModifiedDate (Spring Data JPA의 Auditing)
    # onupdate=func.now(): UPDATE 시 자동으로 현재 시간으로 갱신됩니다
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="수정일시",
    )

    # ── 연관관계 정의 ─────────────────────────────────────────────────────────
    # Spring JPA 비교: @OneToMany(mappedBy = "post", cascade = CascadeType.ALL)
    # back_populates: 양방향 관계에서 반대편 속성 이름 (Comment.post)
    # cascade: "all, delete-orphan" = CascadeType.ALL + orphanRemoval=true
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete-orphan",  # 게시글 삭제 시 댓글도 함께 삭제
        lazy="select",                 # 기본 로딩 전략 (Spring의 FetchType.LAZY와 유사)
    )

    def __repr__(self) -> str:
        """객체를 문자열로 표현 (디버깅용) - Java의 toString() 역할"""
        return f"<Post id={self.id} title='{self.title}' author='{self.author}'>"
