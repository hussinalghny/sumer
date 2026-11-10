import os
os.environ.update({"SUMERMAIL_ENV": "test", "SUMERMAIL_ALLOW_PRIVATE_NETWORKS": "1", "SUMERMAIL_INSECURE_TLS": "1",
                   "SUMERMAIL_COOKIE_SECURE": "0", "SUMERMAIL_REDIS_URL": "redis://localhost:6379/14",
                   "SUMERMAIL_SECRET": "t" * 40})

import imaplib
import ssl
import subprocess
import time
from email.message import EmailMessage

import pytest
import redis

IMAP_HOST, IMAP_PORT = "localhost", 10993
SMTP_PORT = 10465
USERS = {"alice@test.iq": "alice-pass", "bob@test.iq": "bob-pass"}


def _imap(user):
    c = ssl.create_default_context(); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE
    m = imaplib.IMAP4_SSL("127.0.0.1", IMAP_PORT, ssl_context=c)
    m.login(user, USERS[user])
    return m


def _msg(frm, subject, text=None, html=None, headers=None, attach=None):
    m = EmailMessage()
    m["From"] = frm; m["To"] = "alice@test.iq"; m["Subject"] = subject
    m["Date"] = "Mon, 09 Nov 2026 10:00:00 +0300"
    for k, v in (headers or {}).items():
        m[k] = v
    if text is not None:
        m.set_content(text)
    if html is not None:
        if text is None:
            m.set_content(html, subtype="html")
        else:
            m.add_alternative(html, subtype="html")
    for name, data, mt in (attach or []):
        m.add_attachment(data, maintype=mt.split("/")[0], subtype=mt.split("/")[1], filename=name)
    return m.as_bytes()


SEED = [
    ("normal", _msg("سارة محمد <sara@test.iq>", "ملاحظات اجتماع الأمس", "هلا، هاي ملاحظات الاجتماع.\nhttps://docs.test.iq/notes")),
    ("phish", _msg('"Google Security" <no-reply@g00gle-security.top>', "Your account will be closed within 24 hours",
                   None, '<p>Verify your account immediately.</p><a href="http://192.0.2.7/login">https://accounts.google.com</a>'
                         '<img src="https://track.evil.top/open?id=1" width="1" height="1">',
                   headers={"Authentication-Results": "mx.test.iq; spf=fail smtp.mailfrom=g00gle-security.top; dmarc=fail"})),
    ("bank", _msg("خدمة عملاء المصرف <support@bank-iq-secure.co>", "تم إيقاف بطاقتك مؤقتاً",
                  "عزيزي العميل، حدّث بياناتك خلال 24 ساعة وأدخل رقم البطاقة لتجنب الإغلاق: http://bank-iq-secure.co/update")),
    ("tracker", _msg("Newsletter <news@shop.test.iq>", "عروض الأسبوع", None,
                     '<p>عروض</p><img src="https://cdn.shop.test/banner.png"><img src="https://list-manage.com/track/open.php?u=1" width="1" height="1">'
                     '<script>alert(1)</script><a href="javascript:alert(1)">x</a>')),
    ("exe", _msg("Ali <ali@test.iq>", "الفاتورة", "شوف الفاتورة المرفقة", attach=[("invoice.pdf.exe", b"MZ\x90\x00", "application/octet-stream")])),
]


@pytest.fixture(scope="session", autouse=True)
def mailserver():
    # صناديق نظيفة
    for u in USERS:
        m = _imap(u)
        for f in ("INBOX", "Sent", "Trash", "Junk"):
            m.select(f)
            typ, data = m.search(None, "ALL")
            if data and data[0]:
                m.store(b",".join(data[0].split()).decode(), "+FLAGS", "\\Deleted")
                m.expunge()
        m.logout()
    m = _imap("alice@test.iq")
    for _, raw in SEED:
        m.append("INBOX", None, imaplib.Time2Internaldate(time.time()), raw)
        time.sleep(0.01)
    m.logout()
    yield


@pytest.fixture(scope="session")
def smtp():
    from aiosmtpd.controller import Controller
    from aiosmtpd.smtp import AuthResult, LoginPassword
    got = []

    class H:
        async def handle_DATA(self, server, session, envelope):
            got.append(envelope)
            return "250 OK"

    def auth(server, session, envelope, mechanism, auth_data):
        ok = isinstance(auth_data, LoginPassword) and USERS.get(auth_data.login.decode()) == auth_data.password.decode()
        return AuthResult(success=ok)

    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain("/tmp/dove/cert.pem", "/tmp/dove/key.pem")
    c = Controller(H(), hostname="127.0.0.1", port=SMTP_PORT, ssl_context=ctx, authenticator=auth,
                   auth_require_tls=False, auth_exclude_mechanism=["DONT"])
    c.start()
    yield got
    c.stop()


@pytest.fixture(autouse=True)
def clean_redis():
    redis.Redis.from_url(os.environ["SUMERMAIL_REDIS_URL"]).flushdb()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from sumermail.app import app
    with TestClient(app, headers={"x-sumer-mail": "1"}) as c:
        yield c


def add(client, user="alice@test.iq", pw=None):
    return client.post("/api/accounts", json={"email": user, "password": pw or USERS[user], "provider": "custom",
                                              "imap_host": IMAP_HOST, "imap_port": IMAP_PORT,
                                              "smtp_host": "localhost", "smtp_port": SMTP_PORT})
