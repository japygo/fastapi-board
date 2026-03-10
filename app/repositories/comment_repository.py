# app/repositories/comment_repository.py
# 댓글 레포지토리 (Spring의 @Repository 역할)

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.domain.comment import Comment


class CommentRepository:
    """댓글 레포지토리"""

    def find_by_post_id(self, db: Session, post_id: int) -> list[Comment]:
        """
        특정 게시글의 댓글 목록 조회

        Spring JPA 비교:
            @Query("SELECT c FROM Comment c WHERE c.post.id = :postId")
            List<Comment> findByPostId(@Param("postId") Long postId);
        또는 JPA 쿼리 메서드:
            List<Comment> findByPostId(Long postId);
        """
        stmt = (
            select(Comment)
            .where(Comment.post_id == post_id)   # WHERE post_id = :post_id
            .order_by(Comment.created_at.asc())  # ORDER BY created_at ASC (오래된 순)
        )
        return list(db.execute(stmt).scalars().all())

    def find_by_id(self, db: Session, comment_id: int) -> Comment | None:
        """ID로 댓글 단건 조회"""
        return db.get(Comment, comment_id)

    def save(self, db: Session, comment: Comment) -> Comment:
        """댓글 저장"""
        db.add(comment)
        db.flush()
        db.refresh(comment)
        return comment

    def delete(self, db: Session, comment: Comment) -> None:
        """댓글 삭제"""
        db.delete(comment)
        db.flush()
