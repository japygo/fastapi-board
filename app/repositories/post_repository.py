# app/repositories/post_repository.py
# Spring의 @Repository + JpaRepository 역할
# 데이터베이스 CRUD 쿼리를 담당하는 레이어입니다
#
# [Spring JPA 비교]
# public interface PostRepository extends JpaRepository<Post, Long> {
#     List<Post> findAll();
#     Optional<Post> findById(Long id);
#     Post save(Post post);
#     void deleteById(Long id);
# }
#
# Python에서는 인터페이스 대신 클래스로 구현하며,
# 세션(Session)을 직접 받아 쿼리를 실행합니다.

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.domain.post import Post


class PostRepository:
    """
    게시글 레포지토리

    Spring의 JpaRepository 와 달리, SQLAlchemy에서는 직접 메서드를 구현합니다.
    각 메서드는 Session 을 받아 쿼리를 실행합니다.

    [의존성 주입 방식]
    Spring: @Autowired PostRepository postRepository;
    Python: __init__에서 Session 주입 또는 각 메서드 파라미터로 전달

    여기서는 각 메서드에 db(Session)를 파라미터로 받는 방식을 사용합니다.
    (서비스 레이어에서 트랜잭션을 관리하는 패턴)
    """

    def find_all(self, db: Session, skip: int = 0, limit: int = 20) -> list[Post]:
        """
        게시글 목록 조회 (페이지네이션 포함)

        Spring JPA 비교:
            postRepository.findAll(PageRequest.of(page, size))

        SQLAlchemy 2.x 방식:
            select() 함수로 쿼리를 빌드하고 execute() 로 실행합니다.
            (이전 방식: db.query(Post).all())

        Args:
            db: 데이터베이스 세션
            skip: 건너뛸 레코드 수 (OFFSET, 0부터 시작)
            limit: 조회할 최대 레코드 수 (LIMIT)
        """
        # select(Post): SELECT * FROM posts
        # offset(skip): OFFSET skip
        # limit(limit): LIMIT limit
        # order_by(Post.created_at.desc()): ORDER BY created_at DESC (최신순)
        stmt = (
            select(Post)
            .order_by(Post.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        # scalars(): 결과에서 첫 번째 컬럼(Post 객체)만 추출
        # all(): 결과를 리스트로 반환
        return list(db.execute(stmt).scalars().all())

    def count(self, db: Session) -> int:
        """
        전체 게시글 수 조회

        Spring JPA 비교: postRepository.count()
        """
        stmt = select(func.count()).select_from(Post)
        return db.execute(stmt).scalar_one()  # 단일 값 반환

    def find_by_id(self, db: Session, post_id: int) -> Post | None:
        """
        ID로 게시글 단건 조회

        Spring JPA 비교: postRepository.findById(id)
        반환 타입: Post | None (Spring의 Optional<Post> 와 동일)

        db.get(): 기본 키(Primary Key)로 조회하는 최적화된 메서드
        - 1차 캐시(세션 내 캐시)를 먼저 확인하고, 없으면 DB 쿼리
        - JPA의 em.find() 와 동일한 동작
        """
        return db.get(Post, post_id)

    def save(self, db: Session, post: Post) -> Post:
        """
        게시글 저장 (생성)

        Spring JPA 비교: postRepository.save(post)

        db.add(): INSERT 준비 (영속성 컨텍스트에 추가)
        db.flush(): DB에 SQL 전송 (커밋은 아님, id 등 DB 생성 값 반영)
        db.refresh(): DB에서 최신 데이터 다시 조회 (자동 생성 필드 반영)

        [트랜잭션 관리]
        commit()은 서비스 레이어에서 처리합니다.
        레포지토리는 DB 접근만 담당합니다.
        """
        db.add(post)
        db.flush()    # id 자동 생성을 위해 flush (commit 전 SQL 전송)
        db.refresh(post)  # DB에서 새로 조회 (created_at 등 반영)
        return post

    def delete(self, db: Session, post: Post) -> None:
        """
        게시글 삭제

        Spring JPA 비교: postRepository.delete(post)
        """
        db.delete(post)
        db.flush()
