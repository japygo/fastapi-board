# migrations/env.py
# Alembic 마이그레이션 실행 환경 설정
#
# [Flyway 비교]
# Flyway:  resources/db/migration/V1__init.sql 파일을 직접 작성
# Alembic: autogenerate 기능으로 SQLAlchemy 모델을 분석해 마이그레이션 파일 자동 생성
#          또는 직접 작성 가능
#
# [Alembic 핵심 개념]
# - 마이그레이션 파일: versions/ 폴더의 Python 파일 (Flyway의 V1__*.sql 역할)
# - revision: 각 마이그레이션의 고유 ID (Flyway의 버전 번호 역할)
# - head: 가장 최신 마이그레이션 상태
# - alembic_version 테이블: 현재 적용된 버전 추적 (Flyway의 flyway_schema_history 역할)

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Alembic 설정 객체 (alembic.ini 파일을 읽음)
config = context.config

# 로깅 설정 (alembic.ini 의 [loggers] 섹션)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── 핵심 설정 1: .env 파일에서 DB URL 읽기 ────────────────────────────────────
# Flyway의 flyway.url=jdbc:postgresql://... 설정과 동일한 역할
# alembic.ini의 sqlalchemy.url 대신 .env 파일을 읽어 동적으로 URL을 설정합니다
from app.config import settings

# alembic.ini의 sqlalchemy.url을 .env의 값으로 덮어쓰기
config.set_main_option("sqlalchemy.url", settings.database_url)

# ── 핵심 설정 2: 모델 메타데이터 등록 (autogenerate 핵심) ─────────────────────
# autogenerate: 현재 DB 스키마와 SQLAlchemy 모델을 비교해 변경사항을 자동 감지
# Flyway는 SQL을 직접 작성하지만, Alembic은 모델 변경을 감지해 SQL을 자동 생성합니다
#
# 반드시 모든 도메인 모델을 임포트해야 autogenerate가 테이블을 감지합니다
from app.database import Base
from app.domain import post, comment  # noqa: F401 - 모델 등록을 위한 임포트

# target_metadata: autogenerate 시 비교 기준이 되는 메타데이터
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    오프라인 모드 마이그레이션 실행

    DB 연결 없이 SQL 스크립트만 생성합니다.
    alembic upgrade head --sql 명령으로 실행됩니다.
    Flyway의 마이그레이션 SQL 파일 미리보기와 유사합니다.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite 비교를 위한 render_as_batch 옵션
        # SQLite는 ALTER TABLE을 지원하지 않아 batch 모드로 처리합니다
        # PostgreSQL로 전환 시 이 옵션을 제거해도 됩니다
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    온라인 모드 마이그레이션 실행 (일반적인 사용 방식)

    실제 DB에 연결하여 마이그레이션을 적용합니다.
    alembic upgrade head 명령으로 실행됩니다.
    Flyway의 flyway migrate 와 동일합니다.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # 마이그레이션은 단발성 작업이므로 커넥션 풀 불필요
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite: ALTER TABLE 미지원으로 batch 모드 필요
            # PostgreSQL 사용 시 이 옵션 제거 가능
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# 오프라인/온라인 모드 분기
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
