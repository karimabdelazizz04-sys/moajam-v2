# HANDOFF — Moajam V2 Legal Translation Platform

> ملخّص العمل ليوم 2026-06-25 / 2026-06-26
> الغرض: تسليم الحالة الكاملة للمشروع عشان أي حد (أو جلسة جديدة) يكمل من نفس النقطة.

---

## 1) المشروع

- **الاسم:** Moajam Almaani / معجم المعاني — منصّة ترجمة قانونية (Legal Translation Platform) V2.
- **الموقع العام:** https://moajamalmaani.com (WordPress).
- **الـ Backend API (Production):** https://moajam-api.onrender.com (FastAPI على Render).
- **الترجمة:** تتم بالـ backend عبر Anthropic Claude (`claude-sonnet-4-6`). مفتاح Anthropic موجود على الخادم فقط (`backend/.env`) — لا يظهر إطلاقًا في المتصفح.
- **تخزين الملفات:** WordPress Media Library هو المخزن الوحيد الدائم. خادم Render **stateless** — لا يخزّن ملفات على قرصه؛ يستقبل URL، يترجم، ويرفع الناتج لـ WordPress.

### معماريّة الـ backend (مهم)
ليس ملف `app.py` واحد. هو تطبيق FastAPI **منظّم**:
- `app/main.py` — نقطة الدخول.
- `app/api/v1/*.py` — الـ routers.
- `app/core/config.py` — إعدادات pydantic Settings.
- `app/services/*.py` — منطق الخدمات (WordPress, Claude, docx, ...).

### مخططات المصادقة (Authentication)
- **`X-API-Key` header** → لمسارات `translations` و `portal`.
- **OAuth2 / Bearer token** → لمسارات `clients` و `invoices` و `accounting`.
- مسار الحسابات الصحيح: `/api/v1/accounting/accounts` (وليس `/api/v1/accounts`).

---

## 2) اللي اتعمل النهاردة

### أ) الـ Backend — endpoint رفع ملفات جديد
الهدف: المتصفح يرفع الملف للـ backend، والـ backend يرفعه لـ WordPress بكلمة مرور تبقى **على الخادم فقط** (أأمن من الرفع المباشر من المتصفح).

تدفّق الرفع الآمن: **المتصفح → الـ Backend → WordPress**.

التعديلات:
- **`app/api/v1/translations.py`**
  - أضيف endpoint جديد: `POST /api/v1/translations/upload` (status 201).
  - يستقبل `UploadFile`، يتحقق من الامتداد (`.docx`, `.pdf`, `.txt`) والحجم (`MAX_UPLOAD_SIZE_MB`)، يرفعه لـ WordPress، ويُرجع `{"url", "filename", "id"}`.
  - محمي تلقائيًا بـ `X-API-Key` (الـ router عليه `dependencies=[Depends(verify_api_key)]`).
- **`app/services/wordpress_service.py`**
  - أضيفت دالة `upload_source_to_wordpress(file_bytes, filename, content_type)` ترفع عبر مسار WordPress الأساسي `/wp-json/wp/v2/media` بـ Basic Auth (Application Password).
  - تُرجع `{"id", "url"}` (الـ url = `source_url` من رد WordPress).
- **`app/core/config.py`**
  - أضيف `WP_USER` و `WP_APP_PASSWORD`.
- **`.env.example`**
  - أضيف `WP_USER=CHANGE_ME` و `WP_APP_PASSWORD=CHANGE_ME` (placeholders فقط — لا أسرار حقيقية).

### ب) الـ Frontend — ربط الرفع بالـ backend
- **`admin-dashboard-FINAL.html`**: دالة `uploadFileToWordPress()` بقت ترفع عبر `POST /api/v1/translations/upload` بدل WordPress مباشرة. كلمة مرور WordPress لم تعد تُلمس في المتصفح.
- **`client-portal-FINAL.html`**: نفس المنطق — يرفع للـ backend الأول، ياخد الـ URL، ويبعته للـ backend عند إنشاء مهمة الترجمة.
- الملفات vanilla HTML/CSS/JS، RTL عربي، self-contained. بيانات الاعتماد تتخزّن في `localStorage` عبر لوحة الإعدادات ⚙️ — لا تُكتب أبدًا داخل الـ HTML.

### ج) التحقق (verification)
- كل الـ JS: `node --check` → **JS OK** للملفين.
- كل الـ Python المعدّل: `py_compile` → **PYTHON COMPILE OK**.

### د) الـ Deploy
- الـ backend منشور بالفعل على Render: https://moajam-api.onrender.com
- التعديلات الجديدة (endpoint الرفع) **معمولة في working tree محليًا فقط** — لسه **مش معمولها commit/push** ومن ثَمّ لسه **مش موجودة على Render**.

---

## 3) المشكلة الحالية

رفع الملفات عبر endpoint `/api/v1/translations/upload`:
- الكود متكتب ومتحقّق منه محليًا (compile OK).
- **لكنه لسه مش deployed على Render** لأنه محتاج commit + push للـ repo اللي Render بيسحب منه.

---

