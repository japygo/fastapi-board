# app/main.py
# Spring의 @SpringBootApplication + main() 메서드 역할
# FastAPI 애플리케이션의 진입점(Entry Point)입니다

from fastapi import FastAPI

from app.config import settings

# FastAPI 애플리케이션 인스턴스 생성
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
