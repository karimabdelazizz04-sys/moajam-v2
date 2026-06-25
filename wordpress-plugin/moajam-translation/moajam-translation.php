<?php
/**
 * Plugin Name: Moajam Translation Platform
 * Description: Public-facing translation request form, status tracking, and download button. Talks to the Moajam Almaani FastAPI backend - no file ever stays on the backend, it's stored in this site's Media Library.
 * Version: 1.0.0
 * Text Domain: moajam-translation
 *
 * Setup (wp-config.php):
 *   define('MOAJAM_API_BASE_URL', 'https://moajam-api.onrender.com');
 *   define('MOAJAM_API_KEY', '...'); // same X-API-Key the backend expects
 *
 * Usage: add the [moajam_translate_form] shortcode to any page/post.
 */

if (!defined('ABSPATH')) {
    exit;
}

define('MOAJAM_TRANSLATE_PLUGIN_FILE', __FILE__);
define('MOAJAM_TRANSLATE_PLUGIN_DIR', plugin_dir_path(__FILE__));
define('MOAJAM_TRANSLATE_PLUGIN_URL', plugin_dir_url(__FILE__));

require_once MOAJAM_TRANSLATE_PLUGIN_DIR . 'class-api-client.php';

const MOAJAM_TRANSLATE_ALLOWED_EXT = ['docx', 'pdf', 'txt'];

function moajam_translate_enqueue_assets() {
    wp_enqueue_style(
        'moajam-translate',
        MOAJAM_TRANSLATE_PLUGIN_URL . 'assets/css/moajam-translation.css',
        [],
        '1.0.0'
    );
    wp_enqueue_script(
        'moajam-translate',
        MOAJAM_TRANSLATE_PLUGIN_URL . 'assets/js/moajam-translation.js',
        [],
        '1.0.0',
        true
    );
    wp_localize_script('moajam-translate', 'MoajamTranslate', [
        'ajaxUrl' => admin_url('admin-ajax.php'),
        'nonce'   => wp_create_nonce('moajam_translate_nonce'),
    ]);
}

function moajam_translate_form_shortcode() {
    moajam_translate_enqueue_assets();
    ob_start();
    include MOAJAM_TRANSLATE_PLUGIN_DIR . 'templates/form.php';
    return ob_get_clean();
}
add_shortcode('moajam_translate_form', 'moajam_translate_form_shortcode');

/**
 * Sideload a directly-uploaded file into this site's Media Library and
 * return its permanent URL. The backend never receives file bytes - only
 * this URL - so the FastAPI service stays stateless.
 */
function moajam_translate_sideload_file(array $file) {
    require_once ABSPATH . 'wp-admin/includes/image.php';
    require_once ABSPATH . 'wp-admin/includes/file.php';
    require_once ABSPATH . 'wp-admin/includes/media.php';

    $attachment_id = media_handle_upload('file', 0);
    if (is_wp_error($attachment_id)) {
        return $attachment_id;
    }
    return wp_get_attachment_url($attachment_id);
}

function moajam_translate_handle_create_job() {
    check_ajax_referer('moajam_translate_nonce', 'nonce');

    if (empty($_FILES['file']) || !is_uploaded_file($_FILES['file']['tmp_name'])) {
        wp_send_json_error(['message' => __('لم يتم رفع أي ملف', 'moajam-translation')], 400);
    }

    $ext = strtolower(pathinfo($_FILES['file']['name'], PATHINFO_EXTENSION));
    if (!in_array($ext, MOAJAM_TRANSLATE_ALLOWED_EXT, true)) {
        wp_send_json_error(['message' => __('نوع الملف غير مسموح (docx, pdf, txt فقط)', 'moajam-translation')], 400);
    }

    $source_filename = sanitize_file_name($_FILES['file']['name']);
    $media_url = moajam_translate_sideload_file($_FILES['file']);
    if (is_wp_error($media_url)) {
        wp_send_json_error(['message' => $media_url->get_error_message()], 500);
    }

    $result = Moajam_Translate_Api_Client::create_translation_job([
        'source_file_url' => $media_url,
        'source_filename' => $source_filename,
        'source_language' => 'auto-detect',
        'target_language' => sanitize_text_field($_POST['target_language'] ?? 'Arabic'),
        'legal_domain'    => sanitize_text_field($_POST['legal_domain'] ?? ''),
        'client_name'     => sanitize_text_field($_POST['client_name'] ?? ''),
        'client_email'    => sanitize_email($_POST['client_email'] ?? ''),
        'client_phone'    => sanitize_text_field($_POST['client_phone'] ?? ''),
    ]);

    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }
    wp_send_json_success($result['data']);
}
add_action('wp_ajax_moajam_translate_create_job', 'moajam_translate_handle_create_job');
add_action('wp_ajax_nopriv_moajam_translate_create_job', 'moajam_translate_handle_create_job');

function moajam_translate_handle_check_status() {
    check_ajax_referer('moajam_translate_nonce', 'nonce');

    $job_id = sanitize_text_field($_POST['job_id'] ?? '');
    if (!$job_id) {
        wp_send_json_error(['message' => __('رقم الطلب مطلوب', 'moajam-translation')], 400);
    }

    $result = Moajam_Translate_Api_Client::get_job($job_id);
    if (isset($result['error'])) {
        wp_send_json_error(['message' => $result['error']], $result['code']);
    }

    $job = $result['data'];
    $job['download_url'] = ($job['status'] ?? '') === 'done'
        ? Moajam_Translate_Api_Client::download_job_url($job_id)
        : null;

    wp_send_json_success($job);
}
add_action('wp_ajax_moajam_translate_check_status', 'moajam_translate_handle_check_status');
add_action('wp_ajax_nopriv_moajam_translate_check_status', 'moajam_translate_handle_check_status');
