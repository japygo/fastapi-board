# app/config.py
# Spring의 application.properties + @ConfigurationProperties 역할
# pydantic-settings 라이브러리가 .env 파일을 읽어 설정값을 자동 주입합니다

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    애플리케이션 전역 설정 클래스

    Spring의 @ConfigurationProperties 와 유사합니다.
    pydantic-settings 가 .env 파일에서 값을 읽어 자동으로 타입 변환합니다.

    예) .env 파일의 APP_NAME="FastAPI 게시판" → app_name: str 에 자동 주입
    """

    # 앱 기본 정보
    app_name: str = "FastAPI 게시판"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── JWT 설정 (Spring Security의 JwtProperties 역할) ──────────────────────
    # secret_key: JWT 서명에 사용하는 비밀 키
    # Spring의 @Value("${jwt.secret}") 와 동일한 방식으로 .env 에서 읽습니다
    secret_key: str = "changeme-use-openssl-rand-hex-32-in-production"
    # 서명 알고리즘 (HS256 = HMAC-SHA256, Spring의 SignatureAlgorithm.HS256)
    algorithm: str = "HS256"
    # 액세스 토큰 만료 시간(분) (Spring의 jwt.expiration 설정)
    access_token_expire_minutes: int = 30

    # 데이터베이스 연결 URL
    # SQLite:      sqlite:///./board.db          (파일 기반)
    # SQLite 메모리: sqlite:///:memory:           (테스트용, 프로세스 종료 시 사라짐)
    # PostgreSQL:  postgresql://user:pass@host:5432/dbname
    database_url: str = "sqlite:///./board.db"

    # ── Redis 설정 (Spring의 spring.data.redis.* 역할) ───────────────────────
    # spring.data.redis.host=localhost
    # spring.data.redis.port=6379
    # spring.data.redis.database=0
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # SettingsConfigDict: 설정 메타데이터 (Spring의 @PropertySource 역할)
    model_config = SettingsConfigDict(
        # 읽을 .env 파일 경로 (여러 파일 지정 가능, 뒤에 오는 파일이 우선순위 높음)
        env_file=".env",
        # 대소문자 구분 없이 환경 변수 읽기 (DATABASE_URL == database_url)
        case_sensitive=False,
    )


# 싱글톤 패턴으로 설정 인스턴스 생성
# Spring의 @Bean + @Singleton 과 동일한 효과
# 모듈 로딩 시 한 번만 생성되고 이후에는 같은 인스턴스를 재사용합니다
settings = Settings()
