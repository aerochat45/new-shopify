# webhook_routes.py
from flask import request, jsonify
import hmac
import hashlib
import base64
import requests
from config import logger, datetime, json, API_SECRET, THIRD_PARTY_API_URL
from database import db

def delete_shop_data(shop_domain):
    """Hard-delete shop and related subscriptions. Safe to comment out when not needed."""
    try:
        if not shop_domain:
            return False
        return db.delete_shop_and_subscriptions(shop_domain)
    except Exception as e:
        logger.error(f"delete_shop_data failed for {shop_domain}: {str(e)}")
        return False

def notify_third_party_unsubscribe(shop_domain):
    """Call AeroChat unsubscribe API. Safe to comment out the call site if needed."""
    try:
        if not shop_domain:
            return
        api_url = 'https://app.aerochat.ai/chat/api/v2/unsubscribe'
        payload = {'store_url': shop_domain}
        response = requests.post(api_url, json=payload, timeout=15)
        logger.info(f"Unsubscribe API status {response.status_code} for {shop_domain}")
        if response.status_code >= 400:
            logger.error(f"Unsubscribe API failed for {shop_domain}: {response.text}")
    except requests.exceptions.RequestException as api_err:
        logger.error(f"Unsubscribe API error for {shop_domain}: {str(api_err)}")
    except Exception as e:
        logger.error(f"Unexpected error calling unsubscribe API for {shop_domain}: {str(e)}")

def uninstall_webhook():
    """Handle app uninstallation webhook"""
    logger.info("App uninstall webhook received")
    
    try:
        # Verify HMAC
        hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
        data = request.get_data()
        computed_hmac = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), data, hashlib.sha256).digest()).decode()
        
        if not hmac.compare_digest(computed_hmac, hmac_header):
            logger.error("Invalid uninstall webhook HMAC verification failed")
            return jsonify({'error': 'Invalid webhook HMAC'}), 401

        webhook_data = request.json
        shop_domain = request.headers.get('X-Shopify-Shop-Domain')
        
        logger.info(f"Processing uninstall webhook for shop: {shop_domain}")
        logger.info(f"Uninstall webhook data: {json.dumps(webhook_data, indent=2)}")

        # Clean up shop data (soft-delete/mark as uninstalled)
        if shop_domain:
            # Update shop record to mark as uninstalled
            db.create_or_update_shop(shop_domain,
                                     status='uninstalled',
                                     uninstalled_at=datetime.now().isoformat())
            logger.info(f"Marked shop {shop_domain} as uninstalled")

            # Third-party unsubscribe (safe, non-blocking). Comment out next line to disable.
            notify_third_party_unsubscribe(shop_domain)

            # Optional: Hard delete data from our DB
            delete_shop_data(shop_domain)
            
            # You could also call a third-party API to handle uninstallation
            # notify_third_party_uninstall(shop_domain)
            # try:
            #     api_url = 'https://aerochat-staging.dummywebdemo.xyz/chat/api/unsubscribe'  # Replace with actual URL
            #     payload = {'store_url': shop_domain}
            #     response = requests.post(api_url, json=payload, timeout=5)  # Timeout to avoid blocking
            #     response.raise_for_status()
            #     logger.info(f"Third-party API called successfully for {shop_domain}")
            # except requests.exceptions.RequestException as api_err:
            #     logger.error(f"Third-party API call failed for {shop_domain}: {str(api_err)}")
            # Don't fail the webhook—log and proceed
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error in uninstall webhook: {str(e)}")
        return jsonify({'error': 'Uninstall webhook processing failed'}), 500

