# app/main.py
# Spring의 @SpringBootApplication + main() 메서드 역할
# FastAPI 애플리케이션의 진입점(Entry Point)입니다

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware import LoggingMiddleware, setup_logging
from app.routers import post_router, comment_router, auth_router

# 도메인 모델 임포트 (SQLAlchemy 레지스트리에 등록)
from app.domain import post, comment, user  # noqa: F401

# ── 로깅 초기화 ─────────────────────────────────────────────────────────────
# 앱 시작 시 가장 먼저 실행 (Spring의 @PostConstruct 또는 ApplicationRunner 역할)
# debug=True 면 SQL 쿼리 포함 상세 로그 출력
setup_logging(debug=settings.debug)

# ── 테이블 관리 방식 변경 안내 ─────────────────────────────────────────────────
# [Before] Base.metadata.create_all(bind=engine)
#   → Spring의 ddl-auto=create 와 같이 앱 시작 시 테이블을 자동 생성
#   → 개발 편의용이지만, 컬럼 추가/삭제 등 변경사항을 추적하지 못함
#
# [After] Alembic이 테이블 생성 및 변경 관리
#   → Spring의 Flyway/Liquibase 와 동일한 방식
#   → 서버 실행 전에 반드시 마이그레이션 적용 필요:
#      $ uv run alembic upgrade head
#   → 테이블 변경 시 새 마이그레이션 파일 생성:
#      $ uv run alembic revision --autogenerate -m "변경_내용"

# ── FastAPI 애플리케이션 인스턴스 생성 ────────────────────────────────────────
# Spring Boot의 SpringApplication.run() 과 유사한 역할
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    # Swagger UI 설명 (Spring의 SpringDoc OpenAPI 설정과 유사)
    description="""
    FastAPI + SQLAlchemy 학습용 게시판 API

    ## 기능
    - 게시글 CRUD (작성, 조회, 수정, 삭제)
    - 댓글 CRUD
    """,
)

# ── 미들웨어 등록 ──────────────────────────────────────────────────────────────
# 주의: 미들웨어는 등록 순서의 역순으로 실행됩니다 (스택 구조)
# 마지막에 등록한 미들웨어가 가장 먼저 요청을 받습니다
#
# Spring의 FilterRegistrationBean.setOrder() 와 유사한 개념

# CORS 미들웨어 (Spring의 CorsConfigurationSource + @CrossOrigin 역할)
# 프론트엔드(React, Vue 등)가 다른 도메인에서 API를 호출할 수 있게 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 허용할 프론트엔드 도메인
    allow_credentials=True,                   # 쿠키/인증 헤더 허용
    allow_methods=["*"],                      # 모든 HTTP 메서드 허용
    allow_headers=["*"],                      # 모든 헤더 허용
)

# 로깅 미들웨어 (Spring의 CommonsRequestLoggingFilter 역할)
# CORS보다 먼저 등록 → 실제로는 CORS보다 먼저 실행되어 모든 요청을 로깅
app.add_middleware(LoggingMiddleware)

# ── 라우터 등록 ────────────────────────────────────────────────────────────────
# Spring의 @RestController 를 @SpringBootApplication 이 자동으로 스캔하는 것과 달리,
# FastAPI는 명시적으로 include_router() 로 등록해야 합니다
app.include_router(auth_router.router)     # 인증 API (회원가입/로그인)
app.include_router(post_router.router)     # 게시글 API
app.include_router(comment_router.router)  # 댓글 API


# ── 헬스체크 엔드포인트 ─────────────────────────────────────────────────────────
# Spring Actuator의 /actuator/health 와 유사한 역할
@app.get("/health", tags=["시스템"])
def health_check():
    """서버가 정상 동작 중인지 확인하는 엔드포인트"""
    return {"status": "ok", "app": settings.app_name}


# ── 루트 엔드포인트 ────────────────────────────────────────────────────────────
@app.get("/", tags=["시스템"])
def root():
    """API 루트 - Swagger UI 링크 안내"""
    return {
        "message": f"{settings.app_name}에 오신 것을 환영합니다!",
        "docs": "/docs",       # Swagger UI (Spring의 Springdoc /swagger-ui.html)
        "redoc": "/redoc",     # ReDoc UI (대안적 API 문서 UI)
    }
