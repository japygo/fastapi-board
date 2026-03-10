# app/schemas/auth.py
# 인증 관련 요청/응답 DTO

from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    """
    회원가입 요청 DTO

    Spring 비교:
        public record UserRegisterRequest(
            @NotBlank String username,
            @NotBlank @Size(min=8) String password
        ) {}
    """

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="사용자 아이디 (3~50자)",
        examples=["hong_gildong"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="비밀번호 (8자 이상)",
        examples=["securepassword123"],
    )


class UserResponse(BaseModel):
    """사용자 정보 응답 DTO (비밀번호 제외)"""

    id: int
    username: str
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """
    JWT 토큰 응답 DTO

    Spring Security + JWT 비교:
        public record TokenResponse(String accessToken, String tokenType) {}

    OAuth2 표준 응답 형식을 따릅니다.
    """

    access_token: str = Field(description="JWT 액세스 토큰")
    token_type: str = Field(default="bearer", description="토큰 타입 (항상 'bearer')")
