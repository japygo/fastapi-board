# app/tasks.py
# Spring의 @Async 서비스 메서드 역할
#
# [Spring 비교]
# @Service
# public class AsyncTaskService {
#
#     @Async                          ← 별도 스레드풀에서 비동기 실행
#     public void incrementViewCount(Long postId) {
#         postRepository.incrementViewCount(postId);
#     }
#
#     @Async
#     public void sendNotificationEmail(String to, String subject) {
#         emailService.send(to, subject);
#     }
# }
#
# FastAPI BackgroundTasks 특징:
# - 응답을 먼저 클라이언트에게 반환한 뒤, 이후에 태스크를 실행
# - I/O 대기(DB 쿼리, 이메일 발송 등) 작업에 적합
# - Spring @Async는 별도 스레드풀을 사용하지만,
#   FastAPI BackgroundTasks는 같은 워커 프로세스에서 순차 실행됩니다
#   (CPU 집약적 작업은 별도 프로세스/Celery 권장)

import logging

from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)


# ── 태스크 1: 게시글 조회수 증가 ───────────────────────────────────────────────
def increment_view_count(post_id: int) -> None:
    """
    게시글 조회수를 1 증가시키는 백그라운드 태스크.

    [왜 BackgroundTasks를 사용하는가?]
    조회수 증가는 사용자에게 응답을 반환하는 것과 무관한 부가 작업입니다.
    응답 속도에 영향을 주지 않도록 백그라운드에서 처리합니다.

    Spring @Async 비교:
        @Async("taskExecutor")
        @Transactional
        public CompletableFuture<Void> incrementViewCount(Long postId) {
            postRepository.incrementViewCount(postId);
            return CompletableFuture.completedFuture(null);
        }

    [주의] 라우터에서 받은 db 세션을 재사용하지 않습니다.
    응답 반환 후 라우터의 db 세션은 이미 닫혀 있기 때문에,
    백그라운드 태스크에서는 새 세션을 직접 생성합니다.
    (Spring @Async에서 새 트랜잭션이 시작되는 것과 동일한 이유)
    """
    # 백그라운드 태스크는 라우터의 DB 세션과 별개로 새 세션 생성
    # Spring의 @Transactional(propagation = Propagation.REQUIRES_NEW) 와 유사
    db: Session = SessionLocal()
    try:
        # 순환 임포트 방지를 위해 함수 내부에서 임포트
        from app.domain.post import Post

        post = db.query(Post).filter(Post.id == post_id).first()
        if post is None:
            logger.warning("[백그라운드] 게시글을 찾을 수 없음 (post_id=%d)", post_id)
            return

        post.view_count += 1
        db.commit()

        logger.info(
            "[백그라운드] 게시글 조회수 증가 완료 (post_id=%d, view_count=%d)",
            post_id,
            post.view_count,
        )

    except Exception as e:
        # 백그라운드 태스크 실패는 클라이언트 응답에 영향 없음
        # Spring @Async 에서 예외가 발생해도 클라이언트에 전파되지 않는 것과 동일
        logger.error(
            "[백그라운드] 조회수 증가 실패 (post_id=%d): %s",
            post_id,
            str(e),
        )
        db.rollback()
    finally:
        # 세션 반드시 닫기 (Spring의 EntityManager.close() 와 동일)
        db.close()


# ── 태스크 2: 이메일 알림 발송 (예시) ──────────────────────────────────────────
def send_welcome_email(username: str, email: str) -> None:
    """
    회원가입 완료 후 환영 이메일을 발송하는 백그라운드 태스크.

    실제 이메일 발송은 구현하지 않지만, 패턴을 보여줍니다.
    실무에서는 smtplib, SendGrid SDK, AWS SES 등을 사용합니다.

    Spring @Async 비교:
        @Async
        public void sendWelcomeEmail(String username, String email) {
            emailService.send(email, "환영합니다, " + username + "!");
        }

    사용 예시 (auth_router.py):
        @router.post("/register")
        def register(request: RegisterRequest, background_tasks: BackgroundTasks):
            user = auth_service.register(db, request)
            background_tasks.add_task(send_welcome_email, user.username, user.email)
            return user
    """
    try:
        # 실제 이메일 발송 로직 (smtplib, SendGrid 등 사용)
        # email_client.send(to=email, subject=f"환영합니다, {username}님!")
        logger.info(
            "[백그라운드] 환영 이메일 발송 (username=%s, email=%s)",
            username,
            email,
        )
    except Exception as e:
        logger.error(
            "[백그라운드] 이메일 발송 실패 (email=%s): %s",
            email,
            str(e),
        )
