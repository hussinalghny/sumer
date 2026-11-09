# واجهات API الداخلية

كل الطلبات JSON. نص البحث يُرسل دائماً في جسم طلب POST، ولا يوضع في الرابط. في بيئة التطوير يوجد توثيق تفاعلي على `/api/docs` (معطّل في الإنتاج).

## العامة

| الطريقة | المسار | الجسم | الوصف |
| --- | --- | --- | --- |
| GET | `/api/public/config` | — | الاسم، الشعار، الإعلان، اللغات، الميزات المتاحة فعلاً |
| POST | `/api/search` | `{q, page?, lang?, category?, since_days?, safe?, sort?}` | نتائج مع `understood` و`did_you_mean` و`corrected` و`related` و`panel` |
| POST | `/api/suggest` | `{q}` | اقتراحات من عناوين الفهرس |
| POST | `/api/images` | `{q, page?, size?, format?, safe?}` | بحث الصور بالنص |
| POST | `/api/images/reverse` | multipart `file` | بحث عكسي (بحد أقصى 8MB، يُعالج بالذاكرة) |
| GET | `/api/images/thumb/{id}` | — | مصغّرة من خادمنا |
| POST | `/api/inspect` | `{url}` | معلومات الموقع من الفهرس فقط |
| POST | `/api/voice` | multipart `file`, `language?` | نص من الصوت، أو 503 إذا النموذج غير مثبت |
| POST | `/api/translate` | `{text, source?, target}` | ترجمة محلية، أو 503 |
| POST | `/api/detect-language` | `{q}` | كشف اللغة |
| GET | `/api/status` | — | حالة الخدمات العامة |

الأخطاء: `429 rate_limited`، `503 maintenance|disabled`، `422 invalid_request` (بدون إعادة المدخلات).

## لوحة التحكم (`/api/admin`)

المصادقة بكوكي `sumer_admin` (HttpOnly، Secure، SameSite=Strict). كل طلب يغيّر حالة يحتاج الترويسة `X-CSRF-Token`، وقيمتها من `/auth/login` أو `/auth/me`. كل مسار يفحص صلاحية محددة في الخلفية.

| المجموعة | المسارات | الصلاحية |
| --- | --- | --- |
| المصادقة | `POST auth/login` · `auth/mfa` · `auth/logout` · `GET auth/me` · `POST auth/password` · `auth/2fa/setup` · `auth/2fa/enable` | — |
| النظرة العامة | `GET overview` | dashboard.view |
| البحث | `GET/PUT search/settings` · `GET languages` · `PUT languages/{code}` · `POST search/test` · `GET/PUT search/eval-set` · `POST search/evaluate` · `GET search/quality` | search.view / manage / test |
| الزاحف | `GET crawler/status` · `POST crawler/state` · `PUT crawler/config` · `GET/POST crawler/seeds` · `DELETE crawler/seeds/{id}` · `GET domains` · `PATCH domains/{id}` · `GET crawler/jobs` · `POST crawler/jobs/retry` · `POST crawler/jobs/cancel` · `GET crawler/logs` | crawler.view / control / manage |
| الفهرس | `GET index/documents[/{id}]` · `DELETE index/documents/{id}` · `POST index/reindex-domain` · `POST index/delete-outdated` · `POST index/rebuild` · `POST index/maintenance/{refresh_terms,compute_authority}` · `GET index/duplicates` · `POST index/duplicates/purge` · `GET index/versions` · `GET index/errors` · `GET index/storage` | index.view / manage |
| الصور | `GET images/stats` · `GET images` · `POST images/retry-failed` · `POST images/duplicates/purge` | images.view / manage |
| الذكاء | `GET ai/status` · `POST ai/{key}/load` · `POST ai/{key}/unload` | ai.view / manage |
| الأمن | `GET/PUT security/settings` · `POST security/cleanup` · `GET security/events` · `GET security/sessions` · `DELETE security/sessions/{id}` · `GET security/access-history` · `GET audit` | security.* / audit.view |
| التحليلات | `GET analytics?hours=` · `POST analytics/flush` | analytics.view |
| المشرفون | `GET admins` · `POST admins` · `PATCH admins/{id}` · `POST admins/{id}/revoke-sessions` · `POST admins/{id}/reset-2fa` · `GET roles` · `PUT roles/{id}` · `GET permissions` | admins.view / manage |
| البنية | `GET infra` · `POST infra/restart` · `POST backups` | infra.view / control |
| الإعدادات | `GET/PUT settings/site` · `POST settings/logo` | settings.view / manage |
