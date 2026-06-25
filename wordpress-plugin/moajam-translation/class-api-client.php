<?php
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Thin wrapper around the FastAPI backend's translation endpoints. The API
 * key lives only in wp-config.php constants and is attached server-side -
 * it never reaches the browser.
 */
class Moajam_Translate_Api_Client {

    private static function base_url() {
        return defined('MOAJAM_API_BASE_URL') ? rtrim(MOAJAM_API_BASE_URL, '/') : '';
    }

    private static function api_key() {
        return defined('MOAJAM_API_KEY') ? MOAJAM_API_KEY : '';
    }

    private static function request($method, $path, $args = []) {
        $url = self::base_url() . $path;
        $args['method']  = $method;
        $args['timeout'] = $args['timeout'] ?? 30;
        $args['headers'] = array_merge(
            ['X-API-Key' => self::api_key()],
            $args['headers'] ?? []
        );

        $response = wp_remote_request($url, $args);
        if (is_wp_error($response)) {
            return ['error' => $response->get_error_message(), 'code' => 502];
        }

        $code = wp_remote_retrieve_response_code($response);
        $body = wp_remote_retrieve_body($response);
        $data = json_decode($body, true);

        if ($code >= 400) {
            $message = is_array($data) && isset($data['detail']) ? $data['detail'] : 'Request failed';
            return ['error' => $message, 'code' => $code];
        }

        return ['data' => $data, 'code' => $code];
    }

    /**
     * Create a translation job from a file already sideloaded into WordPress's
     * own Media Library (see moajam_translate_sideload_file() in the main
     * plugin file). Render only ever receives the URL, never the file bytes.
     */
    public static function create_translation_job($fields) {
        $fields = array_filter($fields, fn($v) => $v !== null && $v !== '');
        return self::request('POST', '/api/v1/translations', [
            'headers' => ['Content-Type' => 'application/x-www-form-urlencoded'],
            'body'    => $fields,
            'timeout' => 60,
        ]);
    }

    public static function get_job($job_id) {
        return self::request('GET', '/api/v1/translations/' . rawurlencode($job_id));
    }

    public static function download_job_url($job_id) {
        return self::base_url() . '/api/v1/translations/' . rawurlencode($job_id) . '/download';
    }
}
