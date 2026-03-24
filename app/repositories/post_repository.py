# app/repositories/post_repository.py
# Spring의 @Repository + JpaRepository 역할 (비동기 버전)
#
# [Before → After: 동기 → 비동기 전환 핵심 변경]
#
#   Before: def find_all(self, db: Session, ...)
#           return list(db.execute(stmt).scalars().all())
#
#   After:  async def find_all(self, db: AsyncSession, ...)
#           result = await db.execute(stmt)   ← await 추가
#           return list(result.scalars().all())
#
# Spring WebFlux + R2DBC 비교:
#   Mono<Post> findById(Long id);    → async def find_by_id() → Post | None
#   Flux<Post> findAll();            → async def find_all()   → list[Post]

from sqlalchemy.ext.asyncio import AsyncSession  # Session → AsyncSession
from sqlalchemy import select, func

from app.domain.post import Post


class PostRepository:
    """게시글 레포지토리 (비동기 버전)"""

    async def find_all(self, db: AsyncSession, skip: int = 0, limit: int = 20) -> list[Post]:
        """
        게시글 목록 조회 (페이지네이션)

        [Before → After]
        Before: return list(db.execute(stmt).scalars().all())
        After:  result = await db.execute(stmt)    ← await
                return list(result.scalars().all())

        await: DB I/O 대기 중 이벤트 루프가 다른 코루틴 실행 가능
        """
        stmt = (
            select(Post)
            .order_by(Post.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)  # ← await
        return list(result.scalars().all())

    async def count(self, db: AsyncSession) -> int:
        """전체 게시글 수 조회"""
        stmt = select(func.count()).select_from(Post)
        result = await db.execute(stmt)  # ← await
        return result.scalar_one()

    async def find_by_id(self, db: AsyncSession, post_id: int) -> Post | None:
        """
        ID로 게시글 단건 조회

        [Before → After]
        Before: return db.get(Post, post_id)
        After:  return await db.get(Post, post_id)   ← await

        db.get(): 기본 키 조회 (1차 캐시 확인 → DB 쿼리)
        Spring JPA의 em.find(Post.class, id) 와 동일
        """
        return await db.get(Post, post_id)  # ← await

    async def save(self, db: AsyncSession, post: Post) -> Post:
        """
        게시글 저장 (생성)

        [Before → After]
        Before: db.add(post); db.flush(); db.refresh(post)
        After:  db.add(post); await db.flush(); await db.refresh(post)  ← await 추가
        """
        db.add(post)
        await db.flush()        # ← await: id 자동 생성을 위한 SQL 전송
        await db.refresh(post)  # ← await: DB에서 최신 데이터 재조회
        return post

    async def delete(self, db: AsyncSession, post: Post) -> None:
        """게시글 삭제"""
        await db.delete(post)  # ← await
        await db.flush()       # ← await
