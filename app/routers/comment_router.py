# app/routers/comment_router.py
# 댓글 라우터 (Spring의 @RestController 역할)
#
# RESTful URL 설계: 댓글은 게시글의 하위 리소스
# GET    /api/posts/{post_id}/comments        → 댓글 목록
# POST   /api/posts/{post_id}/comments        → 댓글 생성
# PATCH  /api/posts/{post_id}/comments/{id}   → 댓글 수정
# DELETE /api/posts/{post_id}/comments/{id}   → 댓글 삭제

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.comment_service import CommentService
from app.schemas.comment import (
    CommentCreateRequest,
    CommentUpdateRequest,
    CommentResponse,
)

# prefix에 post_id를 포함: /api/posts/{post_id}/comments
router = APIRouter(
    prefix="/api/posts/{post_id}/comments",
    tags=["댓글"],
)

comment_service = CommentService()


@router.get("/", response_model=list[CommentResponse], summary="댓글 목록 조회")
def get_comments(
    post_id: int,              # URL 경로의 {post_id} 자동 바인딩
    db: Session = Depends(get_db),
):
    """특정 게시글의 댓글 목록을 조회합니다."""
    return comment_service.get_comments(db, post_id)


@router.post(
    "/",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="댓글 생성",
)
def create_comment(
    post_id: int,
    request: CommentCreateRequest,
    db: Session = Depends(get_db),
):
    """게시글에 댓글을 작성합니다."""
    return comment_service.create_comment(db, post_id, request)


@router.patch(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="댓글 수정",
)
def update_comment(
    post_id: int,
    comment_id: int,
    request: CommentUpdateRequest,
    db: Session = Depends(get_db),
):
    """댓글 내용을 수정합니다."""
    return comment_service.update_comment(db, post_id, comment_id, request)


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="댓글 삭제",
)
def delete_comment(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
):
    """댓글을 삭제합니다."""
    comment_service.delete_comment(db, post_id, comment_id)
