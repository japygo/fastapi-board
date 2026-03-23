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
        GET /api/posts/{id} 호출 후 view_count 가 1 증가하는지 검증

        [핵심 동작 순서 - BackgroundTask vs @Async 차이]

        BackgroundTask:
            요청 A: [조회(view=0) → 응답반환(view=0)] → [백그라운드: view=1로 업데이트]
            요청 B: [조회(view=1) → 응답반환(view=1)] → [백그라운드: view=2로 업데이트]
            ↑ 응답 본문에는 "업데이트 이전" 값이 담깁니다.
            ↑ 다음 요청에서 업데이트된 값을 볼 수 있습니다.

        Spring @Async:
            요청 A: [조회(view=0) → @Async 호출 → 응답반환(view=0)]
            @Async: 별도 스레드에서 view=1로 업데이트
            ↑ 마찬가지로 응답 본문에는 "업데이트 이전" 값이 담깁니다.

        TestClient 특이사항:
        - 실제 서버와 달리 BackgroundTask를 응답 직후 동기적으로 실행합니다.
        - 따라서 다음 요청에서 이미 업데이트된 view_count 를 읽을 수 있습니다.
        - Spring @Async 테스트에서 Thread.sleep() 이 필요 없는 것과 유사합니다.
        """
        post = self._create_post(client)
        post_id = post["id"]

        # view_count 초기값 확인
        assert post["view_count"] == 0

        # 1번째 조회: 응답에는 view_count=0 (BackgroundTask가 아직 반영 전)
        first_response = client.get(f"/api/posts/{post_id}").json()
        assert first_response["view_count"] == 0
        # → TestClient가 BackgroundTask 실행 완료: DB에 view_count=1 저장됨

        # 2번째 조회: 1번째 BackgroundTask가 반영된 값(1)을 읽음
        second_response = client.get(f"/api/posts/{post_id}").json()
        assert second_response["view_count"] == 1
        # → TestClient가 BackgroundTask 실행 완료: DB에 view_count=2 저장됨

    def test_여러_번_조회_시_조회수_누적(self, client):
        """
        게시글을 N번 조회하면 view_count 가 N만큼 증가

        [패턴]
        조회 응답에 담기는 view_count 는 항상 "이전 BackgroundTask까지의 결과" 입니다.
        - 1번째 조회 응답: 0 (초기값)
        - 2번째 조회 응답: 1 (1번째 BackgroundTask 결과)
        - 3번째 조회 응답: 2 (2번째 BackgroundTask 결과)
        - ...
        """
        post = self._create_post(client)
        post_id = post["id"]

        조회_횟수 = 5
        for i in range(조회_횟수):
            response = client.get(f"/api/posts/{post_id}").json()
            # i번째 조회 응답에는 (i)번째 BackgroundTask 결과가 담김
            assert response["view_count"] == i

        # 마지막 조회(6번째)에서 최종 누적값 확인
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
