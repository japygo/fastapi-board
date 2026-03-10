# tests/test_api.py
# API 엔드포인트 통합 테스트 (HTTP 레벨)
# Spring 비교: @SpringBootTest + MockMvc 또는 TestRestTemplate
#
# httpx.TestClient: FastAPI 내장 테스트 클라이언트 (실제 HTTP 요청/응답)
# Spring의 MockMvc.perform(get("/api/posts")) 와 유사

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

# ── 테스트용 DB 오버라이드 설정 ────────────────────────────────────────────────
# Spring의 @TestConfiguration 으로 테스트용 DataSource 를 재정의하는 것과 동일

TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """
    테스트용 DB 세션 의존성 오버라이드

    FastAPI의 의존성 오버라이드(Dependency Override):
    Spring의 @MockBean 또는 @TestConfiguration 과 유사한 개념
    실제 DB 대신 테스트용 인메모리 DB를 사용하도록 교체합니다
    """
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


# 의존성 오버라이드 적용 (실제 get_db → 테스트용 get_db 교체)
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    """
    각 테스트마다 테이블 초기화

    autouse=True: 이 파일의 모든 테스트에 자동 적용
    Spring의 @BeforeEach/@AfterEach 와 동일
    """
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# TestClient: 실제 서버 없이 FastAPI 앱을 직접 호출
# Spring의 MockMvc 와 동일한 역할
client = TestClient(app)


class TestPostAPI:
    """게시글 API 통합 테스트"""

    def _create_post(self, title="테스트", content="내용", author="작성자"):
        """테스트용 게시글 생성 헬퍼"""
        response = client.post("/api/posts/", json={
            "title": title,
            "content": content,
            "author": author,
        })
        assert response.status_code == 201
        return response.json()

    def test_게시글_생성_201(self):
        """
        POST /api/posts/ → 201 Created

        Spring MockMvc 비교:
            mockMvc.perform(post("/api/posts")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
                .andExpect(status().isCreated())
        """
        response = client.post("/api/posts/", json={
            "title": "첫 번째 게시글",
            "content": "FastAPI 학습 중입니다.",
            "author": "홍길동",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["title"] == "첫 번째 게시글"
        assert data["author"] == "홍길동"
        assert "created_at" in data

    def test_게시글_생성_유효성_오류_422(self):
        """빈 제목으로 생성 시 422 Unprocessable Entity (Spring의 400 @Valid 오류 대응)"""
        response = client.post("/api/posts/", json={
            "title": "",  # 빈 제목 → 유효성 검사 실패
            "content": "내용",
            "author": "작성자",
        })
        assert response.status_code == 422

    def test_게시글_목록_조회_200(self):
        """GET /api/posts/ → 200 OK + 목록 반환"""
        self._create_post(title="게시글 1")
        self._create_post(title="게시글 2")

        response = client.get("/api/posts/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["posts"]) == 2

    def test_게시글_단건_조회_200(self):
        """GET /api/posts/{id} → 200 OK"""
        created = self._create_post()

        response = client.get(f"/api/posts/{created['id']}")

        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_존재하지_않는_게시글_조회_404(self):
        """GET /api/posts/9999 → 404 Not Found"""
        response = client.get("/api/posts/9999")
        assert response.status_code == 404

    def test_게시글_수정_200(self):
        """PATCH /api/posts/{id} → 200 OK"""
        created = self._create_post(title="원래 제목")

        response = client.patch(f"/api/posts/{created['id']}", json={
            "title": "수정된 제목",
        })

        assert response.status_code == 200
        assert response.json()["title"] == "수정된 제목"

    def test_게시글_삭제_204(self):
        """DELETE /api/posts/{id} → 204 No Content"""
        created = self._create_post()

        # 삭제 요청
        delete_response = client.delete(f"/api/posts/{created['id']}")
        assert delete_response.status_code == 204

        # 삭제 후 조회 시 404
        get_response = client.get(f"/api/posts/{created['id']}")
        assert get_response.status_code == 404


class TestCommentAPI:
    """댓글 API 통합 테스트"""

    def _create_post(self):
        """게시글 생성 헬퍼"""
        response = client.post("/api/posts/", json={
            "title": "게시글", "content": "내용", "author": "작성자",
        })
        return response.json()

    def _create_comment(self, post_id, content="댓글", author="댓글러"):
        """댓글 생성 헬퍼"""
        response = client.post(f"/api/posts/{post_id}/comments/", json={
            "content": content,
            "author": author,
        })
        assert response.status_code == 201
        return response.json()

    def test_댓글_생성_201(self):
        """POST /api/posts/{post_id}/comments/ → 201 Created"""
        post = self._create_post()

        response = client.post(f"/api/posts/{post['id']}/comments/", json={
            "content": "좋은 글이네요!",
            "author": "댓글러",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["post_id"] == post["id"]

    def test_존재하지_않는_게시글에_댓글_생성_404(self):
        """없는 게시글에 댓글 생성 시 404"""
        response = client.post("/api/posts/9999/comments/", json={
            "content": "댓글", "author": "작성자",
        })
        assert response.status_code == 404

    def test_댓글_목록_조회_200(self):
        """GET /api/posts/{post_id}/comments/ → 200 OK"""
        post = self._create_post()
        self._create_comment(post["id"], content="댓글 1")
        self._create_comment(post["id"], content="댓글 2")

        response = client.get(f"/api/posts/{post['id']}/comments/")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_댓글_삭제_후_목록에서_제거(self):
        """DELETE → 204, 이후 목록 조회 시 사라짐"""
        post = self._create_post()
        comment = self._create_comment(post["id"])

        delete_response = client.delete(
            f"/api/posts/{post['id']}/comments/{comment['id']}"
        )
        assert delete_response.status_code == 204

        # 댓글 목록 재조회
        list_response = client.get(f"/api/posts/{post['id']}/comments/")
        assert len(list_response.json()) == 0
