# app/tasks.py
# Spring의 @Async 서비스 메서드 역할 (비동기 버전)
#
# [Before → After: 동기 → 비동기 전환]
#
# Before (동기):
#   def increment_view_count(post_id: int):
#       db = SessionLocal()
#       try:
#           post = db.query(Post).filter(...).first()
#           post.view_count += 1
#           db.commit()
#       finally:
#           db.close()
#
# After (비동기):
#   async def increment_view_count(post_id: int):
#       async with AsyncSessionLocal() as db:    ← async with (자동 close)
#           result = await db.execute(...)       ← await
#           post.view_count += 1
#           await db.commit()                    ← await
#
# FastAPI BackgroundTasks는 async def 함수를 지원합니다.
# add_task(increment_view_count, post_id) 그대로 사용 가능.
#
# Spring @Async 비교:
# @Async → 별도 스레드풀에서 실행
# FastAPI async BackgroundTasks → 같은 이벤트 루프에서 응답 후 실행

import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal  # SessionLocal → AsyncSessionLocal

logger = logging.getLogger(__name__)


async def increment_view_count(post_id: int) -> None:
    """
    게시글 조회수를 1 증가시키는 비동기 백그라운드 태스크.

    [Before → After]
    Before: db = SessionLocal(); try: ... finally: db.close()
    After:  async with AsyncSessionLocal() as db:  ← async with (자동 close 보장)

    [왜 async with 를 사용하는가?]
    - 동기의 try/finally db.close() 와 동일한 효과
    - 예외 발생 시에도 세션이 안전하게 닫힘
    - await 를 사용하므로 DB 대기 중 다른 태스크 실행 가능

    [왜 라우터의 db 세션을 재사용하지 않는가?]
    - 응답 반환 후 라우터의 세션은 이미 닫혀 있음
    - 새 세션을 생성해야 함 (Spring @Async의 새 트랜잭션과 동일한 이유)
    """
    async with AsyncSessionLocal() as db:  # ← async with (Before: try/finally)
        try:
            from app.domain.post import Post

            result = await db.execute(  # ← await (Before: db.query().filter().first())
                select(Post).where(Post.id == post_id)
            )
            post = result.scalar_one_or_none()

            if post is None:
                logger.warning("[백그라운드] 게시글을 찾을 수 없음 (post_id=%d)", post_id)
                return

            post.view_count += 1
            await db.commit()  # ← await

            logger.info(
                "[백그라운드] 게시글 조회수 증가 완료 (post_id=%d, view_count=%d)",
                post_id,
                post.view_count,
            )
        except Exception as e:
            logger.error(
                "[백그라운드] 조회수 증가 실패 (post_id=%d): %s",
                post_id,
                str(e),
            )
            await db.rollback()  # ← await


async def send_welcome_email(username: str, email: str) -> None:
    """
    회원가입 완료 후 환영 이메일 발송 비동기 백그라운드 태스크.

    [Before → After]
    Before: def send_welcome_email(username, email): logger.info(...)
    After:  async def send_welcome_email(username, email): logger.info(...)
            (실제 I/O 작업 시 await email_client.send(...) 추가)

    실제 이메일 발송 시:
        import aiosmtplib  # 비동기 SMTP 라이브러리
        await aiosmtplib.send(message, hostname="smtp.example.com")
    """
    try:
        logger.info(
            "[백그라운드] 환영 이메일 발송 (username=%s, email=%s)",
            username,
            email,
        )
    except Exception as e:
        logger.error("[백그라운드] 이메일 발송 실패 (email=%s): %s", email, str(e))
