# tests/conftest.py
# Spring의 @TestConfiguration 또는 테스트용 ApplicationContext 설정 역할
# pytest의 conftest.py는 모든 테스트 파일에서 공유되는 픽스처(fixture)를 정의합니다
#
# [픽스처(Fixture)란?]
# Spring의 @BeforeEach + @AfterEach 를 합쳐놓은 개념입니다.
# 테스트 실행 전에 필요한 객체를 준비하고, 테스트 후에 정리합니다.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# 모든 도메인 모델을 임포트하여 SQLAlchemy 레지스트리에 등록
# Post가 relationship("Comment")를 참조하므로, Comment도 반드시 임포트 필요
# Spring에서 @Entity 클래스들이 컨텍스트 로딩 시 자동 스캔되는 것과 유사한 역할
from app.domain import post, comment, user  # noqa: F401

# ── 공유 테스트 DB 설정 ────────────────────────────────────────────────────────
# 모든 테스트 파일이 이 단일 엔진을 공유합니다.
# 각 파일에 별도 엔진을 두면 app.dependency_overrides 가 충돌합니다.
#
# StaticPool: 여러 스레드에서 같은 인메모리 DB 연결을 공유
# (인메모리 SQLite는 연결이 끊기면 데이터가 사라지므로 연결 유지 필요)
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    """
    테스트용 DB 세션 의존성 오버라이드 (모든 테스트 파일 공유)

    FastAPI의 의존성 오버라이드:
    Spring의 @MockBean DataSource 와 유사한 개념
    """
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# 앱 레벨에서 의존성 오버라이드 등록 (한 번만 실행)
app.dependency_overrides[get_db] = override_get_db

# ── BackgroundTask 세션 오버라이드 ──────────────────────────────────────────────
# tasks.py의 increment_view_count 는 SessionLocal() 을 직접 호출합니다.
# 테스트 시 실제 DB가 아닌 테스트 DB를 사용하도록 오버라이드합니다.
#
# Spring 비교:
# @MockBean AsyncTaskService 로 @Async 메서드를 목(Mock) 처리하거나,
# @TestConfiguration 으로 다른 DataSource 를 주입하는 것과 동일한 역할
import app.tasks as tasks_module
tasks_module.SessionLocal = TestSessionLocal  # type: ignore[assignment]


# ── 단위 테스트용 DB 세션 픽스처 ───────────────────────────────────────────────
@pytest.fixture(scope="function")
def db():
    """
    단위 테스트용 DB 세션 픽스처 (도메인, 레포지토리, 서비스 테스트에 사용)

    [Spring 비교]
    @BeforeEach: Base.metadata.create_all() → 테이블 생성
    @AfterEach:  Base.metadata.drop_all()   → 테이블 삭제 (테스트 격리)

    scope="function": 각 테스트 함수마다 새로운 DB 세션 생성
    """
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


# ── API 통합 테스트용 TestClient 픽스처 ───────────────────────────────────────
@pytest.fixture(scope="function")
def client():
    """
    API 통합 테스트용 TestClient 픽스처

    각 테스트마다 테이블을 초기화하여 테스트 격리를 보장합니다.
    Spring의 @SpringBootTest + @Transactional(rollback=true) 와 유사합니다.
    """
    Base.metadata.create_all(bind=test_engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=test_engine)
