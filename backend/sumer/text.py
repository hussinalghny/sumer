"""معالجة النص: تطبيع العربية والكردية، تجذيع خفيف عربي وإنكليزي، كشف اللغة،
اللهجة العراقية، العربيزي، وبصمة SimHash لكشف التكرار.

نفس الدوال تُستخدم للفهرسة وللاستعلام. إذا تغيّر سلوكها، ارفع ANALYZER_VERSION
وأعد بناء الفهرس من لوحة التحكم.
"""

import hashlib
import re
import unicodedata

ANALYZER_VERSION = 1

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
# حروف عربية + حروف كردية/فارسية إضافية + لاتينية + أرقام
_WORD = re.compile(r"[ء-يٱ-ەۥۦۮ-ۿa-z0-9]+")
_ARABIC_SCRIPT = re.compile(r"[؀-ۿ]")
_LATIN = re.compile(r"[a-zA-Z]")
# حروف تميّز الكردية السورانية عن العربية
_KURDISH_MARKERS = set("ڕڵۆێەڤپچژگ")
_KURDISH_STRONG = set("ڕڵۆێە")

_CHAR_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي", "ی": "ي", "ې": "ي",
    "ؤ": "و",
    "ة": "ه", "ھ": "ه",
    "ك": "ك", "ک": "ك",
    "گ": "ك",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
})

STOPWORDS = set("""
في من الي علي عن ان او ما لا هذا هذه ذلك تلك التي الذي الذين كان كانت مع هو هي ثم قد لقد كل بين عند حتي اذا لم لن و يا اي ايضا بعد قبل
له لها لهم هم هن نحن انت انا كما لكن بل ام اما الا غير فقط منذ خلال حول ضد عبر
the a an of and or to in is are was were for on at by with from as be this that it its not but
و لە بۆ لەگەڵ کە ئەم ئەو یان
""".split())

# اللهجة العراقية -> مرادفات بالفصحى (كلها مطبّعة). الكلمة الأصلية تبقى بالاستعلام أيضاً.
IRAQI_DIALECT = {
    "شلون": ["كيف"], "شنو": ["ماذا", "ما"], "شكو": ["ماذا"], "وين": ["اين"], "شوكت": ["متي"],
    "ليش": ["لماذا"], "شكد": ["كم"], "اكو": ["يوجد"], "ماكو": ["يوجد"], "هسه": ["الان"],
    "هسع": ["الان"], "باجر": ["غدا"], "اطلع": ["استخراج", "اصدار"], "اسوي": ["استخراج", "اصدار", "عمل"],
    "تسوي": ["استخراج", "اصدار"], "هويه": ["بطاقه", "وطنيه", "هويه"], "سنويه": ["تسجيل", "مركبه", "سنويه"],
    "شغل": ["عمل", "وظيفه", "تعيين"], "تعيينات": ["تعيين", "وظائف"], "احسن": ["افضل"], "زين": ["جيد"],
    "خوش": ["جيد"], "واجد": ["كثير"], "مولده": ["مولده", "امبير"], "تكنلوجيه": ["تكنولوجيه"],
    "نت": ["انترنت"], "انترنيت": ["انترنت"], "اكل": ["مطعم", "اكلات"], "بانزين": ["بنزين", "وقود"],
    "دكتور": ["طبيب", "دكتور"], "مستشفي": ["مستشفي"], "صيدليه": ["صيدليه"], "ابي": ["اريد"],
}

_EN_SUFFIXES = ("ational", "ization", "fulness", "ousness", "iveness", "ations", "ation", "ments",
                "ement", "ment", "ness", "ings", "ing", "edly", "ies", "ied", "ers", "est", "ed", "er", "es", "ly", "s")
_AR_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")
_AR_SUFFIXES = ("ات", "ون", "ين", "يه", "ها", "هم", "ان", "ه", "ي")
_KU_SUFFIXES = ("ەکان", "ەکە", "یەکان", "کان", "ەوە", "ان", "ەی", "ی")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = _DIACRITICS.sub("", text)
    return text.translate(_CHAR_MAP).lower()


def detect_language(text: str) -> str | None:
    """كشف لغة بالحروف: عربية، كردية سورانية، أو لاتينية (إنكليزية/كرمانجية)."""
    sample = (text or "")[:5000]
    arabic = len(_ARABIC_SCRIPT.findall(sample))
    latin = len(_LATIN.findall(sample))
    if arabic == 0 and latin == 0:
        return None
    if arabic >= latin:
        strong = sum(1 for ch in sample if ch in _KURDISH_STRONG)
        markers = sum(1 for ch in sample if ch in _KURDISH_MARKERS)
        if strong >= 3 or (arabic and markers / arabic > 0.03 and strong >= 1):
            return "ckb"
        return "ar"
    low = sample.lower()
    kmr_hits = sum(low.count(w) for w in (" û ", " ji ", " bi ", " ê ", "ê ", "ş", "ç", "î"))
    en_hits = sum(low.count(w) for w in (" the ", " and ", " of ", " to ", " is "))
    return "kmr" if kmr_hits > en_hits * 2 and kmr_hits > 5 else "en"


