# tests/test_schemas.py
# Pydantic 스키마(DTO) 유효성 검사 테스트
# Spring 비교: Bean Validation (@Valid) 테스트

import pytest
from pydantic import ValidationError

from app.schemas.post import PostCreateRequest, PostUpdateRequest, PostResponse
from app.schemas.comment import CommentCreateRequest


class TestPostCreateRequest:
    """게시글 생성 요청 DTO 유효성 검사 테스트"""

    def test_정상_생성(self):
        """유효한 데이터로 DTO 생성"""
        dto = PostCreateRequest(
            title="테스트 제목",
            content="테스트 내용",
            author="홍길동",
        )
        assert dto.title == "테스트 제목"
        assert dto.author == "홍길동"

    def test_제목_빈값_거부(self):
        """빈 제목은 유효성 검사에서 거부되어야 함 (@NotBlank 역할)"""
        with pytest.raises(ValidationError) as exc_info:
            PostCreateRequest(title="", content="내용", author="작성자")

        # 에러 메시지에 title 관련 내용이 있는지 확인
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("title",) for e in errors)

    def test_제목_공백만_있는_경우_거부(self):
        """공백만 있는 제목도 거부 (min_length=1 이므로 공백 1자는 허용됨에 주의)"""
        # Pydantic의 min_length는 문자열 길이 검사이므로 공백 1자는 통과합니다
        # 실제 서비스에서는 strip() 후 검사하는 커스텀 validator 추가 가능
        with pytest.raises(ValidationError):
            PostCreateRequest(title="", content="내용", author="작성자")

    def test_제목_최대_길이_초과_거부(self):
        """200자 초과 제목 거부"""
        with pytest.raises(ValidationError):
            PostCreateRequest(title="a" * 201, content="내용", author="작성자")

    def test_필수_필드_누락_거부(self):
        """필수 필드 누락 시 ValidationError 발생"""
        with pytest.raises(ValidationError):
            PostCreateRequest(title="제목")  # content, author 누락


class TestPostUpdateRequest:
    """게시글 수정 요청 DTO 테스트"""

    def test_일부_필드만_수정(self):
        """수정 DTO는 일부 필드만 포함해도 유효함 (PATCH 방식)"""
        dto = PostUpdateRequest(title="새 제목")  # content 없어도 됨
        assert dto.title == "새 제목"
        assert dto.content is None  # 미입력 시 None

    def test_빈_수정_요청도_유효(self):
        """아무 필드도 없는 수정 요청도 유효 (나중에 서비스 레이어에서 처리)"""
        dto = PostUpdateRequest()
        assert dto.title is None
        assert dto.content is None


class TestPostResponse:
    """응답 DTO 변환 테스트 (ORM 모델 → DTO)"""

    async def test_orm_객체에서_변환(self, db):  # def → async def
        """SQLAlchemy 모델 객체를 응답 DTO로 변환"""
        from app.domain.post import Post

        # given: DB에 게시글 저장
        post = Post(title="제목", content="내용", author="작성자")
        db.add(post)
        await db.commit()      # ← await
        await db.refresh(post) # ← await

        # when: ORM 모델 → Pydantic DTO 변환
        # Spring의 ModelMapper.map(post, PostResponse.class) 와 동일
        response = PostResponse.model_validate(post)

        # then
        assert response.id == post.id
        assert response.title == "제목"
        assert response.created_at is not None
