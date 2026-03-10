# tests/test_auth.py
# 인증 API 통합 테스트
# Spring 비교: @SpringBootTest + Spring Security 테스트
#
# [DB 설정]
# conftest.py의 `client` 픽스처를 통해 각 테스트마다 인메모리 DB를 사용합니다.


class TestRegister:
    """회원가입 API 테스트"""

    def test_회원가입_성공_201(self, client):
        """정상 회원가입 시 201 반환"""
        response = client.post("/api/auth/register", json={
            "username": "testuser",
            "password": "password123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["is_active"] is True
        # 비밀번호는 절대 응답에 포함되면 안 됨
        assert "password" not in data
        assert "hashed_password" not in data

    def test_중복_아이디_409(self, client):
        """동일한 아이디로 두 번 가입 시 409 Conflict"""
        client.post("/api/auth/register", json={"username": "dupe", "password": "password123"})
        response = client.post("/api/auth/register", json={"username": "dupe", "password": "password123"})
        assert response.status_code == 409

    def test_짧은_비밀번호_422(self, client):
        """8자 미만 비밀번호 시 422 (Pydantic 유효성 검사)"""
        response = client.post("/api/auth/register", json={
            "username": "user1",
            "password": "short",  # 8자 미만
        })
        assert response.status_code == 422


class TestLogin:
    """로그인 API 테스트"""

    def _register(self, client, username="testuser", password="password123"):
        client.post("/api/auth/register", json={"username": username, "password": password})

    def test_로그인_성공_JWT_발급(self, client):
        """
        올바른 아이디/비밀번호로 로그인 시 JWT 토큰 발급

        Spring Security 비교: AuthenticationManager.authenticate() 성공 후 토큰 반환
        """
        self._register(client)

        # OAuth2PasswordRequestForm은 JSON이 아닌 form 데이터로 전송
        response = client.post("/api/auth/login", data={
            "username": "testuser",
            "password": "password123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_잘못된_비밀번호_401(self, client):
        """비밀번호 불일치 시 401"""
        self._register(client)
        response = client.post("/api/auth/login", data={
            "username": "testuser",
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    def test_없는_사용자_401(self, client):
        """존재하지 않는 사용자 로그인 시 401"""
        response = client.post("/api/auth/login", data={
            "username": "nobody",
            "password": "password123",
        })
        assert response.status_code == 401


class TestProtectedEndpoint:
    """인증이 필요한 엔드포인트 테스트"""

    def _get_token(self, client, username="testuser", password="password123") -> str:
        """토큰 발급 헬퍼"""
        client.post("/api/auth/register", json={"username": username, "password": password})
        response = client.post("/api/auth/login", data={"username": username, "password": password})
        return response.json()["access_token"]

    def test_토큰_없이_게시글_생성_401(self, client):
        """
        인증 없이 게시글 생성 시 401

        Spring Security 비교:
        @PreAuthorize("isAuthenticated()") 가 적용된 API 호출 시
        토큰 없으면 401 반환
        """
        response = client.post("/api/posts/", json={
            "title": "무단 게시글",
            "content": "내용",
            "author": "작성자",
        })
        assert response.status_code == 401

    def test_유효한_토큰으로_게시글_생성_201(self, client):
        """JWT 토큰을 헤더에 포함하면 게시글 생성 성공"""
        token = self._get_token(client)

        response = client.post(
            "/api/posts/",
            json={"title": "인증된 게시글", "content": "내용", "author": "작성자"},
            # Authorization: Bearer <token> 헤더 추가
            # Spring의 mockMvc.header("Authorization", "Bearer " + token) 와 동일
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201

    def test_게시글_조회는_인증_불필요(self, client):
        """GET 엔드포인트는 인증 없이도 접근 가능 (공개 API)"""
        response = client.get("/api/posts/")
        assert response.status_code == 200

    def test_잘못된_토큰으로_401(self, client):
        """위조된 토큰으로 요청 시 401"""
        response = client.post(
            "/api/posts/",
            json={"title": "게시글", "content": "내용", "author": "작성자"},
            headers={"Authorization": "Bearer fake.invalid.token"},
        )
        assert response.status_code == 401

    def test_내_정보_조회(self, client):
        """인증 후 /me 엔드포인트로 본인 정보 확인"""
        token = self._get_token(client, username="myuser")

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["username"] == "myuser"
