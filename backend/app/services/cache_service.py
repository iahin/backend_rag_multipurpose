import hashlib
import json

from redis.asyncio import Redis


class CacheService:
    def __init__(self, client: Redis, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    def make_key(self, prefix: str, payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"

    async def get_json(self, key: str) -> dict | list | None:
        value = await self._client.get(key)
        if value is None:
            return None
        return json.loads(value)

    async def set_json(self, key: str, value: dict | list) -> None:
        await self._client.set(key, json.dumps(value), ex=self._ttl_seconds)
