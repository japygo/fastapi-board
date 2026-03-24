# app/database.py
# Spring의 DataSource + JPA EntityManagerFactory 설정 역할
# SQLAlchemy 비동기(Async) 엔진과 세션을 설정합니다
#
# [Before → After: 동기 → 비동기 전환]
#
# Before (동기):
#   engine = create_engine(DATABASE_URL)
#   SessionLocal = sessionmaker(bind=engine)
#   def get_db():
#       db = SessionLocal()
#       try: yield db
#       finally: db.close()
#
# After (비동기):
#   async_engine = create_async_engine(DATABASE_URL)        ← create_async_engine
#   AsyncSessionLocal = async_sessionmaker(async_engine)    ← async_sessionmaker
#   async def get_db():                                     ← async def
#       async with AsyncSessionLocal() as db:               ← async with
#           yield db
#
# Spring WebFlux(Reactive) 비교:
#   R2DBC + ReactiveEntityManager 구성과 동일한 목적
#   FastAPI는 코루틴 기반이라 WebFlux보다 코드가 훨씬 간결합니다

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── 비동기 URL 변환 ────────────────────────────────────────────────────────────
def _make_async_url(url: str) -> str:
    """
    동기 DB URL을 비동기 드라이버 URL로 변환합니다.

    예) sqlite:///./board.db    → sqlite+aiosqlite:///./board.db
        postgresql://user@host → postgresql+asyncpg://user@host

    [드라이버 설치]
    SQLite  비동기: uv add aiosqlite   (개발/테스트용)
    PG      비동기: uv add asyncpg     (운영 환경)
    """
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# ── 비동기 엔진 (앱 실행용) ────────────────────────────────────────────────────
# Spring의 R2DBC ConnectionFactory 역할
# 비동기 I/O로 DB와 통신 → 요청 처리 중 DB 대기 시간에 다른 요청을 처리 가능
async_engine = create_async_engine(
    _make_async_url(settings.database_url),
    echo=settings.debug,  # SQL 쿼리 로그 (Spring의 show-sql: true)
)

# ── 비동기 세션 팩토리 ──────────────────────────────────────────────────────────
# Spring의 EntityManagerFactory(비동기) 역할
#
# expire_on_commit=False: commit() 후 객체 속성이 만료되지 않도록 설정
#   → 비동기에서는 commit 후 lazy load가 불가능하므로 필수!
#   → 없으면 commit() 후 obj.field 접근 시 "MissingGreenlet" 오류 발생
#   → Spring에서 OSIV(Open Session In View)를 끄고 DTO로 변환하는 것과 유사
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# ── 동기 엔진 (Alembic 마이그레이션 전용) ─────────────────────────────────────
# Alembic은 동기 방식으로 마이그레이션을 실행합니다.
# 앱 코드(라우터/서비스/레포지토리)에서는 절대 사용하지 않습니다.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, echo=settings.debug)


# ── Base 클래스 ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """모든 SQLAlchemy 모델의 기반 클래스 (Spring의 @Entity 기반 역할)"""
    pass


# ── 비동기 세션 의존성 함수 ────────────────────────────────────────────────────
# [Before → After 핵심 변경점]
#
# Before:  def get_db()          → sync generator
#          db = SessionLocal()   → 동기 세션 생성
#          try: yield db
#          finally: db.close()
#
# After:   async def get_db()            → async generator
#          async with AsyncSessionLocal() as db:  → 비동기 컨텍스트 매니저
#              yield db
#
# async with: 동기의 try/finally와 동일하게 세션 close 보장
# 차이: I/O 대기 중 이벤트 루프가 다른 코루틴을 실행할 수 있음

async def get_db():
    """
    비동기 DB 세션 제공 함수 (FastAPI Depends() 와 함께 사용)

    사용 예시:
        @router.get("/posts")
        async def get_posts(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Post))
            posts = result.scalars().all()

    Spring 비교:
        // Spring Data JPA (동기)
        @Autowired PostRepository postRepository;

        // Spring WebFlux + R2DBC (비동기)
        @Autowired ReactivePostRepository postRepository;
    """
    async with AsyncSessionLocal() as db:
        yield db
