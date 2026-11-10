"""واجهة سومر بريد البرمجية."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import time
from email.utils import parseaddr
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from . import imapsvc as M
from . import sessions as S
from .config import settings
from .providers import PROVIDERS, detect, public_list

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(_app):
    settings.check()
    yield


app = FastAPI(title="Sumer Mail", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
Folder = Literal["inbox", "sent", "trash", "junk", "drafts", "archive"]
EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    # حماية CSRF: الطلبات المعدِّلة لازم تحمل ترويسة خاصة (المتصفح ما يرسلها من مواقع ثانية بدون CORS)
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.headers.get("x-sumer-mail") != "1":
        return JSONResponse({"detail": "csrf"}, status_code=403)
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


def client_ip(request: Request) -> str:
    ip = request.client.host if request.client else "0.0.0.0"
    if settings.trusted_proxy:
        ip = request.headers.get("x-real-ip", ip)
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return "0.0.0.0"


async def rate_limit(request: Request, bucket: str, limit: int, window: int):
    key = f"sm:rl:{bucket}:{client_ip(request)}:{int(time.time() // window)}"
    r = S.rds()
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, window)
    if n > limit:
        raise HTTPException(429, "محاولات كثيرة، انتظر شوية.")


async def session_opt(request: Request) -> S.Session | None:
    return await S.load(request.cookies.get(S.COOKIE))


async def session_req(request: Request) -> S.Session:
    s = await S.load(request.cookies.get(S.COOKIE))
    if not s:
        raise HTTPException(401, "no_session")
    return s


def set_cookie(resp: Response, s: S.Session):
    resp.set_cookie(S.COOKIE, s.cookie, httponly=True, secure=settings.cookie_secure, samesite="strict",
                    max_age=settings.session_max_s, path="/")


def pub_account(a: dict) -> dict:
    return {k: a[k] for k in ("id", "email", "display_name", "provider", "label", "imap_host", "smtp_host")} | {
        "provider_name": PROVIDERS.get(a["provider"], {}).get("name", "بريد"), "sovereign": a.get("sovereign", False)}


def err(e: M.MailError, status: int = 400):
    raise HTTPException(status, {"code": e.code, "message": e.message})


# ------------------------------------------------------------------ عام


@app.get("/api/health")
async def health():
    try:
        await S.rds().ping()
        return {"ok": True}
    except Exception:
        raise HTTPException(503, "redis")


@app.get("/api/providers")
async def providers():
    return {"providers": public_list()}


@app.get("/api/session")
async def session_info(s: S.Session | None = Depends(session_opt)):
    if not s:
        return {"active": False, "accounts": [], "stats": {}}
    return {"active": True, "accounts": [pub_account(a) for a in s.accounts], "stats": s.data.get("stats", {}),
            "expires_in": settings.session_max_s - (int(time.time()) - s.data["created"])}


@app.post("/api/session/logout")
async def logout(response: Response, s: S.Session | None = Depends(session_opt)):
    if s:
        await S.destroy(s)
    response.delete_cookie(S.COOKIE, path="/")
    return {"ok": True}


# ------------------------------------------------------------------ الحسابات


class AccountIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=512)
    provider: str | None = None
    display_name: str = Field("", max_length=80)
    username: str | None = Field(None, max_length=254)
    imap_host: str | None = Field(None, max_length=253)
    imap_port: int | None = None
    smtp_host: str | None = Field(None, max_length=253)
    smtp_port: int | None = None

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("bad email")
        return v


@app.post("/api/accounts")
async def add_account(body: AccountIn, request: Request, response: Response, s: S.Session | None = Depends(session_opt)):
    await rate_limit(request, "login", 10, 600)
    s = s or S.new_session()
    if len(s.accounts) >= settings.max_accounts:
        raise HTTPException(400, {"code": "too_many", "message": "وصلت للحد الأقصى من الحسابات."})
    if any(a["email"] == body.email for a in s.accounts):
        raise HTTPException(400, {"code": "exists", "message": "هذا الحساب مضاف مسبقاً."})
    prov = body.provider if body.provider in PROVIDERS else detect(body.email)
    p = PROVIDERS[prov]
    if p.get("oauth_only"):
        raise HTTPException(400, {"code": "oauth_only", "message": p["help_ar"]})
    imap_host = (body.imap_host or p["imap"][0] or "").strip().lower()
    smtp_host = (body.smtp_host or p["smtp"][0] or "").strip().lower()
    if not imap_host or not smtp_host:
        raise HTTPException(400, {"code": "need_servers", "message": "اكتب عنوان خادم IMAP وSMTP."})
    acc = {"id": M.new_account_id(), "email": body.email, "display_name": body.display_name.strip(), "provider": prov,
           "label": p["name"], "username": (body.username or body.email).strip(), "password": body.password,
           "imap_host": imap_host, "imap_port": body.imap_port or p["imap"][1],
           "smtp_host": smtp_host, "smtp_port": body.smtp_port or p["smtp"][1],
           "sovereign": body.email.endswith("@sumeriq.tech")}
    try:
        await run_in_threadpool(M.test_account, acc)
    except M.MailError as e:
        err(e)
    s.accounts.append(acc)
    await S.save(s)
    set_cookie(response, s)
    return {"account": pub_account(acc)}


@app.delete("/api/accounts/{acc_id}")
async def remove_account(acc_id: str, response: Response, s: S.Session = Depends(session_req)):
    s.data["accounts"] = [a for a in s.accounts if a["id"] != acc_id]
    if not s.accounts:
        await S.destroy(s)
        response.delete_cookie(S.COOKIE, path="/")
        return {"ok": True, "session": False}
    await S.save(s)
    return {"ok": True, "session": True}


def need(s: S.Session, acc_id: str) -> dict:
    a = s.account(acc_id)
    if not a:
        raise HTTPException(404, "account")
    return a


# ------------------------------------------------------------------ الرسائل


@app.get("/api/messages")
async def unified(request: Request, folder: Folder = "inbox", account: str = "all", q: str = "", s: S.Session = Depends(session_req)):
    await rate_limit(request, "list", 120, 60)
    accs = s.accounts if account == "all" else [need(s, account)]
    q = q.strip()[:120]
    results = await asyncio.gather(*[run_in_threadpool(M.list_messages, a, folder, None, q) for a in accs], return_exceptions=True)
    items, errors = [], []
    for a, r in zip(accs, results):
        if isinstance(r, M.MailError):
            errors.append({"account_id": a["id"], "email": a["email"], "code": r.code, "message": r.message})
        elif isinstance(r, Exception):
            errors.append({"account_id": a["id"], "email": a["email"], "code": "error", "message": "تعذّر جلب الرسائل."})
        else:
            items.extend(r)
    items.sort(key=lambda m: m["date"] or "", reverse=True)
    # إحصاءات الحماية (أرقام فقط، بدون أي محتوى)، مرة واحدة لكل رسالة
    seen = set(s.data.get("seen_ids", []))
    new = 0
    for m in items:
        an = m.get("analysis")
        mid = f'{m["account_id"]}:{m["folder"]}:{m["uid"]}'
        if an and mid not in seen:
            seen.add(mid)
            new += 1
            if an["level"] == "danger":
                s.bump("phishing")
            elif an["level"] == "caution":
                s.bump("suspicious")
            if an["trackers"]:
                s.bump("trackers", an["trackers"])
            s.bump("scanned")
    if new:
        s.data["seen_ids"] = list(seen)[-2000:]
        await S.save(s)
    return {"messages": items, "errors": errors}


@app.get("/api/accounts/{acc_id}/messages/{folder}/{uid}")
async def read(acc_id: str, folder: Folder, uid: str, images: bool = False, s: S.Session = Depends(session_req)):
    if not uid.isdigit():
        raise HTTPException(400, "uid")
    try:
        return await run_in_threadpool(M.get_message, need(s, acc_id), folder, uid, show_images=images)
    except M.MailError as e:
        err(e, 404 if e.code == "not_found" else 400)


@app.get("/api/accounts/{acc_id}/messages/{folder}/{uid}/attachments/{index}")
async def attachment(acc_id: str, folder: Folder, uid: str, index: int, inline: bool = False, s: S.Session = Depends(session_req)):
    if not uid.isdigit():
        raise HTTPException(400, "uid")
    try:
        name, ctype, data = await run_in_threadpool(M.get_attachment, need(s, acc_id), folder, uid, index)
    except M.MailError as e:
        err(e, 404)
    safe_inline = inline and ctype in ("image/png", "image/jpeg", "image/gif", "image/webp")
    from urllib.parse import quote
    return Response(data, media_type=ctype if safe_inline else "application/octet-stream", headers={
        "Content-Disposition": ("inline" if safe_inline else "attachment") + f"; filename*=UTF-8''{quote(name)}",
        "Content-Security-Policy": "default-src 'none'; sandbox", "X-Content-Type-Options": "nosniff"})


class FlagsIn(BaseModel):
    seen: bool | None = None
    flagged: bool | None = None


@app.post("/api/accounts/{acc_id}/messages/{folder}/{uid}/flags")
async def flags(acc_id: str, folder: Folder, uid: str, body: FlagsIn, s: S.Session = Depends(session_req)):
    try:
        await run_in_threadpool(M.set_flags, need(s, acc_id), folder, uid, seen=body.seen, flagged=body.flagged)
    except M.MailError as e:
        err(e)
    return {"ok": True}


class MoveIn(BaseModel):
    to: Literal["trash", "junk", "inbox", "archive"]


@app.post("/api/accounts/{acc_id}/messages/{folder}/{uid}/move")
async def move(acc_id: str, folder: Folder, uid: str, body: MoveIn, s: S.Session = Depends(session_req)):
    try:
        await run_in_threadpool(M.move, need(s, acc_id), folder, uid, body.to)
    except M.MailError as e:
        err(e)
    if body.to == "junk":
        s.bump("reported")
        await S.save(s)
    return {"ok": True}


class SendIn(BaseModel):
    account_id: str
    to: list[str] = Field(min_length=1, max_length=50)
    cc: list[str] = Field(default_factory=list, max_length=50)
    subject: str = Field("", max_length=300)
    body: str = Field("", max_length=200_000)
    in_reply_to: str = Field("", max_length=500)
    references: str = Field("", max_length=4000)

    @field_validator("to", "cc")
    @classmethod
    def _addrs(cls, v):
        out = []
        for x in v:
            e = parseaddr(x)[1].strip()
            if not EMAIL_RE.match(e):
                raise ValueError(f"bad address: {x}")
            out.append(e)
        return out


@app.post("/api/send")
async def send(body: SendIn, request: Request, s: S.Session = Depends(session_req)):
    await rate_limit(request, "send", 30, 3600)
    acc = need(s, body.account_id)
    try:
        mid = await run_in_threadpool(M.send, acc, to=body.to, cc=body.cc, subject=body.subject, body=body.body,
                                      in_reply_to=body.in_reply_to, references=body.references)
    except M.MailError as e:
        err(e)
    return {"ok": True, "message_id": mid}
