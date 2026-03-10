# tests/test_domain.py
# 도메인 모델(Entity) 테스트
# Spring의 @DataJpaTest 와 유사한 역할 (DB 레이어만 테스트)

from app.domain.post import Post
from app.domain.comment import Comment


class TestPostModel:
    """
    Post 엔티티 테스트

    Spring 비교:
        @DataJpaTest
        class PostEntityTest { ... }
    """

    def test_게시글_생성(self, db):
        """게시글이 DB에 정상적으로 저장되는지 확인"""
        # given: 테스트 데이터 준비 (Spring의 given 단계)
        post = Post(
            title="첫 번째 게시글",
            content="FastAPI를 공부하고 있습니다.",
            author="홍길동",
        )

        # when: DB에 저장 (Spring의 save() 메서드 역할)
        db.add(post)      # INSERT 준비 (영속성 컨텍스트에 추가)
        db.commit()       # 실제 DB에 반영 (트랜잭션 커밋)
        db.refresh(post)  # DB에서 최신 데이터 재조회 (자동 생성된 id, created_at 등 반영)

        # then: 저장 결과 검증
        assert post.id is not None, "기본 키(id)가 자동 생성되어야 합니다"
        assert post.title == "첫 번째 게시글"
        assert post.author == "홍길동"
        assert post.created_at is not None, "작성일시가 자동 설정되어야 합니다"

    def test_게시글_조회(self, db):
        """저장한 게시글을 조회할 수 있는지 확인"""
        # given
        post = Post(title="조회 테스트", content="내용", author="작성자")
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id

        # when: 기본 키로 조회 (Spring의 findById() 역할)
        # db.get(): 기본 키로 단건 조회
        found = db.get(Post, post_id)

        # then
        assert found is not None
        assert found.title == "조회 테스트"

    def test_게시글_수정(self, db):
        """게시글 내용이 수정되는지 확인"""
        # given
        post = Post(title="원래 제목", content="원래 내용", author="작성자")
        db.add(post)
        db.commit()
        db.refresh(post)

        # when: 필드 변경 후 커밋 (JPA의 변경 감지와 달리 명시적 commit 필요)
        post.title = "수정된 제목"
        db.commit()
        db.refresh(post)

        # then
        assert post.title == "수정된 제목"

    def test_게시글_삭제(self, db):
        """게시글 삭제 후 조회 시 None이 반환되는지 확인"""
        # given
        post = Post(title="삭제할 게시글", content="내용", author="작성자")
        db.add(post)
        db.commit()
        db.refresh(post)
        post_id = post.id

        # when
        db.delete(post)
        db.commit()

        # then
        deleted = db.get(Post, post_id)
        assert deleted is None, "삭제 후 조회 시 None이어야 합니다"


class TestCommentModel:
    """댓글 엔티티 테스트"""

    def test_댓글_생성_및_게시글_연관관계(self, db):
        """댓글이 게시글과 올바르게 연관되는지 확인"""
        # given: 게시글 먼저 생성 (외래 키 제약으로 인해 선행 필요)
        post = Post(title="댓글 테스트 게시글", content="내용", author="작성자")
        db.add(post)
        db.commit()
        db.refresh(post)

        # when: 댓글 생성
        comment = Comment(
            content="좋은 글이네요!",
            author="댓글러",
            post_id=post.id,  # 외래 키 설정 (@JoinColumn 역할)
        )
        db.add(comment)
        db.commit()
        db.refresh(comment)

        # then
        assert comment.id is not None
        assert comment.post_id == post.id

    def test_게시글_삭제_시_댓글도_삭제(self, db):
        """게시글 삭제 시 연관된 댓글도 CASCADE로 삭제되는지 확인"""
        # given
        post = Post(title="게시글", content="내용", author="작성자")
        db.add(post)
        db.commit()
        db.refresh(post)

        comment = Comment(content="댓글", author="댓글러", post_id=post.id)
        db.add(comment)
        db.commit()
        db.refresh(comment)
        comment_id = comment.id

        # when: 게시글 삭제 (cascade = "all, delete-orphan" 동작)
        db.delete(post)
        db.commit()

        # then: 댓글도 함께 삭제되어야 함
        deleted_comment = db.get(Comment, comment_id)
        assert deleted_comment is None, "게시글 삭제 시 댓글도 삭제되어야 합니다 (CASCADE)"
