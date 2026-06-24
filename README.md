# Moajam Almaani V2

إعادة بناء كاملة للنظام: FastAPI + OpenAI API (vector store على 9 كولكشنات قانونية) + python-docx + WordPress snippet + نظام محاسبة كامل (Chart of Accounts / Journal Entries / P&L / Balance Sheet) + فوترة تلقائية + render.yaml للنشر على Render.

## هيكل المشروع

```
moajam-almaani-v2/
├── backend/                  FastAPI app
│   ├── app/
│   │   ├── core/             config.py, security.py
│   │   ├── db/                session.py, base.py
│   │   ├── models/            SQLAlchemy: User, Client, TranslationJob, Invoice, Accounting (ChartOfAccount/JournalEntry/JournalLine)
│   │   ├── schemas/            Pydantic
│   │   ├── services/          openai_service, docx_service, file_extract_service, invoice_pdf_service, invoicing_service
│   │   ├── api/v1/             auth, clients, invoices, translations, accounting
│   │   ├── assets/fonts/       ضع هنا خط عربي TTF (مثلاً Noto Naskh Arabic) لإظهار العربي بشكل صحيح في الفواتير
│   │   └── main.py
│   ├── alembic/                migrations
│   ├── scripts/create_admin.py, scripts/seed_accounts.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── wordpress-snippet/
│   └── moajam-translation-snippet.php
├── render.yaml
└── docker-compose.yml
```

## اللي تم بناؤه (خلاصة)

1. **Backend**: FastAPI، فيه:
   - `POST /api/v1/translations` — رفع ملف (docx/pdf/txt)، استخراج النص، ترجمته عبر OpenAI (مع file_search على الـ vector stores الخاصة بالـ 9 كولكشنات القانونية)، وإنتاج ملف docx بـ python-docx (بدون LibreOffice).
   - `GET /api/v1/translations/{job_id}` و `/download` — حالة وتحميل الترجمة.
   - عند اكتمال الترجمة، لو الطلب مرتبط بعميل، يتولّد **تلقائيًا** فاتورة Draft مربوطة بالـ job.
   - `POST/GET/PATCH/DELETE /api/v1/clients` — إدارة العملاء.
   - `POST/GET/PATCH/DELETE /api/v1/invoices` — فواتير + PDF احترافي **ثنائي اللغة (عربي/إنجليزي)** بـ reportlab + تحميل. لما الفاتورة تتحدد كـ `paid`، يتولّد قيد محاسبي تلقائي (Debit Cash / Credit Revenue) لو الحسابات الافتراضية موجودة.
   - `GET/POST/DELETE /api/v1/accounting/accounts` — Chart of Accounts.
   - `GET/POST/DELETE /api/v1/accounting/journal-entries` — قيود اليومية (لازم تكون متوازنة Debit = Credit).
   - `GET /api/v1/accounting/reports/profit-and-loss?start_date=...&end_date=...` — تقرير الأرباح والخسائر.
   - `GET /api/v1/accounting/reports/balance-sheet?as_of=...` — الميزانية العمومية.
   - `POST /api/v1/auth/login` — تسجيل دخول الأدمن (JWT).
   - أمان: الترجمة محمية بـ `X-API-Key`، والمحاسبة/الفواتير محمية بـ JWT.

2. **WordPress snippet القديم** (`wordpress-snippet/moajam-translation-snippet.php`) — **متروك لأغراض تاريخية بس**، الاستخدام الفعلي دلوقتي هو الـ WordPress Plugin في بند 4.

3. **render.yaml**: Blueprint جاهز لنشر الباك إند + قاعدة بيانات Postgres على Render. **Render نفسه stateless تمامًا الآن** — مفيش Disk، ومفيش ملف بيُخزَّن على Render محليًا أصلًا (راجع بند 6).

4. **WordPress Plugin** (`wordpress-plugin/moajam-platform/`) — بديل كامل للـ snippet القديم، فيه لوحتين (العميل لا يدخل على النظام نهائيًا - المترجم هو اللي بيسجّل بيانات العميل والسعر بدلًا منه):
   - `[moajam_translator_dashboard]` — لرول WordPress اسمه "Moajam Translator"، **كل مترجم له يوزر WordPress مستقل**: يرفع الملف، يكتب اسم/بريد/تليفون العميل، يحدد السعر المتفق عليه، يتابع طلباته الشخصية فقط (مفلترة تلقائيًا باسم المستخدم بتاعه)، يشوف إشعاراته، ويحمّل الـ DOCX.
   - `[moajam_admin_dashboard]` — لكابابيليتي `moajam_access_admin_dashboard` (الأدمن تلقائيًا): ملخص تحليلي (Analytics)، إدارة المترجمين/المراجعين (Staff) مع إحصائياتهم، **كل** الطلبات من كل المترجمين (مين المترجم، مين العميل، السعر، الحالة، حالة المراجعة)، كل الفواتير، والإشعارات.
   - المفتاح السري بياخده من `wp-config.php` فقط (نفس فكرة الـ snippet القديم) عبر كلاس `Moajam_Api_Client`.
   - عشان تضيف مترجم جديد: من wp-admin → Users → Add New → الدور (Role) = "Moajam Translator".

