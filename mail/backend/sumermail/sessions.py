"""جلسات «المفتاح المقسوم»:
- Redis يحفظ نسخة مشفّرة (AES-256-GCM) من بيانات الحسابات فقط.
- مفتاح فك التشفير موجود فقط بكوكي المستخدم (HttpOnly)، فالخادم ما يكدر يقرأ البيانات إلا وقت طلب المستخدم نفسه.
- تسريب Redis وحده لا يكشف كلمات المرور، ولا تُحفظ أي رسالة."""

import base64
import hashlib
import hmac
import json
import os
import time

import redis.asyncio as aioredis
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings

COOKIE = "sm_session"
_PREFIX = "sm:s:"
_clients: dict[int, aioredis.Redis] = {}


def rds() -> aioredis.Redis:
    import asyncio
    loop = id(asyncio.get_running_loop())
    if loop not in _clients:
        _clients[loop] = aioredis.from_url(settings.redis_url, decode_responses=False)
    return _clients[loop]


def _rkey(sid: bytes) -> str:
    return _PREFIX + hmac.new(settings.secret.encode() or b"dev", sid, hashlib.sha256).hexdigest()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class Session:
    def __init__(self, sid: bytes, key: bytes, data: dict):
        self.sid, self.key, self.data = sid, key, data

    @property
    def cookie(self) -> str:
        return _b64(self.sid + self.key)

    @property
    def accounts(self) -> list[dict]:
        return self.data.setdefault("accounts", [])

    def account(self, acc_id: str) -> dict | None:
        return next((a for a in self.accounts if a["id"] == acc_id), None)

    def bump(self, stat: str, n: int = 1):
        st = self.data.setdefault("stats", {})
        st[stat] = st.get(stat, 0) + n


def new_session() -> Session:
    now = int(time.time())
    return Session(os.urandom(24), os.urandom(32), {"accounts": [], "stats": {}, "created": now, "seen_ids": []})


async def load(cookie: str | None) -> Session | None:
    if not cookie:
        return None
    try:
        raw = _unb64(cookie)
    except Exception:
        return None
    if len(raw) != 56:
        return None
    sid, key = raw[:24], raw[24:]
    blob = await rds().get(_rkey(sid))
    if not blob:
        return None
    try:
        data = json.loads(AESGCM(key).decrypt(blob[:12], blob[12:], sid))
    except Exception:
        return None
    if time.time() - data.get("created", 0) > settings.session_max_s:
        await destroy(Session(sid, key, data))
        return None
    return Session(sid, key, data)


async def save(s: Session):
    nonce = os.urandom(12)
    blob = nonce + AESGCM(s.key).encrypt(nonce, json.dumps(s.data, ensure_ascii=False).encode(), s.sid)
    remaining = settings.session_max_s - (int(time.time()) - s.data.get("created", 0))
    await rds().set(_rkey(s.sid), blob, ex=max(1, min(settings.session_idle_s, remaining)))


async def destroy(s: Session):
    await rds().delete(_rkey(s.sid))
