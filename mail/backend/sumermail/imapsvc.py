"""التعامل مع خوادم IMAP/SMTP. كل دالة هنا متزامنة وتُشغَّل بخيط منفصل.
لا شي يُحفظ: الرسائل تُجلب وتُحلَّل وتُرجع للمستخدم مباشرة."""

from __future__ import annotations

import imaplib
import re
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr, formatdate

from imap_tools import AND, MailBox, MailMessage, MailMessageFlags
from imap_tools.errors import MailboxLoginError

from . import analyze as A
from .config import settings
from .netguard import NetError, PinnedIMAP4_SSL, PinnedSMTP, PinnedSMTP_SSL, check_port, resolve
from .providers import PROVIDERS


class MailError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


NET_MSG = {"dns": "ما لكينا هذا الخادم. تأكد من العنوان.", "private": "عنوان الخادم غير مسموح.",
           "bad_host": "عنوان الخادم غير صحيح.", "port": "المنفذ غير مسموح. استخدم 993 لـ IMAP و465 أو 587 لـ SMTP."}


class SafeMailBox(MailBox):
    def __init__(self, host: str, port: int):
        check_port(port, "imap")
        self._ip = resolve(host, port)
        super().__init__(host, port, timeout=settings.imap_timeout)

    def _get_mailbox_client(self) -> imaplib.IMAP4:
        return PinnedIMAP4_SSL(self._host, self._port, self._ip, settings.imap_timeout)


def connect(acc: dict) -> SafeMailBox:
    try:
        mb = SafeMailBox(acc["imap_host"], int(acc["imap_port"]))
        mb.login(acc["username"], acc["password"])
        return mb
    except NetError as e:
        raise MailError(f"net_{e}", NET_MSG.get(str(e), "تعذّر الاتصال بالخادم."))
    except MailboxLoginError:
        hint = PROVIDERS.get(acc.get("provider", ""), {}).get("help_ar", "")
        raise MailError("auth", "اسم المستخدم أو كلمة المرور غير صحيحة. " + hint)
    except ssl.SSLError:
        raise MailError("tls", "شهادة الأمان للخادم غير صالحة، فرفضنا الاتصال لحمايتك.")
    except (OSError, imaplib.IMAP4.error) as e:
        raise MailError("connect", f"تعذّر الاتصال بالخادم ({type(e).__name__}).")


# ------------------------------------------------------------------ المجلدات

SPECIAL = {"inbox": None, "sent": "\\Sent", "trash": "\\Trash", "junk": "\\Junk", "drafts": "\\Drafts", "archive": "\\Archive"}
FALLBACK_NAMES = {"sent": ("Sent", "Sent Items", "Sent Messages", "[Gmail]/Sent Mail", "INBOX.Sent"),
                  "trash": ("Trash", "Deleted Items", "Deleted Messages", "[Gmail]/Trash", "[Gmail]/Bin", "INBOX.Trash"),
                  "junk": ("Junk", "Spam", "Junk E-mail", "[Gmail]/Spam", "INBOX.Junk"),
                  "drafts": ("Drafts", "[Gmail]/Drafts", "INBOX.Drafts"), "archive": ("Archive", "[Gmail]/All Mail")}


def folder_name(mb: SafeMailBox, kind: str) -> str | None:
    if kind == "inbox":
        return "INBOX"
    folders = list(mb.folder.list())
    flag = SPECIAL.get(kind)
    for f in folders:
        if flag and flag in f.flags:
            return f.name
    names = {f.name.lower(): f.name for f in folders}
    for n in FALLBACK_NAMES.get(kind, ()):
        if n.lower() in names:
            return names[n.lower()]
    return None


# ------------------------------------------------------------------ تحويل الرسائل


def _addr(s: str) -> dict:
    name, email = parseaddr(s or "")
    return {"name": name or email.split("@")[0], "email": email}


def _headers(msg: MailMessage, name: str) -> list[str]:
    return [v for v in msg.headers.get(name.lower(), ())]


def _att_list(msg: MailMessage) -> list[dict]:
    out = []
    for i, a in enumerate(msg.attachments):
        out.append({"index": i, "filename": a.filename or f"attachment-{i + 1}", "size": a.size,
                    "content_type": a.content_type, "inline": a.content_disposition == "inline", "cid": (a.content_id or "").strip("<>")})
    return out


