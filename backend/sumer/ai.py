"""خدمات الذكاء الاصطناعي المحلية فقط. لا توجد أي واجهة خارجية.

كل خدمة تفحص فعلياً: هل المكتبة مثبتة؟ هل ملفات النموذج موجودة؟ هل النموذج محمّل؟
إذا غير متوفرة، الواجهة ترجع 503 مع السبب، ولا تحاكي النتيجة أبداً.

مواقع النماذج (داخل SUMER_MODELS_DIR):
  whisper/       نموذج faster-whisper (مثل large-v3 أو small بصيغة CTranslate2)
  translation/   نموذج NLLB-200 بصيغة CTranslate2 + sentencepiece.model
  clip/          نموذج open_clip (اختياري، للتشابه الدلالي للصور)
  embeddings/    نموذج تضمين نصي (اختياري، للبحث الدلالي)
"""

import importlib.util
import os
import shutil
import subprocess
import tempfile
import threading
import time

import psutil

from . import text as T
from .config import settings
from .privacy import temp_dir


class ServiceUnavailable(Exception):
    pass


_loaded: dict = {}
_lock = threading.Lock()
_queues = {"speech": 0, "translation": 0, "image_similarity": 0, "embeddings": 0}

SERVICES = {
    "language_detection": {"package": None, "model_dir": None, "label_ar": "كشف اللغة", "label_en": "Language detection"},
    "speech": {"package": "faster_whisper", "model_dir": "whisper", "label_ar": "التعرّف على الكلام", "label_en": "Speech recognition"},
    "translation": {"package": "ctranslate2", "model_dir": "translation", "label_ar": "الترجمة", "label_en": "Translation"},
    "embeddings": {"package": "sentence_transformers", "model_dir": "embeddings", "label_ar": "نماذج التضمين", "label_en": "Embedding models"},
    "image_similarity": {"package": "open_clip", "model_dir": "clip", "label_ar": "تشابه الصور الدلالي", "label_en": "Image similarity (semantic)"},
    "image_hash": {"package": "PIL", "model_dir": None, "label_ar": "البصمة الإدراكية للصور", "label_en": "Perceptual image hashing"},
}

NLLB_CODES = {"ar": "arb_Arab", "ckb": "ckb_Arab", "kmr": "kmr_Latn", "en": "eng_Latn", "tr": "tur_Latn",
              "fa": "pes_Arab", "fr": "fra_Latn", "de": "deu_Latn", "es": "spa_Latn", "ru": "rus_Cyrl", "zh": "zho_Hans"}


def _model_path(name):
    return settings.models_dir / name if name else None


def gpu_info():
    if not shutil.which("nvidia-smi"):
        return {"available": False}
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout
        gpus = []
        for line in out.strip().splitlines():
            name, util, used, total = [x.strip() for x in line.split(",")]
            gpus.append({"name": name, "utilization": float(util), "memory_used_mb": float(used), "memory_total_mb": float(total)})
        return {"available": bool(gpus), "gpus": gpus}
    except Exception as e:
        return {"available": False, "error": str(e)}


def status() -> list[dict]:
    out = []
    for key, s in SERVICES.items():
        pkg_ok = True if s["package"] is None else importlib.util.find_spec(s["package"]) is not None
        mp = _model_path(s["model_dir"])
        model_ok = True if mp is None else (mp.exists() and any(mp.iterdir()))
        state = "ready" if pkg_ok and model_ok else "missing_package" if not pkg_ok else "missing_model"
        out.append({"key": key, "label_ar": s["label_ar"], "label_en": s["label_en"], "state": state,
                    "package": s["package"], "package_installed": pkg_ok,
                    "model_path": str(mp) if mp else None, "model_present": model_ok,
                    "loaded": key in _loaded, "queue": _queues.get(key, 0)})
    return out


def available(key) -> bool:
    return next(s for s in status() if s["key"] == key)["state"] == "ready"


def resources():
    p = psutil.Process()
    return {"process_rss_mb": round(p.memory_info().rss / 2**20, 1), "gpu": gpu_info()}


# ---------------- الكلام ----------------
def _whisper():
    with _lock:
        if "speech" not in _loaded:
            if not available("speech"):
                raise ServiceUnavailable("نموذج التعرّف على الكلام غير مثبت على الخادم")
            from faster_whisper import WhisperModel
            device = "cuda" if gpu_info()["available"] else "cpu"
            _loaded["speech"] = WhisperModel(str(_model_path("whisper")), device=device,
                                             compute_type="float16" if device == "cuda" else "int8")
        return _loaded["speech"]


def transcribe(audio: bytes, language: str | None = None) -> dict:
    model = _whisper()
    _queues["speech"] += 1
    fd, path = tempfile.mkstemp(dir=temp_dir(), suffix=".audio")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(audio)
        lang = {"ckb": None, "kmr": None}.get(language, language)
        segments, info = model.transcribe(path, language=lang, vad_filter=True, beam_size=5)
        text = " ".join(s.text.strip() for s in segments)
        return {"text": text, "language": info.language, "probability": round(info.language_probability, 3)}
    finally:
        _queues["speech"] -= 1
        try:
            os.remove(path)  # لا نحتفظ بالصوت
        except FileNotFoundError:
            pass


# ---------------- الترجمة ----------------
def _translator():
    with _lock:
        if "translation" not in _loaded:
            if not available("translation"):
                raise ServiceUnavailable("نموذج الترجمة غير مثبت على الخادم")
            import ctranslate2
            import sentencepiece as spm
            mp = _model_path("translation")
            device = "cuda" if gpu_info()["available"] else "cpu"
            tr = ctranslate2.Translator(str(mp), device=device)
            sp = spm.SentencePieceProcessor(model_file=str(mp / "sentencepiece.bpe.model"))
            _loaded["translation"] = (tr, sp)
        return _loaded["translation"]


def translate(text: str, source: str | None, target: str) -> dict:
    src = source or T.detect_language(text) or "en"
    if src not in NLLB_CODES or target not in NLLB_CODES:
        raise ValueError("لغة غير مدعومة")
    tr, sp = _translator()
    _queues["translation"] += 1
    try:
        t0 = time.time()
        out = []
        for para in text.split("\n"):
            if not para.strip():
                out.append("")
                continue
            toks = [NLLB_CODES[src]] + sp.encode(para, out_type=str) + ["</s>"]
            res = tr.translate_batch([toks], target_prefix=[[NLLB_CODES[target]]], beam_size=4, max_decoding_length=512)
            hyp = res[0].hypotheses[0][1:]
            out.append(sp.decode(hyp))
        return {"text": "\n".join(out), "source": src, "target": target, "ms": int((time.time() - t0) * 1000)}
    finally:
        _queues["translation"] -= 1


def detect(text: str) -> dict:
    return {"language": T.detect_language(text)}
