import time

from redis.asyncio import Redis


class RateLimiter:
    def __init__(
        self,
        redis_client: Redis,
        limit: int,
        window_seconds: int,
    ) -> None:
        self._redis = redis_client
        self._limit = limit
        self._window_seconds = window_seconds

    async def check(self, key: str) -> tuple[bool, int]:
        now = int(time.time())
        bucket = now // self._window_seconds
        redis_key = f"rate_limit:{key}:{bucket}"
        current = await self._redis.incr(redis_key)
        if current == 1:
            await self._redis.expire(redis_key, self._window_seconds)

        remaining = max(self._limit - current, 0)
        allowed = current <= self._limit
        return allowed, remaining
