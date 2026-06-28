# HANDOFF — Moajam V2 Legal Translation Platform

> آخر تحديث: 2026-06-28
> الغرض: تسليم الحالة الكاملة للمشروع عشان أي حد (أو جلسة جديدة) يكمل من نفس النقطة.

---

## 1) المشروع

- **الاسم:** Moajam Almaani / معجم المعاني — منصّة ترجمة قانونية (Legal Translation Platform) V2.
- **الموقع العام:** https://moajamalmaani.com (WordPress).
- **الـ Backend API (Production):** https://moajam-api.onrender.com (FastAPI على Render — Docker).
- **الـ Git repo:** https://github.com/karimabdelazizz04-sys/moajam-v2.git (branch `main`، Render بيعمل auto-deploy منه).
- **الترجمة:** تتم بالـ backend عبر Anthropic Claude (`claude-sonnet-4-6`). مفتاح Anthropic على الخادم فقط (`backend/.env`) — لا يظهر في المتصفح.
- **تخزين الملفات:** WordPress Media Library هو المخزن الوحيد الدائم. خادم Render **stateless**.
- **الموارد:** Render حاليًا على خطة بـ **2GB RAM** (مش 512MB زي الأول).

### معماريّة الـ backend
تطبيق FastAPI منظّم: `app/main.py` (دخول + CORS) · `app/api/v1/*.py` (routers) · `app/core/config.py` (pydantic Settings) · `app/services/*.py` (WordPress, Claude, docx, knowledge, file_extract...).

### المصادقة
- **`X-API-Key` header** → مسارات `translations` و `portal`.
- **OAuth2 / Bearer token** → مسارات `clients` و `invoices` و `accounting`.
- مسار الحسابات: `/api/v1/accounting/accounts`.

---

## 2) الحالة الحالية ✅ — الـ pipeline كامل بيشتغل

تمّت ترجمة كاملة فعلية بنجاح end-to-end (الملف الناتج اترفع على WordPress:
`translated_Cargo-2023-2024-1-3.docx`). تدفّق الـ job:
تنزيل المصدر → استخراج نص (مع OCR للمصوّر) → ترجمة Claude → بناء DOCX → رفع لـ WordPress → `DONE`.

---

## 3) اللي اتعمل في جلسة 2026-06-27/28 (كله committed + pushed على `main`)

| commit | الوصف |
|--------|-------|
| `ff2effe` | OCR fallback (Claude Vision) للـ PDF المصوّر + حارس النص الفاضي |
| `b6207fa` | endpoint `POST /translations/{id}/retry` لإعادة تشغيل job عالق + تقليل ذاكرة الـ OCR (DPI 120، صفحة-صفحة، gc، حد 10 صفحات) |
| `732440b` | timeout 5 دقائق على نداءات Claude + رفع WordPress (`APITimeoutError`/`requests.Timeout` → FAILED برسالة ودّية) |
| `89fd82a` | logs تشخيصية لرفع WordPress (endpoint/user/طول الباسورد/status — بدون كشف أسرار) |
| `067ebfb` | **إصلاح الـ jobs العالقة على PROCESSING**: `_run_translation_job` بيفتح DB session خاصّة (`SessionLocal`) بدل session الـ request المقفولة + logs مرحلية |
| `aec397a` | رفع الملف الناتج عبر core route `wp/v2/media` + Basic Auth (بدل plugin route + X-API-Key) |
| `d347e42` | ربط ملفات الـ knowledge + الـ SYSTEM_PROMPT بالترجمة (`_resolve_collection` أولوية لـ legal_domain، استرجاع من الـ index، رسالة منظّمة، max_tokens 8192) |
| `0649818` | قاعدة: لو مفيش لاي-اوت مطابق في الـ knowledge → حافظ على شكل المستند الأصلي (في التعليمة + الـ SYSTEM_PROMPT) |

### ملاحظة مهمة عن مسارَي رفع WordPress
- `upload_source_to_wordpress` (المصدر) و `upload_media_to_wordpress` (الناتج) **الاتنين دلوقتي** بيستخدموا core route `wp/v2/media` + **Basic Auth** (`WP_USER`/`WP_APP_PASSWORD`). المسار ده مثبت إنه شغّال (رجّع 201). تم التخلّي عن plugin route لأنه كان بيرجّع 404.

---

## 4) الفرونت (ملفات محلية — مش في الـ git repo)

