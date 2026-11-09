"""عميل Redis غير متزامن لكل حلقة أحداث (آمن مع عدة عمّال uvicorn والاختبارات)."""

import asyncio

import redis.asyncio as aioredis

from .config import settings

_clients: dict = {}


def get() -> aioredis.Redis:
    loop = asyncio.get_running_loop()
    c = _clients.get(id(loop))
    if c is None:
        c = _clients[id(loop)] = aioredis.from_url(settings.redis_url, decode_responses=True)
    return c
