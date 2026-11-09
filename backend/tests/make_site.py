"""يولّد موقعاً تجريبياً محلياً لاختبار الزاحف والبحث (عربي، كردي، إنكليزي، PDF، صور، sitemap...)."""

import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw

PAGES = {
    "index.html": ("بوابة الخدمات العراقية", "دليل الخدمات للمواطن العراقي",
                   "<h1>بوابة الخدمات</h1><p>مرحباً بكم في بوابة الخدمات التي تجمع أدلة المعاملات اليومية للمواطنين في العراق.</p>"),
    "passport.html": ("كيفية استخراج جواز السفر العراقي", "خطوات استخراج وتجديد جواز السفر",
                      "<h1>استخراج جواز السفر</h1><p>لاستخراج جواز السفر العراقي يجب أولاً امتلاك البطاقة الوطنية الموحدة.</p>"
                      "<p>بعدها يتم الحجز الإلكتروني للموعد، ثم مراجعة مديرية الجوازات لأخذ البصمة والصورة.</p>"
                      "<p>يُسلَّم الجواز بعد اكتمال التدقيق، ويمكن متابعة حالة الطلب إلكترونياً.</p>"
                      '<img src="/img/passport.png" alt="نموذج جواز سفر عراقي" width="300" height="200">'),
    "national-id.html": ("البطاقة الوطنية الموحدة", "التسجيل على البطاقة الوطنية",
                         "<h1>البطاقة الوطنية</h1><p>البطاقة الوطنية الموحدة تجمع هوية الأحوال المدنية وشهادة الجنسية.</p>"
                         "<p>يتم الحجز إلكترونياً ثم مراجعة دائرة الأحوال المدنية لأخذ البصمات.</p>"),
    "admission.html": ("القبول المركزي في الجامعات العراقية", "التقديم على الجامعات والكليات",
                       "<h1>القبول المركزي</h1><p>يتم التقديم على القبول المركزي في الجامعات والكليات الحكومية إلكترونياً بعد إعلان نتائج السادس الإعدادي.</p>"
                       "<p>يختار الطالب رغباته حسب المعدل والفرع العلمي أو الأدبي.</p>"),
    "restaurants.html": ("أفضل مطاعم بغداد", "دليل المطاعم في بغداد",
                         "<h1>مطاعم بغداد</h1><p>يشتهر شارع أبو نؤاس بمطاعم السمك المسكوف المطلة على نهر دجلة.</p>"
                         "<p>أما الكرادة والمنصور فتضم مطاعم الكباب والمشويات والمأكولات الشعبية العراقية.</p>"
                         '<img src="/img/masgouf.png" alt="سمك مسكوف مشوي على الحطب" width="400" height="260">'),
    "generator.html": ("اشتراك المولدة الأهلية والكهرباء الوطنية", "أسعار وتنظيم اشتراك المولدات",
                       "<h1>المولدة والكهرباء</h1><p>يعتمد كثير من البيوت على اشتراك المولدة الأهلية عند انقطاع الكهرباء الوطنية.</p>"
                       "<p>تحدد المجالس المحلية سعر الأمبير شهرياً وتراقب ساعات التشغيل.</p>"),
    "jobs.html": ("التعيينات والوظائف الحكومية", "آخر أخبار التعيين في الوزارات",
                  "<h1>التعيينات</h1><p>تعلن الوزارات عن درجات وظيفية للتعيين عبر بوابات إلكترونية رسمية.</p>"
                  "<p>يجب على المتقدم رفع الوثائق الدراسية والبطاقة الوطنية.</p>"),
    "kurdish.html": ("زانکۆی سلێمانی", "زانیاری دەربارەی زانکۆکان لە هەرێمی کوردستان",
                     "<h1>زانکۆکانی کوردستان</h1><p>زانکۆی سلێمانی یەکێکە لە گەورەترین زانکۆکانی هەرێمی کوردستان و خوێندکارانی زۆری هەیە.</p>"
                     "<p>وەرگرتنی خوێندکاران بەپێی نمرە و بەشەکان دەکرێت.</p>"),
    "english.html": ("Baghdad travel guide", "Visiting Baghdad: history, food and culture",
                     "<h1>Baghdad travel guide</h1><p>Baghdad is the capital of Iraq, known for Al-Mutanabbi Street, the Tigris river and its famous masgouf grilled fish.</p>"
                     "<p>Visitors enjoy the book markets on Friday mornings.</p>"),
    "duplicate.html": ("كيفية استخراج جواز السفر العراقي", "خطوات استخراج وتجديد جواز السفر",
                       "<h1>استخراج جواز السفر</h1><p>لاستخراج جواز السفر العراقي يجب أولاً امتلاك البطاقة الوطنية الموحدة.</p>"
                       "<p>بعدها يتم الحجز الإلكتروني للموعد، ثم مراجعة مديرية الجوازات لأخذ البصمة والصورة.</p>"
                       "<p>يُسلَّم الجواز بعد اكتمال التدقيق، ويمكن متابعة حالة الطلب إلكترونياً.</p>"
                       '<img src="/img/passport.png" alt="نموذج جواز سفر عراقي" width="300" height="200">'),
    "spam.html": ("رخيص رخيص رخيص", "رخيص",
                  "<p>" + " ".join(["رخيص"] * 150 + ["عروض"] * 10) + "</p>"),
    "draft.html": ("مسودة غير منشورة", "مسودة", "<p>هذه مسودة عن جواز السفر لا يجب فهرستها.</p>"),
    "private/secret.html": ("صفحة سرية", "سري", "<p>محتوى سري ممنوع على الزواحف جواز.</p>"),
    "admin-area/x.html": ("منطقة مستثناة", "مستثناة", "<p>هذه صفحة في مسار مستثنى جواز.</p>"),
    "old.html": None,  # تحويل
    "canon-a.html": ("نسخة طباعة: طقس العراق", "طقس",
                     "<p>نسخة الطباعة لصفحة الطقس في العراق صيفاً وشتاءً.</p>"),
    "weather.html": ("طقس العراق", "حالة الطقس ودرجات الحرارة",
                     "<h1>الطقس</h1><p>يتميز صيف العراق بدرجات حرارة مرتفعة جداً، بينما يكون الشتاء معتدلاً مع أمطار قليلة.</p>"),
    "from-sitemap.html": ("صفحة من خريطة الموقع فقط", "اكتشاف عبر sitemap",
                          "<p>هذه الصفحة غير مرتبطة بأي رابط وتكتشف فقط من خريطة الموقع sitemap.</p>"),
}

