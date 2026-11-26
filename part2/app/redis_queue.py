"""Redis-backed queue using atomic RPUSH and LPOP."""

from __future__ import annotations

import redis

from app.queue import _validate_name


class RedisQueue:
    def __init__(self, url: str, key: str = "lab_queue") -> None:
        self._client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        self._key = key

    def join(self, name: str) -> int:
        cleaned = _validate_name(name)
        # RPUSH atomically appends and returns the new list length.
        return int(self._client.rpush(self._key, cleaned))

    def take(self) -> str:
        item = self._client.lpop(self._key)
        if item is None:
            raise LookupError("empty")
        return str(item)

    def length(self) -> int:
        return int(self._client.llen(self._key))