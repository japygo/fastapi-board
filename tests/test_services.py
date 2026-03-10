# tests/test_services.py
# 서비스 레이어 테스트
# Spring 비교: @SpringBootTest (슬라이스 없이 서비스 레이어 직접 테스트)

import pytest
from fastapi import HTTPException

from app.services.post_service import PostService
from app.services.comment_service import CommentService
from app.schemas.post import PostCreateRequest, PostUpdateRequest
from app.schemas.comment import CommentCreateRequest, CommentUpdateRequest

# 서비스 인스턴스 (테스트 전체에서 공유)
post_service = PostService()
comment_service = CommentService()


class TestPostService:
    """게시글 서비스 테스트"""

    def _create_post(self, db, title="테스트", content="내용", author="작성자"):
        """테스트용 게시글 생성 헬퍼"""
        return post_service.create_post(
            db,
            PostCreateRequest(title=title, content=content, author=author),
        )

    def test_게시글_생성(self, db):
        """게시글 생성 후 응답 DTO 반환 확인"""
        response = self._create_post(db, title="새 게시글", author="홍길동")

        assert response.id is not None
        assert response.title == "새 게시글"
        assert response.author == "홍길동"

    def test_게시글_목록_조회(self, db):
        """게시글 목록 조회 (total 포함)"""
        self._create_post(db, title="게시글 1")
        self._create_post(db, title="게시글 2")

        result = post_service.get_posts(db)

        assert result.total == 2
        assert len(result.posts) == 2

    def test_게시글_단건_조회(self, db):
        """ID로 게시글 조회"""
        created = self._create_post(db)
        found = post_service.get_post(db, created.id)

        assert found.id == created.id
        assert found.title == created.title

    def test_존재하지_않는_게시글_조회_시_404(self, db):
        """없는 게시글 조회 시 HTTPException 404 발생"""
        # Spring 비교: assertThrows(PostNotFoundException.class, () -> ...)
        with pytest.raises(HTTPException) as exc_info:
            post_service.get_post(db, post_id=9999)

        assert exc_info.value.status_code == 404

    def test_게시글_제목_수정(self, db):
        """제목만 수정 (PATCH 방식)"""
        created = self._create_post(db, title="원래 제목", content="원래 내용")

        updated = post_service.update_post(
            db, created.id,
            PostUpdateRequest(title="수정된 제목"),  # content는 None → 변경 안 함
        )

        assert updated.title == "수정된 제목"
        assert updated.content == "원래 내용"  # 변경되지 않아야 함

    def test_존재하지_않는_게시글_수정_시_404(self, db):
        """없는 게시글 수정 시 404"""
        with pytest.raises(HTTPException) as exc_info:
            post_service.update_post(db, 9999, PostUpdateRequest(title="수정"))

        assert exc_info.value.status_code == 404

    def test_게시글_삭제(self, db):
        """게시글 삭제 후 조회 시 404"""
        created = self._create_post(db)

        post_service.delete_post(db, created.id)

        # 삭제 후 조회 시 404 예외
        with pytest.raises(HTTPException) as exc_info:
            post_service.get_post(db, created.id)
        assert exc_info.value.status_code == 404

    def test_존재하지_않는_게시글_삭제_시_404(self, db):
        """없는 게시글 삭제 시 404"""
        with pytest.raises(HTTPException) as exc_info:
            post_service.delete_post(db, 9999)

        assert exc_info.value.status_code == 404


class TestCommentService:
    """댓글 서비스 테스트"""

    def _create_post(self, db):
        """테스트용 게시글 생성"""
        return post_service.create_post(
            db, PostCreateRequest(title="게시글", content="내용", author="작성자")
        )

    def _create_comment(self, db, post_id, content="댓글", author="댓글러"):
        """테스트용 댓글 생성"""
        return comment_service.create_comment(
            db, post_id, CommentCreateRequest(content=content, author=author)
        )

    def test_댓글_생성(self, db):
        """댓글 생성 후 게시글 ID 포함 확인"""
        post = self._create_post(db)
        comment = self._create_comment(db, post.id)

        assert comment.id is not None
        assert comment.post_id == post.id

    def test_존재하지_않는_게시글에_댓글_생성_시_404(self, db):
        """없는 게시글에 댓글 생성 시 404"""
        with pytest.raises(HTTPException) as exc_info:
            self._create_comment(db, post_id=9999)

        assert exc_info.value.status_code == 404

    def test_댓글_목록_조회(self, db):
        """게시글의 댓글 목록 조회"""
        post = self._create_post(db)
        self._create_comment(db, post.id, content="댓글 1")
        self._create_comment(db, post.id, content="댓글 2")

        comments = comment_service.get_comments(db, post.id)

        assert len(comments) == 2

    def test_댓글_수정(self, db):
        """댓글 내용 수정"""
        post = self._create_post(db)
        comment = self._create_comment(db, post.id, content="원래 댓글")

        updated = comment_service.update_comment(
            db, post.id, comment.id,
            CommentUpdateRequest(content="수정된 댓글"),
        )

        assert updated.content == "수정된 댓글"

    def test_댓글_삭제(self, db):
        """댓글 삭제 후 목록에서 제거 확인"""
        post = self._create_post(db)
        comment = self._create_comment(db, post.id)

        comment_service.delete_comment(db, post.id, comment.id)

        remaining = comment_service.get_comments(db, post.id)
        assert len(remaining) == 0
