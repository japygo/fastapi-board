# tests/test_domain.py
# 도메인 모델(Entity) 테스트 (비동기 버전)
# Spring의 @DataJpaTest 와 유사한 역할 (DB 레이어만 테스트)
#
# [Before → After]
# Before: def test_*(self, db):    db.add(post); db.commit(); db.refresh(post)
# After:  async def test_*(self, db): await db.add(post) → db.add(post)은 sync
#                                     await db.commit(); await db.refresh(post)  ← await
#
# ※ db.add()는 세션 내 메모리 작업이라 sync. I/O가 발생하는 commit/flush/refresh만 await

from app.domain.post import Post
from app.domain.comment import Comment


class TestPostModel:
    """Post 엔티티 테스트 (비동기)"""

    async def test_게시글_생성(self, db):  # def → async def
        """게시글이 DB에 정상적으로 저장되는지 확인"""
        post = Post(title="첫 번째 게시글", content="FastAPI를 공부하고 있습니다.", author="홍길동")

        db.add(post)           # add()는 메모리 작업 → await 불필요
        await db.commit()      # ← await: DB에 SQL 전송
        await db.refresh(post) # ← await: 자동 생성 필드(id, created_at) 반영

        assert post.id is not None
        assert post.title == "첫 번째 게시글"
        assert post.author == "홍길동"
        assert post.created_at is not None

    async def test_게시글_조회(self, db):  # def → async def
        """저장한 게시글을 조회할 수 있는지 확인"""
        post = Post(title="조회 테스트", content="내용", author="작성자")
        db.add(post)
        await db.commit()      # ← await
        await db.refresh(post) # ← await
        post_id = post.id

        found = await db.get(Post, post_id)  # ← await: DB 조회

        assert found is not None
        assert found.title == "조회 테스트"

    async def test_게시글_수정(self, db):  # def → async def
        """게시글 내용이 수정되는지 확인"""
        post = Post(title="원래 제목", content="원래 내용", author="작성자")
        db.add(post)
        await db.commit()      # ← await
        await db.refresh(post) # ← await

        post.title = "수정된 제목"
        await db.commit()      # ← await: 변경 감지(Dirty Checking) + 커밋
        await db.refresh(post) # ← await

        assert post.title == "수정된 제목"

    async def test_게시글_삭제(self, db):  # def → async def
        """게시글 삭제 후 조회 시 None이 반환되는지 확인"""
        post = Post(title="삭제할 게시글", content="내용", author="작성자")
        db.add(post)
        await db.commit()      # ← await
        await db.refresh(post) # ← await
        post_id = post.id

        await db.delete(post)  # ← await
        await db.commit()      # ← await

        deleted = await db.get(Post, post_id)  # ← await
        assert deleted is None


class TestCommentModel:
    """댓글 엔티티 테스트 (비동기)"""

    async def test_댓글_생성_및_게시글_연관관계(self, db):  # def → async def
        """댓글이 게시글과 올바르게 연관되는지 확인"""
        post = Post(title="댓글 테스트 게시글", content="내용", author="작성자")
        db.add(post)
        await db.commit()      # ← await
        await db.refresh(post) # ← await

        comment = Comment(content="좋은 글이네요!", author="댓글러", post_id=post.id)
        db.add(comment)
        await db.commit()         # ← await
        await db.refresh(comment) # ← await

        assert comment.id is not None
        assert comment.post_id == post.id

    async def test_게시글_삭제_시_댓글도_삭제(self, db):  # def → async def
        """게시글 삭제 시 연관된 댓글도 CASCADE로 삭제되는지 확인"""
        post = Post(title="게시글", content="내용", author="작성자")
        db.add(post)
        await db.commit()      # ← await
        await db.refresh(post) # ← await

        comment = Comment(content="댓글", author="댓글러", post_id=post.id)
        db.add(comment)
        await db.commit()         # ← await
        await db.refresh(comment) # ← await
        comment_id = comment.id

        await db.delete(post)  # ← await: cascade="all, delete-orphan" 동작
        await db.commit()      # ← await

        deleted_comment = await db.get(Comment, comment_id)  # ← await
        assert deleted_comment is None, "게시글 삭제 시 댓글도 삭제되어야 합니다 (CASCADE)"