5. **نظام ERP** (`app/models/erp.py`, `app/api/v1/erp.py`) عبر `/api/v1/erp/*` (محمي بـ X-API-Key):
   - **Staff** — سجل ERP لكل مترجم/مراجع (مرتبط بـ `username` بتاع WordPress)، فيه نسبة عمولة، وإحصائيات تلقائية (عدد الطلبات، المكتمل، الإيراد).
   - **Projects** — تجميع أكتر من طلب ترجمة تحت مشروع واحد لعميل معيّن.
   - **Review workflow** — `PATCH /erp/jobs/{id}/review` لتعيين مراجع وتحديد حالة المراجعة (pending/approved/rejected)، وبيولّد إشعار تلقائي للمراجع وللمترجم.
   - **Analytics** — `GET /erp/analytics/summary` تجميع الطلبات/الإيراد لكل مترجم وكل عميل، بفلترة بتاريخ.
   - **Notifications** — إشعارات تلقائية عند اكتمال/فشل الترجمة وعند دفع الفاتورة، تظهر في لوحتي المترجم والأدمن.

6. **Render stateless 100%** — مفيش ملف واحد بيتخزن على Render:
   - المترجم برفع الملف من لوحته → البلجن يحفظه فورًا في **WordPress Media Library** (`media_handle_upload`) → يبعت للباك إند **رابط الملف فقط** (`source_file_url`)، مش الملف نفسه.
   - الباك إند بينزّل الملف من الرابط في الذاكرة/ملف مؤقت، يترجم، يبني DOCX في ملف مؤقت، **يرفعه فورًا على WordPress** عبر REST endpoint جديد `/wp-json/moajam/v1/media` (محمي بنفس `X-API-Key`)، وبعدين **يمسح كل الملفات المؤقتة**. الناتج النهائي بيتخزن في `job.output_url` (رابط WordPress دائم).
   - نفس المنطق على فواتير PDF: `pdf_url` بدل `pdf_path`.
   - لو عملت `redeploy` على Render، مفيش حاجة تضيع لأن مفيش ملف أصلًا على Render.
   - الملف الجديد `wordpress-plugin/moajam-platform/includes/rest-media.php` هو المسؤول عن استقبال الملفات من الباك إند وحفظها في Media Library.

7. **نظام RAG على `backend/knowledge/`** (`app/services/knowledge_service.py`):
   - بيقرا كل ملف PDF/DOCX/TXT تحت `backend/knowledge/` (فيها فعلاً عينات لكل الكولكشنات: `A_Banking_Financial.pdf`... `I_Translator_Affairs_Internal.pdf`، وملفات عامة زي `LETTERHEAD_MASTER.pdf` و `01_ALL_IN_ONE_KNOWLEDGE_MASTER_RULES.txt`).
   - **تصنيف تلقائي للكولكشن**: من اسم الملف لو مطابق لكود كولكشن، وإلا بمطابقة كلمات مفتاحية، والملفات العامة (master rules / letterhead / override) بتتعلّم `GLOBAL` وتتضاف لكل سياق بحث.
   - **Embeddings index**: `python -m scripts.build_knowledge_index` يقسّم كل ملف لقطع نصية، يعمل embeddings بـ OpenAI (`text-embedding-3-small`)، ويخزنهم في `backend/knowledge/.knowledge_index.json` (غير متتبّع في git، ومفيش بناء أوتوماتيكي وقت تشغيل السيرفر لتجنّب تكلفة/تأخير عند كل cold start).
   - **وقت كل ترجمة جديدة**: `openai_service.translate_text` بينده على `route_collection()` (تصنيف بـ OpenAI + fallback كلمات مفتاحية) ثم `retrieve_context()` (أقرب عيّنات بالـ cosine similarity) ويحقن النتيجة كـ `collection_context` في `get_translation_prompt()` من `translation_prompt.py` — يعني الترجمة دلوقتي مبنية على نفس منطق الـ Custom GPT (system prompt + sample context + النص الأصلي).