NAV = ('<nav>' + " ".join(f'<a href="/{p}">{p}</a>' for p in PAGES if p not in ("from-sitemap.html",))
       + ' <a href="/report.pdf">تقرير</a> <a href="mailto:a@b.iq">بريد</a> <a href="/x.zip">ملف</a>'
       + ' <a href="/passport.html?utm_source=x#top">تتبع</a></nav>')


def build(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    for name, spec in PAGES.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if spec is None:
            continue
        title, desc, body = spec
        extra = ""
        if name == "draft.html":
            extra = '<meta name="robots" content="noindex">'
        if name == "canon-a.html":
            extra = '<link rel="canonical" href="/weather.html">'
        lang = "ckb" if name == "kurdish.html" else "en" if name == "english.html" else "ar"
        p.write_text(f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{title}</title>
<meta name="description" content="{desc}">{extra}<script>var tracking='لا يجب أن يُفهرس';</script></head>
<body>{NAV}<main>{body}</main><footer>حقوق النشر</footer></body></html>""", encoding="utf-8")
    (root / "robots.txt").write_text("User-agent: *\nDisallow: /private/\nSitemap: /sitemap.xml\n")
    pages = "".join(f"<url><loc>{{BASE}}/{n}</loc></url>" for n in ("index.html", "from-sitemap.html"))
    (root / "sitemap.xml.tpl").write_text(
        f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{pages}</urlset>')
    img = root / "img"
    img.mkdir(exist_ok=True)
    for name, color in (("passport.png", (20, 60, 140)), ("masgouf.png", (200, 120, 40))):
        im = Image.new("RGB", (400, 260), color)
        d = ImageDraw.Draw(im)
        for i in range(0, 400, 40):
            d.rectangle([i, (i * 3) % 200, i + 20, (i * 3) % 200 + 50], fill=(255 - color[0], 230, 255 - color[2]))
        im.save(img / name)
    (root / "report.pdf").write_bytes(_pdf("National Development Plan for Iraq 2024 education infrastructure report"))


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 18 Tf 50 750 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for o in offs:
        out.write(b"%010d 00000 n \n" % o)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


if __name__ == "__main__":
    build(Path(sys.argv[1]))
