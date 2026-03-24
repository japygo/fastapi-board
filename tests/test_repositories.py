# tests/test_repositories.py
# 레포지토리 레이어 테스트 (비동기 버전)
# Spring 비교: @DataJpaTest - JPA 레이어만 테스트 (실제 DB 사용)
#
# [Before → After]
# Before: def test_*(self, db): result = post_repo.find_all(db)
# After:  async def test_*(self, db): result = await post_repo.find_all(db)  ← await

from app.domain.post import Post
from app.domain.comment import Comment
from app.repositories.post_repository import PostRepository
from app.repositories.comment_repository import CommentRepository

post_repo = PostRepository()
comment_repo = CommentRepository()


class TestPostRepository:
    """게시글 레포지토리 테스트 (비동기)"""

    async def _create_post(self, db, title="테스트 게시글", content="내용", author="작성자") -> Post:
        """테스트용 게시글 생성 헬퍼 (def → async def)"""
        post = Post(title=title, content=content, author=author)
        return await post_repo.save(db, post)  # ← await

    async def test_게시글_저장(self, db):  # def → async def
        """게시글 저장 후 ID가 자동 생성되는지 확인"""
        post = Post(title="저장 테스트", content="내용", author="작성자")
        saved = await post_repo.save(db, post)  # ← await

        assert saved.id is not None
        assert saved.title == "저장 테스트"
        assert saved.created_at is not None

    async def test_전체_게시글_조회(self, db):  # def → async def
        """여러 게시글 저장 후 전체 조회"""
        for i in range(3):
            await self._create_post(db, title=f"게시글 {i}")  # ← await
        await db.commit()  # ← await

        posts = await post_repo.find_all(db)  # ← await

        assert len(posts) == 3

    async def test_게시글_페이지네이션(self, db):  # def → async def
        """페이지네이션 (skip, limit) 동작 확인"""
        for i in range(5):
            await self._create_post(db, title=f"게시글 {i}")  # ← await
        await db.commit()  # ← await

        page2 = await post_repo.find_all(db, skip=2, limit=2)  # ← await

        assert len(page2) == 2

    async def test_게시글_수_조회(self, db):  # def → async def
        """전체 게시글 수 카운트"""
        for i in range(3):
            await self._create_post(db, title=f"게시글 {i}")  # ← await
        await db.commit()  # ← await

        count = await post_repo.count(db)  # ← await

        assert count == 3

    async def test_ID로_게시글_조회(self, db):  # def → async def
        """ID로 게시글 조회 성공 케이스"""
        post = await self._create_post(db)  # ← await
        await db.commit()  # ← await

        found = await post_repo.find_by_id(db, post.id)  # ← await

        assert found is not None
        assert found.id == post.id

    async def test_존재하지_않는_ID_조회_시_None(self, db):  # def → async def
        result = await post_repo.find_by_id(db, post_id=9999)  # ← await
        assert result is None

    async def test_게시글_삭제(self, db):  # def → async def
        """게시글 삭제 후 조회 시 None"""
        post = await self._create_post(db)  # ← await
        await db.commit()  # ← await
        post_id = post.id

        await post_repo.delete(db, post)  # ← await
        await db.commit()  # ← await

        assert await post_repo.find_by_id(db, post_id) is None  # ← await


class TestCommentRepository:
    """댓글 레포지토리 테스트 (비동기)"""

    async def _create_post(self, db) -> Post:
        """테스트용 게시글 생성 (def → async def)"""
        post = Post(title="게시글", content="내용", author="작성자")
        await post_repo.save(db, post)  # ← await
        await db.commit()  # ← await
        return post

    async def test_댓글_저장(self, db):  # def → async def
        """댓글 저장 테스트"""
        post = await self._create_post(db)  # ← await

        comment = Comment(content="좋은 글!", author="댓글러", post_id=post.id)
        saved = await comment_repo.save(db, comment)  # ← await
        await db.commit()  # ← await

        assert saved.id is not None
        assert saved.post_id == post.id

    async def test_게시글별_댓글_조회(self, db):  # def → async def
        """특정 게시글의 댓글만 조회되는지 확인"""
        post1 = await self._create_post(db)  # ← await
        post2 = await self._create_post(db)  # ← await

        await comment_repo.save(db, Comment(content="댓글1", author="작성자", post_id=post1.id))
        await comment_repo.save(db, Comment(content="댓글2", author="작성자", post_id=post1.id))
        await comment_repo.save(db, Comment(content="다른 댓글", author="작성자", post_id=post2.id))
        await db.commit()  # ← await

        comments = await comment_repo.find_by_post_id(db, post1.id)  # ← await

        assert len(comments) == 2
        assert all(c.post_id == post1.id for c in comments)
