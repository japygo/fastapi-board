# app/services/post_service.py
# Spring의 @Service 역할 (비동기 버전)
#
# [Before → After: 동기 → 비동기 전환 핵심 변경]
#
#   Before: def get_post(self, db: Session, post_id: int)
#           post = self.post_repo.find_by_id(db, post_id)
#           db.commit()
#
#   After:  async def get_post(self, db: AsyncSession, post_id: int)
#           post = await self.post_repo.find_by_id(db, post_id)  ← await
#           await db.commit()                                     ← await
#
# @cacheable / @cache_evict 데코레이터는 cache.py 에서 async 함수도 지원하도록 수정됨

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession  # Session → AsyncSession

from app.cache import cacheable, cache_evict, make_cache_key, evict_post_cache
from app.domain.post import Post
from app.repositories.post_repository import PostRepository
from app.schemas.post import PostCreateRequest, PostUpdateRequest, PostListResponse, PostResponse


class PostService:
    """게시글 서비스 (비동기 버전)"""

    def __init__(self):
        self.post_repo = PostRepository()

    # ── 게시글 목록 조회 (캐시 적용) ─────────────────────────────────────────────
    # Spring @Cacheable 비교:
    #   @Cacheable(value = "posts", key = "'posts:' + #skip + ':' + #limit")
    #   @Transactional(readOnly = true)
    #   public PostListResponse getPosts(int skip, int limit) { ... }
    @cacheable(
        key_func=lambda db, skip=0, limit=20, **kw: make_cache_key("posts", skip, limit),
        ttl=60,
    )
    async def get_posts(self, db: AsyncSession, skip: int = 0, limit: int = 20) -> PostListResponse:
        """
        게시글 목록 조회 (캐시 적용)

        [Before → After]
        Before: def get_posts(self, db: Session, ...)
                posts = self.post_repo.find_all(db, ...)
        After:  async def get_posts(self, db: AsyncSession, ...)
                posts = await self.post_repo.find_all(db, ...)   ← await

        [캐시 키] posts:{skip}:{limit}
        """
        posts = await self.post_repo.find_all(db, skip=skip, limit=limit)  # ← await
        total = await self.post_repo.count(db)                              # ← await
        post_responses = [PostResponse.model_validate(post) for post in posts]
        return PostListResponse(posts=post_responses, total=total)

    # ── 게시글 단건 조회 (캐시 적용) ─────────────────────────────────────────────
    # Spring @Cacheable 비교:
    #   @Cacheable(value = "post", key = "#postId")
    @cacheable(
        key_func=lambda db, post_id, **kw: make_cache_key("post", post_id),
        ttl=300,
    )
    async def get_post(self, db: AsyncSession, post_id: int) -> PostResponse:
        """
        게시글 단건 조회 (캐시 적용)

        [Before → After]
        Before: post = self.post_repo.find_by_id(db, post_id)
        After:  post = await self.post_repo.find_by_id(db, post_id)   ← await

        [캐시 키] post:{post_id}
        """
        post = await self.post_repo.find_by_id(db, post_id)  # ← await
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"게시글을 찾을 수 없습니다. (id={post_id})",
            )
        return PostResponse.model_validate(post)

    # ── 게시글 생성 (캐시 무효화) ─────────────────────────────────────────────────
    # Spring @CacheEvict 비교:
    #   @CacheEvict(value = "posts", allEntries = true)
    @cache_evict("posts:*")
    async def create_post(self, db: AsyncSession, request: PostCreateRequest) -> PostResponse:
        """
        게시글 생성 (목록 캐시 무효화)

        [Before → After]
        Before: saved_post = self.post_repo.save(db, post); db.commit()
        After:  saved_post = await self.post_repo.save(db, post); await db.commit()
        """
        post = Post(
            title=request.title,
            content=request.content,
            author=request.author,
        )
        saved_post = await self.post_repo.save(db, post)  # ← await
        await db.commit()                                  # ← await
        return PostResponse.model_validate(saved_post)

    async def update_post(
        self, db: AsyncSession, post_id: int, request: PostUpdateRequest
    ) -> PostResponse:
        """
        게시글 수정 + 캐시 무효화

        [Before → After]
        Before: post = self.post_repo.find_by_id(db, post_id); db.commit(); db.refresh(post)
        After:  post = await self.post_repo.find_by_id(...); await db.commit(); await db.refresh(post)

        [변경 감지(Dirty Checking)]
        Spring JPA: @Transactional 안에서 필드 변경 → 자동 UPDATE
        SQLAlchemy 비동기: 동일하게 await db.commit() 으로 처리
        """
        post = await self.post_repo.find_by_id(db, post_id)  # ← await
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"게시글을 찾을 수 없습니다. (id={post_id})",
            )

        if request.title is not None:
            post.title = request.title
        if request.content is not None:
            post.content = request.content

        await db.commit()       # ← await: 변경 감지 + 커밋
        await db.refresh(post)  # ← await: updated_at 등 반영

        evict_post_cache(post_id)
        return PostResponse.model_validate(post)

    async def delete_post(self, db: AsyncSession, post_id: int) -> None:
        """
        게시글 삭제 + 캐시 무효화

        [Before → After]
        Before: self.post_repo.delete(db, post); db.commit()
        After:  await self.post_repo.delete(db, post); await db.commit()
        """
        post = await self.post_repo.find_by_id(db, post_id)  # ← await
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"게시글을 찾을 수 없습니다. (id={post_id})",
            )

        await self.post_repo.delete(db, post)  # ← await
        await db.commit()                      # ← await

        evict_post_cache(post_id)
