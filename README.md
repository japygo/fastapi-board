# FastAPI 게시판 API

FastAPI + SQLAlchemy 학습용 게시판 프로젝트입니다.
Java Spring 개발자를 위해 Spring과 1:1 대응되는 구조로 설계되었습니다.

---

## Spring ↔ FastAPI 대응표

| Spring | FastAPI / Python | 파일 위치 |
|--------|-----------------|----------|
| `@SpringBootApplication` | `FastAPI()` 인스턴스 | `app/main.py` |
| `application.properties` | `.env` + pydantic-settings | `app/config.py` |
| `DataSource` + `EntityManagerFactory` | SQLAlchemy `engine` + `SessionLocal` | `app/database.py` |
| `@Entity` | `Base` 상속 SQLAlchemy 모델 | `app/domain/` |
| DTO / Record | Pydantic `BaseModel` | `app/schemas/` |
| `@Repository` / `JpaRepository` | Repository 클래스 (Session 직접 사용) | `app/repositories/` |
| `@Service` + `@Transactional` | Service 클래스 (명시적 `db.commit()`) | `app/services/` |
| `@RestController` + `@RequestMapping` | `APIRouter` | `app/routers/` |
| Flyway / Liquibase | **Alembic** | `migrations/` |
| `BCryptPasswordEncoder` | passlib + bcrypt | `app/auth/password.py` |
| `JwtTokenProvider` | python-jose | `app/auth/jwt.py` |
| `@PreAuthorize("isAuthenticated()")` | `Depends(get_current_user)` | `app/auth/dependencies.py` |
| `@SpringBootTest` + MockMvc | `TestClient` + pytest | `tests/` |
| Maven / Gradle | **uv** | `pyproject.toml` |

---

## 프로젝트 구조

```
fastapi-board/
├── app/
│   ├── main.py              # @SpringBootApplication 진입점
│   ├── config.py            # application.properties (pydantic-settings)
│   ├── database.py          # DataSource + SessionLocal 설정
│   ├── auth/
│   │   ├── password.py      # BCryptPasswordEncoder
│   │   ├── jwt.py           # JwtTokenProvider
│   │   └── dependencies.py  # SecurityFilterChain (@PreAuthorize)
│   ├── domain/              # @Entity 클래스
│   │   ├── post.py
│   │   ├── comment.py
│   │   └── user.py
│   ├── schemas/             # DTO / Record
│   │   ├── post.py
│   │   ├── comment.py
│   │   └── auth.py
│   ├── repositories/        # @Repository
│   │   ├── post_repository.py
│   │   └── comment_repository.py
│   ├── services/            # @Service
│   │   ├── post_service.py
│   │   └── comment_service.py
│   └── routers/             # @RestController
│       ├── post_router.py
│       ├── comment_router.py
│       └── auth_router.py
├── migrations/              # Alembic (Flyway 대응)
│   └── versions/            # 마이그레이션 파일 (V1__*.sql 대응)
├── tests/
│   ├── conftest.py          # @TestConfiguration (공통 픽스처)
│   ├── test_domain.py       # @DataJpaTest
│   ├── test_schemas.py      # DTO 유효성 검사 테스트
│   ├── test_repositories.py # Repository 레이어 테스트
│   ├── test_services.py     # Service 레이어 테스트
│   ├── test_api.py          # @SpringBootTest + MockMvc (통합 테스트)
│   └── test_auth.py         # Spring Security 테스트
├── .env                     # 로컬 환경 설정 (git 제외)
├── .env.test                # 테스트 환경 설정
├── alembic.ini              # Alembic 설정
└── pyproject.toml           # 의존성 관리 (pom.xml / build.gradle 대응)
```

---

## 시작하기

### 1. 의존성 설치

```bash
# uv가 없다면 먼저 설치
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치 (npm install / mvn install 과 동일)
uv sync
```

### 2. 환경 변수 설정

`.env` 파일을 생성합니다 (`.env.test` 참고):

```bash
cp .env.test .env
```

`.env` 파일 주요 항목:

```properties
# 앱 설정
APP_NAME="FastAPI 게시판"
DEBUG=True

# JWT 설정 (운영 환경에서는 반드시 변경!)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# DB 설정
# SQLite (기본, 설치 불필요)
DATABASE_URL=sqlite:///./board.db

# PostgreSQL로 전환 시 위 줄을 주석 처리하고 아래 줄 사용
# DATABASE_URL=postgresql://username:password@localhost:5432/board_db
```

> `SECRET_KEY` 생성: `openssl rand -hex 32`

### 3. 데이터베이스 마이그레이션

```bash
# 테이블 생성 (flyway migrate 와 동일)
uv run alembic upgrade head
```

### 4. 서버 실행

```bash
# 개발 서버 실행 (--reload: 코드 변경 시 자동 재시작)
uv run uvicorn app.main:app --reload

# 포트 변경 시
uv run uvicorn app.main:app --reload --port 8080
```

서버 실행 후:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **헬스체크**: http://localhost:8000/health

---

## API 목록

### 인증 (`/api/auth`)

