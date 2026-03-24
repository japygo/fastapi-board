# tests/test_api.py
# API 엔드포인트 통합 테스트 (HTTP 레벨, 비동기 fixture 버전)
# Spring 비교: @SpringBootTest + MockMvc 또는 TestRestTemplate
#
# [Before → After]
# Before: def test_*(self, client):
# After:  async def test_*(self, client):
#
# ※ TestClient 자체는 동기(sync) HTTP 클라이언트입니다.
#   async def 테스트 안에서 client.get() 을 동기 방식으로 호출해도 됩니다.
#   (async fixture와의 연결을 위해 async def 필요)

import time

from tests.conftest import fake_redis


def get_auth_header(client) -> dict:
    """테스트용 인증 헤더 생성 헬퍼 (동기 유틸 함수, 변경 없음)"""
    client.post("/api/auth/register", json={"username": "testuser", "password": "password123"})
    login_response = client.post("/api/auth/login", data={"username": "testuser", "password": "password123"})
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestPostAPI:
    """게시글 API 통합 테스트"""

    def _create_post(self, client, title="테스트", content="내용", author="작성자"):
        """게시글 생성 헬퍼 (동기 유틸, 변경 없음)"""
        response = client.post("/api/posts/", json={
            "title": title, "content": content, "author": author,
        }, headers=get_auth_header(client))
        assert response.status_code == 201
        return response.json()

    async def test_게시글_생성_201(self, client):  # def → async def
        response = client.post("/api/posts/", json={
            "title": "첫 번째 게시글", "content": "FastAPI 학습 중입니다.", "author": "홍길동",
        }, headers=get_auth_header(client))

        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["title"] == "첫 번째 게시글"
        assert "created_at" in data

    async def test_게시글_생성_유효성_오류_422(self, client):  # def → async def
        response = client.post("/api/posts/", json={
            "title": "", "content": "내용", "author": "작성자",
        }, headers=get_auth_header(client))
        assert response.status_code == 422

    async def test_게시글_목록_조회_200(self, client):  # def → async def
        self._create_post(client, title="게시글 1")
        self._create_post(client, title="게시글 2")

        response = client.get("/api/posts/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["posts"]) == 2

    async def test_게시글_단건_조회_200(self, client):  # def → async def
        created = self._create_post(client)
        response = client.get(f"/api/posts/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    async def test_존재하지_않는_게시글_조회_404(self, client):  # def → async def
        response = client.get("/api/posts/9999")
        assert response.status_code == 404

    async def test_게시글_수정_200(self, client):  # def → async def
        created = self._create_post(client, title="원래 제목")
        response = client.patch(f"/api/posts/{created['id']}", json={
            "title": "수정된 제목",
        }, headers=get_auth_header(client))
        assert response.status_code == 200
        assert response.json()["title"] == "수정된 제목"

    async def test_게시글_삭제_204(self, client):  # def → async def
        created = self._create_post(client)
        delete_response = client.delete(f"/api/posts/{created['id']}", headers=get_auth_header(client))
        assert delete_response.status_code == 204
        get_response = client.get(f"/api/posts/{created['id']}")
        assert get_response.status_code == 404


class TestBackgroundTasks:
    """BackgroundTasks 테스트 (비동기 fixture 버전)"""

    def _create_post(self, client) -> dict:
        headers = get_auth_header(client)
        resp = client.post(
            "/api/posts/",
            json={"title": "테스트", "content": "내용", "author": "작성자"},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_게시글_조회_시_조회수_증가(self, client):  # def → async def
        """
        GET /api/posts/{id} 호출 후 view_count 가 DB에 1 증가하는지 검증

        [캐시 + BackgroundTask 트레이드오프]
        캐시가 있을 때: 캐시 TTL 동안 view_count 응답은 stale
        이 테스트: 캐시를 무효화해서 DB의 실제 값을 확인합니다.
        """
        post = self._create_post(client)
        post_id = post["id"]
        cache_key = f"post:{post_id}"

        first_response = client.get(f"/api/posts/{post_id}").json()
        assert first_response["view_count"] == 0

        fake_redis.delete(cache_key)
        second_response = client.get(f"/api/posts/{post_id}").json()
        assert second_response["view_count"] == 1

    async def test_여러_번_조회_시_조회수_누적(self, client):  # def → async def
        post = self._create_post(client)
        post_id = post["id"]
        cache_key = f"post:{post_id}"

        조회_횟수 = 5
        for i in range(조회_횟수):
            fake_redis.delete(cache_key)
            response = client.get(f"/api/posts/{post_id}").json()
            assert response["view_count"] == i

        fake_redis.delete(cache_key)
        final = client.get(f"/api/posts/{post_id}").json()
        assert final["view_count"] == 조회_횟수

    async def test_존재하지_않는_게시글_조회수_증가_오류_없음(self, client):  # def → async def
        response = client.get("/api/posts/99999")
        assert response.status_code == 404


class TestCommentAPI:
    """댓글 API 통합 테스트"""

    def _create_post(self, client):
        response = client.post("/api/posts/", json={
            "title": "게시글", "content": "내용", "author": "작성자",
        }, headers=get_auth_header(client))
        return response.json()

    def _create_comment(self, client, post_id, content="댓글", author="댓글러"):
        response = client.post(f"/api/posts/{post_id}/comments/", json={
            "content": content, "author": author,
        })
        assert response.status_code == 201
        return response.json()

    async def test_댓글_생성_201(self, client):  # def → async def
        post = self._create_post(client)
        response = client.post(f"/api/posts/{post['id']}/comments/", json={
            "content": "좋은 글이네요!", "author": "댓글러",
        })
        assert response.status_code == 201
        assert response.json()["post_id"] == post["id"]

    async def test_존재하지_않는_게시글에_댓글_생성_404(self, client):  # def → async def
        response = client.post("/api/posts/9999/comments/", json={
            "content": "댓글", "author": "작성자",
        })
        assert response.status_code == 404

    async def test_댓글_목록_조회_200(self, client):  # def → async def
        post = self._create_post(client)
        self._create_comment(client, post["id"], content="댓글 1")
        self._create_comment(client, post["id"], content="댓글 2")
        response = client.get(f"/api/posts/{post['id']}/comments/")
        assert response.status_code == 200
        assert len(response.json()) == 2

    async def test_댓글_삭제_후_목록에서_제거(self, client):  # def → async def
        post = self._create_post(client)
        comment = self._create_comment(client, post["id"])
        delete_response = client.delete(f"/api/posts/{post['id']}/comments/{comment['id']}")
        assert delete_response.status_code == 204
        list_response = client.get(f"/api/posts/{post['id']}/comments/")
        assert len(list_response.json()) == 0


class TestRedisCache:
    """Redis 캐싱 테스트"""

    def _create_post(self, client) -> dict:
        headers = get_auth_header(client)
        resp = client.post(
            "/api/posts/",
            json={"title": "캐시 테스트", "content": "내용", "author": "작성자"},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_게시글_단건_조회_캐시_히트(self, client):  # def → async def
        post = self._create_post(client)
        post_id = post["id"]

        resp1 = client.get(f"/api/posts/{post_id}")
        assert resp1.status_code == 200

        cache_key = f"post:{post_id}"
        assert fake_redis.exists(cache_key)

        resp2 = client.get(f"/api/posts/{post_id}")
        assert resp2.status_code == 200
        assert resp1.json()["title"] == resp2.json()["title"]

    async def test_게시글_목록_조회_캐시_저장(self, client):  # def → async def
        self._create_post(client)
        client.get("/api/posts/?skip=0&limit=20")
        assert fake_redis.exists("posts:0:20")

    async def test_게시글_생성_시_목록_캐시_무효화(self, client):  # def → async def
        headers = get_auth_header(client)
        client.get("/api/posts/?skip=0&limit=20")
        assert fake_redis.exists("posts:0:20")

        client.post("/api/posts/", json={
            "title": "새 게시글", "content": "내용", "author": "작성자",
        }, headers=headers)

        assert not fake_redis.exists("posts:0:20")

    async def test_게시글_수정_시_단건_및_목록_캐시_무효화(self, client):  # def → async def
        headers = get_auth_header(client)
        post = self._create_post(client)
        post_id = post["id"]

        client.get(f"/api/posts/{post_id}")
        client.get("/api/posts/?skip=0&limit=20")
        assert fake_redis.exists(f"post:{post_id}")
        assert fake_redis.exists("posts:0:20")

        client.patch(f"/api/posts/{post_id}", json={"title": "수정"}, headers=headers)

        assert not fake_redis.exists(f"post:{post_id}")
        assert not fake_redis.exists("posts:0:20")

    async def test_게시글_삭제_시_캐시_무효화(self, client):  # def → async def
        headers = get_auth_header(client)
        post = self._create_post(client)
        post_id = post["id"]

        client.get(f"/api/posts/{post_id}")
        client.get("/api/posts/?skip=0&limit=20")
        client.delete(f"/api/posts/{post_id}", headers=headers)

        assert not fake_redis.exists(f"post:{post_id}")
        assert not fake_redis.exists("posts:0:20")
