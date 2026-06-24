<?php
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Client dashboard: track translation requests and invoices tied to the
 * logged-in WordPress user's email address. Any logged-in user can view
 * their own data; there is no separate "client" WP role required.
 */
add_shortcode('moajam_client_dashboard', function () {
    if (!is_user_logged_in()) {
        return '<p>' . esc_html__('من فضلك سجّل الدخول لعرض طلباتك.', 'moajam-platform') . '</p>';
    }

    ob_start();
    ?>
    <div class="moajam-dashboard moajam-client-dashboard">
        <h2><?php esc_html_e('طلباتي وفواتيري', 'moajam-platform'); ?></h2>

        <h3><?php esc_html_e('طلبات الترجمة', 'moajam-platform'); ?></h3>
        <table class="moajam-table">
            <thead>
                <tr>
                    <th><?php esc_html_e('الملف', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الحالة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('تاريخ الإنشاء', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('تحميل', 'moajam-platform'); ?></th>
                </tr>
            </thead>
            <tbody id="moajam-c-jobs"><tr><td colspan="4"><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></td></tr></tbody>
        </table>

        <h3><?php esc_html_e('الفواتير', 'moajam-platform'); ?></h3>
        <table class="moajam-table">
            <thead>
                <tr>
                    <th><?php esc_html_e('رقم الفاتورة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الحالة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الإجمالي', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('تحميل PDF', 'moajam-platform'); ?></th>
                </tr>
            </thead>
            <tbody id="moajam-c-invoices"><tr><td colspan="4"><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></td></tr></tbody>
        </table>
    </div>

    <script>
    (function () {
        const nonce = '<?php echo esc_js(wp_create_nonce('moajam_client')); ?>';
        const ajaxUrl = '<?php echo esc_url(admin_url('admin-ajax.php')); ?>';

        async function loadJobs() {
            const body = document.getElementById('moajam-c-jobs');
            const res = await fetch(ajaxUrl + '?action=moajam_c_list_jobs&_ajax_nonce=' + nonce);
            const data = await res.json();
            if (!data.success) {
                body.innerHTML = '<tr><td colspan="4">' + (data.data && data.data.message || 'خطأ') + '</td></tr>';
                return;
            }
            if (!data.data.length) {
                body.innerHTML = '<tr><td colspan="4"><?php echo esc_js(__('لا توجد طلبات بعد', 'moajam-platform')); ?></td></tr>';
                return;
            }
            body.innerHTML = data.data.map(function (job) {
                const dl = job.status === 'done'
                    ? '<a href="' + ajaxUrl + '?action=moajam_c_download_job&job_id=' + encodeURIComponent(job.id) + '&_ajax_nonce=' + nonce + '" target="_blank">تحميل</a>'
                    : '-';
                return '<tr><td>' + job.source_filename + '</td>'
                    + '<td><span class="moajam-badge moajam-badge-' + job.status + '">' + job.status + '</span></td>'
                    + '<td>' + new Date(job.created_at).toLocaleString() + '</td><td>' + dl + '</td></tr>';
            }).join('');
        }

        async function loadInvoices() {
            const body = document.getElementById('moajam-c-invoices');
            const res = await fetch(ajaxUrl + '?action=moajam_c_list_invoices&_ajax_nonce=' + nonce);
            const data = await res.json();
            if (!data.success) {
                body.innerHTML = '<tr><td colspan="4">' + (data.data && data.data.message || 'خطأ') + '</td></tr>';
                return;
            }
            if (!data.data.length) {
                body.innerHTML = '<tr><td colspan="4"><?php echo esc_js(__('لا توجد فواتير بعد', 'moajam-platform')); ?></td></tr>';
                return;
            }
            body.innerHTML = data.data.map(function (inv) {
                const dl = inv.pdf_path
                    ? '<a href="' + ajaxUrl + '?action=moajam_c_download_invoice&invoice_id=' + inv.id + '&_ajax_nonce=' + nonce + '" target="_blank">تحميل</a>'
                    : '-';
                return '<tr><td>' + inv.number + '</td>'
                    + '<td><span class="moajam-badge moajam-badge-' + inv.status + '">' + inv.status + '</span></td>'
                    + '<td>' + inv.total.toLocaleString() + ' ' + inv.currency + '</td><td>' + dl + '</td></tr>';
            }).join('');
        }

        loadJobs();
        loadInvoices();
    })();
    </script>
    <?php
    return ob_get_clean();
});

function moajam_c_check_access() {
    if (!is_user_logged_in()) {
        wp_send_json_error(['message' => 'غير مصرح'], 403);
    }
    check_ajax_referer('moajam_client');
}

add_action('wp_ajax_moajam_c_list_jobs', function () {
    moajam_c_check_access();
    $email = wp_get_current_user()->user_email;
    $result = Moajam_Api_Client::list_jobs($email);
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});

add_action('wp_ajax_moajam_c_list_invoices', function () {
    moajam_c_check_access();
    $email = wp_get_current_user()->user_email;
    $result = Moajam_Api_Client::list_invoices($email);
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});

add_action('wp_ajax_moajam_c_download_job', function () {
    if (!is_user_logged_in()) {
        wp_die('غير مصرح');
    }
    check_ajax_referer('moajam_client');

    $job_id = sanitize_text_field($_GET['job_id'] ?? '');
    $email = wp_get_current_user()->user_email;

    // Ownership check: the job must belong to this user's email before streaming it.
    $jobs_result = Moajam_Api_Client::list_jobs($email);
    $owned = false;
    if (!isset($jobs_result['error'])) {
        foreach ($jobs_result['data'] as $job) {
            if ($job['id'] === $job_id) {
                $owned = true;
                break;
            }
        }
    }
    if (!$owned) {
        wp_die('غير مصرح بتحميل هذا الملف.');
    }

    $result = Moajam_Api_Client::fetch_job_download($job_id);
    if (isset($result['error'])) {
        wp_die('تعذر تحميل الملف.');
    }
    header('Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document');
    header('Content-Disposition: attachment; filename="translated-' . $job_id . '.docx"');
    echo $result['raw_body'];
    exit;
});

add_action('wp_ajax_moajam_c_download_invoice', function () {
    if (!is_user_logged_in()) {
        wp_die('غير مصرح');
    }
    check_ajax_referer('moajam_client');

    $invoice_id = intval($_GET['invoice_id'] ?? 0);
    $email = wp_get_current_user()->user_email;

    // Ownership check: the invoice must belong to this user's email before streaming it.
    $invoices_result = Moajam_Api_Client::list_invoices($email);
    $owned = false;
    if (!isset($invoices_result['error'])) {
        foreach ($invoices_result['data'] as $inv) {
            if ((int) $inv['id'] === $invoice_id) {
                $owned = true;
                break;
            }
        }
    }
    if (!$owned) {
        wp_die('غير مصرح بتحميل هذه الفاتورة.');
    }

    $result = Moajam_Api_Client::fetch_invoice_download($invoice_id);
    if (isset($result['error'])) {
        wp_die('تعذر تحميل الفاتورة.');
    }
    header('Content-Type: application/pdf');
    header('Content-Disposition: attachment; filename="invoice-' . $invoice_id . '.pdf"');
    echo $result['raw_body'];
    exit;
});
