import json

from redis.asyncio import Redis

from app.models.schemas import ChatMessage


class SessionService:
    def __init__(
        self,
        redis_client: Redis,
        ttl_seconds: int,
        enabled: bool,
        max_messages: int,
    ) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled
        self._max_messages = max_messages

    async def get_messages(self, session_id: str | None) -> list[ChatMessage]:
        if not self._enabled or not session_id:
            return []

        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return []

        payload = json.loads(raw)
        return [ChatMessage.model_validate(item) for item in payload]

    async def append_messages(
        self,
        session_id: str | None,
        messages: list[ChatMessage],
    ) -> None:
        if not self._enabled or not session_id or not messages:
            return

        existing = await self.get_messages(session_id)
        merged = (existing + messages)[-self._max_messages :]
        await self._redis.set(
            self._key(session_id),
            json.dumps([message.model_dump() for message in merged]),
            ex=self._ttl_seconds,
        )

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"
