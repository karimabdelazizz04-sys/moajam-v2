<?php
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Thin wrapper around the FastAPI backend. The API key lives only in
 * wp-config.php constants and is attached server-side - it never reaches
 * the browser.
 */
class Moajam_Api_Client {

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

        return ['data' => $data, 'code' => $code, 'raw_body' => $body, 'response' => $response];
    }

    private static function query(array $params) {
        $params = array_filter($params, fn($v) => $v !== null && $v !== '');
        return $params ? '?' . http_build_query($params) : '';
    }

    // -------------------------------------------------------------------
    // Translation jobs
    // -------------------------------------------------------------------

    public static function create_translation_job($file_tmp_path, $file_name, $fields) {
        $boundary = wp_generate_password(24, false);
        $eol = "\r\n";
        $body = '';

        foreach ($fields as $name => $value) {
            if ($value === null || $value === '') {
                continue;
            }
            $body .= '--' . $boundary . $eol;
            $body .= 'Content-Disposition: form-data; name="' . $name . '"' . $eol . $eol;
            $body .= $value . $eol;
        }

        $body .= '--' . $boundary . $eol;
        $body .= 'Content-Disposition: form-data; name="file"; filename="' . basename($file_name) . '"' . $eol;
        $body .= 'Content-Type: application/octet-stream' . $eol . $eol;
        $body .= file_get_contents($file_tmp_path) . $eol;
        $body .= '--' . $boundary . '--' . $eol;

        return self::request('POST', '/api/v1/translations', [
            'headers' => ['Content-Type' => 'multipart/form-data; boundary=' . $boundary],
            'body'    => $body,
            'timeout' => 60,
        ]);
    }

    public static function get_job($job_id) {
        return self::request('GET', '/api/v1/translations/' . rawurlencode($job_id));
    }

    public static function list_jobs($client_email = null, $client_id = null) {
        $qs = self::query(['client_email' => $client_email, 'client_id' => $client_id]);
        return self::request('GET', '/api/v1/translations' . $qs);
    }

    public static function download_job_url($job_id) {
        return self::base_url() . '/api/v1/translations/' . rawurlencode($job_id) . '/download';
    }

    public static function fetch_job_download($job_id) {
        return self::request('GET', '/api/v1/translations/' . rawurlencode($job_id) . '/download', ['timeout' => 30]);
    }

    // -------------------------------------------------------------------
    // Portal (invoices / clients, read-only via shared API key)
    // -------------------------------------------------------------------

    public static function list_invoices($client_email = null, $client_id = null) {
        $qs = self::query(['client_email' => $client_email, 'client_id' => $client_id]);
        return self::request('GET', '/api/v1/portal/invoices' . $qs);
    }

    public static function fetch_invoice_download($invoice_id) {
        return self::request('GET', '/api/v1/portal/invoices/' . intval($invoice_id) . '/download', ['timeout' => 30]);
    }

    public static function lookup_client($email) {
        $qs = self::query(['email' => $email]);
        return self::request('GET', '/api/v1/portal/clients/lookup' . $qs);
    }
}
