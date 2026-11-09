"""مصادقة المشرفين: Argon2id، جلسات بتوكن عشوائي (نخزن بصمته فقط)، TOTP مشفّر، CSRF، وصلاحيات تُفحص بالخلفية."""

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, HTTPException, Request

from . import db
from .config import settings

COOKIE = "sumer_admin"
SESSION_HOURS = 8
IDLE_MINUTES = 60
MAX_FAILED = 5
LOCK_MINUTES = 15
_ph = PasswordHasher()


def hash_password(pw: str) -> str:
    validate_password(pw)
    return _ph.hash(pw)


def validate_password(pw: str):
    if len(pw) < 12:
        raise ValueError("كلمة المرور يجب أن تكون 12 حرفاً على الأقل")
    classes = sum(any(f(c) for c in pw) for f in (str.islower, str.isupper, str.isdigit, lambda c: not c.isalnum()))
    if classes < 3:
        raise ValueError("كلمة المرور يجب أن تجمع 3 أنواع على الأقل: صغيرة، كبيرة، أرقام، رموز")


def verify_password(hash_: str, pw: str) -> bool:
    try:
        return _ph.verify(hash_, pw)
    except (VerificationError, Exception):
        return False


def _aes():
    return AESGCM(hashlib.sha256(b"sumer-totp|" + settings.secret_bytes).digest())


def encrypt_secret(secret: str) -> str:
    nonce = secrets.token_bytes(12)
    return base64.b64encode(nonce + _aes().encrypt(nonce, secret.encode(), b"totp")).decode()


def decrypt_secret(blob: str) -> str:
    raw = base64.b64decode(blob)
    return _aes().decrypt(raw[:12], raw[12:], b"totp").decode()


def verify_totp(user, code: str) -> bool:
    if not user["totp_secret_enc"] or not code:
        return False
    return pyotp.TOTP(decrypt_secret(user["totp_secret_enc"])).verify(code.strip().replace(" ", ""), valid_window=1)


def _token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def create_session(user_id: int, ip: str | None, ua: str | None, mfa_passed: bool) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    db.execute("INSERT INTO admin_sessions (token_hash, user_id, csrf_token, mfa_passed, ip, user_agent, expires_at) "
               "VALUES (%s, %s, %s, %s, %s, %s, now() + make_interval(hours => %s))",
               (_token_hash(token), user_id, csrf, mfa_passed, ip, (ua or "")[:300], SESSION_HOURS))
    return token, csrf


def client_ip(request: Request) -> str | None:
    import ipaddress
    raw = request.headers.get("x-real-ip") if settings.trusted_proxy else None
    raw = raw or (request.client.host if request.client else None)
    try:
        return str(ipaddress.ip_address(raw)) if raw else None
    except ValueError:
        return None


@dataclass
class AdminCtx:
    user: dict
    session: dict
    perms: set
    ip: str

    @property
    def id(self):
        return self.user["id"]


def load_session(request: Request) -> AdminCtx | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    row = db.fetchone(
        "SELECT s.*, u.id AS uid, u.email, u.name, u.status, u.role_id, u.totp_enabled, u.must_change_pw, "
        "r.name AS role, r.permissions FROM admin_sessions s JOIN admin_users u ON u.id = s.user_id "
        "JOIN admin_roles r ON r.id = u.role_id WHERE s.token_hash = %s", (_token_hash(token),))
    if not row or row["revoked_at"] or row["status"] != "active":
        return None
    now = datetime.now(timezone.utc)
    if row["expires_at"] < now or row["last_seen_at"] < now - timedelta(minutes=IDLE_MINUTES):
        return None
    db.execute("UPDATE admin_sessions SET last_seen_at = now() WHERE token_hash = %s", (row["token_hash"],))
    user = {"id": row["uid"], "email": row["email"], "name": row["name"], "role": row["role"],
            "totp_enabled": row["totp_enabled"], "must_change_pw": row["must_change_pw"]}
    return AdminCtx(user=user, session=dict(row), perms=set(row["permissions"]), ip=client_ip(request))


def require(*perms: str, allow_pre_mfa: bool = False):
    """تبعية FastAPI: جلسة صالحة + MFA + CSRF للطلبات المغيّرة + كل الصلاحيات المطلوبة."""
    def dep(request: Request) -> AdminCtx:
        ctx = load_session(request)
        if ctx is None:
            raise HTTPException(401, "unauthenticated")
        if not allow_pre_mfa and not ctx.session["mfa_passed"]:
            raise HTTPException(401, "mfa_required")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            sent = request.headers.get("x-csrf-token", "")
            if not secrets.compare_digest(sent, ctx.session["csrf_token"]):
                raise HTTPException(403, "csrf_failed")
        if not allow_pre_mfa and db.get_setting("security.require_2fa", False) and not ctx.user["totp_enabled"]:
            raise HTTPException(403, "2fa_setup_required")
        missing = [p for p in perms if p not in ctx.perms]
        if missing:
            audit(ctx, "permission_denied", request.url.path, {"missing": missing}, success=False)
            raise HTTPException(403, "forbidden")
        return ctx
    return Depends(dep)


def audit(ctx: AdminCtx | None, action: str, target: str | None = None, details: dict | None = None,
          success: bool = True, ip: str | None = None, email: str | None = None):
    db.execute("INSERT INTO audit_logs (admin_id, admin_email, action, target, details, ip, success) "
               "VALUES (%s, %s, %s, %s, %s, %s, %s)",
               (ctx.id if ctx else None, ctx.user["email"] if ctx else email, action, target,
                json.dumps(details or {}, ensure_ascii=False, default=str), ctx.ip if ctx else ip, success))


def create_admin(email: str, name: str, password: str, role: str, created_by: int | None = None) -> int:
    r = db.fetchone("SELECT id FROM admin_roles WHERE name = %s", (role,))
    if not r:
        raise ValueError("دور غير معروف")
    return db.fetchone("INSERT INTO admin_users (email, name, password_hash, role_id, created_by) "
                       "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                       (email.strip().lower(), name.strip(), hash_password(password), r["id"], created_by))["id"]