def subscription_webhook():
    logger.info("Subscription webhook received")
    
    try:
        # Verify HMAC
        hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
        data = request.get_data()
        computed_hmac = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), data, hashlib.sha256).digest()).decode()
        
        if not hmac.compare_digest(computed_hmac, hmac_header):
            logger.error("Invalid webhook HMAC verification failed")
            return jsonify({'error': 'Invalid webhook HMAC'}), 401

        webhook_data = request.json
        shop_domain = request.headers.get('X-Shopify-Shop-Domain', 'unknown.myshopify.com')
        
        logger.info(f"Processing webhook for shop: {shop_domain}")
        logger.info(f"Webhook data: {json.dumps(webhook_data, indent=2)}")

        subscription = webhook_data.get('app_subscription')
        if not subscription:
            logger.error("Missing app_subscription in webhook data")
            return jsonify({'error': 'Missing app_subscription in webhook data'}), 400

        # Get shop data from database
        shop_data = db.get_shop(shop_domain)
        logger.info(f"Shop data from database: {json.dumps(shop_data, indent=2, default=str)}")

        if not shop_data:
            logger.error(f"No shop data found for: {shop_domain}")
            # Try to create minimal shop record
            db.create_or_update_shop(shop_domain)
            shop_data = db.get_shop(shop_domain)

        # Update subscription in database
        db.create_or_update_subscription(shop_domain, subscription)

        # Prepare data for third-party API
        email = shop_data.get('email', 'support+test52@aerochat.ai')
        print(f"Email: {email}")
        store_url = shop_data.get('store_url', shop_domain.replace('.myshopify.com', ''))
        
        plan_name = subscription.get('name', 'Unknown').strip()
        
        # Extract interval from lineItems if available
        interval = 'unknown'
        line_items = subscription.get('lineItems', [])
        print(f"Line items: {line_items}")
        if line_items and len(line_items) > 0:
            plan_data = line_items[0].get('plan', {})
            if plan_data.get('__typename') == 'AppRecurringPricing':
                interval = plan_data.get('interval', 'unknown')
        if not line_items or interval == 'unknown' or not interval:
            try:
                active_sub = db.get_active_subscription(shop_domain)
                if active_sub and active_sub.get('interval'):
                    interval = active_sub.get('interval')
            except Exception as _e:
                logger.error(f"Failed to get interval from DB for {shop_domain}: {str(_e)}")

        # Normalize interval to display label
        interval_lc = (interval or '').lower()
        if interval_lc in ['every_30_days', 'monthly', 'month']:
            interval_label = 'Monthly'
        elif interval_lc in ['annual', 'yearly', 'year']:
            interval_label = 'Yearly'
        else:
            interval_label = 'Unknown'

        plan_id = f'{plan_name} | {interval_label} Plan'

        payload = {
            'email': email,
            'store_url': f'{store_url}.myshopify.com',
            'plan_id': plan_id
        }

        logger.info(f"Calling third-party API with payload: {json.dumps(payload, indent=2)}")

        # Call third-party API
        try:
            third_party_response = requests.post(THIRD_PARTY_API_URL, json=payload, timeout=10)
            
            logger.info(f"Third-party API response status: {third_party_response.status_code}")
            logger.info(f"Third-party API response body: {third_party_response.text}")
            
            if third_party_response.status_code != 200:
                logger.error(f'Third-party API call failed: Status {third_party_response.status_code}, Response: {third_party_response.text}')
            else:
                logger.info("Third-party API call successful")
                
        except requests.exceptions.Timeout:
            logger.error("Third-party API call timed out")
        except Exception as e:
            logger.error(f'Error calling third-party API: {str(e)}')

        # Log final database state
        #db.log_database_state()

        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error in subscription webhook: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def customers_data_request_webhook():
    """GDPR: customers/data_request - verify HMAC and return 200"""
    logger.info("GDPR customers/data_request webhook received")
    try:
        hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
        data = request.get_data()
        computed_hmac = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), data, hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(computed_hmac, hmac_header or ''):
            logger.error("Invalid HMAC for customers/data_request")
            return jsonify({'error': 'Invalid webhook HMAC'}), 401

        logger.info(f"customers/data_request payload: {json.dumps(request.json or {}, indent=2)}")
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"Error in customers/data_request webhook: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def customers_redact_webhook():
    """GDPR: customers/redact - verify HMAC and return 200"""
    logger.info("GDPR customers/redact webhook received")
    try:
        hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
        data = request.get_data()
        computed_hmac = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), data, hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(computed_hmac, hmac_header or ''):
            logger.error("Invalid HMAC for customers/redact")
            return jsonify({'error': 'Invalid webhook HMAC'}), 401

        logger.info(f"customers/redact payload: {json.dumps(request.json or {}, indent=2)}")
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"Error in customers/redact webhook: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def shop_redact_webhook():
    """GDPR: shop/redact - verify HMAC and return 200"""
    logger.info("GDPR shop/redact webhook received")
    try:
        hmac_header = request.headers.get('X-Shopify-Hmac-Sha256')
        data = request.get_data()
        computed_hmac = base64.b64encode(hmac.new(API_SECRET.encode('utf-8'), data, hashlib.sha256).digest()).decode()
        if not hmac.compare_digest(computed_hmac, hmac_header or ''):
            logger.error("Invalid HMAC for shop/redact")
            return jsonify({'error': 'Invalid webhook HMAC'}), 401

        logger.info(f"shop/redact payload: {json.dumps(request.json or {}, indent=2)}")
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        logger.error(f"Error in shop/redact webhook: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500