# app/middleware.py
# Spring의 Filter / HandlerInterceptor 역할
#
# [Spring 비교]
# @Component
# public class LoggingFilter implements Filter {
#     @Override
#     public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
#         // 요청 전 처리
#         chain.doFilter(req, res);
#         // 응답 후 처리
#     }
# }
#
# FastAPI에서는 두 가지 방법으로 미들웨어를 구현합니다:
# 1. BaseHTTPMiddleware 상속 (Spring Filter와 가장 유사)
# 2. @app.middleware("http") 데코레이터 (간단한 경우)
#
# 여기서는 두 방법을 모두 보여줍니다.

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# ── 로거 설정 ───────────────────────────────────────────────────────────────
# Spring의 LoggerFactory.getLogger(ClassName.class) 와 동일
# __name__ 은 현재 모듈 이름("app.middleware")이 됩니다
logger = logging.getLogger(__name__)


# ── 미들웨어 1: 요청/응답 로깅 ─────────────────────────────────────────────
# Spring의 HandlerInterceptor (preHandle + afterCompletion) 역할
class LoggingMiddleware(BaseHTTPMiddleware):
    """
    모든 HTTP 요청/응답을 자동으로 로깅하는 미들웨어.

    Spring HandlerInterceptor 비교:
        preHandle  → await call_next(request) 호출 이전
        afterCompletion → await call_next(request) 호출 이후
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # ── 요청 전처리 (Spring의 preHandle) ───────────────────────────────
        # 요청마다 고유한 ID 부여 → 로그에서 같은 요청의 흐름을 추적할 수 있음
        # Spring의 MDC.put("requestId", UUID) 패턴과 동일한 목적
        request_id = str(uuid.uuid4())[:8]

        # 요청 시작 시간 기록
        start_time = time.perf_counter()

        logger.info(
            "[%s] → %s %s (from %s)",
            request_id,
            request.method,            # GET, POST, ...
            request.url.path,          # /api/posts, /api/posts/1, ...
            request.client.host if request.client else "unknown",
        )

        # ── 다음 미들웨어 또는 라우터 호출 (Spring의 chain.doFilter()) ──────
        response = await call_next(request)

        # ── 응답 후처리 (Spring의 afterCompletion) ─────────────────────────
        # 처리 시간 계산 (밀리초 단위)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 응답 헤더에 요청 ID와 처리 시간 추가
        # → 클라이언트(또는 프론트엔드)에서도 추적 가능
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms:.1f}ms"

        logger.info(
            "[%s] ← %s %s | %d | %.1fms",
            request_id,
            request.method,
            request.url.path,
            response.status_code,       # 200, 201, 404, ...
            elapsed_ms,
        )

        return response


# ── 미들웨어 2: CORS 설정 ───────────────────────────────────────────────────
# Spring의 CorsConfigurationSource + CorsFilter 역할
# 프론트엔드(React 등)에서 API를 호출할 때 필요
# main.py에서 CORSMiddleware를 등록하는 방식으로 사용합니다
# (아래에 등록 방법 예시 주석 참고)


# ── 로깅 기본 설정 함수 ─────────────────────────────────────────────────────
def setup_logging(debug: bool = False) -> None:
    """
    애플리케이션 전체 로깅 설정.
    Spring의 logback-spring.xml 또는 application.yml의 logging.level 역할.

    debug=True  → DEBUG 레벨 (상세 로그, 개발 환경)
    debug=False → INFO 레벨 (일반 로그, 운영 환경)
    """
    level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        # 로그 포맷: 시간 | 로그레벨 | 모듈명 | 메시지
        # Spring의 %d{HH:mm:ss} %-5level %logger{36} - %msg%n 과 유사
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )

    # SQLAlchemy의 SQL 쿼리 로그는 별도 제어
    # Spring의 logging.level.org.hibernate.SQL=DEBUG 와 동일
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if debug else logging.WARNING
    )
