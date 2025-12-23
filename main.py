# app.py
from flask import Flask
import os
from config import logger, SECRET_KEY
from routes import install, callback, check_subscription, home, debug_shop, fetch_pages, sync_pages, sync_articles, public_dashboard, get_store_info, get_app_embed_url, api_initial_sync,connect
from webhook_routes import uninstall_webhook, subscription_webhook, customers_data_request_webhook, customers_redact_webhook, shop_redact_webhook
from flask_cors import CORS  # <-- add this
app = Flask(__name__)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_NAME'] = 'session'
app.secret_key = SECRET_KEY
CORS(app, resources={r"/*": {"origins": "*"}})
# Register routes
app.route('/install')(install)
app.route('/oauth/callback')(callback)
app.route('/check_subscription')(check_subscription)
app.route('/')(home)
app.route('/debug/shop/<shop_domain>')(debug_shop)
app.route('/fetch_pages')(fetch_pages)
app.route('/sync_pages')(sync_pages)
app.route('/sync_articles')(sync_articles)
app.route('/public_dashboard')(public_dashboard)
app.route('/api/store_info')(get_store_info)
app.route('/api/app_embed_url')(get_app_embed_url)
app.route('/api/initial_sync')(api_initial_sync)
app.route('/connect')(connect)
# Register webhook routes
app.route('/webhooks/uninstall', methods=['POST'])(uninstall_webhook)
app.route('/webhooks/subscription', methods=['POST'])(subscription_webhook)
app.route('/webhooks/customers/data_request', methods=['POST'])(customers_data_request_webhook)
app.route('/webhooks/customers/redact', methods=['POST'])(customers_redact_webhook)
app.route('/webhooks/shop/redact', methods=['POST'])(shop_redact_webhook)

if __name__ == '__main__':
    logger.info("Starting Shopify App...")
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)