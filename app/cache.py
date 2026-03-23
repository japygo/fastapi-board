# app/cache.py
# Spring의 @EnableCaching + RedisCacheManager + @Cacheable / @CacheEvict 역할
#
# [Spring 비교]
# @Configuration
# @EnableCaching
# public class CacheConfig {
#     @Bean
#     public RedisCacheManager cacheManager(RedisConnectionFactory factory) {
#         RedisCacheConfiguration config = RedisCacheConfiguration.defaultCacheConfig()
#             .entryTtl(Duration.ofMinutes(5))
#             .serializeValuesWith(RedisSerializationContext.SerializationPair
#                 .fromSerializer(new GenericJackson2JsonRedisSerializer()));
#         return RedisCacheManager.builder(factory).cacheDefaults(config).build();
#     }
# }
#
# Python에서는 Redis 클라이언트를 직접 사용하고,
# @Cacheable 패턴을 데코레이터로 직접 구현합니다.

import json
import logging
from functools import wraps
from typing import Any, Callable, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)

# ── Redis 클라이언트 (싱글톤) ───────────────────────────────────────────────────
# Spring의 RedisConnectionFactory / LettuceConnectionFactory 역할
# 애플리케이션 전체에서 하나의 클라이언트 인스턴스를 공유합니다
#
# decode_responses=True: bytes 대신 str 로 값을 반환 (JSON 처리 편의)
redis_client: redis.Redis = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    decode_responses=True,
)


def get_redis() -> redis.Redis:
    """
    Redis 클라이언트 반환 (테스트에서 교체 가능하도록 함수로 래핑)

    Spring의 @Autowired RedisTemplate<String, Object> 와 유사합니다.
    테스트에서는 이 함수를 monkeypatch 하거나 fakeredis 로 교체합니다.
    """
    return redis_client


# ── 캐시 키 생성 ────────────────────────────────────────────────────────────────
# Spring의 @Cacheable(key = "#id") 에서 SpEL 표현식이 하는 역할
def make_cache_key(namespace: str, *args: Any) -> str:
    """
    일관된 캐시 키를 생성합니다.

    예시:
        make_cache_key("post", 1)        → "post:1"
        make_cache_key("posts", 0, 20)   → "posts:0:20"

    Spring @Cacheable 비교:
        @Cacheable(value = "posts", key = "#skip + '_' + #limit")
        → 캐시 이름 + 키 조합
    """
    parts = [str(a) for a in args]
    return f"{namespace}:{':'.join(parts)}" if parts else namespace


