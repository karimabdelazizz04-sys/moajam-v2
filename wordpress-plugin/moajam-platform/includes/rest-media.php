<?php
if (!defined('ABSPATH')) {
    exit;
}

/**
 * REST endpoint the FastAPI backend calls to push generated files (translated
 * DOCX, invoice PDF) into this site's Media Library. This is the other half
 * of keeping Render stateless: Render never stores a file of its own, it
 * always either reads from or writes to WordPress.
 *
 * Protected by the same shared secret used everywhere else (MOAJAM_API_KEY),
 * sent as the X-API-Key header - symmetric with how WordPress calls the
 * backend's translation endpoints.
 */
add_action('rest_api_init', function () {
    register_rest_route('moajam/v1', '/media', [
        'methods'             => 'POST',
        'callback'            => 'moajam_rest_upload_media',
        'permission_callback' => 'moajam_rest_verify_api_key',
    ]);
});

function moajam_rest_verify_api_key(\WP_REST_Request $request) {
    $provided = $request->get_header('x-api-key');
    if (!defined('MOAJAM_API_KEY') || !$provided || !hash_equals(MOAJAM_API_KEY, $provided)) {
        return new \WP_Error('moajam_unauthorized', 'Invalid API key', ['status' => 401]);
    }
    return true;
}

function moajam_rest_upload_media(\WP_REST_Request $request) {
    $files = $request->get_file_params();
    if (empty($files['file'])) {
        return new \WP_Error('moajam_no_file', 'No file provided', ['status' => 400]);
    }

    require_once ABSPATH . 'wp-admin/includes/image.php';
    require_once ABSPATH . 'wp-admin/includes/file.php';
    require_once ABSPATH . 'wp-admin/includes/media.php';

    $attachment_id = media_handle_sideload($files['file'], 0);
    if (is_wp_error($attachment_id)) {
        return new \WP_Error('moajam_upload_failed', $attachment_id->get_error_message(), ['status' => 500]);
    }

    return new \WP_REST_Response([
        'id'  => $attachment_id,
        'url' => wp_get_attachment_url($attachment_id),
    ], 201);
}
