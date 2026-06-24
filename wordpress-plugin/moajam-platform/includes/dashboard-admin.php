<?php
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Admin dashboard: full visibility - every translation job and every
 * invoice, across all clients. Restricted to the
 * 'moajam_access_admin_dashboard' capability (Administrators by default).
 */
add_shortcode('moajam_admin_dashboard', function () {
    if (!is_user_logged_in() || !current_user_can('moajam_access_admin_dashboard')) {
        return '<p>' . esc_html__('غير مصرح لك بالوصول لهذه اللوحة.', 'moajam-platform') . '</p>';
    }

    ob_start();
    ?>
    <div class="moajam-dashboard moajam-admin-dashboard">
        <h2><?php esc_html_e('لوحة الإدارة - كل الطلبات والفواتير', 'moajam-platform'); ?></h2>
        <button id="moajam-a-refresh" type="button"><?php esc_html_e('تحديث', 'moajam-platform'); ?></button>

        <h3><?php esc_html_e('كل طلبات الترجمة', 'moajam-platform'); ?></h3>
        <table class="moajam-table">
            <thead>
                <tr>
                    <th><?php esc_html_e('الملف', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('Client ID', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('اللغة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الحالة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('تاريخ الإنشاء', 'moajam-platform'); ?></th>
                </tr>
            </thead>
            <tbody id="moajam-a-jobs"><tr><td colspan="5"><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></td></tr></tbody>
        </table>

        <h3><?php esc_html_e('كل الفواتير', 'moajam-platform'); ?></h3>
        <table class="moajam-table">
            <thead>
                <tr>
                    <th><?php esc_html_e('رقم الفاتورة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('Client ID', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الحالة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الإجمالي', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('تاريخ الإصدار', 'moajam-platform'); ?></th>
                </tr>
            </thead>
            <tbody id="moajam-a-invoices"><tr><td colspan="5"><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></td></tr></tbody>
        </table>

        <p class="moajam-admin-note">
            <?php esc_html_e('لإدارة الحسابات والمحاسبة (Chart of Accounts / Journal Entries / P&L / Balance Sheet) ادخل على الباك إند مباشرة بحساب الأدمن (JWT) - راجع README.', 'moajam-platform'); ?>
        </p>
    </div>

    <script>
    (function () {
        const nonce = '<?php echo esc_js(wp_create_nonce('moajam_admin')); ?>';
        const ajaxUrl = '<?php echo esc_url(admin_url('admin-ajax.php')); ?>';

        async function loadJobs() {
            const body = document.getElementById('moajam-a-jobs');
            const res = await fetch(ajaxUrl + '?action=moajam_a_list_jobs&_ajax_nonce=' + nonce);
            const data = await res.json();
            if (!data.success) {
                body.innerHTML = '<tr><td colspan="5">' + (data.data && data.data.message || 'خطأ') + '</td></tr>';
                return;
            }
            body.innerHTML = data.data.length ? data.data.map(function (job) {
                return '<tr><td>' + job.source_filename + '</td><td>' + (job.client_id ?? '-') + '</td>'
                    + '<td>' + job.target_language + '</td>'
                    + '<td><span class="moajam-badge moajam-badge-' + job.status + '">' + job.status + '</span></td>'
                    + '<td>' + new Date(job.created_at).toLocaleString() + '</td></tr>';
            }).join('') : '<tr><td colspan="5">-</td></tr>';
        }

        async function loadInvoices() {
            const body = document.getElementById('moajam-a-invoices');
            const res = await fetch(ajaxUrl + '?action=moajam_a_list_invoices&_ajax_nonce=' + nonce);
            const data = await res.json();
            if (!data.success) {
                body.innerHTML = '<tr><td colspan="5">' + (data.data && data.data.message || 'خطأ') + '</td></tr>';
                return;
            }
            body.innerHTML = data.data.length ? data.data.map(function (inv) {
                return '<tr><td>' + inv.number + '</td><td>' + inv.client_id + '</td>'
                    + '<td><span class="moajam-badge moajam-badge-' + inv.status + '">' + inv.status + '</span></td>'
                    + '<td>' + inv.total.toLocaleString() + ' ' + inv.currency + '</td>'
                    + '<td>' + inv.issue_date + '</td></tr>';
            }).join('') : '<tr><td colspan="5">-</td></tr>';
        }

        function loadAll() { loadJobs(); loadInvoices(); }
        document.getElementById('moajam-a-refresh').addEventListener('click', loadAll);
        loadAll();
    })();
    </script>
    <?php
    return ob_get_clean();
});

function moajam_a_check_access() {
    if (!is_user_logged_in() || !current_user_can('moajam_access_admin_dashboard')) {
        wp_send_json_error(['message' => 'غير مصرح'], 403);
    }
    check_ajax_referer('moajam_admin');
}

add_action('wp_ajax_moajam_a_list_jobs', function () {
    moajam_a_check_access();
    $result = Moajam_Api_Client::list_jobs();
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});

add_action('wp_ajax_moajam_a_list_invoices', function () {
    moajam_a_check_access();
    $result = Moajam_Api_Client::list_invoices();
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});