---

## الخطوات المطلوبة منك بالتفصيل

### 1. اعمل API Key من OpenAI + Vector Stores
- روح على https://platform.openai.com/api-keys وخد مفتاح API.
- اعمل الـ 9 Vector Stores من https://platform.openai.com/storage/vector_stores (واحدة لكل كولكشن قانوني)، وارفع المستندات المرجعية لكل واحدة.
- خد الـ IDs (شكلها `vs_...`) وحطهم مفصولين بفاصلة في `OPENAI_VECTOR_STORE_IDS`.

### 2. ضيف خط عربي للفواتير (مهم)
- نزّل خط TTF عربي (مثلاً [Noto Naskh Arabic](https://fonts.google.com/noto/specimen/Noto+Naskh+Arabic)) وحطه في:
  `backend/app/assets/fonts/NotoNaskhArabic-Regular.ttf`
- من غير الخط ده، النص العربي في PDF الفاتورة هيظهر بحروف Helvetica غير صحيحة.

### 3. النشر على Render (الأسهل: Blueprint)
- روح على https://dashboard.render.com → New → Blueprint → اربط GitHub repo `moajam-v2`.
- Render هيقرا `render.yaml` تلقائيًا وهيجهز: قاعدة بيانات Postgres + خدمة الباك إند + Disk دائم.
- بعد ما يخلص، روح على الخدمة → Environment وحدد القيم المطلوبة يدويًا (مُعلّمة `sync: false` في render.yaml):
  - `OPENAI_API_KEY`
  - `OPENAI_VECTOR_STORE_IDS`
  - (اختياري) `PAYMOB_API_KEY`, `PAYMOB_INTEGRATION_ID`
- `SECRET_KEY` و `API_KEY` بيتولّدوا أوتوماتيك (`generateValue: true`) — خد قيمة `API_KEY` بعد التوليد وحطها في WordPress.

### 4. أول Migration + أول مستخدم أدمن + Chart of Accounts + RAG index
من Render Shell (أو محليًا بـ docker compose):
```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
python -m scripts.create_admin admin "كلمة-سر-قوية"
python -m scripts.seed_accounts
python -m scripts.build_knowledge_index
```
آخر أمر (`build_knowledge_index`) لازم تعيد تشغيله لو ضفت/عدّلت أي ملف في `backend/knowledge/`.

### 5. دومين + SSL
Render بيوفر دومين `xxx.onrender.com` بشهادة SSL تلقائي. لو عايز `api.moajamalmaani.com`، ضيفه من Render → Settings → Custom Domain، ووجّه CNAME من عندك.

### 6. فعّل WordPress Plugin (مش الـ snippet القديم)
في `wp-config.php`:
```php
define('MOAJAM_API_BASE_URL', 'https://api.moajamalmaani.com');
define('MOAJAM_API_KEY', 'القيمة-اللي-أخدتها-من-Render-Environment');
```
ارفع مجلد `wordpress-plugin/moajam-platform` إلى `wp-content/plugins/` وفعّله من wp-admin → Plugins. ده هيسجّل تلقائيًا REST endpoint جديد (`/wp-json/moajam/v1/media`) اللي الباك إند يستخدمه لرفع الملفات المترجمة، فمحتاج كمان تضيف على الباك إند في Render:
```
WP_BASE_URL=https://moajamalmaani.com
```
(موجودة في `render.yaml` لكن لو الدومين اختلف لازم تحدّثها).

### 7. اختبر الـ Flow كامل
- رفّع ملف docx تجريبي من الصفحة، شوف الترجمة، نزّل الناتج.
- اعمل عميل + فاتورة من `/api/v1/clients` و `/api/v1/invoices`، نزّل PDF واتأكد إن العربي ظاهر صحيح.
- حدّث حالة فاتورة لـ `paid` وشيك إن قيد اليومية اتعمل في `/api/v1/accounting/journal-entries`.

---

## ملاحظات مهمة

- النظام بيعالج الترجمة بـ `BackgroundTasks` المدمجة في FastAPI. لو الحجم زاد كتير، الخطوة التالية هي Celery + Redis.
- `Base.metadata.create_all` في `main.py` بيعمل الجداول أول مرة لو مفيش migrations — الأفضل دايمًا `alembic upgrade head` في الإنتاج.
- ملف `.env` لازم يفضل خارج git (موجود في `.gitignore` بالفعل).
- التوكنز (GitHub، OpenAI، إلخ) لازم تتحط كـ environment variables فقط، ومتتكتبش في أي ملف بيترفع على git.
