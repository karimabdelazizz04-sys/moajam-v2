<?php
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Translator dashboard: upload a document for translation, track status,
 * download the finished DOCX. Restricted to users with the
 * 'moajam_access_translator_dashboard' capability (the "Moajam Translator"
 * role, or Administrators).
 */
add_shortcode('moajam_translator_dashboard', function () {
    if (!is_user_logged_in()) {
        return '<p>' . esc_html__('من فضلك سجّل الدخول لعرض لوحة المترجم.', 'moajam-platform') . '</p>';
    }
    if (!current_user_can('moajam_access_translator_dashboard')) {
        return '<p>' . esc_html__('غير مصرح لك بالوصول لهذه اللوحة.', 'moajam-platform') . '</p>';
    }

    ob_start();
    ?>
    <div class="moajam-dashboard moajam-translator-dashboard">
        <h2><?php esc_html_e('لوحة المترجم', 'moajam-platform'); ?></h2>

        <form id="moajam-t-form" enctype="multipart/form-data" class="moajam-form">
            <p>
                <label><?php esc_html_e('الملف (docx, pdf, txt):', 'moajam-platform'); ?></label><br>
                <input type="file" name="file" accept=".docx,.pdf,.txt" required>
            </p>
            <p>
                <label><?php esc_html_e('بريد العميل (اختياري - لربط الفاتورة):', 'moajam-platform'); ?></label><br>
                <input type="email" name="client_email" placeholder="client@example.com">
            </p>
            <p>
                <label><?php esc_html_e('اللغة الهدف:', 'moajam-platform'); ?></label><br>
                <select name="target_language">
                    <option value="Arabic">العربية</option>
                    <option value="English">English</option>
                    <option value="French">Français</option>
                </select>
            </p>
            <p>
                <label><?php esc_html_e('نوع المستند (اختياري):', 'moajam-platform'); ?></label><br>
                <input type="text" name="legal_domain" placeholder="عقد، حكم قضائي، شهادة">
            </p>
            <p><button type="submit"><?php esc_html_e('ابدأ الترجمة', 'moajam-platform'); ?></button></p>
        </form>
        <div id="moajam-t-status"></div>

        <h3><?php esc_html_e('كل الطلبات', 'moajam-platform'); ?></h3>
        <button id="moajam-t-refresh" type="button"><?php esc_html_e('تحديث', 'moajam-platform'); ?></button>
        <table class="moajam-table">
            <thead>
                <tr>
                    <th><?php esc_html_e('الملف', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('اللغة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الحالة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('تاريخ الإنشاء', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('تحميل', 'moajam-platform'); ?></th>
                </tr>
            </thead>
            <tbody id="moajam-t-jobs"><tr><td colspan="5"><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></td></tr></tbody>
        </table>
    </div>

    <script>
    (function () {
        const nonce = '<?php echo esc_js(wp_create_nonce('moajam_translator')); ?>';
        const ajaxUrl = '<?php echo esc_url(admin_url('admin-ajax.php')); ?>';
        const form = document.getElementById('moajam-t-form');
        const statusBox = document.getElementById('moajam-t-status');
        const jobsBody = document.getElementById('moajam-t-jobs');

        async function loadJobs() {
            jobsBody.innerHTML = '<tr><td colspan="5"><?php echo esc_js(__('جاري التحميل...', 'moajam-platform')); ?></td></tr>';
            const res = await fetch(ajaxUrl + '?action=moajam_t_list_jobs&_ajax_nonce=' + nonce);
            const data = await res.json();
            if (!data.success) {
                jobsBody.innerHTML = '<tr><td colspan="5">' + (data.data && data.data.message || 'خطأ') + '</td></tr>';
                return;
            }
            if (!data.data.length) {
                jobsBody.innerHTML = '<tr><td colspan="5"><?php echo esc_js(__('لا توجد طلبات بعد', 'moajam-platform')); ?></td></tr>';
                return;
            }
            jobsBody.innerHTML = data.data.map(function (job) {
                const dl = job.status === 'done'
                    ? '<a href="' + ajaxUrl + '?action=moajam_t_download&job_id=' + encodeURIComponent(job.id) + '&_ajax_nonce=' + nonce + '" target="_blank">تحميل</a>'
                    : '-';
                return '<tr><td>' + job.source_filename + '</td><td>' + job.target_language + '</td>'
                    + '<td><span class="moajam-badge moajam-badge-' + job.status + '">' + job.status + '</span></td>'
                    + '<td>' + new Date(job.created_at).toLocaleString() + '</td><td>' + dl + '</td></tr>';
            }).join('');
        }

        document.getElementById('moajam-t-refresh').addEventListener('click', loadJobs);
        loadJobs();

        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            statusBox.textContent = '<?php echo esc_js(__('جاري الرفع...', 'moajam-platform')); ?>';
            const formData = new FormData(form);
            formData.append('action', 'moajam_t_create_job');
            formData.append('_ajax_nonce', nonce);
            try {
                const res = await fetch(ajaxUrl, { method: 'POST', body: formData });
                const data = await res.json();
                if (!data.success) {
                    statusBox.textContent = 'خطأ: ' + (data.data && data.data.message || 'فشل غير معروف');
                    return;
                }
                statusBox.textContent = 'تم إنشاء الطلب، حالته: ' + data.data.status;
                form.reset();
                setTimeout(loadJobs, 1500);
            } catch (err) {
                statusBox.textContent = 'حدث خطأ في الاتصال بالخادم.';
            }
        });
    })();
    </script>
    <?php
    return ob_get_clean();
});

function moajam_t_check_access() {
    if (!is_user_logged_in() || !current_user_can('moajam_access_translator_dashboard')) {
        wp_send_json_error(['message' => 'غير مصرح'], 403);
    }
    check_ajax_referer('moajam_translator');
}

add_action('wp_ajax_moajam_t_create_job', function () {
    moajam_t_check_access();

    if (empty($_FILES['file']) || !is_uploaded_file($_FILES['file']['tmp_name'])) {
        wp_send_json_error(['message' => 'لم يتم رفع أي ملف'], 400);
    }
    $allowed_ext = ['docx', 'pdf', 'txt'];
    $ext = strtolower(pathinfo($_FILES['file']['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, $allowed_ext, true)) {
        wp_send_json_error(['message' => 'نوع الملف غير مسموح'], 400);
    }

    $result = Moajam_Api_Client::create_translation_job(
        $_FILES['file']['tmp_name'],
        $_FILES['file']['name'],
        [
            'target_language' => sanitize_text_field($_POST['target_language'] ?? 'Arabic'),
            'legal_domain'    => sanitize_text_field($_POST['legal_domain'] ?? ''),
            'client_email'    => sanitize_email($_POST['client_email'] ?? ''),
            'source_language' => 'auto-detect',
        ]
    );

    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});

add_action('wp_ajax_moajam_t_list_jobs', function () {
    moajam_t_check_access();
    $result = Moajam_Api_Client::list_jobs();
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});

add_action('wp_ajax_moajam_t_download', function () {
    if (!is_user_logged_in() || !current_user_can('moajam_access_translator_dashboard')) {
        wp_die('غير مصرح');
    }
    check_ajax_referer('moajam_translator');

    $job_id = sanitize_text_field($_GET['job_id'] ?? '');
    $result = Moajam_Api_Client::fetch_job_download($job_id);
    if (isset($result['error'])) {
        wp_die('تعذر تحميل الملف.');
    }
    header('Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    header('Content-Disposition: attachment; filename="translated-' . $job_id . '.docx"');
    echo $result['raw_body'];
    exit;
});