| Method | URL | 설명 | 인증 필요 |
|--------|-----|------|----------|
| `POST` | `/api/auth/register` | 회원가입 | ✗ |
| `POST` | `/api/auth/login` | 로그인 (JWT 발급) | ✗ |
| `GET` | `/api/auth/me` | 내 정보 조회 | ✓ |

### 게시글 (`/api/posts`)

| Method | URL | 설명 | 인증 필요 |
|--------|-----|------|----------|
| `GET` | `/api/posts/` | 게시글 목록 (페이지네이션) | ✗ |
| `GET` | `/api/posts/{id}` | 게시글 단건 조회 | ✗ |
| `POST` | `/api/posts/` | 게시글 생성 | ✓ |
| `PATCH` | `/api/posts/{id}` | 게시글 수정 | ✓ |
| `DELETE` | `/api/posts/{id}` | 게시글 삭제 | ✓ |

### 댓글 (`/api/posts/{post_id}/comments`)

| Method | URL | 설명 | 인증 필요 |
|--------|-----|------|----------|
| `GET` | `/api/posts/{post_id}/comments/` | 댓글 목록 | ✗ |
| `POST` | `/api/posts/{post_id}/comments/` | 댓글 생성 | ✗ |
| `PATCH` | `/api/posts/{post_id}/comments/{id}` | 댓글 수정 | ✗ |
| `DELETE` | `/api/posts/{post_id}/comments/{id}` | 댓글 삭제 | ✗ |

### 인증 방법 (Swagger UI)

1. `POST /api/auth/register` 로 회원가입
2. `POST /api/auth/login` 으로 로그인 → `access_token` 복사
3. Swagger UI 우상단 **Authorize** 버튼 클릭
4. `Bearer <access_token>` 입력 후 Authorize

---

## 테스트

```bash
# 전체 테스트 실행
uv run pytest

# 상세 출력
uv run pytest -v

# 특정 파일만
uv run pytest tests/test_api.py -v

# 특정 테스트만
uv run pytest tests/test_services.py::TestPostService::test_게시글_생성 -v

# 커버리지 포함 (pytest-cov 설치 필요: uv add --dev pytest-cov)
uv run pytest --cov=app
```

### 테스트 구조

| 파일 | Spring 대응 | 설명 |
|------|------------|------|
| `test_domain.py` | `@DataJpaTest` | Entity CRUD, CASCADE 검증 |
| `test_schemas.py` | Bean Validation 테스트 | DTO 유효성 검사 |
| `test_repositories.py` | `@DataJpaTest` | Repository 쿼리 테스트 |
| `test_services.py` | `@SpringBootTest` 서비스 레이어 | 비즈니스 로직, 예외 처리 |
| `test_api.py` | `@SpringBootTest` + MockMvc | HTTP 통합 테스트 |
| `test_auth.py` | Spring Security 테스트 | 인증/인가 테스트 |

---

## Alembic 마이그레이션

Spring의 Flyway / Liquibase에 대응하는 DB 마이그레이션 도구입니다.

```bash
# 현재 적용된 버전 확인 (flyway info)
uv run alembic current

# 마이그레이션 히스토리 확인
uv run alembic history --verbose

# 최신 버전으로 적용 (flyway migrate)
uv run alembic upgrade head

# 한 단계 롤백 (flyway undo - 유료 기능을 Alembic은 무료 지원)
uv run alembic downgrade -1

# 특정 버전으로 롤백
uv run alembic downgrade <revision_id>

# 모델 변경 후 새 마이그레이션 파일 자동 생성 (flyway는 직접 SQL 작성)
uv run alembic revision --autogenerate -m "변경_내용_설명"
```

### 마이그레이션 워크플로우

```
1. app/domain/*.py 에서 모델(Entity) 변경
      ↓
2. uv run alembic revision --autogenerate -m "컬럼_추가"
      ↓  (migrations/versions/ 에 새 파일 자동 생성)
3. 생성된 파일 검토 (자동 생성이지만 반드시 확인!)
      ↓
4. uv run alembic upgrade head
```

---

## 의존성 관리 (uv)

Spring의 Maven/Gradle에 대응하는 Python 패키지 관리 도구입니다.

```bash
# 패키지 추가 (mvn dependency:add / implementation '...')
uv add fastapi

# 개발 전용 패키지 추가 (testImplementation '...')
uv add --dev pytest

# 패키지 제거
uv remove some-package

# 의존성 동기화 (mvn install / gradle dependencies)
uv sync

# 설치된 패키지 목록
uv pip list
```

---

## 커밋 히스토리 (학습 순서)

```
Commit 1: 프로젝트 초기 설정      → uv, 폴더 구조, config, database
Commit 2: 도메인 모델(Entity)      → @Entity, 연관관계, Cascade
Commit 3: Pydantic 스키마(DTO)     → @RequestBody, @ResponseBody, 유효성 검사
Commit 4: 레포지토리 레이어        → JpaRepository, 쿼리 메서드
Commit 5: 서비스 레이어            → @Service, @Transactional, 예외 처리
Commit 6: API 라우터               → @RestController, @RequestMapping
Commit 7: Alembic 마이그레이션     → Flyway, DB 스키마 버전 관리
Commit 8: JWT 인증                 → Spring Security, BCrypt, JWT
```

각 커밋을 `git checkout <hash>` 로 이동하며 단계별 학습이 가능합니다.
