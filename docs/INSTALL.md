# التثبيت والنشر

## المتطلبات

| المرحلة | الخوادم | المعالج والذاكرة | التخزين |
| --- | --- | --- | --- |
| تجريبي (حتى مليون صفحة) | خادم واحد | 8 أنوية، 32GB | SSD بسعة 500GB |
| المرحلة الأولى (عشرات الملايين) | 6 إلى 8 | 16 نواة، 64 إلى 128GB لكل خادم | NVMe |
| خدمات الذكاء (اختياري) | خادم GPU | 24GB VRAM أو أكثر لـ Whisper large وNLLB | 50GB للنماذج |

البرمجيات: Linux وDocker 24 أو أحدث وDocker Compose. PostgreSQL 16 وRedis 7 تُشغَّل داخل Compose.

## النشر بـ Docker Compose

```bash
git clone <repo> sumer && cd sumer
cp .env.example .env
# ولّد قيماً عشوائية طويلة:
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # SUMER_APP_SECRET
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # SUMER_BACKUP_KEY (احفظه خارج الخادم)
mkdir -p deploy/certs   # ضع fullchain.pem وprivkey.pem (Let's Encrypt أو جهة عراقية)
docker compose up -d --build
docker compose run --rm api python -m sumer create-admin --email admin@your.iq --name "المشرف"
```

ثم افتح `https://your-domain/admin` وسجّل الدخول، وفعّل التحقق بخطوتين من «حسابي»، وأضف روابط البداية من «الزاحف».

ملاحظة: ملفات Docker كُتبت حسب المواصفات، لكنها لم تُشغّل في بيئة التطوير لعدم توفر Docker فيها. شغّلها أولاً على خادم اختبار.

## بدون Docker (systemd)

```bash
cd backend && python3 -m venv /opt/sumer/venv && /opt/sumer/venv/bin/pip install -r requirements.txt
# ‏/etc/sumer.env يحتوي متغيرات .env نفسها + SUMER_DATABASE_URL وSUMER_REDIS_URL
```
خدمات مقترحة: `sumer-api` (`python -m sumer api --workers 4`)، و`sumer-worker@N` (`python -m sumer worker`)، مع `StandardOutput=null` حتى لا تُحفظ مخرجات في journald.

## التوسّع
- **العمّال:** شغّل أي عدد من `worker` على أي عدد من الخوادم. الطابور في PostgreSQL يستخدم `FOR UPDATE SKIP LOCKED`، فلا تتكرر المهام بين العمّال.
- **الواجهة البرمجية:** عدّة نسخ خلف nginx، لأنها بلا حالة.
- **الفهرس:** فهرس GIN على PostgreSQL يكفي لعشرات الملايين من الصفحات. بعد ذلك، أضف نسخ قراءة (read replicas) للبحث. كل الاسترجاع معزول في `search._retrieve`، فالانتقال إلى OpenSearch أو Lucene لاحقاً لا يغيّر باقي النظام.

## خدمات الذكاء المحلية (اختياري)

```bash
pip install -r backend/requirements-ai.txt
# الكلام: نموذج faster-whisper (صيغة CTranslate2) في models/whisper/
# الترجمة: حوّل NLLB-200 إلى CTranslate2 في models/translation/ مع sentencepiece.bpe.model
ct2-transformers-converter --model facebook/nllb-200-distilled-600M --output_dir models/translation
```
النماذج تُنزّل مرة واحدة وقت التثبيت. بعدها لا يتصل النظام بأي جهة خارجية. صفحة «خدمات الذكاء» في لوحة التحكم تعرض حالة كل خدمة.

## النسخ الاحتياطي والاستعادة
- من لوحة التحكم: البنية التحتية ← «نسخة احتياطية الآن» (pg_dump مشفّر بـ AES-256-GCM في `/data/backups`).
- من سطر الأوامر: `python -m sumer backup`
- الاستعادة متاحة من سطر الأوامر فقط، وبتأكيد صريح: `python -m sumer restore FILE --yes`

## الصيانة الدورية (تلقائية)
العامل يجدول تلقائياً: إعادة الزحف حسب تكرار كل نطاق، وتحديث قاموس المصطلحات كل 10 دقائق، وحساب سلطة النطاقات يومياً، وتطبيق سياسات الاحتفاظ كل ساعة.