## 4) الخطوة الجاية بالظبط

**نتأكد إن `/api/v1/translations/upload` موجود وشغّال على Render.**

1. اعمل deploy للتعديلات (commit + push للـ branch اللي Render بيراقبه، أو Manual Deploy من لوحة Render). **لا تعمل push إلا لما تطلب ذلك صراحةً.**
2. ضيف متغيّرات البيئة على Render (Environment):
   ```
   WP_USER = <اسم مستخدم WordPress>
   WP_APP_PASSWORD = <App Password الجديد بعد التدوير>
   ```
3. تأكّد إن الـ endpoint ظاهر في الـ OpenAPI spec:
   - افتح: https://moajam-api.onrender.com/docs
   - أو: https://moajam-api.onrender.com/openapi.json — ودوّر على `/api/v1/translations/upload`.
4. اختبار سريع (يحتاج `X-API-Key` صحيح):
   ```bash
   curl -X POST https://moajam-api.onrender.com/api/v1/translations/upload \
     -H "X-API-Key: <API_KEY>" \
     -F "file=@test.docx"
   ```
   المتوقّع: `201` مع JSON فيه `url` و `filename` و `id`.
5. ارفع ملفّي الـ HTML على موقع WordPress (cPanel → File Manager → `public_html`) وافتح:
   - https://moajamalmaani.com/admin-dashboard-FINAL.html
   - https://moajamalmaani.com/client-portal-FINAL.html

---

## 5) كل الملفات ومساراتها

### Backend — `C:\Users\Acer\moajam-almaani-v2\backend\`
| الملف | الحالة | الوصف |
|------|--------|-------|
| `app/api/v1/translations.py` | معدّل | أضيف endpoint `POST /upload` |
| `app/services/wordpress_service.py` | معدّل | أضيفت `upload_source_to_wordpress()` |
| `app/core/config.py` | معدّل | أضيف `WP_USER`, `WP_APP_PASSWORD` |
| `.env.example` | معدّل | أضيف placeholders للـ WP creds |
| `.env` | **لا يُلمس** | فيه أسرار حقيقية، gitignored — لا تقرأه/تكتبه/ترفعه |
| `app/main.py` | كما هو | نقطة دخول FastAPI |

### Frontend — `C:\Users\Acer\frontend\`
| الملف | الحالة | الوصف |
|------|--------|-------|
| `admin-dashboard-FINAL.html` | **النسخة النهائية** | لوحة الأدمن، رفع عبر الـ backend |
| `client-portal-FINAL.html` | **النسخة النهائية** | بوابة العميل، رفع عبر الـ backend |
| `admin-dashboard-fixed.html` | نسخة سابقة | login تجريبي + لوحة إعدادات |
| `client-portal-fixed.html` | نسخة سابقة | بوابة عميل بالإيميل |
| `dashboard-production.html` | نسخة سابقة | أول نسخة API حقيقي |
| `dashboard.html` | mockup | النسخة الثابتة الأولى |

> **النسخ المعتمدة للرفع = ملفّي `*-FINAL.html` فقط.**

---

## 6) الحاجات الأمنية ⚠️ (الأهم)

### مفاتيح مكشوفة — لازم تتعمل لها revoke فورًا
خلال الشغل اتشاركت سرّين حقيقيين في المحادثة، وأي سرّ بيظهر في محادثة يُعتبر **مكشوفًا**:

1. **WordPress Application Password** (للمستخدم `KarimAbdelazizz`)
   - **revoke:** WordPress Admin → Users → Profile → Application Passwords → Revoke القديم.
   - أنشئ واحدًا جديدًا → حُطّه في `WP_APP_PASSWORD` على Render فقط.

2. **Anthropic API Key** (`sk-ant-...`)
   - **revoke:** https://console.anthropic.com/settings/keys → Revoke القديم → Create Key جديد.
   - حدّث `ANTHROPIC_API_KEY` على Render فقط.

### قواعد أمان ثابتة (لازم تستمر)
- لا تُكتب المفاتيح المكشوفة (Anthropic أو WordPress) في أي ملف أو commit — تم استخدام `CHANGE_ME` placeholders فقط.
- لا يُوضع أي سرّ/مفتاح داخل الـ HTML — بيانات الاعتماد في `localStorage` عبر لوحة الإعدادات ⚙️، أو في `backend/.env` فقط.
- لا commit/push لـ git إلا بطلب صريح.
- `backend/.env` فيه أسرار حقيقية وهو gitignored — لا يُقرأ/يُكشف/يُكتب فوقه.

---

## 7) قيود لا أقدر أتجاوزها (محتاجة تدخّلك)
- **لا أقدر أرفع ملفات HTML على moajamalmaani.com** — مفيش وصول FTP/SSH/لوحة تحكم. الرفع يدوي عبر cPanel.
- **لا أقدر أفتح الروابط الحيّة للتأكد من التحميل** — مفيش متصفح/وصول للموقع.
- **لا أقدر أعمل deploy على Render بنفسي** — محتاج commit/push (بطلب صريح) أو Manual Deploy منك.
