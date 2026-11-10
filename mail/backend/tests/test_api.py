from conftest import USERS, add


def test_providers_and_empty_session(client):
    assert any(p["id"] == "gmail" for p in client.get("/api/providers").json()["providers"])
    assert client.get("/api/session").json()["active"] is False
    assert client.get("/api/messages").status_code == 401


def test_csrf_header_required():
    from fastapi.testclient import TestClient
    from sumermail.app import app
    with TestClient(app) as c:
        r = c.post("/api/accounts", json={"email": "a@b.iq", "password": "x"})
        assert r.status_code == 403


def test_wrong_password(client):
    r = add(client, pw="nope")
    assert r.status_code == 400 and r.json()["detail"]["code"] == "auth"
    assert client.get("/api/session").json()["active"] is False


def test_outlook_needs_oauth(client):
    r = client.post("/api/accounts", json={"email": "x@outlook.com", "password": "p"})
    assert r.json()["detail"]["code"] == "oauth_only"


def test_private_network_blocked_without_dev_flag(client, monkeypatch):
    import dataclasses
    from sumermail import netguard
    monkeypatch.setattr(netguard, "settings", dataclasses.replace(netguard.settings, allow_private=False))
    r = add(client)
    assert r.status_code == 400 and r.json()["detail"]["code"] in ("net_private", "net_port")


def test_session_is_encrypted_at_rest(client):
    import redis, os
    assert add(client).status_code == 200
    r = redis.Redis.from_url(os.environ["SUMERMAIL_REDIS_URL"])
    keys = r.keys("sm:s:*")
    assert len(keys) == 1
    blob = r.get(keys[0])
    assert USERS["alice@test.iq"].encode() not in blob and b"alice@test.iq" not in blob
    # بدون الكوكي (المفتاح) ما تفيد البيانات
    client.cookies.clear()
    assert client.get("/api/session").json()["active"] is False


def test_unified_inbox_and_protection(client):
    assert add(client).status_code == 200
    assert add(client, "bob@test.iq").status_code == 200
    s = client.get("/api/session").json()
    assert len(s["accounts"]) == 2
    data = client.get("/api/messages").json()
    assert not data["errors"]
    msgs = {m["subject"]: m for m in data["messages"]}
    assert msgs["ملاحظات اجتماع الأمس"]["analysis"]["level"] == "safe"
    assert msgs["Your account will be closed within 24 hours"]["analysis"]["level"] == "danger"
    assert msgs["تم إيقاف بطاقتك مؤقتاً"]["analysis"]["level"] in ("caution", "danger")
    assert msgs["الفاتورة"]["analysis"]["level"] == "danger" and msgs["الفاتورة"]["has_attachments"]
    assert msgs["عروض الأسبوع"]["analysis"]["trackers"] == 1
    stats = client.get("/api/session").json()["stats"]
    assert stats["phishing"] >= 2 and stats["trackers"] >= 1 and stats["scanned"] == 5
    # الإحصاءات ما تتكرر عند إعادة الجلب
    client.get("/api/messages")
    assert client.get("/api/session").json()["stats"]["scanned"] == 5
    # البحث
    found = client.get("/api/messages", params={"q": "الفاتورة"}).json()["messages"]
    assert [m["subject"] for m in found] == ["الفاتورة"]


def test_read_message_sanitized(client):
    add(client)
    msgs = client.get("/api/messages").json()["messages"]
    t = next(m for m in msgs if m["subject"] == "عروض الأسبوع")
    d = client.get(f"/api/accounts/{t['account_id']}/messages/inbox/{t['uid']}").json()
    assert "<script" not in d["html"] and "javascript:" not in d["html"] and "cdn.shop.test" not in d["html"]
    assert d["remote_images"] == 2 and d["images_shown"] is False
    d2 = client.get(f"/api/accounts/{t['account_id']}/messages/inbox/{t['uid']}", params={"images": 1}).json()
    assert "cdn.shop.test/banner.png" in d2["html"]
    p = next(m for m in msgs if m["subject"].startswith("Your account"))
    dp = client.get(f"/api/accounts/{p['account_id']}/messages/inbox/{p['uid']}").json()
    assert dp["analysis"]["level"] == "danger" and "href" not in dp["html"]
    assert any(l["flags"] for l in dp["links"])


def test_attachment_download_is_never_inline_for_exe(client):
    add(client)
    m = next(x for x in client.get("/api/messages").json()["messages"] if x["subject"] == "الفاتورة")
    d = client.get(f"/api/accounts/{m['account_id']}/messages/inbox/{m['uid']}").json()
    a = d["attachments"][0]
    assert a["risk"] == "danger"
    r = client.get(f"/api/accounts/{m['account_id']}/messages/inbox/{m['uid']}/attachments/{a['index']}?inline=1")
    assert r.status_code == 200 and r.content.startswith(b"MZ")
    assert r.headers["content-type"] == "application/octet-stream" and r.headers["content-disposition"].startswith("attachment")


def test_flags_move_and_junk(client):
    add(client)
    m = next(x for x in client.get("/api/messages").json()["messages"] if x["subject"] == "تم إيقاف بطاقتك مؤقتاً")
    base = f"/api/accounts/{m['account_id']}/messages/inbox/{m['uid']}"
    assert client.post(base + "/flags", json={"seen": True}).status_code == 200
    m2 = next(x for x in client.get("/api/messages").json()["messages"] if x["uid"] == m["uid"])
    assert m2["seen"] is True
    assert client.post(base + "/move", json={"to": "junk"}).status_code == 200
    assert all(x["uid"] != m["uid"] for x in client.get("/api/messages").json()["messages"])
    junk = client.get("/api/messages", params={"folder": "junk"}).json()["messages"]
    assert any(x["subject"] == "تم إيقاف بطاقتك مؤقتاً" for x in junk)
    assert client.get("/api/session").json()["stats"]["reported"] == 1


def test_send_and_save_to_sent(client, smtp):
    acc = add(client).json()["account"]
    r = client.post("/api/send", json={"account_id": acc["id"], "to": ["bob@test.iq"], "subject": "تجربة سومر بريد", "body": "هلا بوب"})
    assert r.status_code == 200, r.text
    assert smtp and smtp[-1].rcpt_tos == ["bob@test.iq"]
    assert "تجربة سومر بريد".encode() in smtp[-1].content or b"=?utf-8?" in smtp[-1].content.lower()
    sent = client.get("/api/messages", params={"folder": "sent"}).json()["messages"]
    assert any(x["subject"] == "تجربة سومر بريد" for x in sent)


def test_header_injection_rejected(client, smtp):
    acc = add(client).json()["account"]
    r = client.post("/api/send", json={"account_id": acc["id"], "to": ["bob@test.iq"], "subject": "hi\r\nBcc: x@evil.com", "body": "x"})
    assert r.status_code == 400


def test_remove_account_and_logout(client):
    acc = add(client).json()["account"]
    assert client.delete(f"/api/accounts/{acc['id']}").json()["session"] is False
    assert client.get("/api/session").json()["active"] is False
