# app/schemas/post.py
# Spring의 DTO(Data Transfer Object) / Record 역할
# Pydantic 스키마 = API 요청/응답 데이터의 유효성 검사 + 직렬화 담당
#
# [Spring JPA 비교]
# Entity  → 데이터베이스 테이블과 직접 매핑 (app/domain/post.py)
# DTO     → API 요청/응답에 사용하는 데이터 구조 (이 파일)
# Entity를 그대로 API 응답에 쓰지 않는 이유: 보안(민감 필드 노출 방지), 순환 참조 방지

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── 기본 스키마 ────────────────────────────────────────────────────────────────
class PostBase(BaseModel):
    """
    게시글 공통 필드 정의 (추상 기반 클래스 역할)

    Spring 비교: 공통 필드를 모은 추상 클래스나 인터페이스
    요청/응답 스키마가 공통으로 상속받아 코드 중복을 줄입니다.
    """

    title: str = Field(
        ...,                    # ... = 필수 필드 (Spring의 @NotBlank 역할)
        min_length=1,           # @Size(min=1)
        max_length=200,         # @Size(max=200)
        description="게시글 제목",
        examples=["FastAPI 공부 시작했어요"],
    )
    content: str = Field(
        ...,
        min_length=1,
        description="게시글 내용",
        examples=["오늘부터 FastAPI를 공부하기로 했습니다."],
    )
    author: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="작성자 이름",
        examples=["홍길동"],
    )


# ── 요청 스키마 ────────────────────────────────────────────────────────────────
class PostCreateRequest(PostBase):
    """
    게시글 생성 요청 DTO

    Spring 비교:
        public record PostCreateRequest(
            @NotBlank String title,
            @NotBlank String content,
            @NotBlank String author
        ) {}

    PostBase 의 모든 필드를 그대로 상속합니다.
    현재는 추가 필드가 없지만, 나중에 카테고리나 태그 등을 추가할 수 있습니다.
    """
    pass


class PostUpdateRequest(BaseModel):
    """
    게시글 수정 요청 DTO

    Spring 비교:
        public record PostUpdateRequest(String title, String content) {}

    수정 시에는 일부 필드만 변경할 수 있어야 합니다.
    Optional[str] = None: 값을 보내지 않으면 수정하지 않음 (PATCH 방식)
    """

    title: Optional[str] = Field(
        default=None,       # None이면 수정하지 않음
        min_length=1,
        max_length=200,
        description="수정할 제목 (미입력 시 변경 없음)",
    )
    content: Optional[str] = Field(
        default=None,
        min_length=1,
        description="수정할 내용 (미입력 시 변경 없음)",
    )


# ── 응답 스키마 ────────────────────────────────────────────────────────────────
class PostResponse(PostBase):
    """
    게시글 단건 응답 DTO

    Spring 비교:
        public record PostResponse(
            Long id, String title, String content, String author,
            LocalDateTime createdAt, LocalDateTime updatedAt
        ) {}

    DB에서 조회한 Post 엔티티를 이 스키마로 변환해서 반환합니다.
    from_attributes=True: SQLAlchemy 모델 객체를 직접 변환 가능
    (Spring의 ModelMapper.map(post, PostResponse.class) 와 유사)
    """

    id: int = Field(description="게시글 ID")
    created_at: datetime = Field(description="작성일시")
    updated_at: datetime = Field(description="수정일시")

    # Pydantic 설정
    model_config = {
        # from_attributes=True: ORM 객체(SQLAlchemy Model)를 직접 변환 가능하게 합니다
        # Post 엔티티 객체를 PostResponse(**post.__dict__) 없이 바로 변환
        "from_attributes": True,
    }


class PostListResponse(BaseModel):
    """
    게시글 목록 응답 DTO

    Spring 비교:
        public record PostListResponse(List<PostResponse> posts, int total) {}

    페이지네이션 정보도 포함할 수 있습니다.
    """

    posts: list[PostResponse]
    total: int = Field(description="전체 게시글 수")