def snippet(msg: MailMessage) -> str:
    h = re.sub(r"<(script|style|head)\b.*?</\1>", " ", msg.html or "", flags=re.I | re.S)
    t = msg.text or A.TAG_RE.sub(" ", h)
    t = re.sub(r"\s+", " ", A.htmlmod.unescape(t)).strip()
    return t[:180]


def report_for(msg: MailMessage, atts: list[dict] | None = None) -> A.Report:
    return A.analyze(
        from_header=msg.from_values.full if msg.from_values else msg.from_, reply_to=", ".join(msg.reply_to or ()),
        subject=msg.subject or "", text=msg.text or "", html=msg.html or "",
        attachments=atts if atts is not None else _att_list(msg), auth_results=_headers(msg, "authentication-results"))


def summary(acc: dict, folder: str, msg: MailMessage, full: bool) -> dict:
    d = {"account_id": acc["id"], "folder": folder, "uid": msg.uid, "subject": msg.subject or "(بدون عنوان)",
         "from": _addr(msg.from_values.full if msg.from_values else msg.from_), "to": [_addr(x.full) for x in msg.to_values],
         "date": msg.date.isoformat() if msg.date and msg.date.year > 1970 else None,
         "seen": MailMessageFlags.SEEN in msg.flags, "flagged": MailMessageFlags.FLAGGED in msg.flags,
         "size": msg.size_rfc822, "snippet": "", "has_attachments": False, "analysis": None}
    if full:
        atts = _att_list(msg)
        d["has_attachments"] = any(not a["inline"] for a in atts)
        d["snippet"] = snippet(msg)
        rep = report_for(msg, atts)
        d["analysis"] = {"level": rep.level, "score": min(rep.score, 100), "top": rep.as_dict()["reasons"][:1], "trackers": rep.trackers}
    return d


# ------------------------------------------------------------------ العمليات


def test_account(acc: dict) -> dict:
    mb = connect(acc)
    try:
        folders = [f.name for f in mb.folder.list()]
        return {"folders": len(folders)}
    finally:
        mb.logout()


def list_messages(acc: dict, kind: str = "inbox", limit: int | None = None, query: str = "") -> list[dict]:
    limit = min(limit or settings.list_limit, 60)
    mb = connect(acc)
    try:
        folder = folder_name(mb, kind)
        if not folder:
            return []
        mb.folder.set(folder, readonly=True)
        crit = AND(text=query) if query else "ALL"
        heads = list(mb.fetch(crit, charset="UTF-8" if query else "US-ASCII", limit=limit, reverse=True,
                              mark_seen=False, headers_only=True, bulk=True))
        small = [m.uid for m in heads if (m.size_rfc822 or 0) <= settings.full_fetch_max_bytes]
        fulls = {}
        if small:
            for m in mb.fetch(uid_list=small, mark_seen=False, bulk=10):
                fulls[m.uid] = m
        out = []
        for h in heads:
            m = fulls.get(h.uid)
            out.append(summary(acc, kind, m or h, full=m is not None))
        return out
    finally:
        mb.logout()


def get_message(acc: dict, kind: str, uid: str, *, show_images: bool = False) -> dict:
    mb = connect(acc)
    try:
        folder = folder_name(mb, kind)
        if not folder:
            raise MailError("not_found", "المجلد غير موجود.")
        mb.folder.set(folder)
        msgs = list(mb.fetch(uid_list=[uid], mark_seen=False))
        if not msgs:
            raise MailError("not_found", "الرسالة غير موجودة.")
        msg = msgs[0]
        atts = _att_list(msg)
        rep = report_for(msg, atts)
        cid_map = {a["cid"]: f"/api/accounts/{acc['id']}/messages/{kind}/{uid}/attachments/{a['index']}?inline=1"
                   for a in atts if a["cid"] and a["content_type"].startswith("image/")}
        body_html = A.sanitize(msg.html, rep, show_images=show_images, cid_map=cid_map) if msg.html else ""
        d = summary(acc, kind, msg, full=True)
        d.update({
            "html": body_html, "text": msg.text or "", "attachments": [a for a in atts if not a["inline"] or not a["cid"]],
            "cc": [_addr(x.full) for x in msg.cc_values], "reply_to": list(msg.reply_to or ()),
            "message_id": (msg.headers.get("message-id") or ("",))[0], "references": (msg.headers.get("references") or ("",))[0],
            "analysis": rep.as_dict(), "links": [l for l in rep.links if l["flags"]][:20],
            "remote_images": A.remote_images(msg.html or ""), "images_shown": show_images,
        })
        return d
    finally:
        mb.logout()


