<?php
if (!defined('ABSPATH')) {
    exit;
}
?>
<div class="moajam-translate-widget" dir="rtl">

    <section class="moajam-translate-card" id="moajam-translate-upload-section">
        <h3><?php esc_html_e('اطلب ترجمة جديدة', 'moajam-translation'); ?></h3>

        <form id="moajam-translate-form" enctype="multipart/form-data">
            <div class="moajam-translate-field">
                <label for="moajam-translate-file"><?php esc_html_e('الملف (docx, pdf, txt)', 'moajam-translation'); ?></label>
                <input type="file" id="moajam-translate-file" name="file" accept=".docx,.pdf,.txt" required>
            </div>

            <div class="moajam-translate-field">
                <label for="moajam-translate-target-language"><?php esc_html_e('اللغة المطلوبة', 'moajam-translation'); ?></label>
                <select id="moajam-translate-target-language" name="target_language">
                    <option value="Arabic"><?php esc_html_e('العربية', 'moajam-translation'); ?></option>
                    <option value="English"><?php esc_html_e('الإنجليزية', 'moajam-translation'); ?></option>
                </select>
            </div>

            <div class="moajam-translate-field">
                <label for="moajam-translate-legal-domain"><?php esc_html_e('نوع المستند (اختياري)', 'moajam-translation'); ?></label>
                <input type="text" id="moajam-translate-legal-domain" name="legal_domain"
                       placeholder="<?php esc_attr_e('مثال: عقد، شهادة، فاتورة', 'moajam-translation'); ?>">
            </div>

            <div class="moajam-translate-field">
                <label for="moajam-translate-client-name"><?php esc_html_e('الاسم', 'moajam-translation'); ?></label>
                <input type="text" id="moajam-translate-client-name" name="client_name" required>
            </div>

            <div class="moajam-translate-field">
                <label for="moajam-translate-client-email"><?php esc_html_e('البريد الإلكتروني', 'moajam-translation'); ?></label>
                <input type="email" id="moajam-translate-client-email" name="client_email" required>
            </div>

            <div class="moajam-translate-field">
                <label for="moajam-translate-client-phone"><?php esc_html_e('رقم الهاتف (اختياري)', 'moajam-translation'); ?></label>
                <input type="text" id="moajam-translate-client-phone" name="client_phone">
            </div>

            <button type="submit" class="moajam-translate-btn">
                <?php esc_html_e('إرسال الطلب', 'moajam-translation'); ?>
            </button>
        </form>

        <div id="moajam-translate-upload-result" class="moajam-translate-result" hidden></div>
    </section>

    <section class="moajam-translate-card" id="moajam-translate-status-section">
        <h3><?php esc_html_e('تتبع حالة طلب سابق', 'moajam-translation'); ?></h3>

        <form id="moajam-translate-status-form">
            <div class="moajam-translate-field">
                <label for="moajam-translate-job-id"><?php esc_html_e('رقم الطلب (Job ID)', 'moajam-translation'); ?></label>
                <input type="text" id="moajam-translate-job-id" name="job_id" required>
            </div>
            <button type="submit" class="moajam-translate-btn moajam-translate-btn-secondary">
                <?php esc_html_e('تحقق من الحالة', 'moajam-translation'); ?>
            </button>
        </form>

        <div id="moajam-translate-status-result" class="moajam-translate-result" hidden></div>
    </section>

</div>
