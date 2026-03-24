# app/routers/post_router.py
# Spring의 @RestController 역할 (비동기 버전)
#
# [Before → After: 가장 눈에 띄는 변경점]
# Before: def get_posts(db: Session = Depends(get_db)):
#             return post_service.get_posts(db, ...)
#
# After:  async def get_posts(db: AsyncSession = Depends(get_db)):
#             return await post_service.get_posts(db, ...)    ← async def + await

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession  # Session → AsyncSession

from app.database import get_db
from app.domain.user import User
from app.auth.dependencies import get_current_active_user
from app.services.post_service import PostService
from app.tasks import increment_view_count
from app.schemas.post import (
    PostCreateRequest,
    PostUpdateRequest,
    PostResponse,
    PostListResponse,
)

router = APIRouter(prefix="/api/posts", tags=["게시글"])
post_service = PostService()


@router.get("/", response_model=PostListResponse, summary="게시글 목록 조회")
async def get_posts(  # def → async def
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),  # Session → AsyncSession
):
    return await post_service.get_posts(db, skip=skip, limit=limit)  # ← await


@router.get("/{post_id}", response_model=PostResponse, summary="게시글 단건 조회")
async def get_post(  # def → async def
    post_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),  # Session → AsyncSession
):
    """
    [BackgroundTasks + async 동작 순서]
    1. await post_service.get_post() → DB 조회 (비동기)
    2. 클라이언트에 응답 반환
    3. 응답 완료 후 → increment_view_count(post_id) 백그라운드 실행
       (async 함수도 BackgroundTasks.add_task()로 등록 가능)
    """
    post = await post_service.get_post(db, post_id)  # ← await
    background_tasks.add_task(increment_view_count, post_id)
    return post


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED, summary="게시글 생성")
async def create_post(  # def → async def
    request: PostCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await post_service.create_post(db, request)  # ← await


@router.patch("/{post_id}", response_model=PostResponse, summary="게시글 수정 (일부 필드)")
async def update_post(  # def → async def
    post_id: int,
    request: PostUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await post_service.update_post(db, post_id, request)  # ← await


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, summary="게시글 삭제")
async def delete_post(  # def → async def
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await post_service.delete_post(db, post_id)  # ← await
