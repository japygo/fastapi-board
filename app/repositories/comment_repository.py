# app/repositories/comment_repository.py
# 댓글 레포지토리 (Spring의 @Repository 역할, 비동기 버전)

from sqlalchemy.ext.asyncio import AsyncSession  # Session → AsyncSession
from sqlalchemy import select

from app.domain.comment import Comment


class CommentRepository:
    """댓글 레포지토리 (비동기 버전)"""

    async def find_by_post_id(self, db: AsyncSession, post_id: int) -> list[Comment]:
        """
        특정 게시글의 댓글 목록 조회

        [Before → After]
        Before: return list(db.execute(stmt).scalars().all())
        After:  result = await db.execute(stmt)    ← await
                return list(result.scalars().all())

        Spring JPA 비교:
            List<Comment> findByPostId(Long postId);
        """
        stmt = (
            select(Comment)
            .where(Comment.post_id == post_id)
            .order_by(Comment.created_at.asc())
        )
        result = await db.execute(stmt)  # ← await
        return list(result.scalars().all())

    async def find_by_id(self, db: AsyncSession, comment_id: int) -> Comment | None:
        """ID로 댓글 단건 조회"""
        return await db.get(Comment, comment_id)  # ← await

    async def save(self, db: AsyncSession, comment: Comment) -> Comment:
        """댓글 저장"""
        db.add(comment)
        await db.flush()           # ← await
        await db.refresh(comment)  # ← await
        return comment

    async def delete(self, db: AsyncSession, comment: Comment) -> None:
        """댓글 삭제"""
        await db.delete(comment)  # ← await
        await db.flush()          # ← await
