# app/domain/comment.py
# Spring의 @Entity 클래스 역할 - 댓글 엔티티

from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Comment(Base):
    """
    댓글 엔티티

    Spring JPA 비교:
        @Entity
        @Table(name = "comments")
        public class Comment { ... }
    """

    __tablename__ = "comments"

    # 기본 키 (자동 증가)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 댓글 내용
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="댓글 내용")

    # 작성자
    author: Mapped[str] = mapped_column(String(50), nullable=False, comment="작성자")

    # ── 외래 키 ───────────────────────────────────────────────────────────────
    # Spring JPA 비교: @ManyToOne @JoinColumn(name = "post_id")
    # ForeignKey("posts.id"): posts 테이블의 id 컬럼을 참조
    # ondelete="CASCADE": DB 레벨에서도 게시글 삭제 시 댓글 삭제 보장
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        comment="게시글 ID (외래 키)",
    )

    # 작성일시 (자동 설정)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        comment="작성일시",
    )

    # 수정일시 (자동 갱신)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="수정일시",
    )

    # ── 연관관계 정의 ─────────────────────────────────────────────────────────
    # Spring JPA 비교: @ManyToOne(fetch = FetchType.LAZY)
    # back_populates: Post.comments 와 양방향 연결
    post: Mapped["Post"] = relationship(
        "Post",
        back_populates="comments",
    )

    def __repr__(self) -> str:
        """디버깅용 문자열 표현 - Java의 toString() 역할"""
        return f"<Comment id={self.id} post_id={self.post_id} author='{self.author}'>"
