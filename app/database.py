# app/database.py
# Spring의 DataSource + JPA EntityManagerFactory 설정 역할
# SQLAlchemy 엔진과 세션을 설정합니다

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings


# ── 엔진 생성 ──────────────────────────────────────────────────────────────────
# Spring의 DataSource 빈(Bean) 역할
# 데이터베이스와의 실제 연결을 관리하는 객체입니다

# SQLite 사용 시 connect_args 설정 필요
# check_same_thread=False: SQLite는 기본적으로 한 스레드에서만 사용 가능한데,
# FastAPI는 여러 스레드를 사용하므로 이 제한을 해제합니다
# (PostgreSQL이나 MySQL은 이 설정이 필요 없습니다)
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    # echo=True: 실행되는 SQL을 콘솔에 출력 (Spring의 show-sql: true 와 동일)
    echo=settings.debug,
)


# SQLite 전용: 외래 키 제약 조건 활성화
# SQLite는 기본적으로 외래 키를 검사하지 않습니다
# (PostgreSQL, MySQL은 이 설정이 필요 없습니다)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ── 세션 팩토리 ────────────────────────────────────────────────────────────────
# Spring의 EntityManager + @Transactional 역할
# 데이터베이스 작업의 단위(트랜잭션)를 관리합니다

SessionLocal = sessionmaker(
    # 트랜잭션 자동 커밋 비활성화 (명시적으로 commit() 호출 필요)
    # Spring의 @Transactional 에서 메서드 종료 시 자동 커밋하는 것과 달리,
    # Python에서는 명시적으로 관리합니다
    autocommit=False,
    # 변경사항 자동 flush 비활성화 (명시적으로 flush() 호출 필요)
    autoflush=False,
    bind=engine,
)


# ── Base 클래스 ────────────────────────────────────────────────────────────────
# Spring의 @Entity 가 상속받는 JPA 엔티티의 기반 역할
# 모든 도메인 모델(테이블)은 이 Base 를 상속받습니다

class Base(DeclarativeBase):
    """
    모든 SQLAlchemy 모델의 기반 클래스

    Spring에서 @Entity 어노테이션을 붙이는 것처럼,
    Python에서는 이 Base 클래스를 상속받아 테이블을 정의합니다.
    """
    pass


# ── 의존성 주입용 세션 제공 함수 ────────────────────────────────────────────────
# Spring의 @Autowired EntityManager 역할
# FastAPI의 Depends() 와 함께 사용하여 각 요청마다 새로운 세션을 제공합니다

def get_db():
    """
    데이터베이스 세션을 생성하고, 요청 처리 후 자동으로 닫는 제너레이터 함수

    FastAPI의 의존성 주입(Dependency Injection) 시스템과 연동됩니다.
    Spring의 @Transactional 과 유사하게, 요청 시작 시 세션을 열고
    요청 종료 시(성공/실패 모두) 세션을 닫습니다.

    사용 예시:
        @router.get("/posts")
        def get_posts(db: Session = Depends(get_db)):
            ...

    yield 키워드: Python 제너레이터. try/finally 로 세션 정리를 보장합니다.
    """
    db = SessionLocal()
    try:
        yield db          # 이 시점에서 라우터 함수에 세션을 전달
    finally:
        db.close()        # 요청 완료 후 항상 세션 닫기 (finally = Spring의 @After)
