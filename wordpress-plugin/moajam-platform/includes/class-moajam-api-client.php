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

    private static function json_request($method, $path, $payload = null) {
        $args = ['headers' => ['Content-Type' => 'application/json']];
        if ($payload !== null) {
            $args['body'] = wp_json_encode($payload);
        }
        return self::request($method, $path, $args);
    }

    // -------------------------------------------------------------------
    // Translation jobs
    // -------------------------------------------------------------------

    /**
     * Create a translation job from a file already sitting in WordPress's own
     * Media Library (see moajam_sideload_to_media() in dashboard-translator.php).
     * Render only ever receives the URL, never the file bytes - this is the
     * whole point of keeping Render stateless.
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

    public static function list_jobs($client_email = null, $client_id = null, $created_by = null) {
        $qs = self::query(['client_email' => $client_email, 'client_id' => $client_id, 'created_by' => $created_by]);
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

    // -------------------------------------------------------------------
    // ERP: staff, projects, review, analytics, notifications
    // -------------------------------------------------------------------

    public static function list_staff() {
        return self::request('GET', '/api/v1/erp/staff');
    }

    public static function create_staff($payload) {
        return self::json_request('POST', '/api/v1/erp/staff', $payload);
    }

    public static function update_staff($staff_id, $payload) {
        return self::json_request('PATCH', '/api/v1/erp/staff/' . intval($staff_id), $payload);
    }

    public static function delete_staff($staff_id) {
        return self::request('DELETE', '/api/v1/erp/staff/' . intval($staff_id));
    }

    public static function list_projects($client_id = null) {
        $qs = self::query(['client_id' => $client_id]);
        return self::request('GET', '/api/v1/erp/projects' . $qs);
    }

    public static function create_project($payload) {
        return self::json_request('POST', '/api/v1/erp/projects', $payload);
    }

    public static function review_job($job_id, $payload) {
        return self::json_request('PATCH', '/api/v1/erp/jobs/' . rawurlencode($job_id) . '/review', $payload);
    }

    public static function analytics_summary($start_date = null, $end_date = null) {
        $qs = self::query(['start_date' => $start_date, 'end_date' => $end_date]);
        return self::request('GET', '/api/v1/erp/analytics/summary' . $qs);
    }

    public static function list_notifications($recipient, $unread_only = false) {
        $qs = self::query(['recipient' => $recipient, 'unread_only' => $unread_only ? 'true' : '']);
        return self::request('GET', '/api/v1/erp/notifications' . $qs);
    }

    public static function mark_notification_read($notification_id) {
        return self::request('POST', '/api/v1/erp/notifications/' . intval($notification_id) . '/read');
    }
}
