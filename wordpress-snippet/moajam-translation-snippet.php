<?php
/**
 * Moajam Almaani - V2 Translation Snippet
 *
 * Install with the "Code Snippets" plugin (or paste into your child theme's
 * functions.php). Provides:
 *   - [moajam_translate_form] shortcode: upload form + status polling + download
 *   - AJAX proxy endpoints that call the FastAPI backend using a server-side API key
 *     (the key never reaches the browser).
 *
 * Before activating, set these constants (wp-config.php is the recommended place,
 * NOT inside this snippet, so the key isn't visible in the Code Snippets UI):
 *
 *   define('MOAJAM_API_BASE_URL', 'https://api.moajamalmaani.com');
 *   define('MOAJAM_API_KEY', 'the-same-value-as-API_KEY-in-backend/.env');
 */

if (!defined('MOAJAM_API_BASE_URL')) {
    define('MOAJAM_API_BASE_URL', 'https://api.moajamalmaani.com');
}

// -----------------------------------------------------------------------
// Shortcode: renders the upload form
// -----------------------------------------------------------------------
add_shortcode('moajam_translate_form', function () {
    ob_start();
    ?>
    <div id="moajam-translate-app">
        <form id="moajam-translate-form" enctype="multipart/form-data">
            <p>
                <label for="moajam-file">اختر الملف (docx, pdf, txt):</label><br>
                <input type="file" id="moajam-file" name="file" accept=".docx,.pdf,.txt" required>
            </p>
            <p>
                <label for="moajam-target-lang">اللغة المطلوب الترجمة إليها:</label><br>
                <select id="moajam-target-lang" name="target_language">
                    <option value="Arabic">العربية</option>
                    <option value="English">English</option>
                    <option value="French">Français</option>
                </select>
            </p>
            <p>
                <label for="moajam-domain">نوع المستند (اختياري):</label><br>
                <input type="text" id="moajam-domain" name="legal_domain" placeholder="مثال: عقد، حكم قضائي، شهادة">
            </p>
            <p>
                <button type="submit" id="moajam-submit-btn">ابدأ الترجمة</button>
            </p>
        </form>
        <div id="moajam-status" style="display:none;"></div>
    </div>

    <script>
    (function () {
        const form = document.getElementById('moajam-translate-form');
        const statusBox = document.getElementById('moajam-status');
        const submitBtn = document.getElementById('moajam-submit-btn');

        form.addEventListener('submit', async function (e) {
            e.preventDefault();
            submitBtn.disabled = true;
            statusBox.style.display = 'block';
            statusBox.textContent = 'جاري رفع الملف...';

            const formData = new FormData(form);
            formData.append('action', 'moajam_create_translation');
            formData.append('_ajax_nonce', '<?php echo esc_js(wp_create_nonce('moajam_translate')); ?>');

            try {
                const res = await fetch('<?php echo esc_url(admin_url('admin-ajax.php')); ?>', {
                    method: 'POST',
                    body: formData,
                });
                const data = await res.json();
                if (!data.success) {
                    statusBox.textContent = 'خطأ: ' + (data.data && data.data.message ? data.data.message : 'فشل غير معروف');
                    submitBtn.disabled = false;
                    return;
                }
                pollStatus(data.data.job_id);
            } catch (err) {
                statusBox.textContent = 'حدث خطأ في الاتصال بالخادم.';
                submitBtn.disabled = false;
            }
        });

        function pollStatus(jobId) {
            statusBox.textContent = 'جاري الترجمة... قد تستغرق دقيقة.';
            const interval = setInterval(async function () {
                try {
                    const url = '<?php echo esc_url(admin_url('admin-ajax.php')); ?>'
                        + '?action=moajam_translation_status&job_id=' + encodeURIComponent(jobId)
                        + '&_ajax_nonce=<?php echo esc_js(wp_create_nonce('moajam_translate')); ?>';
                    const res = await fetch(url);
                    const data = await res.json();
                    if (!data.success) {
                        clearInterval(interval);
                        statusBox.textContent = 'خطأ: ' + (data.data && data.data.message ? data.data.message : 'فشل غير معروف');
                        submitBtn.disabled = false;
                        return;
                    }
                    const status = data.data.status;
                    if (status === 'done') {
                        clearInterval(interval);
                        statusBox.innerHTML = 'تمت الترجمة بنجاح! <a href="'
                            + '<?php echo esc_url(admin_url('admin-ajax.php')); ?>'
                            + '?action=moajam_translation_download&job_id=' + encodeURIComponent(jobId)
                            + '&_ajax_nonce=<?php echo esc_js(wp_create_nonce('moajam_translate')); ?>" target="_blank">تحميل الملف المترجم</a>';
                        submitBtn.disabled = false;
                    } else if (status === 'failed') {
                        clearInterval(interval);
                        statusBox.textContent = 'فشلت الترجمة: ' + (data.data.error_message || '');
                        submitBtn.disabled = false;
                    } else {
                        statusBox.textContent = 'الحالة: ' + status + ' ...';
                    }
                } catch (err) {
                    clearInterval(interval);
                    statusBox.textContent = 'حدث خطأ أثناء التحقق من الحالة.';
                    submitBtn.disabled = false;
                }
            }, 4000);
        }
    })();
    </script>
    <?php
    return ob_get_clean();
});

