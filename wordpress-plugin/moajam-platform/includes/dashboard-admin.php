<?php
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Admin dashboard: full visibility - every translation job and invoice
 * across all clients/translators, plus ERP basics (staff, analytics,
 * notifications). Restricted to the 'moajam_access_admin_dashboard'
 * capability (Administrators by default).
 */
add_shortcode('moajam_admin_dashboard', function () {
    if (!is_user_logged_in() || !current_user_can('moajam_access_admin_dashboard')) {
        return '<p>' . esc_html__('غير مصرح لك بالوصول لهذه اللوحة.', 'moajam-platform') . '</p>';
    }

    ob_start();
    ?>
    <div class="moajam-dashboard moajam-admin-dashboard">
        <h2><?php esc_html_e('لوحة الإدارة', 'moajam-platform'); ?></h2>
        <button id="moajam-a-refresh" type="button"><?php esc_html_e('تحديث الكل', 'moajam-platform'); ?></button>

        <h3><?php esc_html_e('ملخص تحليلي', 'moajam-platform'); ?></h3>
        <div id="moajam-a-analytics"><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></div>

        <h3><?php esc_html_e('المترجمون والمراجعون', 'moajam-platform'); ?></h3>
        <form id="moajam-a-staff-form" class="moajam-form">
            <p>
                <label><?php esc_html_e('اسم مستخدم WordPress (user_login):', 'moajam-platform'); ?></label><br>
                <input type="text" name="username" required>
            </p>
            <p>
                <label><?php esc_html_e('الاسم الكامل:', 'moajam-platform'); ?></label><br>
                <input type="text" name="name" required>
            </p>
            <p>
                <label><?php esc_html_e('الدور:', 'moajam-platform'); ?></label><br>
                <select name="role">
                    <option value="translator"><?php esc_html_e('مترجم', 'moajam-platform'); ?></option>
                    <option value="reviewer"><?php esc_html_e('مراجع', 'moajam-platform'); ?></option>
                </select>
            </p>
            <p>
                <label><?php esc_html_e('نسبة العمولة (مثال 0.30 = 30%):', 'moajam-platform'); ?></label><br>
                <input type="number" name="commission_rate" min="0" max="1" step="0.01" value="0">
            </p>
            <p><button type="submit"><?php esc_html_e('إضافة', 'moajam-platform'); ?></button></p>
        </form>
        <table class="moajam-table">
            <thead>
                <tr>
                    <th><?php esc_html_e('اليوزر', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الاسم', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الدور', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('العمولة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('عدد الطلبات', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('المكتمل', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الإيراد', 'moajam-platform'); ?></th>
                </tr>
            </thead>
            <tbody id="moajam-a-staff"><tr><td colspan="7"><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></td></tr></tbody>
        </table>

        <h3><?php esc_html_e('كل طلبات الترجمة', 'moajam-platform'); ?></h3>
        <table class="moajam-table">
            <thead>
                <tr>
                    <th><?php esc_html_e('الملف', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('العميل', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('المترجم', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('السعر', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('اللغة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('الحالة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('المراجعة', 'moajam-platform'); ?></th>
                    <th><?php esc_html_e('تاريخ الإنشاء', 'moajam-platform'); ?></th>
                </tr>
            </thead>
            <tbody id="moajam-a-jobs"><tr><td colspan="8"><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></td></tr></tbody>
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

        <h3><?php esc_html_e('الإشعارات', 'moajam-platform'); ?></h3>
        <ul id="moajam-a-notifications"><li><?php esc_html_e('جاري التحميل...', 'moajam-platform'); ?></li></ul>

        <p class="moajam-admin-note">
            <?php esc_html_e('لإدارة الحسابات والمحاسبة (Chart of Accounts / Journal Entries / P&L / Balance Sheet) ادخل على الباك إند مباشرة بحساب الأدمن (JWT) - راجع README.', 'moajam-platform'); ?>
        </p>
    </div>

    <script>
    (function () {
        const nonce = '<?php echo esc_js(wp_create_nonce('moajam_admin')); ?>';
        const ajaxUrl = '<?php echo esc_url(admin_url('admin-ajax.php')); ?>';

        async function callAjax(action, params) {
            const url = new URL(ajaxUrl);
            url.searchParams.set('action', action);
            url.searchParams.set('_ajax_nonce', nonce);
            Object.entries(params || {}).forEach(([k, v]) => url.searchParams.set(k, v));
            const res = await fetch(url);
            return res.json();
        }

        async function loadAnalytics() {
            const box = document.getElementById('moajam-a-analytics');
            const data = await callAjax('moajam_a_analytics');
            if (!data.success) {
                box.innerHTML = data.data && data.data.message || 'خطأ';
                return;
            }
            const s = data.data;
            box.innerHTML = '<p>'
                + 'إجمالي الطلبات: <strong>' + s.jobs_total + '</strong> | '
                + 'الإيراد الإجمالي: <strong>' + s.revenue_total.toLocaleString() + '</strong> | '
                + Object.entries(s.jobs_by_status).map(([k, v]) => k + ': ' + v).join(' | ')
                + '</p>';
        }

        async function loadStaff() {
            const body = document.getElementById('moajam-a-staff');
            const data = await callAjax('moajam_a_list_staff');
            if (!data.success) {
                body.innerHTML = '<tr><td colspan="7">' + (data.data && data.data.message || 'خطأ') + '</td></tr>';
                return;
            }
            body.innerHTML = data.data.length ? data.data.map(function (s) {
                return '<tr><td>' + s.username + '</td><td>' + s.name + '</td><td>' + s.role + '</td>'
                    + '<td>' + (s.commission_rate * 100).toFixed(0) + '%</td>'
                    + '<td>' + s.jobs_total + '</td><td>' + s.jobs_done + '</td>'
                    + '<td>' + s.revenue_total.toLocaleString() + '</td></tr>';
            }).join('') : '<tr><td colspan="7">-</td></tr>';
        }

        async function loadJobs() {
            const body = document.getElementById('moajam-a-jobs');
            const data = await callAjax('moajam_a_list_jobs');
            if (!data.success) {
                body.innerHTML = '<tr><td colspan="8">' + (data.data && data.data.message || 'خطأ') + '</td></tr>';
                return;
            }
            body.innerHTML = data.data.length ? data.data.map(function (job) {
                return '<tr><td>' + job.source_filename + '</td><td>' + (job.client_name || '-') + '</td>'
                    + '<td>' + (job.created_by || '-') + '</td>'
                    + '<td>' + (job.price != null ? job.price : '-') + '</td>'
                    + '<td>' + job.target_language + '</td>'
                    + '<td><span class="moajam-badge moajam-badge-' + job.status + '">' + job.status + '</span></td>'
                    + '<td>' + job.review_status + '</td>'
                    + '<td>' + new Date(job.created_at).toLocaleString() + '</td></tr>';
            }).join('') : '<tr><td colspan="8">-</td></tr>';
        }

        async function loadInvoices() {
            const body = document.getElementById('moajam-a-invoices');
            const data = await callAjax('moajam_a_list_invoices');
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

        async function loadNotifications() {
            const list = document.getElementById('moajam-a-notifications');
            const data = await callAjax('moajam_a_list_notifications');
            if (!data.success) {
                list.innerHTML = '<li>' + (data.data && data.data.message || 'خطأ') + '</li>';
                return;
            }
            list.innerHTML = data.data.length ? data.data.map(function (n) {
                return '<li>' + (n.is_read ? '' : '🔵 ') + '[' + n.type + '] ' + n.message
                    + ' <small>' + new Date(n.created_at).toLocaleString() + '</small></li>';
            }).join('') : '<li><?php echo esc_js(__('لا توجد إشعارات', 'moajam-platform')); ?></li>';
        }

        function loadAll() { loadAnalytics(); loadStaff(); loadJobs(); loadInvoices(); loadNotifications(); }
        document.getElementById('moajam-a-refresh').addEventListener('click', loadAll);
        loadAll();

        document.getElementById('moajam-a-staff-form').addEventListener('submit', async function (e) {
            e.preventDefault();
            const formData = new FormData(e.target);
            const params = {};
            formData.forEach((v, k) => { params[k] = v; });
            const data = await callAjax('moajam_a_create_staff', params);
            if (!data.success) {
                alert('خطأ: ' + (data.data && data.data.message || 'فشل غير معروف'));
                return;
            }
            e.target.reset();
            loadStaff();
        });
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

add_action('wp_ajax_moajam_a_list_staff', function () {
    moajam_a_check_access();
    $result = Moajam_Api_Client::list_staff();
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});

add_action('wp_ajax_moajam_a_create_staff', function () {
    moajam_a_check_access();
    $result = Moajam_Api_Client::create_staff([
        'username'        => sanitize_text_field($_GET['username'] ?? ''),
        'name'            => sanitize_text_field($_GET['name'] ?? ''),
        'role'            => sanitize_text_field($_GET['role'] ?? 'translator'),
        'commission_rate' => floatval($_GET['commission_rate'] ?? 0),
    ]);
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});

add_action('wp_ajax_moajam_a_analytics', function () {
    moajam_a_check_access();
    $result = Moajam_Api_Client::analytics_summary();
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});

add_action('wp_ajax_moajam_a_list_notifications', function () {
    moajam_a_check_access();
    $result = Moajam_Api_Client::list_notifications('admin');
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
});
