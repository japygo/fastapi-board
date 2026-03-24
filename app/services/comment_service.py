# app/services/comment_service.py
# 댓글 서비스 (Spring의 @Service 역할, 비동기 버전)

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession  # Session → AsyncSession

from app.domain.comment import Comment
from app.repositories.comment_repository import CommentRepository
from app.repositories.post_repository import PostRepository
from app.schemas.comment import CommentCreateRequest, CommentUpdateRequest, CommentResponse


class CommentService:
    """댓글 서비스 (비동기 버전)"""

    def __init__(self):
        self.comment_repo = CommentRepository()
        self.post_repo = PostRepository()

    async def _get_post_or_404(self, db: AsyncSession, post_id: int):
        """
        게시글 조회 헬퍼 - 없으면 404 예외

        [Before → After]
        Before: post = self.post_repo.find_by_id(db, post_id)
        After:  post = await self.post_repo.find_by_id(db, post_id)   ← await
        """
        post = await self.post_repo.find_by_id(db, post_id)  # ← await
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"게시글을 찾을 수 없습니다. (id={post_id})",
            )
        return post

    async def get_comments(self, db: AsyncSession, post_id: int) -> list[CommentResponse]:
        """특정 게시글의 댓글 목록 조회"""
        await self._get_post_or_404(db, post_id)  # ← await
        comments = await self.comment_repo.find_by_post_id(db, post_id)  # ← await
        return [CommentResponse.model_validate(c) for c in comments]

    async def create_comment(
        self, db: AsyncSession, post_id: int, request: CommentCreateRequest
    ) -> CommentResponse:
        """댓글 생성"""
        await self._get_post_or_404(db, post_id)  # ← await

        comment = Comment(
            content=request.content,
            author=request.author,
            post_id=post_id,
        )
        saved = await self.comment_repo.save(db, comment)  # ← await
        await db.commit()                                   # ← await
        return CommentResponse.model_validate(saved)

    async def update_comment(
        self, db: AsyncSession, post_id: int, comment_id: int, request: CommentUpdateRequest
    ) -> CommentResponse:
        """댓글 수정"""
        await self._get_post_or_404(db, post_id)  # ← await

        comment = await self.comment_repo.find_by_id(db, comment_id)  # ← await
        if comment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"댓글을 찾을 수 없습니다. (id={comment_id})",
            )
        if comment.post_id != post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="해당 게시글의 댓글이 아닙니다.",
            )

        if request.content is not None:
            comment.content = request.content

        await db.commit()          # ← await
        await db.refresh(comment)  # ← await
        return CommentResponse.model_validate(comment)

    async def delete_comment(self, db: AsyncSession, post_id: int, comment_id: int) -> None:
        """댓글 삭제"""
        await self._get_post_or_404(db, post_id)  # ← await

        comment = await self.comment_repo.find_by_id(db, comment_id)  # ← await
        if comment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"댓글을 찾을 수 없습니다. (id={comment_id})",
            )
        if comment.post_id != post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="해당 게시글의 댓글이 아닙니다.",
            )

        await self.comment_repo.delete(db, comment)  # ← await
        await db.commit()                             # ← await