**المكان:** `C:\Users\Acer\frontend\` — أهم نسختين: `admin-dashboard.html` و `client-portal.html`.
**اترفعوا يدويًا على الموقع عبر cPanel** (مفيش FTP/SSH).

تعديلات الجلسة على الملفين (محليًا):
1. **شيل أي `/` زيادة من الـ base URL** قبل بناء الطلب (`state.baseUrl.replace(/\/+$/, '')`) — كان بيسبّب سلاش مزدوج → 404.
2. **زر التحميل بيفتح `output_url` مباشرةً** (الرابط العام لملف WordPress) بدل ما ينده `/download` (اللي بيعمل redirect عابر للأصول → CORS error).
3. (معالجة `X-API-Key` كانت سليمة أصلًا.)

> ⚠️ **مطلوب:** رفع `admin-dashboard.html` + `client-portal.html` المحدّثين على cPanel ثم `Ctrl+F5`، عشان التعديلات دي تفعّل على الموقع الحي.

### سلسلة أخطاء الواجهة اللي اتحلّت (للتوثيق)
`missing X-API-Key` (نسخة فرونت قديمة مرفوعة) → `شبكة/CORS` (base URL غلط في localStorage) → `404` (سلاش مزدوج) → `CORS عند التحميل` (redirect) → ✅ اتحلّت كلها. الباكند والـ CORS سليمين (متأكَّد بالاختبار المباشر).

---

## 5) كيف بتشتغل الترجمة + الـ knowledge (مفحوص فعليًا)

- `claude_service.translate_text()`: يختار collection (`_resolve_collection`) → يجيب `knowledge_context` عبر `retrieve_context()` (أعلى 6 chunks بتطابق الكلمات + كل قطع GLOBAL، سقف 60K حرف) → `system=SYSTEM_PROMPT` كامل → رسالة user منظّمة (KNOWLEDGE + SOURCE + تعليمات).
- الـ knowledge مخزّن مسبقًا في `backend/knowledge/.knowledge_index.json` (**2415 chunk**، keys: `file/collection/text`). مفيش إعادة قراءة للـ PDFات الضخمة (7-100MB) وقت الترجمة.
- إعادة بناء الـ index بعد أي تغيير في `backend/knowledge/`: عبر `knowledge_service.build_index()`.

### ⚠️ مشاكل جودة الـ knowledge (مكتشفة، لسه محتاجة حل)
1. **استخراج النص من الـ PDF متلخبط (garbled)** للعربي (`pypdf`) — النص المُغذّى لـ Claude مشوّه.
2. **محتوى F_Tenancy ضعيف**: غالبيته إيميلات/وكالة، مش نماذج عقود نضيفة (19 chunk فقط).
3. **توزيع غير متوازن**: H_Medical=1464، C=318، B=266 ... بينما E_Government=6، D_POA=11، F_Tenancy=19.

---

## 6) الخطوات الجاية (Next steps)

1. **[واجهة]** رفع `admin-dashboard.html` + `client-portal.html` المحدّثين على cPanel ثم `Ctrl+F5`، وتجربة زر "تحميل".
2. **[جودة]** تحسين استخراج نص الـ knowledge: تجربة `pdfplumber` بدل `pypdf` و/أو OCR للـ PDFات المصوّرة، ثم إعادة بناء الـ index. (اقتراح: نبدأ باختبار مقارنة على `F_Tenancy_Real_Estate.pdf`.)
3. **[جودة]** إضافة نماذج عقود/مستندات نضيفة فعلية لكل collection (خصوصًا الضعيفة).
4. **[اختياري]** تحويل خانة `legal_domain` في الفرونت لقائمة منسدلة بالـ 9 أكواد عشان legal_domain يطابق دايمًا.
5. **[تشغيل]** الـ jobs العالقة القديمة (قبل commit `067ebfb`) تُعاد بـ `POST /api/v1/translations/{id}/retry` (+ X-API-Key).

---

## 7) الأمان ⚠️ (قائم — مهم)

- **مفاتيح مكشوفة لازم revoke:** WordPress Application Password (للمستخدم `KarimAbdelazizz`) + Anthropic API Key — اتشاركوا في محادثات سابقة فيُعتبروا مكشوفين. دوّرهم، وحدّث القيم على **Render Environment فقط**.
- لا تُكتب أي أسرار في الكود/commits — `CHANGE_ME` placeholders فقط في `.env.example`.
- لا أسرار داخل الـ HTML — بيانات الاعتماد في `localStorage` عبر ⚙️ أو `backend/.env` فقط.
- `backend/.env` فيه أسرار حقيقية وهو gitignored — لا يُقرأ/يُكشف/يُكتب فوقه.

### متغيّرات بيئة Render المطلوبة
`ANTHROPIC_API_KEY` · `SECRET_KEY` · `API_KEY` · `DATABASE_URL` · `WP_BASE_URL` · `WP_USER` · `WP_APP_PASSWORD` · `CORS_ORIGINS`.

---

## 8) قيود تحتاج تدخّل المستخدم (لا أقدر أعملها)

- رفع ملفات HTML على moajamalmaani.com — يدوي عبر cPanel (مفيش FTP/SSH).
- إعداد متغيّرات البيئة / Manual Deploy على Render.
- revoke/تدوير المفاتيح المكشوفة.