# ── cacheable 데코레이터 ────────────────────────────────────────────────────────
# Spring의 @Cacheable 어노테이션을 Python 데코레이터로 구현
#
# Spring @Cacheable 동작:
# 1. 캐시에 값이 있으면 → 메서드 실행 없이 캐시 값 반환
# 2. 캐시에 값이 없으면 → 메서드 실행 후 결과를 캐시에 저장
def cacheable(key_func: Callable, ttl: int = 300) -> Callable:
    """
    메서드 결과를 Redis에 캐시하는 데코레이터.

    사용 예시:
        @cacheable(key_func=lambda post_id, **kw: make_cache_key("post", post_id), ttl=300)
        def get_post(self, db, post_id): ...

    Spring @Cacheable 비교:
        @Cacheable(value = "post", key = "#postId", unless = "#result == null")
        public PostResponse getPost(Long postId) { ... }

    Args:
        key_func: 캐시 키를 생성하는 함수 (메서드 인자를 받음)
        ttl: 캐시 유효시간 (초). Spring의 entryTtl(Duration.ofSeconds(ttl)) 역할
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)  # 원본 함수의 이름/docstring 유지
        def wrapper(*args, **kwargs):
            # self 제거 후 나머지 인자로 캐시 키 생성
            # (첫 번째 인자가 self인 메서드 대응)
            func_args = args[1:] if args else args
            cache_key = key_func(*func_args, **kwargs)
            client = get_redis()

            try:
                # ① 캐시 조회 (Spring의 @Cacheable 1단계: 캐시 히트 확인)
                cached = client.get(cache_key)
                if cached is not None:
                    logger.debug("[캐시 HIT] key=%s", cache_key)
                    # JSON 문자열 → Python 객체로 역직렬화
                    # Spring의 GenericJackson2JsonRedisSerializer 역직렬화와 동일
                    return json.loads(cached)

                # ② 캐시 미스 → 실제 메서드 실행 (Spring의 @Cacheable 2단계)
                logger.debug("[캐시 MISS] key=%s → DB 조회", cache_key)
                result = func(*args, **kwargs)

                # ③ 결과 캐시 저장 (Spring의 @Cacheable 3단계: 결과 저장)
                # Pydantic 모델은 .model_dump() 로 dict 변환 후 JSON 직렬화
                if hasattr(result, "model_dump"):
                    serializable = result.model_dump(mode="json")
                elif isinstance(result, list):
                    serializable = [
                        item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                        for item in result
                    ]
                else:
                    serializable = result

                client.setex(cache_key, ttl, json.dumps(serializable, ensure_ascii=False))
                logger.debug("[캐시 저장] key=%s (TTL=%ds)", cache_key, ttl)

                return result

            except redis.RedisError as e:
                # Redis 장애 시 캐시를 건너뛰고 DB에서 직접 조회
                # Spring의 @Cacheable 에서 Redis 장애 시 메서드가 정상 실행되는 것과 동일
                logger.warning("[캐시 오류] Redis 연결 실패, DB에서 직접 조회: %s", e)
                return func(*args, **kwargs)

        return wrapper
    return decorator


# ── cache_evict 데코레이터 ──────────────────────────────────────────────────────
# Spring의 @CacheEvict 어노테이션을 Python 데코레이터로 구현
#
# Spring @CacheEvict 동작:
# 메서드 실행 후 → 지정된 캐시 키들을 삭제
def cache_evict(*key_patterns: str) -> Callable:
    """
    메서드 실행 후 지정된 캐시 패턴을 삭제하는 데코레이터.

    사용 예시:
        @cache_evict("posts:*", "post:{post_id}")
        def create_post(self, db, request): ...

    Spring @CacheEvict 비교:
        @CacheEvict(value = {"posts", "post"}, allEntries = true)
        public PostResponse createPost(PostCreateRequest request) { ... }

    Args:
        key_patterns: 삭제할 캐시 키 패턴 (와일드카드 * 지원)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 먼저 메서드 실행
            # Spring의 @CacheEvict(beforeInvocation=false, 기본값) 와 동일
            result = func(*args, **kwargs)

            # 메서드 성공 후 캐시 삭제
            client = get_redis()
            try:
                for pattern in key_patterns:
                    # 와일드카드 패턴으로 키 검색 후 삭제
                    # Spring의 allEntries=true 와 유사
                    keys = client.keys(pattern)
                    if keys:
                        client.delete(*keys)
                        logger.debug("[캐시 삭제] pattern=%s, %d개 삭제", pattern, len(keys))
            except redis.RedisError as e:
                # 캐시 삭제 실패는 비즈니스 로직에 영향 없음
                logger.warning("[캐시 삭제 오류] %s", e)

            return result
        return wrapper
    return decorator


# ── 수동 캐시 삭제 헬퍼 ──────────────────────────────────────────────────────────
def evict_post_cache(post_id: Optional[int] = None) -> None:
    """
    게시글 관련 캐시를 수동으로 삭제합니다.

    Spring의 @CacheEvict 를 직접 호출하는 것과 유사합니다.
    데코레이터를 쓰기 어려운 상황(예: 동적 키)에서 사용합니다.
    """
    client = get_redis()
    try:
        # 목록 캐시 전체 삭제 (게시글이 변경되면 목록도 갱신 필요)
        list_keys = client.keys("posts:*")
        if list_keys:
            client.delete(*list_keys)

        # 단건 캐시 삭제
        if post_id is not None:
            client.delete(make_cache_key("post", post_id))

        logger.debug("[캐시 수동 삭제] post_id=%s", post_id)
    except redis.RedisError as e:
        logger.warning("[캐시 삭제 오류] %s", e)