def _stem_ar(t: str) -> str:
    if len(t) <= 3:
        return t
    for p in _AR_PREFIXES:
        if t.startswith(p) and len(t) - len(p) >= 3:
            t = t[len(p):]
            break
    for s in _AR_SUFFIXES:
        if t.endswith(s) and len(t) - len(s) >= 3:
            t = t[: -len(s)]
            break
    return t


def _stem_ku(t: str) -> str:
    for s in _KU_SUFFIXES:
        if t.endswith(s) and len(t) - len(s) >= 3:
            return t[: -len(s)]
    return t


def _stem_en(t: str) -> str:
    if len(t) <= 4 or not t.isalpha():
        return t
    for s in _EN_SUFFIXES:
        if t.endswith(s) and len(t) - len(s) >= 3:
            t = t[: -len(s)]
            if s in ("ies", "ied"):
                t += "y"
            break
    if len(t) > 3 and t[-1] == t[-2] and t[-1] not in "lsz":
        t = t[:-1]
    return t


def stem(token: str) -> str:
    if not token:
        return token
    ch = token[0]
    if "a" <= ch <= "z":
        return _stem_en(token)
    if any(c in _KURDISH_STRONG for c in token):
        return _stem_ku(token)
    if "ء" <= ch <= "ۿ":
        return _stem_ar(token)
    return token


def words(text: str) -> list[str]:
    return _WORD.findall(normalize(text))


def tokens(text: str) -> list[str]:
    return [stem(w) for w in words(text) if w not in STOPWORDS and len(w) > 1]


def analyzed(text: str) -> str:
    """نص جاهز لـ to_tsvector('simple', ...)"""
    return " ".join(tokens(text))


# ---------------- العربيزي ----------------
_ARABIZI_MULTI = [("sh", "ش"), ("kh", "خ"), ("gh", "غ"), ("th", "ث"), ("dh", "ذ"), ("ch", "چ"),
                  ("ee", "ي"), ("oo", "و"), ("ou", "و"), ("aa", "ا"), ("3'", "غ"), ("7'", "خ")]
_ARABIZI_ONE = {"2": "ء", "3": "ع", "5": "خ", "6": "ط", "7": "ح", "8": "ق", "9": "ص",
                "b": "ب", "t": "ت", "j": "ج", "d": "د", "r": "ر", "z": "ز", "s": "س", "f": "ف",
                "q": "ق", "k": "ك", "l": "ل", "m": "م", "n": "ن", "h": "ه", "w": "و", "y": "ي",
                "g": "ك", "p": "ب", "v": "ف", "c": "ك", "x": "كس"}
_VOWELS = {"a": ("", "ا"), "e": ("", "ي"), "i": ("", "ي"), "o": ("", "و"), "u": ("", "و")}


def is_latin_word(w: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9']+", w)) and bool(re.search(r"[a-z]", w))


def arabizi_variants(word: str, limit: int = 128) -> list[str]:
    """كل حرف علة إما يُحذف أو يصير حرف مد. المستدعي يُصفّي حسب المصطلحات الموجودة بالفهرس."""
    w = word.lower()
    for a, b in _ARABIZI_MULTI:
        w = w.replace(a, b)
    out = [""]
    for i, ch in enumerate(w):
        opts = ("ا",) if (ch in _VOWELS and i == 0) else _VOWELS.get(ch, (_ARABIZI_ONE.get(ch, ch),))
        out = [v + o for v in out for o in opts][:limit]
    return list(dict.fromkeys(normalize(v) for v in out if len(v) >= 2))


# ---------------- SimHash ----------------
def simhash(text: str) -> int:
    """بصمة 64 بت على ثلاثيات الكلمات. فرق ≤ 3 بتات = صفحتان شبه متطابقتين."""
    toks = tokens(text)
    if len(toks) < 3:
        toks = toks or [""]
        grams = toks
    else:
        grams = [" ".join(toks[i:i + 3]) for i in range(len(toks) - 2)]
    v = [0] * 64
    for g in grams:
        h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "big")
        for i in range(64):
            v[i] += 1 if (h >> i) & 1 else -1
    out = 0
    for i in range(64):
        if v[i] > 0:
            out |= 1 << i
    # تحويل إلى bigint موقّع لـ PostgreSQL
    return out - (1 << 64) if out >= 1 << 63 else out


def hamming(a: int, b: int) -> int:
    return bin((a ^ b) & ((1 << 64) - 1)).count("1")
