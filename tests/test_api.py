# tests/test_api.py
# API 엔드포인트 통합 테스트 (HTTP 레벨)
# Spring 비교: @SpringBootTest + MockMvc 또는 TestRestTemplate
#
# TestClient: FastAPI 내장 테스트 클라이언트 (실제 HTTP 요청/응답)
# Spring의 MockMvc.perform(get("/api/posts")) 와 유사
#
# [DB 설정]
# conftest.py의 `client` 픽스처를 통해 각 테스트마다 인메모리 DB를 사용합니다.
# DB 설정 중복 코드가 여기에 없는 이유도 conftest.py로 통합했기 때문입니다.


def get_auth_header(client) -> dict:
    """
    테스트용 인증 헤더 생성 헬퍼

    회원가입 → 로그인 → JWT 토큰을 Authorization 헤더로 반환합니다.
    Spring Security 테스트의 mockMvc.with(jwt()) 와 유사합니다.
    """
    client.post("/api/auth/register", json={"username": "testuser", "password": "password123"})
    login_response = client.post("/api/auth/login", data={"username": "testuser", "password": "password123"})
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestPostAPI:
    """게시글 API 통합 테스트"""

    def _create_post(self, client, title="테스트", content="내용", author="작성자"):
        """테스트용 게시글 생성 헬퍼 (인증 헤더 포함)"""
        response = client.post("/api/posts/", json={
            "title": title,
            "content": content,
            "author": author,
        }, headers=get_auth_header(client))
        assert response.status_code == 201
        return response.json()

    def test_게시글_생성_201(self, client):
        """
        POST /api/posts/ → 201 Created (인증 필요)

        Spring MockMvc 비교:
            mockMvc.perform(post("/api/posts")
                .header("Authorization", "Bearer " + token)
                .contentType(APPLICATION_JSON)
                .content(json))
                .andExpect(status().isCreated())
        """
        response = client.post("/api/posts/", json={
            "title": "첫 번째 게시글",
            "content": "FastAPI 학습 중입니다.",
            "author": "홍길동",
        }, headers=get_auth_header(client))

        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["title"] == "첫 번째 게시글"
        assert data["author"] == "홍길동"
        assert "created_at" in data

    def test_게시글_생성_유효성_오류_422(self, client):
        """빈 제목으로 생성 시 422 Unprocessable Entity (Spring의 400 @Valid 오류 대응)"""
        response = client.post("/api/posts/", json={
            "title": "",  # 빈 제목 → 유효성 검사 실패
            "content": "내용",
            "author": "작성자",
        }, headers=get_auth_header(client))
        assert response.status_code == 422

    def test_게시글_목록_조회_200(self, client):
        """GET /api/posts/ → 200 OK + 목록 반환"""
        self._create_post(client, title="게시글 1")
        self._create_post(client, title="게시글 2")

        response = client.get("/api/posts/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["posts"]) == 2

    def test_게시글_단건_조회_200(self, client):
        """GET /api/posts/{id} → 200 OK"""
        created = self._create_post(client)

        response = client.get(f"/api/posts/{created['id']}")

        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_존재하지_않는_게시글_조회_404(self, client):
        """GET /api/posts/9999 → 404 Not Found"""
        response = client.get("/api/posts/9999")
        assert response.status_code == 404

    def test_게시글_수정_200(self, client):
        """PATCH /api/posts/{id} → 200 OK (인증 필요)"""
        created = self._create_post(client, title="원래 제목")

        response = client.patch(f"/api/posts/{created['id']}", json={
            "title": "수정된 제목",
        }, headers=get_auth_header(client))

        assert response.status_code == 200
        assert response.json()["title"] == "수정된 제목"

    def test_게시글_삭제_204(self, client):
        """DELETE /api/posts/{id} → 204 No Content (인증 필요)"""
        created = self._create_post(client)

        delete_response = client.delete(f"/api/posts/{created['id']}", headers=get_auth_header(client))
        assert delete_response.status_code == 204

        get_response = client.get(f"/api/posts/{created['id']}")
        assert get_response.status_code == 404


class TestCommentAPI:
    """댓글 API 통합 테스트"""

    def _create_post(self, client):
        """게시글 생성 헬퍼"""
        response = client.post("/api/posts/", json={
            "title": "게시글", "content": "내용", "author": "작성자",
        }, headers=get_auth_header(client))
        return response.json()

    def _create_comment(self, client, post_id, content="댓글", author="댓글러"):
        """댓글 생성 헬퍼"""
        response = client.post(f"/api/posts/{post_id}/comments/", json={
            "content": content,
            "author": author,
        })
        assert response.status_code == 201
        return response.json()

    def test_댓글_생성_201(self, client):
        """POST /api/posts/{post_id}/comments/ → 201 Created"""
        post = self._create_post(client)

        response = client.post(f"/api/posts/{post['id']}/comments/", json={
            "content": "좋은 글이네요!",
            "author": "댓글러",
        })

        assert response.status_code == 201
        data = response.json()
        assert data["post_id"] == post["id"]

    def test_존재하지_않는_게시글에_댓글_생성_404(self, client):
        """없는 게시글에 댓글 생성 시 404"""
        response = client.post("/api/posts/9999/comments/", json={
            "content": "댓글", "author": "작성자",
        })
        assert response.status_code == 404

    def test_댓글_목록_조회_200(self, client):
        """GET /api/posts/{post_id}/comments/ → 200 OK"""
        post = self._create_post(client)
        self._create_comment(client, post["id"], content="댓글 1")
        self._create_comment(client, post["id"], content="댓글 2")

        response = client.get(f"/api/posts/{post['id']}/comments/")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_댓글_삭제_후_목록에서_제거(self, client):
        """DELETE → 204, 이후 목록 조회 시 사라짐"""
        post = self._create_post(client)
        comment = self._create_comment(client, post["id"])

        delete_response = client.delete(
            f"/api/posts/{post['id']}/comments/{comment['id']}"
        )
        assert delete_response.status_code == 204

        list_response = client.get(f"/api/posts/{post['id']}/comments/")
        assert len(list_response.json()) == 0
