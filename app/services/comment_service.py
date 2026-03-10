# app/services/comment_service.py
# 댓글 서비스 (Spring의 @Service 역할)

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain.comment import Comment
from app.repositories.comment_repository import CommentRepository
from app.repositories.post_repository import PostRepository
from app.schemas.comment import CommentCreateRequest, CommentUpdateRequest, CommentResponse


class CommentService:
    """댓글 서비스"""

    def __init__(self):
        self.comment_repo = CommentRepository()
        # 게시글 존재 여부 확인을 위해 PostRepository도 사용
        self.post_repo = PostRepository()

    def _get_post_or_404(self, db: Session, post_id: int):
        """
        게시글 조회 헬퍼 - 없으면 404 예외

        Spring 비교: private Post getPostOrThrow(Long postId) {...}
        """
        post = self.post_repo.find_by_id(db, post_id)
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"게시글을 찾을 수 없습니다. (id={post_id})",
            )
        return post

    def get_comments(self, db: Session, post_id: int) -> list[CommentResponse]:
        """특정 게시글의 댓글 목록 조회"""
        # 게시글 존재 여부 먼저 확인
        self._get_post_or_404(db, post_id)

        comments = self.comment_repo.find_by_post_id(db, post_id)
        return [CommentResponse.model_validate(c) for c in comments]

    def create_comment(
        self, db: Session, post_id: int, request: CommentCreateRequest
    ) -> CommentResponse:
        """댓글 생성"""
        # 게시글 존재 여부 먼저 확인 (없으면 404)
        self._get_post_or_404(db, post_id)

        comment = Comment(
            content=request.content,
            author=request.author,
            post_id=post_id,
        )

        saved = self.comment_repo.save(db, comment)
        db.commit()

        return CommentResponse.model_validate(saved)

    def update_comment(
        self, db: Session, post_id: int, comment_id: int, request: CommentUpdateRequest
    ) -> CommentResponse:
        """댓글 수정"""
        # 게시글 존재 여부 확인
        self._get_post_or_404(db, post_id)

        comment = self.comment_repo.find_by_id(db, comment_id)
        if comment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"댓글을 찾을 수 없습니다. (id={comment_id})",
            )

        # 해당 게시글의 댓글인지 확인 (다른 게시글의 댓글 수정 방지)
        if comment.post_id != post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="해당 게시글의 댓글이 아닙니다.",
            )

        if request.content is not None:
            comment.content = request.content

        db.commit()
        db.refresh(comment)

        return CommentResponse.model_validate(comment)

    def delete_comment(self, db: Session, post_id: int, comment_id: int) -> None:
        """댓글 삭제"""
        self._get_post_or_404(db, post_id)

        comment = self.comment_repo.find_by_id(db, comment_id)
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

        self.comment_repo.delete(db, comment)
        db.commit()
