# app/routers/post_router.py
# Spring의 @RestController 역할
# HTTP 요청을 받고 응답을 반환하는 레이어입니다
#
# [Spring 비교]
# @RestController
# @RequestMapping("/api/posts")
# public class PostController {
#     @Autowired PostService postService;
#     ...
# }

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain.user import User
from app.auth.dependencies import get_current_active_user
from app.services.post_service import PostService
from app.tasks import increment_view_count
from app.schemas.post import (
    PostCreateRequest,
    PostUpdateRequest,
    PostResponse,
    PostListResponse,
)

# APIRouter: Spring의 @RequestMapping 역할
# prefix: 모든 엔드포인트 앞에 붙는 경로
# tags: Swagger UI에서 그룹 이름
router = APIRouter(
    prefix="/api/posts",
    tags=["게시글"],
)

# 서비스 인스턴스 생성
# Spring의 @Autowired 와 달리, FastAPI는 Depends() 로 의존성을 주입합니다
# 간단한 경우 전역 인스턴스를 사용합니다
post_service = PostService()


# ── 게시글 목록 조회 ───────────────────────────────────────────────────────────
@router.get(
    "/",
    response_model=PostListResponse,    # 반환 타입 (Spring의 ResponseEntity<PostListResponse>)
    summary="게시글 목록 조회",
)
def get_posts(
    skip: int = 0,         # 쿼리 파라미터 (Spring의 @RequestParam int skip = 0)
    limit: int = 20,       # 쿼리 파라미터 (Spring의 @RequestParam int limit = 20)
    db: Session = Depends(get_db),  # 의존성 주입 (Spring의 @Autowired)
):
    """
    게시글 목록을 페이지네이션으로 조회합니다.

    - **skip**: 건너뛸 게시글 수 (0부터 시작)
    - **limit**: 한 번에 조회할 최대 수
    """
    return post_service.get_posts(db, skip=skip, limit=limit)


# ── 게시글 단건 조회 ───────────────────────────────────────────────────────────
@router.get(
    "/{post_id}",           # 경로 변수 (Spring의 @PathVariable Long postId)
    response_model=PostResponse,
    summary="게시글 단건 조회",
)
def get_post(
    post_id: int,           # FastAPI가 URL에서 자동으로 int로 변환
    background_tasks: BackgroundTasks,  # Spring의 @Async 호출을 위한 트리거 역할
    db: Session = Depends(get_db),
):
    """
    ID로 게시글을 조회합니다. 존재하지 않으면 404를 반환합니다.

    [BackgroundTasks 동작 순서]
    1. 게시글 조회 → 클라이언트에 응답 반환 (빠른 응답)
    2. 응답 반환 완료 후 → 백그라운드에서 view_count += 1 실행

    Spring @Async 비교:
        @GetMapping("/{id}")
        public PostResponse getPost(@PathVariable Long id) {
            PostResponse response = postService.getPost(id);
            asyncTaskService.incrementViewCount(id);  // @Async 메서드 호출
            return response;                          // 즉시 반환, @Async는 별도 실행
        }

    차이점:
    - Spring @Async: 메서드 호출 즉시 별도 스레드에서 실행 시작
    - FastAPI BackgroundTasks: 응답이 클라이언트에 완전히 전송된 뒤 실행 시작
    """
    post = post_service.get_post(db, post_id)

    # 응답 반환 후 백그라운드에서 조회수 증가
    # add_task(함수, *인자) 형태로 등록
    # Spring의 asyncTaskService.incrementViewCount(post_id) 와 동일한 역할
    background_tasks.add_task(increment_view_count, post_id)

    return post


# ── 게시글 생성 ────────────────────────────────────────────────────────────────
@router.post(
    "/",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,  # 성공 시 201 반환 (Spring의 @ResponseStatus(CREATED))
    summary="게시글 생성",
)
def create_post(
    request: PostCreateRequest,
    db: Session = Depends(get_db),
    # 인증 적용: 이 파라미터가 있으면 JWT 토큰이 없을 때 401 자동 반환
    # Spring의 @PreAuthorize("isAuthenticated()") 와 동일한 효과
    current_user: User = Depends(get_current_active_user),
):
    """
    새 게시글을 생성합니다.

    - **title**: 게시글 제목 (1~200자)
    - **content**: 게시글 내용
    - **author**: 작성자 이름 (1~50자)
    """
    return post_service.create_post(db, request)


# ── 게시글 수정 ────────────────────────────────────────────────────────────────
@router.patch(
    "/{post_id}",
    response_model=PostResponse,
    summary="게시글 수정 (일부 필드)",
)
def update_post(
    post_id: int,
    request: PostUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),  # 인증 필요
):
    """
    게시글을 수정합니다. 입력한 필드만 변경됩니다 (PATCH 방식).

    - **title**: 수정할 제목 (미입력 시 변경 없음)
    - **content**: 수정할 내용 (미입력 시 변경 없음)
    """
    return post_service.update_post(db, post_id, request)


# ── 게시글 삭제 ────────────────────────────────────────────────────────────────
@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,  # 성공 시 204 반환 (본문 없음)
    summary="게시글 삭제",
)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),  # 인증 필요
):
    """게시글을 삭제합니다. 연관된 댓글도 함께 삭제됩니다."""
    post_service.delete_post(db, post_id)
    # 204 No Content: return 없음 (Spring의 ResponseEntity.noContent().build() 와 동일)
