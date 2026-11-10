from sumermail import analyze as A


def run(**kw):
    base = dict(from_header="", reply_to="", subject="", text="", html="", attachments=[], auth_results=[])
    base.update(kw)
    return A.analyze(**base)


def codes(r):
    return {x["code"] for x in r.reasons}


def test_clean_message_is_safe():
    r = run(from_header="Sara <sara@uni.edu.iq>", subject="ملاحظات الاجتماع", text="هلا، المرفق بيه الملاحظات.",
            auth_results=["mx; spf=pass; dkim=pass; dmarc=pass"])
    assert r.level == "safe" and not r.reasons


def test_brand_spoof_lookalike_and_dmarc():
    r = run(from_header='"PayPal Support" <service@paypa1-secure.com>', subject="Action required",
            auth_results=["mx; spf=fail; dmarc=fail"])
    assert r.level == "danger"
    assert {"brand_spoof", "lookalike_sender", "dmarc_fail"} <= codes(r)


def test_real_brand_not_flagged():
    r = run(from_header="Google <no-reply@accounts.google.com>", subject="Security alert",
            auth_results=["mx; spf=pass; dkim=pass; dmarc=pass"])
    assert "brand_spoof" not in codes(r) and "lookalike_sender" not in codes(r)


def test_link_mismatch_ip_and_script():
    r = run(html='<a href="http://203.0.113.9/x">www.rafidain.iq</a><a href="javascript:alert(1)">click</a>')
    assert {"link_mismatch", "ip_link", "script_link"} <= codes(r)


def test_arabic_bank_phish():
    r = run(from_header="خدمة عملاء المصرف <support@bank-iq-secure.co>", subject="تم إيقاف بطاقتك",
            text="حدّث بياناتك خلال 24 ساعة وأدخل رقم البطاقة")
    assert {"bank_claim", "urgency", "credentials"} <= codes(r)
    assert r.level in ("caution", "danger")


def test_gov_claim_outside_gov_iq():
    r = run(from_header="وزارة الداخلية <info@moi-iraq.net>", subject="مخالفة مرورية")
    assert "gov_claim" in codes(r)
    r2 = run(from_header="وزارة الداخلية <info@moi.gov.iq>", subject="مخالفة")
    assert "gov_claim" not in codes(r2)


def test_attachments():
    atts = [{"filename": "invoice.pdf.exe"}, {"filename": "login.html"}, {"filename": "report.docm"}, {"filename": "photos.zip"}, {"filename": "cv.pdf"}]
    r = run(attachments=atts)
    assert {"dangerous_attachment", "html_attachment", "macro_attachment", "archive_attachment"} <= codes(r)
    assert [a["risk"] for a in atts] == ["danger", "danger", "danger", "caution", "safe"]
    assert r.level == "danger"


def test_trackers_counted_and_sanitized():
    html = ('<p onclick="x()">hi</p><img src="https://track.x.com/open?id=1" width="1" height="1">'
            '<img src="https://cdn.shop.iq/a.png"><script>alert(1)</script><div style="background:url(https://t.x/p.gif)">b</div>'
            '<a href="https://shop.iq">shop</a>')
    r = run(html=html)
    assert r.trackers == 1
    out = A.sanitize(html, r, show_images=False)
    assert "<script" not in out and "onclick" not in out and "https://track" not in out and "cdn.shop.iq" not in out
    assert "url(" not in out and 'target="_blank"' in out
    shown = A.sanitize(html, r, show_images=True)
    assert "cdn.shop.iq/a.png" in shown


def test_danger_disables_all_links():
    html = '<a href="https://example.com/a">a</a>'
    r = run(html=html, from_header='"Apple" <id@app1e-verify.com>', auth_results=["x; dmarc=fail"])
    assert r.level == "danger"
    out = A.sanitize(html, r, show_images=False)
    assert "href" not in out and "data-blocked" in out


def test_name_with_other_email_and_reply_to():
    r = run(from_header='"support@bank.iq" <x@random.top>', reply_to="collect@other.com")
    assert {"name_has_other_email", "reply_to_mismatch"} <= codes(r)


def test_punycode_and_shortener():
    r = run(text="افتح https://xn--ggle-0nda.com/login و https://bit.ly/abc")
    assert {"punycode_link", "short_link"} <= codes(r)


def test_registrable():
    assert A.registrable("a.b.moi.gov.iq") == "moi.gov.iq"
    assert A.registrable("mail.google.com") == "google.com"
