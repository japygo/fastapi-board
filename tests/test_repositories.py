# tests/test_repositories.py
# 레포지토리 레이어 테스트
# Spring 비교: @DataJpaTest - JPA 레이어만 테스트 (실제 DB 사용)

from app.domain.post import Post
from app.domain.comment import Comment
from app.repositories.post_repository import PostRepository
from app.repositories.comment_repository import CommentRepository


# 테스트에서 사용할 레포지토리 인스턴스
post_repo = PostRepository()
comment_repo = CommentRepository()


class TestPostRepository:
    """게시글 레포지토리 테스트"""

    def _create_post(self, db, title="테스트 게시글", content="내용", author="작성자") -> Post:
        """테스트용 게시글 생성 헬퍼 메서드 (Spring의 @BeforeEach 헬퍼와 유사)"""
        post = Post(title=title, content=content, author=author)
        return post_repo.save(db, post)

    def test_게시글_저장(self, db):
        """게시글 저장 후 ID가 자동 생성되는지 확인"""
        post = Post(title="저장 테스트", content="내용", author="작성자")
        saved = post_repo.save(db, post)

        assert saved.id is not None
        assert saved.title == "저장 테스트"
        assert saved.created_at is not None

    def test_전체_게시글_조회(self, db):
        """여러 게시글 저장 후 전체 조회"""
        # given: 게시글 3개 저장
        for i in range(3):
            self._create_post(db, title=f"게시글 {i}")
        db.commit()  # 트랜잭션 커밋

        # when
        posts = post_repo.find_all(db)

        # then
        assert len(posts) == 3

    def test_게시글_페이지네이션(self, db):
        """페이지네이션 (skip, limit) 동작 확인"""
        # given: 5개 저장
        for i in range(5):
            self._create_post(db, title=f"게시글 {i}")
        db.commit()

        # when: 2개씩, 두 번째 페이지 (skip=2, limit=2)
        page2 = post_repo.find_all(db, skip=2, limit=2)

        # then
        assert len(page2) == 2

    def test_게시글_수_조회(self, db):
        """전체 게시글 수 카운트"""
        # given
        for i in range(3):
            self._create_post(db, title=f"게시글 {i}")
        db.commit()

        # when
        count = post_repo.count(db)

        # then
        assert count == 3

    def test_ID로_게시글_조회(self, db):
        """ID로 게시글 조회 성공 케이스"""
        # given
        post = self._create_post(db)
        db.commit()

        # when
        found = post_repo.find_by_id(db, post.id)

        # then
        assert found is not None
        assert found.id == post.id

    def test_존재하지_않는_ID_조회_시_None(self, db):
        """존재하지 않는 ID 조회 시 None 반환 (Spring의 Optional.empty() 대응)"""
        result = post_repo.find_by_id(db, post_id=9999)
        assert result is None

    def test_게시글_삭제(self, db):
        """게시글 삭제 후 조회 시 None"""
        # given
        post = self._create_post(db)
        db.commit()
        post_id = post.id

        # when
        post_repo.delete(db, post)
        db.commit()

        # then
        assert post_repo.find_by_id(db, post_id) is None


class TestCommentRepository:
    """댓글 레포지토리 테스트"""

    def _create_post(self, db) -> Post:
        """테스트용 게시글 생성"""
        post = Post(title="게시글", content="내용", author="작성자")
        post_repo.save(db, post)
        db.commit()
        return post

    def test_댓글_저장(self, db):
        """댓글 저장 테스트"""
        post = self._create_post(db)

        comment = Comment(content="좋은 글!", author="댓글러", post_id=post.id)
        saved = comment_repo.save(db, comment)
        db.commit()

        assert saved.id is not None
        assert saved.post_id == post.id

    def test_게시글별_댓글_조회(self, db):
        """특정 게시글의 댓글만 조회되는지 확인"""
        # given: 게시글 2개, 각각 댓글 추가
        post1 = self._create_post(db)
        post2 = self._create_post(db)

        comment_repo.save(db, Comment(content="댓글1", author="작성자", post_id=post1.id))
        comment_repo.save(db, Comment(content="댓글2", author="작성자", post_id=post1.id))
        comment_repo.save(db, Comment(content="다른 게시글 댓글", author="작성자", post_id=post2.id))
        db.commit()

        # when: post1의 댓글만 조회
        comments = comment_repo.find_by_post_id(db, post1.id)

        # then: post1 댓글 2개만 반환
        assert len(comments) == 2
        assert all(c.post_id == post1.id for c in comments)
