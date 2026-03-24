# tests/test_services.py
# 서비스 레이어 테스트 (비동기 버전)
# Spring 비교: @SpringBootTest (서비스 레이어 직접 테스트)
#
# [Before → After]
# Before: def test_*(self, db): result = post_service.create_post(db, ...)
# After:  async def test_*(self, db): result = await post_service.create_post(db, ...)

import pytest
from fastapi import HTTPException

from app.services.post_service import PostService
from app.services.comment_service import CommentService
from app.schemas.post import PostCreateRequest, PostUpdateRequest
from app.schemas.comment import CommentCreateRequest, CommentUpdateRequest

post_service = PostService()
comment_service = CommentService()


class TestPostService:
    """게시글 서비스 테스트 (비동기)"""

    async def _create_post(self, db, title="테스트", content="내용", author="작성자"):
        """테스트용 게시글 생성 헬퍼 (def → async def)"""
        return await post_service.create_post(  # ← await
            db, PostCreateRequest(title=title, content=content, author=author),
        )

    async def test_게시글_생성(self, db):  # def → async def
        response = await self._create_post(db, title="새 게시글", author="홍길동")  # ← await

        assert response.id is not None
        assert response.title == "새 게시글"
        assert response.author == "홍길동"

    async def test_게시글_목록_조회(self, db):  # def → async def
        await self._create_post(db, title="게시글 1")  # ← await
        await self._create_post(db, title="게시글 2")  # ← await

        result = await post_service.get_posts(db)  # ← await

        assert result.total == 2
        assert len(result.posts) == 2

    async def test_게시글_단건_조회(self, db):  # def → async def
        created = await self._create_post(db)  # ← await
        found = await post_service.get_post(db, created.id)  # ← await

        assert found.id == created.id
        assert found.title == created.title

    async def test_존재하지_않는_게시글_조회_시_404(self, db):  # def → async def
        with pytest.raises(HTTPException) as exc_info:
            await post_service.get_post(db, post_id=9999)  # ← await

        assert exc_info.value.status_code == 404

    async def test_게시글_제목_수정(self, db):  # def → async def
        created = await self._create_post(db, title="원래 제목", content="원래 내용")  # ← await

        updated = await post_service.update_post(  # ← await
            db, created.id, PostUpdateRequest(title="수정된 제목"),
        )

        assert updated.title == "수정된 제목"
        assert updated.content == "원래 내용"

    async def test_존재하지_않는_게시글_수정_시_404(self, db):  # def → async def
        with pytest.raises(HTTPException) as exc_info:
            await post_service.update_post(db, 9999, PostUpdateRequest(title="수정"))  # ← await

        assert exc_info.value.status_code == 404

    async def test_게시글_삭제(self, db):  # def → async def
        created = await self._create_post(db)  # ← await
        await post_service.delete_post(db, created.id)  # ← await

        with pytest.raises(HTTPException) as exc_info:
            await post_service.get_post(db, created.id)  # ← await
        assert exc_info.value.status_code == 404

    async def test_존재하지_않는_게시글_삭제_시_404(self, db):  # def → async def
        with pytest.raises(HTTPException) as exc_info:
            await post_service.delete_post(db, 9999)  # ← await

        assert exc_info.value.status_code == 404


class TestCommentService:
    """댓글 서비스 테스트 (비동기)"""

    async def _create_post(self, db):
        """테스트용 게시글 생성 (def → async def)"""
        return await post_service.create_post(  # ← await
            db, PostCreateRequest(title="게시글", content="내용", author="작성자")
        )

    async def _create_comment(self, db, post_id, content="댓글", author="댓글러"):
        """테스트용 댓글 생성 (def → async def)"""
        return await comment_service.create_comment(  # ← await
            db, post_id, CommentCreateRequest(content=content, author=author)
        )

    async def test_댓글_생성(self, db):  # def → async def
        post = await self._create_post(db)  # ← await
        comment = await self._create_comment(db, post.id)  # ← await

        assert comment.id is not None
        assert comment.post_id == post.id

    async def test_존재하지_않는_게시글에_댓글_생성_시_404(self, db):  # def → async def
        with pytest.raises(HTTPException) as exc_info:
            await self._create_comment(db, post_id=9999)  # ← await

        assert exc_info.value.status_code == 404

    async def test_댓글_목록_조회(self, db):  # def → async def
        post = await self._create_post(db)  # ← await
        await self._create_comment(db, post.id, content="댓글 1")  # ← await
        await self._create_comment(db, post.id, content="댓글 2")  # ← await

        comments = await comment_service.get_comments(db, post.id)  # ← await

        assert len(comments) == 2

    async def test_댓글_수정(self, db):  # def → async def
        post = await self._create_post(db)  # ← await
        comment = await self._create_comment(db, post.id, content="원래 댓글")  # ← await

        updated = await comment_service.update_comment(  # ← await
            db, post.id, comment.id, CommentUpdateRequest(content="수정된 댓글"),
        )

        assert updated.content == "수정된 댓글"

    async def test_댓글_삭제(self, db):  # def → async def
        post = await self._create_post(db)  # ← await
        comment = await self._create_comment(db, post.id)  # ← await

        await comment_service.delete_comment(db, post.id, comment.id)  # ← await

        remaining = await comment_service.get_comments(db, post.id)  # ← await
        assert len(remaining) == 0
