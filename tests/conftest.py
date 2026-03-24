# tests/conftest.py
# Spring의 @TestConfiguration 역할 (비동기 버전)
#
# [Before → After: 동기 → 비동기 전환]
#
# Before:
#   test_engine = create_engine("sqlite:///:memory:", ...)
#   TestSessionLocal = sessionmaker(...)
#   def override_get_db(): yield db
#   @pytest.fixture def db(): yield session
#
# After:
#   async_test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", ...)
#   AsyncTestSessionLocal = async_sessionmaker(...)
#   async def override_get_db(): yield db        ← async def
#   @pytest.fixture async def db(): yield session ← async fixture

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.domain import post, comment, user  # noqa: F401

# ── 비동기 테스트 DB 설정 ────────────────────────────────────────────────────
# sqlite+aiosqlite: 비동기 SQLite 드라이버 (aiosqlite 패키지 사용)
# StaticPool: 모든 연결이 동일한 인메모리 DB를 공유
#   → 인메모리 SQLite는 연결이 끊기면 데이터가 사라지므로 연결 유지 필요
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"  # sqlite:// → sqlite+aiosqlite://

async_test_engine = create_async_engine(  # create_engine → create_async_engine
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

AsyncTestSessionLocal = async_sessionmaker(  # sessionmaker → async_sessionmaker
    async_test_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ── 비동기 의존성 오버라이드 ─────────────────────────────────────────────────
# [Before → After]
# Before: def override_get_db(): db = TestSessionLocal(); try: yield db; finally: db.close()
# After:  async def override_get_db(): async with AsyncTestSessionLocal() as db: yield db
async def override_get_db():
    async with AsyncTestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db

# ── BackgroundTask 세션 오버라이드 ──────────────────────────────────────────
# tasks.py의 increment_view_count 는 AsyncSessionLocal() 을 직접 호출합니다.
# 테스트 시 테스트 DB를 사용하도록 오버라이드합니다.
import app.tasks as tasks_module
tasks_module.AsyncSessionLocal = AsyncTestSessionLocal  # type: ignore[assignment]

# ── Redis(캐시) 오버라이드 ──────────────────────────────────────────────────
import fakeredis
import app.cache as cache_module

fake_redis = fakeredis.FakeRedis(decode_responses=True)
cache_module.redis_client = fake_redis  # type: ignore[assignment]


# ── 단위 테스트용 비동기 DB 세션 픽스처 ────────────────────────────────────
# [Before → After]
# Before: @pytest.fixture def db(): Base.metadata.create_all(bind=test_engine); yield session
# After:  @pytest.fixture async def db():
#             async with async_test_engine.begin() as conn:
#                 await conn.run_sync(Base.metadata.create_all)  ← await
#             async with AsyncTestSessionLocal() as session:
#                 yield session
@pytest.fixture
async def db():
    """
    단위 테스트용 비동기 DB 세션 픽스처

    [Before → After]
    Before: create_all(bind=test_engine) → sync
    After:  async with engine.begin() as conn: await conn.run_sync(create_all) → async

    conn.run_sync(): 비동기 컨텍스트에서 동기 함수를 실행하는 방법
    (create_all은 동기 함수이므로 run_sync 래핑 필요)
    """
    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # ← await + run_sync

    async with AsyncTestSessionLocal() as session:
        yield session

    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # ← await + run_sync


# ── API 통합 테스트용 TestClient 픽스처 ──────────────────────────────────────
# [Before → After]
# Before: @pytest.fixture def client(): Base.metadata.create_all(bind=test_engine); ...
# After:  @pytest.fixture async def client():
#             async with async_test_engine.begin() as conn:
#                 await conn.run_sync(Base.metadata.create_all)  ← await
@pytest.fixture
async def client():
    """
    API 통합 테스트용 TestClient 픽스처 (비동기 버전)

    TestClient는 동기 HTTP 클라이언트이지만, 비동기 fixture에서 사용 가능합니다.
    TestClient가 내부적으로 별도 스레드에 이벤트 루프를 생성하기 때문입니다.

    Spring 비교:
        @SpringBootTest + TestRestTemplate (동기 방식으로 HTTP 테스트)
    """
    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    fake_redis.flushall()

    with TestClient(app) as c:
        yield c

    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    fake_redis.flushall()
