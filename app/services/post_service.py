# app/services/post_service.py
# Spring의 @Service 역할
# 비즈니스 로직을 담당하는 레이어입니다
#
# [Spring 비교]
# @Service
# @Transactional
# public class PostService { ... }
#
# [레이어 역할 구분]
# Repository: DB 쿼리만 담당 (어떻게 데이터를 가져올지)
# Service:    비즈니스 로직 + 트랜잭션 관리 (무엇을 할지)
# Router:     HTTP 요청/응답 처리 (어떤 데이터를 받고 반환할지)

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.cache import cacheable, cache_evict, make_cache_key, evict_post_cache
from app.domain.post import Post
from app.repositories.post_repository import PostRepository
from app.schemas.post import PostCreateRequest, PostUpdateRequest, PostListResponse, PostResponse


class PostService:
    """
    게시글 서비스

    Spring 비교:
        @Service
        public class PostService {
            @Autowired
            private final PostRepository postRepository;
            ...
        }

    Python에서는 생성자(__init__)에서 레포지토리를 주입받습니다.
    FastAPI의 Depends() 로 서비스 인스턴스를 라우터에 주입합니다.
    """

    def __init__(self):
        # Spring의 @Autowired PostRepository 와 유사
        # 여기서는 간단하게 직접 인스턴스 생성 (DI 컨테이너 없이)
        self.post_repo = PostRepository()

    # ── 게시글 목록 조회 (캐시 적용) ─────────────────────────────────────────────
    # Spring @Cacheable 비교:
    #   @Cacheable(value = "posts", key = "'posts:' + #skip + ':' + #limit")
    #   @Transactional(readOnly = true)
    #   public PostListResponse getPosts(int skip, int limit) { ... }
    @cacheable(
        key_func=lambda db, skip=0, limit=20, **kw: make_cache_key("posts", skip, limit),
        ttl=60,  # 목록은 1분 캐시 (자주 변경되므로 단건보다 짧게)
    )
    def get_posts(self, db: Session, skip: int = 0, limit: int = 20) -> PostListResponse:
        """
        게시글 목록 조회 (캐시 적용)

        [캐시 키] posts:{skip}:{limit}
        예) posts:0:20, posts:20:20

        [캐시 전략]
        - 목록은 게시글 생성/수정/삭제 시 전체 무효화 (allEntries=true 와 유사)
        - TTL: 60초 (목록은 단건보다 변경 빈도가 높으므로 짧게 설정)

        Spring 비교:
            @Transactional(readOnly = true)
            public Page<PostResponse> getPosts(Pageable pageable) { ... }

        트랜잭션: 읽기 전용 (변경 없음)
        """
        posts = self.post_repo.find_all(db, skip=skip, limit=limit)
        total = self.post_repo.count(db)

        # 엔티티 리스트 → 응답 DTO 리스트 변환
        # Spring의 posts.stream().map(PostResponse::from).collect(toList()) 와 동일
        post_responses = [PostResponse.model_validate(post) for post in posts]

        return PostListResponse(posts=post_responses, total=total)

    # ── 게시글 단건 조회 (캐시 적용) ─────────────────────────────────────────────
    # Spring @Cacheable 비교:
    #   @Cacheable(value = "post", key = "#postId")
    #   @Transactional(readOnly = true)
    #   public PostResponse getPost(Long postId) { ... }
    @cacheable(
        key_func=lambda db, post_id, **kw: make_cache_key("post", post_id),
        ttl=300,  # 단건은 5분 캐시
    )
    def get_post(self, db: Session, post_id: int) -> PostResponse:
        """
        게시글 단건 조회 (캐시 적용)

        [캐시 키] post:{post_id}
        예) post:1, post:42

        [캐시 전략]
        - 단건은 해당 게시글 수정/삭제 시에만 무효화
        - TTL: 300초 (5분)

        Spring 비교:
            @Transactional(readOnly = true)
            public PostResponse getPost(Long id) {
                Post post = postRepository.findById(id)
                    .orElseThrow(() -> new PostNotFoundException(id));
                return PostResponse.from(post);
            }
        """
        post = self.post_repo.find_by_id(db, post_id)

        # 존재하지 않는 경우 404 에러 발생
        # Spring의 @ResponseStatus(HttpStatus.NOT_FOUND) 예외와 동일 효과
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"게시글을 찾을 수 없습니다. (id={post_id})",
            )

        return PostResponse.model_validate(post)

    # ── 게시글 생성 (캐시 무효화) ─────────────────────────────────────────────────
    # Spring @CacheEvict 비교:
    #   @CacheEvict(value = "posts", allEntries = true)
    #   @Transactional
    #   public PostResponse createPost(PostCreateRequest request) { ... }
    @cache_evict("posts:*")  # 목록 캐시 전체 무효화 (새 게시글이 추가되었으므로)
    def create_post(self, db: Session, request: PostCreateRequest) -> PostResponse:
        """
        게시글 생성 (목록 캐시 무효화)

        [캐시 동작]
        생성 성공 후 → "posts:*" 패턴의 모든 캐시 삭제
        → 다음 목록 조회 시 DB에서 최신 데이터를 가져와 다시 캐시

        Spring 비교:
            @Transactional
            public PostResponse createPost(PostCreateRequest request) {
                Post post = new Post(request.title(), request.content(), request.author());
                Post saved = postRepository.save(post);
                return PostResponse.from(saved);
            }

        [트랜잭션 관리]
        Spring: @Transactional 어노테이션이 자동으로 트랜잭션 시작/커밋/롤백
        Python: 라우터에서 get_db() 를 통해 세션을 받고, 서비스에서 commit() 호출
                예외 발생 시 FastAPI가 자동으로 세션을 닫음 (conftest의 finally 참고)
        """
        # DTO → 엔티티 변환 (Spring의 new Post(request) 와 동일)
        post = Post(
            title=request.title,
            content=request.content,
            author=request.author,
        )

        saved_post = self.post_repo.save(db, post)
        db.commit()  # 트랜잭션 커밋 (Spring의 @Transactional 종료 시 자동 커밋)

        return PostResponse.model_validate(saved_post)

    def update_post(
        self, db: Session, post_id: int, request: PostUpdateRequest
    ) -> PostResponse:
        """
        게시글 수정 (PATCH - 일부 필드만 수정 가능) + 캐시 무효화

        [캐시 동작]
        수정 성공 후 → 해당 게시글 단건 캐시 + 목록 캐시 모두 삭제

        Spring @CacheEvict 비교:
            @Caching(evict = {
                @CacheEvict(value = "post", key = "#id"),
                @CacheEvict(value = "posts", allEntries = true)
            })
            @Transactional
            public PostResponse updatePost(Long id, PostUpdateRequest request) { ... }

        [변경 감지(Dirty Checking)]
        Spring JPA: @Transactional 안에서 엔티티 필드를 변경하면 자동으로 UPDATE
        SQLAlchemy: 세션 안에서 객체를 변경하고 commit() 하면 자동으로 UPDATE
        → 동일한 개념! 별도의 save() 호출이 필요 없습니다.
        """
        post = self.post_repo.find_by_id(db, post_id)
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"게시글을 찾을 수 없습니다. (id={post_id})",
            )

        # None이 아닌 필드만 업데이트 (PATCH 방식)
        if request.title is not None:
            post.title = request.title
        if request.content is not None:
            post.content = request.content

        # 변경 감지(Dirty Checking): 명시적 save() 없이 commit()만으로 UPDATE 실행
        db.commit()
        db.refresh(post)  # 수정된 updated_at 등 반영

        # 수정된 게시글의 단건 + 목록 캐시 무효화
        # @Caching(evict = {...}) 과 동일한 효과
        evict_post_cache(post_id)

        return PostResponse.model_validate(post)

    def delete_post(self, db: Session, post_id: int) -> None:
        """
        게시글 삭제 + 캐시 무효화

        [캐시 동작]
        삭제 성공 후 → 해당 게시글 단건 캐시 + 목록 캐시 모두 삭제

        Spring @CacheEvict 비교:
            @Caching(evict = {
                @CacheEvict(value = "post", key = "#id"),
                @CacheEvict(value = "posts", allEntries = true)
            })
            @Transactional
            public void deletePost(Long id) { ... }
        """
        post = self.post_repo.find_by_id(db, post_id)
        if post is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"게시글을 찾을 수 없습니다. (id={post_id})",
            )

        self.post_repo.delete(db, post)
        db.commit()

        # 삭제된 게시글의 단건 + 목록 캐시 무효화
        evict_post_cache(post_id)
