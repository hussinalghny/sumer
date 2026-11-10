"""محرك حماية سومر بريد: يكشف التصيّد والانتحال والروابط المضلِّلة والمرفقات الخطرة ومتتبّعات الفتح،
ويعقّم HTML الرسائل قبل عرضها. كل التحليل يتم بالذاكرة ولا يُحفظ شيء.

المخرجات:
- level: safe | caution | danger
- reasons: قائمة أسباب مفهومة بالعربي (code, title, detail, severity)
"""

from __future__ import annotations

import html as htmlmod
import ipaddress
import re
import unicodedata
from dataclasses import dataclass, field
from email.utils import getaddresses, parseaddr
from urllib.parse import urlsplit

import nh3

# ------------------------------------------------------------------ أدوات النطاقات

MULTI_SUFFIX = {"gov.iq", "edu.iq", "com.iq", "org.iq", "net.iq", "co.uk", "com.sa", "gov.sa", "com.tr", "co.jp", "com.au"}


def registrable(host: str) -> str:
    """النطاق القابل للتسجيل بشكل تقريبي (example.com / ministry.gov.iq)."""
    host = (host or "").lower().strip(".")
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in MULTI_SUFFIX:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def domain_of(addr: str) -> str:
    return addr.rsplit("@", 1)[-1].lower().strip(">") if "@" in addr else ""


def is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
        return True
    except ValueError:
        return False


def lev(a: str, b: str, cap: int = 3) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


_HOMO = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "4": "a", "@": "a", "$": "s"})


def skeleton(label: str) -> str:
    s = unicodedata.normalize("NFKD", label.lower()).translate(_HOMO)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("rn", "m").replace("vv", "w").replace("cl", "d").replace("-", "")


# ------------------------------------------------------------------ العلامات المحمية

BRANDS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    (("google", "gmail", "جوجل", "كوكل", "غوغل"), ("google.com", "gmail.com", "youtube.com", "googlemail.com")),
    (("microsoft", "outlook", "office 365", "مايكروسوفت", "اوتلوك"), ("microsoft.com", "outlook.com", "live.com", "office.com", "microsoftonline.com")),
    (("apple", "icloud", "ابل", "أبل"), ("apple.com", "icloud.com")),
    (("paypal", "باي بال"), ("paypal.com",)),
    (("facebook", "meta", "instagram", "whatsapp", "فيسبوك", "انستغرام", "انستقرام", "واتساب"),
     ("facebook.com", "facebookmail.com", "meta.com", "instagram.com", "whatsapp.com")),
    (("amazon", "امازون", "أمازون"), ("amazon.com", "amazon.ae", "amazon.sa")),
    (("netflix", "نتفلكس"), ("netflix.com",)),
    (("dhl",), ("dhl.com",)),
]
PROTECTED = sorted({d for _, ds in BRANDS for d in ds})
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly", "rb.gy", "is.gd", "ow.ly", "shorturl.at", "tiny.cc", "s.id", "rebrand.ly"}
RISKY_TLDS = {"zip", "mov", "top", "xyz", "click", "country", "gq", "tk", "ml", "cf", "ga", "work", "rest", "loan", "support", "cam", "icu"}
DANGEROUS_EXT = {"exe", "scr", "pif", "com", "bat", "cmd", "js", "jse", "vbs", "vbe", "wsf", "hta", "msi", "jar", "ps1", "lnk",
                 "iso", "img", "vhd", "apk", "dll", "reg", "cpl"}
HTML_EXT = {"html", "htm", "shtml", "svg", "xhtml"}
MACRO_EXT = {"docm", "xlsm", "pptm", "dotm", "xlam"}
ARCHIVE_EXT = {"zip", "rar", "7z", "gz", "tar", "cab", "ace"}
TRACKER_HOSTS = ("mailtrack.io", "list-manage.com", "sendgrid.net", "mandrillapp.com", "hubspotemail.net", "hs-analytics.net",
                 "mailchimp.com", "sparkpostmail.com", "mixpanel.com", "pixel.", "track.", "open.", "trk.", "click.")
TRACKER_PATH = re.compile(r"(/open|/o\.gif|/track|/pixel|/beacon|/wf/open|/e/o/|/t\.gif|1x1|spacer\.gif)", re.I)

# ------------------------------------------------------------------ أنماط نصية (عربي + إنكليزي)


def norm_ar(s: str) -> str:
    s = re.sub(r"[ً-ٰٟـ]", "", s or "")
    s = s.translate(str.maketrans("أإآٱىةگچ", "اااايهكج"))
    return s.lower()


