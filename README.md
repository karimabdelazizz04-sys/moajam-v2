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

2. **WordPress snippet** (`wordpress-snippet/moajam-translation-snippet.php`): شورت كود `[moajam_translate_form]` لرفع ملف + متابعة حالة + تحميل، عبر admin-ajax.php (المفتاح يفضل في wp-config.php فقط).

3. **render.yaml**: Blueprint جاهز لنشر الباك إند + قاعدة بيانات Postgres على Render، مع Disk دائم لـ `storage/` (الرفعات والمخرجات والفواتير ما تضيعش بين الـ deployments).

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

### 4. أول Migration + أول مستخدم أدمن + Chart of Accounts
من Render Shell (أو محليًا بـ docker compose):
```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
python -m scripts.create_admin admin "كلمة-سر-قوية"
python -m scripts.seed_accounts
```

### 5. دومين + SSL
Render بيوفر دومين `xxx.onrender.com` بشهادة SSL تلقائي. لو عايز `api.moajamalmaani.com`، ضيفه من Render → Settings → Custom Domain، ووجّه CNAME من عندك.

### 6. فعّل الـ WordPress Snippet
في `wp-config.php`:
```php
define('MOAJAM_API_BASE_URL', 'https://api.moajamalmaani.com');
define('MOAJAM_API_KEY', 'القيمة-اللي-أخدتها-من-Render-Environment');
```
ثم بلجن **Code Snippets** → snippet جديد بمحتوى `wordpress-snippet/moajam-translation-snippet.php` → فعّله، وضيف `[moajam_translate_form]` في أي صفحة.

### 7. اختبر الـ Flow كامل
- رفّع ملف docx تجريبي من الصفحة، شوف الترجمة، نزّل الناتج.
- اعمل عميل + فاتورة من `/api/v1/clients` و `/api/v1/invoices`، نزّل PDF واتأكد إن العربي ظاهر صحيح.
- حدّث حالة فاتورة لـ `paid` وشيك إن قيد اليومية اتعمل في `/api/v1/accounting/journal-entries`.

---

## الباقي المؤجَّل لجلسة تالية (حسب الأولوية اللي تم الاتفاق عليها)

- WordPress Plugin كامل بثلاث Dashboards (مترجم / عميل / أدمن) — يستهلك الـ API الحالي.
- نظام ERP (إدارة مترجمين ومراجعين، Project management، Analytics، Notifications).

## ملاحظات مهمة

- النظام بيعالج الترجمة بـ `BackgroundTasks` المدمجة في FastAPI. لو الحجم زاد كتير، الخطوة التالية هي Celery + Redis.
- `Base.metadata.create_all` في `main.py` بيعمل الجداول أول مرة لو مفيش migrations — الأفضل دايمًا `alembic upgrade head` في الإنتاج.
- ملف `.env` لازم يفضل خارج git (موجود في `.gitignore` بالفعل).
- التوكنز (GitHub، OpenAI، إلخ) لازم تتحط كـ environment variables فقط، ومتتكتبش في أي ملف بيترفع على git.
