# app/routers/comment_router.py
# 댓글 라우터 (Spring의 @RestController 역할, 비동기 버전)
#
# [Before → After]
# Before: def get_comments(db: Session = Depends(get_db))
# After:  async def get_comments(db: AsyncSession = Depends(get_db))

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession  # Session → AsyncSession

from app.database import get_db
from app.services.comment_service import CommentService
from app.schemas.comment import CommentCreateRequest, CommentUpdateRequest, CommentResponse

router = APIRouter(prefix="/api/posts/{post_id}/comments", tags=["댓글"])
comment_service = CommentService()


@router.get("/", response_model=list[CommentResponse], summary="댓글 목록 조회")
async def get_comments(  # def → async def
    post_id: int,
    db: AsyncSession = Depends(get_db),  # Session → AsyncSession
):
    return await comment_service.get_comments(db, post_id)  # ← await


@router.post("/", response_model=CommentResponse, status_code=status.HTTP_201_CREATED, summary="댓글 생성")
async def create_comment(  # def → async def
    post_id: int,
    request: CommentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await comment_service.create_comment(db, post_id, request)  # ← await


@router.patch("/{comment_id}", response_model=CommentResponse, summary="댓글 수정")
async def update_comment(  # def → async def
    post_id: int,
    comment_id: int,
    request: CommentUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await comment_service.update_comment(db, post_id, comment_id, request)  # ← await


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, summary="댓글 삭제")
async def delete_comment(  # def → async def
    post_id: int,
    comment_id: int,
    db: AsyncSession = Depends(get_db),
):
    await comment_service.delete_comment(db, post_id, comment_id)  # ← await
