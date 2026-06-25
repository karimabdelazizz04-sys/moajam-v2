# Moajam Translation Platform

Plugin مستقل وبسيط لطلب الترجمة من أي صفحة في WordPress، بدون الحاجة لتسجيل دخول
أو أدوار مستخدمين - العميل بيتعرّف بالإيميل بس، مطابق لنفس فكرة "العميل ميسجلش
دخول" في الباك إند. لو محتاج لوحات أدمين/مترجم/ERP كاملة، استخدم بلجن
`wordpress-plugin/moajam-platform/` بدل ده.

## التثبيت

1. ارفع مجلد `moajam-translation/` كامل إلى `wp-content/plugins/`
2. فعّله من **wp-admin → Plugins**
3. ضيف في `wp-config.php`:
   ```php
   define('MOAJAM_API_BASE_URL', 'https://moajam-api.onrender.com');
   define('MOAJAM_API_KEY', 'نفس X-API-Key بتاع الباك إند');
   ```
4. ضيف الـ shortcode `[moajam_translate_form]` لأي صفحة أو بوست

## المميزات

- فورم رفع ملف (docx/pdf/txt) + بيانات العميل (اسم/إيميل/تليفون) + اللغة المطلوبة
- الملف بيتحفظ في WordPress Media Library مباشرة (الباك إند مايستقبلش أي bytes، رابط بس)
- تتبّع تلقائي لحالة الطلب بعد الإرسال (polling كل 5 ثواني لحد ما يخلص أو يفشل)
- فورم منفصل لتتبّع أي طلب قديم برقم الـ Job ID
- زرار تحميل تلقائي يظهر لما الترجمة تخلص

## الـ API المستخدم

| Method | Endpoint                              | الغرض                  |
|--------|----------------------------------------|-------------------------|
| POST   | `/api/v1/translations`                 | إنشاء طلب ترجمة جديد   |
| GET    | `/api/v1/translations/{id}`            | حالة الطلب              |
| GET    | `/api/v1/translations/{id}/download`  | تحميل الناتج (redirect لرابط WordPress) |

## الملفات

```
moajam-translation/
├── moajam-translation.php   # الملف الرئيسي: shortcode + AJAX handlers
├── class-api-client.php     # API client (لـ translations بس)
├── templates/form.php       # HTML الفورم
├── assets/js/moajam-translation.js
├── assets/css/moajam-translation.css
└── README.md
```