URGENCY = [norm_ar(x) for x in (
    "خلال 24 ساعة", "خلال ٢٤ ساعة", "خلال 48 ساعة", "فورا", "فوراً", "عاجل", "سيتم اغلاق", "سيتم إيقاف", "تم ايقاف", "تم تعليق",
    "اخر فرصة", "آخر تحذير", "تنتهي صلاحية", "حسابك معلق", "سيتم حذف حسابك",
    "within 24 hours", "immediately", "urgent", "account suspended", "will be closed", "final notice", "action required",
    "unusual activity", "verify within", "last warning")]
CREDENTIAL = [norm_ar(x) for x in (
    "تحديث بياناتك", "حدث بياناتك", "حدّث بياناتك", "تأكيد هويتك", "تاكيد حسابك", "ادخل كلمة المرور", "كلمة السر", "رقم البطاقة",
    "رمز التحقق", "الرقم السري", "بيانات بطاقتك", "تسجيل الدخول للتحقق",
    "verify your account", "confirm your identity", "update your payment", "enter your password", "login to verify",
    "verification code", "card number", "reset your password", "unlock your account")]
MONEY = [norm_ar(x) for x in (
    "ربحت", "فزت", "جائزة", "مبلغ مالي", "حوالة", "استرداد", "اربح", "lottery", "you won", "prize", "refund", "wire transfer",
    "gift card", "bitcoin", "crypto")]

# ------------------------------------------------------------------ النتيجة


@dataclass
class Report:
    score: int = 0
    reasons: list[dict] = field(default_factory=list)
    trackers: int = 0
    links: list[dict] = field(default_factory=list)
    auth: dict = field(default_factory=dict)

    def add(self, code: str, title: str, detail: str, severity: str, points: int):
        if any(r["code"] == code for r in self.reasons):
            return
        self.reasons.append({"code": code, "title": title, "detail": detail, "severity": severity})
        self.score += points

    @property
    def level(self) -> str:
        return "danger" if self.score >= 60 else "caution" if self.score >= 25 else "safe"

    def as_dict(self) -> dict:
        order = {"high": 0, "medium": 1, "low": 2}
        return {"level": self.level, "score": min(self.score, 100),
                "reasons": sorted(self.reasons, key=lambda r: order[r["severity"]]),
                "trackers": self.trackers, "auth": self.auth}


# ------------------------------------------------------------------ تحليل الترويسات


def parse_auth_results(values: list[str]) -> dict:
    """نعتمد على أعلى ترويسة Authentication-Results (يضيفها مزود البريد المستلِم)."""
    out = {}
    if not values:
        return out
    top = values[0].lower()
    for mech in ("spf", "dkim", "dmarc"):
        m = re.search(rf"\b{mech}=(pass|fail|softfail|neutral|none|temperror|permerror|bestguesspass)", top)
        if m:
            out[mech] = m.group(1)
    return out


def brand_claim(display: str, subject: str) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    text = norm_ar(f"{display} {subject}")
    return [(kw, ds) for kw, ds in BRANDS if any(re.search(rf"(?<![\w]){re.escape(norm_ar(k))}(?![\w])", text) for k in kw)]


def lookalike(host: str) -> str | None:
    """يرجع النطاق المحمي اللي يشبهه هذا النطاق (ومو هو نفسه)."""
    reg = registrable(host)
    if not reg or reg in PROTECTED:
        return None
    label = reg.split(".")[0]
    sk = skeleton(label)
    for d in PROTECTED:
        dl = d.split(".")[0]
        if sk == dl or (len(dl) >= 5 and lev(sk, dl) <= (1 if len(dl) < 7 else 2)):
            return d
        # paypal-secure-login.com / secure-google.xyz
        if len(dl) >= 5 and (dl in label or dl in sk) and reg != d:
            return d
    return None