// -----------------------------------------------------------------------
// AJAX: create translation job (proxies multipart upload to the backend)
// -----------------------------------------------------------------------
add_action('wp_ajax_moajam_create_translation', 'moajam_create_translation');
add_action('wp_ajax_nopriv_moajam_create_translation', 'moajam_create_translation');

function moajam_create_translation() {
    check_ajax_referer('moajam_translate');

    if (empty($_FILES['file']) || !is_uploaded_file($_FILES['file']['tmp_name'])) {
        wp_send_json_error(['message' => 'لم يتم رفع أي ملف'], 400);
    }

    $file        = $_FILES['file'];
    $allowed_ext = ['docx', 'pdf', 'txt'];
    $ext         = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, $allowed_ext, true)) {
        wp_send_json_error(['message' => 'نوع الملف غير مسموح'], 400);
    }

    $boundary  = wp_generate_password(24, false);
    $eol       = "\r\n";
    $body      = '';

    $fields = [
        'target_language' => sanitize_text_field($_POST['target_language'] ?? 'Arabic'),
        'legal_domain'    => sanitize_text_field($_POST['legal_domain'] ?? ''),
        'source_language' => 'auto-detect',
    ];
    foreach ($fields as $name => $value) {
        $body .= '--' . $boundary . $eol;
        $body .= 'Content-Disposition: form-data; name="' . $name . '"' . $eol . $eol;
        $body .= $value . $eol;
    }

    $file_contents = file_get_contents($file['tmp_name']);
    $body .= '--' . $boundary . $eol;
    $body .= 'Content-Disposition: form-data; name="file"; filename="' . basename($file['name']) . '"' . $eol;
    $body .= 'Content-Type: application/octet-stream' . $eol . $eol;
    $body .= $file_contents . $eol;
    $body .= '--' . $boundary . '--' . $eol;

    $response = wp_remote_post(MOAJAM_API_BASE_URL . '/api/v1/translations', [
        'headers' => [
            'Content-Type' => 'multipart/form-data; boundary=' . $boundary,
            'X-API-Key'    => MOAJAM_API_KEY,
        ],
        'body'    => $body,
        'timeout' => 60,
    ]);

    if (is_wp_error($response)) {
        wp_send_json_error(['message' => $response->get_error_message()], 502);
    }

    $code = wp_remote_retrieve_response_code($response);
    $data = json_decode(wp_remote_retrieve_body($response), true);

    if ($code >= 400) {
        wp_send_json_error(['message' => $data['detail'] ?? 'فشل إنشاء عملية الترجمة'], $code);
    }

    wp_send_json_success(['job_id' => $data['job_id'], 'status' => $data['status']]);
}

// -----------------------------------------------------------------------
// AJAX: poll job status
// -----------------------------------------------------------------------
add_action('wp_ajax_moajam_translation_status', 'moajam_translation_status');
add_action('wp_ajax_nopriv_moajam_translation_status', 'moajam_translation_status');

function moajam_translation_status() {
    check_ajax_referer('moajam_translate');

    $job_id = sanitize_text_field($_GET['job_id'] ?? '');
    if (!$job_id) {
        wp_send_json_error(['message' => 'job_id missing'], 400);
    }

    $response = wp_remote_get(MOAJAM_API_BASE_URL . '/api/v1/translations/' . rawurlencode($job_id), [
        'headers' => ['X-API-Key' => MOAJAM_API_KEY],
        'timeout' => 20,
    ]);

    if (is_wp_error($response)) {
        wp_send_json_error(['message' => $response->get_error_message()], 502);
    }

    $code = wp_remote_retrieve_response_code($response);
    $data = json_decode(wp_remote_retrieve_body($response), true);

    if ($code >= 400) {
        wp_send_json_error(['message' => $data['detail'] ?? 'تعذر جلب الحالة'], $code);
    }

    wp_send_json_success($data);
}

// -----------------------------------------------------------------------
// AJAX: stream the translated docx back to the browser
// -----------------------------------------------------------------------
add_action('wp_ajax_moajam_translation_download', 'moajam_translation_download');
add_action('wp_ajax_nopriv_moajam_translation_download', 'moajam_translation_download');

function moajam_translation_download() {
    check_ajax_referer('moajam_translate');

    $job_id = sanitize_text_field($_GET['job_id'] ?? '');
    if (!$job_id) {
        wp_die('job_id missing');
    }

    $response = wp_remote_get(MOAJAM_API_BASE_URL . '/api/v1/translations/' . rawurlencode($job_id) . '/download', [
        'headers' => ['X-API-Key' => MOAJAM_API_KEY],
        'timeout' => 30,
    ]);

    if (is_wp_error($response)) {
        wp_die('تعذر تحميل الملف.');
    }

    $code = wp_remote_retrieve_response_code($response);
    if ($code >= 400) {
        wp_die('الملف غير متاح حاليًا.');
    }

    header('Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    header('Content-Disposition: attachment; filename="translated-' . $job_id . '.docx"');
    echo wp_remote_retrieve_body($response);
    exit;
}