def get_attachment(acc: dict, kind: str, uid: str, index: int) -> tuple[str, str, bytes]:
    mb = connect(acc)
    try:
        mb.folder.set(folder_name(mb, kind) or "INBOX", readonly=True)
        msgs = list(mb.fetch(uid_list=[uid], mark_seen=False))
        if not msgs or index >= len(msgs[0].attachments):
            raise MailError("not_found", "المرفق غير موجود.")
        a = msgs[0].attachments[index]
        if a.size > settings.attachment_max_bytes:
            raise MailError("too_big", "المرفق كبير جداً.")
        return a.filename or "attachment", a.content_type or "application/octet-stream", a.payload
    finally:
        mb.logout()


def set_flags(acc: dict, kind: str, uid: str, *, seen: bool | None = None, flagged: bool | None = None):
    mb = connect(acc)
    try:
        mb.folder.set(folder_name(mb, kind) or "INBOX")
        if seen is not None:
            mb.flag([uid], MailMessageFlags.SEEN, seen)
        if flagged is not None:
            mb.flag([uid], MailMessageFlags.FLAGGED, flagged)
    finally:
        mb.logout()


def move(acc: dict, kind: str, uid: str, dest: str):
    mb = connect(acc)
    try:
        src = folder_name(mb, kind) or "INBOX"
        target = folder_name(mb, dest)
        mb.folder.set(src)
        if target:
            mb.move([uid], target)
        else:
            mb.delete([uid])
    finally:
        mb.logout()


# ------------------------------------------------------------------ الإرسال

HEADER_SAFE = re.compile(r"[\r\n]")


def send(acc: dict, *, to: list[str], cc: list[str], subject: str, body: str, in_reply_to: str = "", references: str = "") -> str:
    for v in [subject, in_reply_to, references, *to, *cc]:
        if HEADER_SAFE.search(v or ""):
            raise MailError("bad_header", "قيمة غير صالحة.")
    msg = EmailMessage()
    msg["From"] = formataddr((acc.get("display_name") or "", acc["email"]))
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=acc["email"].rsplit("@", 1)[-1])
    msg["X-Mailer"] = "Sumer Mail"
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = (references + " " + in_reply_to).strip()
    msg.set_content(body)
    host, port = acc["smtp_host"], int(acc["smtp_port"])
    try:
        check_port(port, "smtp")
        ip = resolve(host, port)
        if port == 587:
            s = PinnedSMTP(host, port, ip, settings.imap_timeout)
            s.ehlo()
            from .netguard import tls_context
            s.starttls(context=tls_context())
            s.ehlo()
        else:
            s = PinnedSMTP_SSL(host, port, ip, settings.imap_timeout)
        try:
            s.login(acc["username"], acc["password"])
            s.send_message(msg)
        finally:
            try:
                s.quit()
            except Exception:
                pass
    except NetError as e:
        raise MailError(f"net_{e}", NET_MSG.get(str(e), "تعذّر الاتصال بخادم الإرسال."))
    except smtplib.SMTPAuthenticationError:
        raise MailError("smtp_auth", "خادم الإرسال رفض اسم المستخدم أو كلمة المرور.")
    except smtplib.SMTPRecipientsRefused:
        raise MailError("recipients", "خادم الإرسال رفض عنوان المستلم.")
    except (smtplib.SMTPException, OSError, ssl.SSLError) as e:
        raise MailError("smtp", f"تعذّر الإرسال ({type(e).__name__}).")
    # حفظ نسخة في «المرسل» للمزودين اللي ما يحفظونها تلقائياً
    if not PROVIDERS.get(acc.get("provider", ""), {}).get("saves_sent"):
        try:
            mb = connect(acc)
            try:
                sent = folder_name(mb, "sent")
                if sent:
                    mb.append(msg.as_bytes(), sent, flag_set=[MailMessageFlags.SEEN])
            finally:
                mb.logout()
        except MailError:
            pass
    return msg["Message-ID"]


def new_account_id() -> str:
    return uuid.uuid4().hex[:12]