def analyze_headers(rep: Report, *, from_header: str, reply_to: str, subject: str, auth_results: list[str],
                    return_path: str = "") -> None:
    name, addr = parseaddr(from_header or "")
    fdom = domain_of(addr)
    freg = registrable(fdom)
    rep.auth = parse_auth_results(auth_results)
    a = rep.auth

    if a.get("dmarc") == "fail":
        rep.add("dmarc_fail", "فشل التحقق من هوية المرسل", f"نطاق المرسل {fdom} يرفض هذه الرسالة (DMARC)، فالأغلب إنها منتحلة.", "high", 55)
    elif a.get("spf") in ("fail", "softfail") and a.get("dkim") not in ("pass",):
        rep.add("spf_fail", "المرسل غير مصرّح له", f"الخادم اللي أرسل الرسالة غير مسموح له يرسل باسم {fdom}.", "medium", 30)

    # اسم عرض يحتوي عنوان بريد ثاني: "support@paypal.com" <x@evil.top>
    m = re.search(r"[\w.+-]+@([\w-]+\.[\w.-]+)", name or "")
    if m and registrable(m.group(1).lower()) != freg:
        rep.add("name_has_other_email", "اسم المرسل مضلِّل", f"الاسم يعرض عنوان {m.group(0)} لكن الرسالة جاية فعلياً من {addr}.", "high", 45)

    for kws, legit in brand_claim(name, subject):
        if freg and freg not in {registrable(d) for d in legit}:
            rep.add("brand_spoof", "انتحال اسم جهة معروفة",
                    f"الرسالة تستخدم اسم «{kws[0]}» لكن عنوان المرسل من نطاق آخر: {fdom}.", "high", 50)
            break

    # جهات حكومية عراقية ومصارف
    nd = norm_ar(name)
    if any(k in nd for k in ("وزاره", "الحكومه", "مديريه", "هيئه", "ministry", "government")) and fdom and not fdom.endswith(".gov.iq"):
        rep.add("gov_claim", "يدّعي أنه جهة حكومية", f"الجهات الحكومية العراقية تراسل عادةً من نطاقات gov.iq، وهذا المرسل من {fdom}.", "medium", 30)
    if any(k in nd for k in ("مصرف", "بنك", "bank", "خدمه عملاء المصرف")) and fdom and not fdom.endswith(".iq") and freg not in ("qi.iq",):
        rep.add("bank_claim", "يدّعي أنه مصرف", f"اسم المرسل يوحي بمصرف، لكن العنوان من نطاق غير عراقي وغير رسمي: {fdom}.", "medium", 30)

    look = lookalike(fdom)
    if look:
        rep.add("lookalike_sender", "نطاق مرسل يشبه نطاقاً معروفاً", f"{fdom} يشبه {look} لكنه مو هو.", "high", 50)
    if fdom.startswith("xn--") or ".xn--" in fdom:
        rep.add("punycode_sender", "نطاق بحروف مموّهة", f"عنوان المرسل يستخدم حروفاً شبيهة ({fdom}).", "medium", 25)

    _, rto = parseaddr(reply_to or "")
    rdom = domain_of(rto)
    if rto and rdom and registrable(rdom) != freg:
        rep.add("reply_to_mismatch", "الرد يروح لعنوان مختلف", f"إذا رديت، رسالتك تروح إلى {rto} مو إلى المرسل الظاهر.", "medium", 20)


# ------------------------------------------------------------------ النص


def analyze_text(rep: Report, subject: str, text: str):
    t = norm_ar(f"{subject}\n{text}")[:20000]
    urg = any(k in t for k in URGENCY)
    cred = any(k in t for k in CREDENTIAL)
    money = any(k in t for k in MONEY)
    if urg:
        rep.add("urgency", "أسلوب ضغط واستعجال", "الرسالة تهددك أو تستعجلك حتى تتصرف بدون تفكير.", "low", 12)
    if cred:
        rep.add("credentials", "تطلب بيانات حساسة", "تطلب كلمة مرور أو بيانات بطاقة أو رمز تحقق. الجهات الحقيقية ما تطلبها بالبريد.", "medium", 18)
    if money:
        rep.add("money_bait", "وعد بمال أو جائزة", "عروض الجوائز والحوالات المفاجئة من أشهر أساليب الاحتيال.", "low", 10)
    if urg and cred:
        rep.score += 12  # الجمع بين الاستعجال وطلب البيانات علامة قوية


# ------------------------------------------------------------------ الروابط والـHTML

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
DOMAINISH = re.compile(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}(/\S*)?$", re.I)


