# app/schemas/comment.py
# 댓글 DTO 스키마

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommentBase(BaseModel):
    """댓글 공통 필드"""

    content: str = Field(
        ...,
        min_length=1,
        description="댓글 내용",
        examples=["좋은 글 감사합니다!"],
    )
    author: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="작성자",
        examples=["댓글러"],
    )


class CommentCreateRequest(CommentBase):
    """
    댓글 생성 요청 DTO

    post_id는 URL 경로에서 받으므로 여기에 포함하지 않습니다.
    예) POST /posts/{post_id}/comments
    """
    pass


class CommentUpdateRequest(BaseModel):
    """댓글 수정 요청 DTO (내용만 수정 가능)"""

    content: Optional[str] = Field(
        default=None,
        min_length=1,
        description="수정할 댓글 내용",
    )


class CommentResponse(CommentBase):
    """댓글 응답 DTO"""

    id: int = Field(description="댓글 ID")
    post_id: int = Field(description="게시글 ID")
    created_at: datetime = Field(description="작성일시")
    updated_at: datetime = Field(description="수정일시")

    model_config = {
        "from_attributes": True,  # SQLAlchemy 모델 → Pydantic 변환 허용
    }
