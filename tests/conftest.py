# tests/conftest.py
# Spring의 @TestConfiguration 또는 테스트용 ApplicationContext 설정 역할
# pytest의 conftest.py는 모든 테스트 파일에서 공유되는 픽스처(fixture)를 정의합니다
#
# [픽스처(Fixture)란?]
# Spring의 @BeforeEach + @AfterEach 를 합쳐놓은 개념입니다.
# 테스트 실행 전에 필요한 객체를 준비하고, 테스트 후에 정리합니다.

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base

# 모든 도메인 모델을 임포트하여 SQLAlchemy 레지스트리에 등록
# Post가 relationship("Comment")를 참조하므로, Comment도 반드시 임포트 필요
# Spring에서 @Entity 클래스들이 컨텍스트 로딩 시 자동 스캔되는 것과 유사한 역할
from app.domain import post, comment  # noqa: F401 (사용하지 않아도 등록 목적으로 임포트)

# ── 테스트용 인메모리 DB 설정 ──────────────────────────────────────────────────
# Spring의 @DataJpaTest 가 H2 인메모리 DB를 자동으로 사용하는 것과 동일한 개념
# 각 테스트 세션마다 깨끗한 인메모리 DB를 사용합니다

# StaticPool: 여러 스레드에서 같은 인메모리 DB 연결을 공유
# (인메모리 SQLite는 연결이 끊기면 데이터가 사라지므로 연결 유지 필요)
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # 테스트 중 항상 같은 연결 사용
    echo=False,            # 테스트 중 SQL 출력 비활성화
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


@pytest.fixture(scope="function")
def db():
    """
    테스트용 데이터베이스 세션 픽스처

    [Spring 비교]
    @BeforeEach: Base.metadata.create_all() → 테이블 생성
    @AfterEach:  Base.metadata.drop_all()   → 테이블 삭제 (테스트 격리)

    scope="function": 각 테스트 함수마다 새로운 DB 세션 생성
    (Spring의 @Transactional 테스트에서 각 테스트 후 롤백하는 것과 유사)
    """
    # 테스트 시작 전: 모든 테이블 생성
    Base.metadata.create_all(bind=test_engine)

    session = TestSessionLocal()
    try:
        yield session          # 테스트 함수에 세션 제공
    finally:
        session.close()
        # 테스트 종료 후: 모든 테이블 삭제 (다음 테스트를 위한 초기화)
        Base.metadata.drop_all(bind=test_engine)
