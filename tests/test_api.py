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

import time

from tests.conftest import fake_redis


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


class TestBackgroundTasks:
    """
    BackgroundTasks 테스트

    [Spring @Async 테스트 비교]
    Spring에서는 @Async 메서드를 테스트하려면:
    1. @MockBean 으로 @Async 서비스를 목(Mock) 처리
    2. CompletableFuture.get() 으로 완료를 기다림
    3. 또는 CountDownLatch 로 비동기 실행 대기

    FastAPI TestClient 는 BackgroundTasks 를 응답 반환 즉시 동기적으로 실행합니다.
    따라서 응답 받은 직후 DB를 조회하면 이미 반영된 상태입니다.
    (별도로 await 하거나 sleep 할 필요 없음)
    """

    def _create_post(self, client) -> dict:
        """게시글 생성 헬퍼"""
        headers = get_auth_header(client)
        resp = client.post(
            "/api/posts/",
            json={"title": "테스트", "content": "내용", "author": "작성자"},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()

    def test_게시글_조회_시_조회수_증가(self, client):
        """
        GET /api/posts/{id} 호출 후 view_count 가 DB에 1 증가하는지 검증

        [캐시 + BackgroundTask 함께 쓸 때의 트레이드오프]

        캐시가 없을 때:
            요청 A: [DB조회(view=0) → 응답(view=0)] → [백그라운드: DB view=1]
            요청 B: [DB조회(view=1) → 응답(view=1)] → [백그라운드: DB view=2]

        캐시가 있을 때 (현재 상태):
            요청 A: [캐시MISS→DB조회(view=0) → 응답(view=0) → 캐시저장] → [백그라운드: DB view=1]
            요청 B: [캐시HIT → 응답(view=0, 스테일!)]  ← DB는 1이지만 캐시는 0
            → 캐시 TTL이 만료되기 전까지 view_count 는 응답에서 변화가 없음

        [실무 해결책]
        1. BackgroundTask에서 DB 업데이트 후 캐시도 함께 무효화
        2. view_count 전용 별도 캐시(TTL 짧게) 사용
        3. 응답에는 stale view_count 허용 (대형 서비스의 일반적인 전략)

        [이 테스트의 접근]
        캐시를 초기화하며 DB의 실제 view_count 변화를 검증합니다.
        (실제 서비스에서는 캐시 TTL 만료 후 최신값이 반영됩니다)
        """
        post = self._create_post(client)
        post_id = post["id"]
        cache_key = f"post:{post_id}"

        # 1번째 조회: 캐시 MISS → DB 조회(view=0) → 응답 → 백그라운드: DB view=1
        first_response = client.get(f"/api/posts/{post_id}").json()
        assert first_response["view_count"] == 0

        # 캐시 무효화 후 다시 조회 → DB에서 최신값(1) 읽음
        fake_redis.delete(cache_key)
        second_response = client.get(f"/api/posts/{post_id}").json()
        assert second_response["view_count"] == 1
        # → DB에는 view_count=2 저장됨 (백그라운드 태스크 실행됨)

    def test_여러_번_조회_시_조회수_누적(self, client):
        """
        게시글을 N번 조회하면 view_count 가 DB에 N만큼 누적되는지 검증

        캐시를 매번 무효화하여 DB의 실제 누적값을 확인합니다.
        (실제 운영에서는 캐시 TTL 만료 후 최신 view_count 가 반영됩니다)
        """
        post = self._create_post(client)
        post_id = post["id"]
        cache_key = f"post:{post_id}"

        조회_횟수 = 5
        for i in range(조회_횟수):
            # 캐시 무효화 → 항상 DB에서 최신값을 읽음
            fake_redis.delete(cache_key)
            response = client.get(f"/api/posts/{post_id}").json()
            # 매 조회 시 이전 백그라운드 태스크 결과가 DB에 반영되어 있음
            assert response["view_count"] == i

        # 최종 DB 확인
        fake_redis.delete(cache_key)
        final = client.get(f"/api/posts/{post_id}").json()
        assert final["view_count"] == 조회_횟수

    def test_존재하지_않는_게시글_조회수_증가_오류_없음(self, client):
        """
        없는 게시글 조회 시 404 반환, 백그라운드 태스크 오류도 클라이언트에 전파 안됨

        [핵심]
        BackgroundTask 내부에서 예외가 발생해도 HTTP 응답에는 영향 없음.
        Spring @Async 에서 예외가 CompletableFuture 에 담기지만
        호출자에게 전파되지 않는 것과 동일한 원리.
        """
        # 없는 게시글 → 404 반환 (태스크 등록 전에 서비스에서 예외 발생)
        response = client.get("/api/posts/99999")
        assert response.status_code == 404


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


class TestRedisCache:
    """
    Redis 캐싱 테스트

    [Spring @Cacheable / @CacheEvict 테스트 비교]
    Spring에서는 @SpringBootTest + EmbeddedRedis 또는 @MockBean CacheManager 로 테스트합니다.
    여기서는 conftest.py에서 fakeredis 로 교체했으므로 실제 Redis 없이 테스트합니다.
    """

    def _create_post(self, client) -> dict:
        headers = get_auth_header(client)
        resp = client.post(
            "/api/posts/",
            json={"title": "캐시 테스트", "content": "내용", "author": "작성자"},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()

    def test_게시글_단건_조회_캐시_히트(self, client):
        """
        같은 게시글을 두 번 조회하면 두 번째는 Redis 캐시에서 반환되는지 검증

        [검증 방법]
        fakeredis 에서 캐시 키 존재 여부를 직접 확인합니다.
        Spring 테스트에서 verify(cacheManager).getCache("post") 하는 것과 유사합니다.

        Spring @Cacheable 비교:
            @Test
            void 캐시_히트_테스트() {
                // 첫 번째 호출: DB 조회 후 캐시 저장
                postService.getPost(1L);
                // 두 번째 호출: 캐시에서 반환 (DB 조회 없음)
                postService.getPost(1L);
                // Mockito로 repository 호출 횟수 검증
                verify(postRepository, times(1)).findById(1L);
            }
        """
        post = self._create_post(client)
        post_id = post["id"]

        # 첫 번째 조회: 캐시 MISS → DB 조회 후 캐시 저장
        resp1 = client.get(f"/api/posts/{post_id}")
        assert resp1.status_code == 200

        # fakeredis 에서 캐시 키 확인
        cache_key = f"post:{post_id}"
        assert fake_redis.exists(cache_key), f"캐시 키 '{cache_key}' 가 존재해야 합니다"

        # 두 번째 조회: 캐시 HIT → Redis에서 반환
        resp2 = client.get(f"/api/posts/{post_id}")
        assert resp2.status_code == 200
        assert resp1.json()["title"] == resp2.json()["title"]

    def test_게시글_목록_조회_캐시_저장(self, client):
        """
        게시글 목록 조회 후 캐시가 저장되는지 검증

        Spring @Cacheable 비교:
            @Cacheable(value = "posts", key = "'posts:0:20'")
            public PostListResponse getPosts(int skip, int limit) { ... }
        """
        self._create_post(client)

        # 목록 조회
        client.get("/api/posts/?skip=0&limit=20")

        # 목록 캐시 키 확인
        assert fake_redis.exists("posts:0:20"), "목록 캐시 키 'posts:0:20' 가 존재해야 합니다"

    def test_게시글_생성_시_목록_캐시_무효화(self, client):
        """
        게시글 생성 후 목록 캐시가 삭제되는지 검증 (@CacheEvict 동작)

        Spring @CacheEvict 비교:
            @CacheEvict(value = "posts", allEntries = true)
            public PostResponse createPost(PostCreateRequest request) { ... }
        """
        headers = get_auth_header(client)

        # 1. 목록 캐시 생성
        client.get("/api/posts/?skip=0&limit=20")
        assert fake_redis.exists("posts:0:20"), "목록 캐시가 있어야 합니다"

        # 2. 게시글 생성 → @CacheEvict 동작
        client.post(
            "/api/posts/",
            json={"title": "새 게시글", "content": "내용", "author": "작성자"},
            headers=headers,
        )

        # 3. 목록 캐시가 삭제됐는지 확인
        assert not fake_redis.exists("posts:0:20"), "생성 후 목록 캐시가 삭제돼야 합니다"

    def test_게시글_수정_시_단건_및_목록_캐시_무효화(self, client):
        """
        게시글 수정 후 단건 캐시 + 목록 캐시 모두 삭제되는지 검증

        Spring @Caching 비교:
            @Caching(evict = {
                @CacheEvict(value = "post", key = "#id"),
                @CacheEvict(value = "posts", allEntries = true)
            })
            public PostResponse updatePost(Long id, PostUpdateRequest request) { ... }
        """
        headers = get_auth_header(client)
        post = self._create_post(client)
        post_id = post["id"]

        # 1. 단건 + 목록 캐시 생성
        client.get(f"/api/posts/{post_id}")
        client.get("/api/posts/?skip=0&limit=20")
        assert fake_redis.exists(f"post:{post_id}")
        assert fake_redis.exists("posts:0:20")

        # 2. 게시글 수정 → 캐시 무효화
        client.patch(
            f"/api/posts/{post_id}",
            json={"title": "수정된 제목"},
            headers=headers,
        )

        # 3. 단건 + 목록 캐시 모두 삭제됐는지 확인
        assert not fake_redis.exists(f"post:{post_id}"), "수정 후 단건 캐시가 삭제돼야 합니다"
        assert not fake_redis.exists("posts:0:20"), "수정 후 목록 캐시가 삭제돼야 합니다"

    def test_게시글_삭제_시_캐시_무효화(self, client):
        """게시글 삭제 후 단건 캐시 + 목록 캐시 모두 삭제"""
        headers = get_auth_header(client)
        post = self._create_post(client)
        post_id = post["id"]

        # 캐시 생성
        client.get(f"/api/posts/{post_id}")
        client.get("/api/posts/?skip=0&limit=20")

        # 삭제
        client.delete(f"/api/posts/{post_id}", headers=headers)

        # 캐시 무효화 확인
        assert not fake_redis.exists(f"post:{post_id}")
        assert not fake_redis.exists("posts:0:20")