def check_link(rep: Report, href: str, text: str = "") -> dict:
    info = {"href": href[:500], "text": (text or "")[:200], "host": "", "flags": []}
    h = (href or "").strip()
    low = h.lower()
    if low.startswith(("javascript:", "data:", "vbscript:")):
        info["flags"].append("script")
        rep.add("script_link", "رابط برمجي خطر", "الرسالة بيها رابط ينفّذ أوامر بدل ما يفتح صفحة.", "high", 45)
        return info
    if not low.startswith(("http://", "https://")):
        return info
    try:
        u = urlsplit(h)
    except ValueError:
        return info
    host = (u.hostname or "").lower()
    info["host"] = host
    if "@" in (u.netloc or ""):
        info["flags"].append("userinfo")
        rep.add("userinfo_link", "رابط مخادع", f"الرابط يخفي وجهته الحقيقية ({host}) خلف نص مضلِّل.", "high", 40)
    if is_ip(host):
        info["flags"].append("ip")
        rep.add("ip_link", "رابط لعنوان رقمي", "الرابط يودي لعنوان IP مباشرة بدل اسم موقع، وهذا شائع بالاحتيال.", "medium", 25)
    if registrable(host) in SHORTENERS:
        info["flags"].append("shortener")
        rep.add("short_link", "رابط مختصر يخفي الوجهة", f"الرابط عبر {host} ما يبين وين يوديك.", "low", 8)
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in RISKY_TLDS:
        info["flags"].append("risky_tld")
        rep.add("risky_tld", "نطاق عالي الخطورة", f"الرابط ينتهي بـ .{tld}، نطاق يكثر استخدامه بالاحتيال.", "low", 12)
    if host.startswith("xn--") or ".xn--" in host:
        info["flags"].append("punycode")
        rep.add("punycode_link", "رابط بحروف مموّهة", f"الرابط يستخدم حروفاً شبيهة بحروف موقع معروف ({host}).", "high", 35)
    look = lookalike(host)
    if look:
        info["flags"].append("lookalike")
        rep.add("lookalike_link", "رابط لموقع شبيه بموقع معروف", f"{host} يشبه {look} لكنه موقع ثاني.", "high", 50)
    # نص الرابط يعرض نطاقاً مختلفاً عن وجهته
    shown = (text or "").strip()
    if shown and DOMAINISH.match(shown.split()[0] if shown.split() else ""):
        try:
            sh = urlsplit(shown if "://" in shown else "http://" + shown).hostname or ""
        except ValueError:
            sh = ""
        if sh and registrable(sh) != registrable(host):
            info["flags"].append("mismatch")
            rep.add("link_mismatch", "رابط مضلِّل", f"الرابط مكتوب «{sh}» لكنه يوديك فعلياً إلى {host}.", "high", 45)
    return info


def _attr_filter_factory(rep: Report, show_images: bool, cid_map: dict[str, str]):
    def f(tag: str, attr: str, value: str):
        if tag == "img" and attr == "src":
            v = value.strip()
            if v.lower().startswith("cid:"):
                return cid_map.get(v[4:].strip("<>"))
            if v.lower().startswith(("http://", "https://")):
                return v if show_images else None
            return None
        if attr == "style":
            # url() داخل style يُستخدم للتتبّع
            return re.sub(r"url\s*\([^)]*\)", "none", value, flags=re.I)[:2000]
        return value
    return f


ALLOWED_TAGS = {"a", "abbr", "b", "blockquote", "br", "caption", "center", "code", "col", "colgroup", "dd", "del", "div", "dl", "dt",
                "em", "font", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "img", "ins", "li", "ol", "p", "pre", "q", "s", "small",
                "span", "strike", "strong", "sub", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "u", "ul"}
ALLOWED_ATTRS = {
    "*": {"style", "dir", "align", "title", "lang"},
    "a": {"href"}, "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan", "width", "height", "bgcolor", "valign"}, "th": {"colspan", "rowspan", "width", "valign"},
    "table": {"width", "cellpadding", "cellspacing", "border", "bgcolor"}, "font": {"color", "size", "face"},
}

IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
A_RE = re.compile(r"<a\b[^>]*?href\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)[^>]*>(.*?)</a>", re.I | re.S)
ATTR_RE = lambda name: re.compile(rf"\b{name}\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def _attr(tag: str, name: str) -> str:
    m = ATTR_RE(name).search(tag)
    return htmlmod.unescape(m.group(1).strip("\"'")) if m else ""


def count_trackers(html: str) -> int:
    n = 0
    for tag in IMG_RE.findall(html or ""):
        src = _attr(tag, "src")
        if not src.lower().startswith(("http://", "https://")):
            continue
        w, h = _attr(tag, "width"), _attr(tag, "height")
        style = _attr(tag, "style").replace(" ", "").lower()
        tiny = (w in ("0", "1", "2") or h in ("0", "1", "2") or "display:none" in style or "width:1px" in style
                or "height:1px" in style or "visibility:hidden" in style)
        try:
            u = urlsplit(src)
            host, path = (u.hostname or "").lower(), u.path
        except ValueError:
            host, path = "", ""
        known = any(t in host for t in TRACKER_HOSTS) or bool(TRACKER_PATH.search(path))
        if tiny or known:
            n += 1
    return n


def remote_images(html: str) -> int:
    return sum(1 for t in IMG_RE.findall(html or "") if _attr(t, "src").lower().startswith(("http://", "https://")))


def analyze_links(rep: Report, html: str, text: str):
    seen = set()
    for m in A_RE.finditer(html or ""):
        href = htmlmod.unescape(m.group(1).strip("\"'"))
        label = htmlmod.unescape(TAG_RE.sub("", m.group(2))).strip()
        key = (href, label)
        if key in seen:
            continue
        seen.add(key)
        rep.links.append(check_link(rep, href, label))
        if len(rep.links) > 200:
            break
    for u in URL_RE.findall(text or "")[:100]:
        if all(l["href"] != u for l in rep.links):
            rep.links.append(check_link(rep, u, ""))


def sanitize(html: str, rep: Report, *, show_images: bool, cid_map: dict[str, str] | None = None) -> str:
    disable_links = rep.level == "danger"
    flagged = {l["href"] for l in rep.links if l["flags"]}
    cleaned = nh3.clean(
        html or "", tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, url_schemes={"http", "https", "mailto", "cid"},
        link_rel="noopener noreferrer nofollow", strip_comments=True,
        attribute_filter=_attr_filter_factory(rep, show_images, cid_map or {}),
    )

    def fix_a(m: re.Match) -> str:
        tag = m.group(0)
        href = _attr(tag, "href")
        if disable_links or href in flagged:
            tag = ATTR_RE("href").sub('data-blocked="1"', tag, count=1)
            return tag.replace("<a", '<a title="الرابط معطّل لحمايتك"', 1)
        return tag.replace("<a", '<a target="_blank"', 1)

    return re.sub(r"<a\b[^>]*>", fix_a, cleaned, flags=re.I)


# ------------------------------------------------------------------ المرفقات


def analyze_attachments(rep: Report, atts: list[dict]):
    for a in atts:
        name = (a.get("filename") or "").lower().strip()
        parts = [p for p in name.split(".") if p]
        ext = parts[-1] if len(parts) > 1 else ""
        a["risk"] = "safe"
        if ext in DANGEROUS_EXT:
            a["risk"] = "danger"
            rep.add("dangerous_attachment", "مرفق قابل للتشغيل", f"الملف «{a.get('filename')}» برنامج أو سكربت ممكن يأذي جهازك. لا تفتحه.", "high", 60)
        elif ext in HTML_EXT:
            a["risk"] = "danger"
            rep.add("html_attachment", "مرفق صفحة ويب", f"«{a.get('filename')}» صفحة ويب مرفقة، وهذا أسلوب شائع لسرقة كلمات المرور.", "high", 45)
        elif ext in MACRO_EXT:
            a["risk"] = "danger"
            rep.add("macro_attachment", "مستند بماكرو", f"«{a.get('filename')}» مستند يحتوي أوامر (Macro) ممكن تشغّل برامج ضارة.", "high", 40)
        elif len(parts) >= 3 and parts[-2] in {"pdf", "doc", "docx", "jpg", "png", "xls", "xlsx", "txt"} and ext in DANGEROUS_EXT | ARCHIVE_EXT:
            a["risk"] = "danger"
            rep.add("double_ext", "اسم ملف مموّه", f"«{a.get('filename')}» يتظاهر بأنه {parts[-2].upper()} لكنه فعلياً .{ext}", "high", 55)
        elif ext in ARCHIVE_EXT:
            a["risk"] = "caution"
            rep.add("archive_attachment", "ملف مضغوط", "الملفات المضغوطة ممكن تخفي برامج ضارة. افتحها بس إذا تعرف المرسل.", "low", 8)


# ------------------------------------------------------------------ الواجهة الرئيسية


def analyze(*, from_header: str, reply_to: str, subject: str, text: str, html: str, attachments: list[dict],
            auth_results: list[str], known_contact: bool = False) -> Report:
    rep = Report()
    analyze_headers(rep, from_header=from_header, reply_to=reply_to, subject=subject, auth_results=auth_results)
    analyze_text(rep, subject, text or htmlmod.unescape(TAG_RE.sub(" ", html or "")))
    analyze_links(rep, html, text)
    analyze_attachments(rep, attachments)
    rep.trackers = count_trackers(html)
    if rep.auth.get("dmarc") == "pass" and rep.score < 40:
        rep.score = max(0, rep.score - 10)
    if known_contact and rep.score < 50:
        rep.score = max(0, rep.score - 10)
    return rep
