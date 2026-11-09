"""نتائج الويب العام الاحتياطية: تُضاف فقط عند قلة نتائج الفهرس، موسومة، وبدون تخزين."""

from sumer import websearch as WS

SAMPLE = {"query": {"more_results_available": True}, "web": {"results": [
    {"url": "https://example.com/a", "title": "About <strong>Babylon</strong>", "description": "Ancient <strong>Babylon</strong> &amp; more <b>x</b>"},
    {"url": "javascript:alert(1)", "title": "bad", "description": "bad"},
    {"url": "https://uot.edu.iq/", "title": "UoT", "description": ""},
]}}


def test_parse_is_safe_and_labeled():
    res, more = WS.parse(SAMPLE)
    assert more is True
    assert [r["url"] for r in res] == ["https://example.com/a", "https://uot.edu.iq/"]
    a = res[0]
    assert a["source"] == "web" and a["title"] == "About Babylon"
    assert any(s["h"] and "Babylon" in s["t"] for s in a["title_hl"])
    assert all("<" not in s["t"] for s in a["snippet"])
    assert "&" in "".join(s["t"] for s in a["snippet"])
    assert res[1]["iraqi"] is True


def test_fallback_only_when_index_is_thin(client, monkeypatch):
    calls = []

    async def fake(q, page, lang, safe):
        calls.append(q)
        return WS.parse(SAMPLE)

    monkeypatch.setattr(WS, "enabled", lambda: True)
    monkeypatch.setattr(WS, "threshold", lambda: 1)
    monkeypatch.setattr(WS, "search", fake)

    r = client.post("/api/search", json={"q": "zzqxv qqwvbk"}).json()
    assert r.get("local_total") == 0 and r.get("web_provider") == WS.PROVIDER, r
    assert r["results"][0]["source"] == "web" and r["total"] > 0

    n = len(calls)
    r = client.post("/api/search", json={"q": "جامعة بغداد"}).json()
    assert r["local_total"] >= 1 and r["web_provider"] is None and len(calls) == n


def test_fallback_failure_degrades_gracefully(client, monkeypatch):
    async def boom(*a):
        raise RuntimeError("provider down")
    monkeypatch.setattr(WS, "enabled", lambda: True)
    monkeypatch.setattr(WS, "search", boom)
    r = client.post("/api/search", json={"q": "zzqxv qqwvbk"})
    assert r.status_code == 200 and r.json()["web_provider"] is None


def test_disabled_without_key(client):
    assert WS.enabled() is False
    r = client.post("/api/search", json={"q": "zzqxv qqwvbk"}).json()
    assert r["web_provider"] is None
