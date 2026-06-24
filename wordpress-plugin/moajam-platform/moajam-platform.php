<?php
/**
 * Plugin Name: Moajam Platform
 * Description: Dashboards (Translator / Admin) for the Moajam Almaani translation backend (FastAPI on Render). Clients never log in - translators enter client details and price on their behalf.
 * Version: 2.1.0
 * Text Domain: moajam-platform
 *
 * Required constants (define in wp-config.php, NOT in this plugin or any UI field,
 * so the API key never appears in a database-readable place):
 *
 *   define('MOAJAM_API_BASE_URL', 'https://api.moajamalmaani.com');
 *   define('MOAJAM_API_KEY', 'same value as API_KEY in the backend environment');
 */

if (!defined('ABSPATH')) {
    exit;
}

define('MOAJAM_PLATFORM_DIR', plugin_dir_path(__FILE__));
define('MOAJAM_PLATFORM_URL', plugin_dir_url(__FILE__));

require_once MOAJAM_PLATFORM_DIR . 'includes/class-moajam-api-client.php';
require_once MOAJAM_PLATFORM_DIR . 'includes/dashboard-translator.php';
require_once MOAJAM_PLATFORM_DIR . 'includes/dashboard-admin.php';

/**
 * On activation: create the "Translator" role and a dedicated admin-dashboard
 * capability, so access can be granted without giving out full Administrator.
 */
function moajam_platform_activate() {
    add_role(
        'moajam_translator',
        __('Moajam Translator', 'moajam-platform'),
        [
            'read' => true,
            'moajam_access_translator_dashboard' => true,
        ]
    );

    $admin = get_role('administrator');
    if ($admin) {
        $admin->add_cap('moajam_access_translator_dashboard');
        $admin->add_cap('moajam_access_admin_dashboard');
    }
}
register_activation_hook(__FILE__, 'moajam_platform_activate');

function moajam_platform_enqueue_assets() {
    wp_enqueue_style(
        'moajam-platform',
        MOAJAM_PLATFORM_URL . 'assets/css/moajam.css',
        [],
        '2.0.0'
    );
}
add_action('wp_enqueue_scripts', 'moajam_platform_enqueue_assets');
