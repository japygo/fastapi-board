# tests/test_auth.py
# 인증 API 통합 테스트 (비동기 fixture 버전)
# Spring 비교: @SpringBootTest + Spring Security 테스트
#
# [Before → After]
# Before: def test_*(self, client):
# After:  async def test_*(self, client):
#
# ※ TestClient 자체는 동기입니다. async def 는 async fixture와 연결을 위해 필요합니다.


class TestRegister:
    """회원가입 API 테스트"""

    async def test_회원가입_성공_201(self, client):  # def → async def
        response = client.post("/api/auth/register", json={
            "username": "testuser", "password": "password123",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["is_active"] is True
        assert "password" not in data
        assert "hashed_password" not in data

    async def test_중복_아이디_409(self, client):  # def → async def
        client.post("/api/auth/register", json={"username": "dupe", "password": "password123"})
        response = client.post("/api/auth/register", json={"username": "dupe", "password": "password123"})
        assert response.status_code == 409

    async def test_짧은_비밀번호_422(self, client):  # def → async def
        response = client.post("/api/auth/register", json={
            "username": "user1", "password": "short",
        })
        assert response.status_code == 422


class TestLogin:
    """로그인 API 테스트"""

    def _register(self, client, username="testuser", password="password123"):
        client.post("/api/auth/register", json={"username": username, "password": password})

    async def test_로그인_성공_JWT_발급(self, client):  # def → async def
        self._register(client)
        response = client.post("/api/auth/login", data={
            "username": "testuser", "password": "password123",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_잘못된_비밀번호_401(self, client):  # def → async def
        self._register(client)
        response = client.post("/api/auth/login", data={
            "username": "testuser", "password": "wrongpassword",
        })
        assert response.status_code == 401

    async def test_없는_사용자_401(self, client):  # def → async def
        response = client.post("/api/auth/login", data={
            "username": "nobody", "password": "password123",
        })
        assert response.status_code == 401


class TestProtectedEndpoint:
    """인증이 필요한 엔드포인트 테스트"""

    def _get_token(self, client, username="testuser", password="password123") -> str:
        client.post("/api/auth/register", json={"username": username, "password": password})
        response = client.post("/api/auth/login", data={"username": username, "password": password})
        return response.json()["access_token"]

    async def test_토큰_없이_게시글_생성_401(self, client):  # def → async def
        response = client.post("/api/posts/", json={
            "title": "무단 게시글", "content": "내용", "author": "작성자",
        })
        assert response.status_code == 401

    async def test_유효한_토큰으로_게시글_생성_201(self, client):  # def → async def
        token = self._get_token(client)
        response = client.post(
            "/api/posts/",
            json={"title": "인증된 게시글", "content": "내용", "author": "작성자"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201

    async def test_게시글_조회는_인증_불필요(self, client):  # def → async def
        response = client.get("/api/posts/")
        assert response.status_code == 200

    async def test_잘못된_토큰으로_401(self, client):  # def → async def
        response = client.post(
            "/api/posts/",
            json={"title": "게시글", "content": "내용", "author": "작성자"},
            headers={"Authorization": "Bearer fake.invalid.token"},
        )
        assert response.status_code == 401

    async def test_내_정보_조회(self, client):  # def → async def
        token = self._get_token(client, username="myuser")
        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["username"] == "myuser"
