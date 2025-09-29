# routes.py
from flask import request, jsonify, redirect, url_for, session, render_template
import requests
from urllib.parse import urlencode
from config import logger, API_KEY, API_SECRET, SCOPES, REDIRECT_URI, APP_HANDLE, THIRD_PARTY_API_URL, GET_COMPANY_ID_URL, json
from database import db
from utils import get_shop_details, get_active_subscriptions, get_pages
from webhooks import register_subscription_webhook, register_uninstall_webhook

def install():
    shop = request.args.get('shop')
    logger.info(f"Install request received for shop: {shop}")
    
    if not shop:
        logger.error("Install request missing shop parameter")
        return jsonify({'error': 'Shop parameter is required'}), 400
    
    try:
        # Create initial shop record
        db.create_or_update_shop(shop)
        
        params = {
            'client_id': API_KEY,
            'scope': SCOPES,
            'redirect_uri': REDIRECT_URI,
            'state': 'nonce'
        }
        install_url = f'https://{shop}/admin/oauth/authorize?{urlencode(params)}'
        
        logger.info(f"Redirecting to install URL: {install_url}")
        return redirect(install_url)
        
    except Exception as e:
        logger.error(f"Error in install route for shop {shop}: {str(e)}")
        return jsonify({'error': 'Installation failed'}), 500

def callback():
    shop = request.args.get('shop')
    code = request.args.get('code')
    
    logger.info(f"OAuth callback received for shop: {shop}")
    
    if not shop or not code:
        logger.error(f"OAuth callback missing parameters - shop: {shop}, code: {bool(code)}")
        return jsonify({'error': 'Missing required parameters'}), 400

    try:
        # Get access token
        token_url = f'https://{shop}/admin/oauth/access_token'
        payload = {
            'client_id': API_KEY,
            'client_secret': API_SECRET,
            'code': code
        }
        
        logger.info(f"Requesting access token from: {token_url}")
        response = requests.post(token_url, json=payload)
        
        if response.status_code != 200:
            logger.error(f"Failed to obtain access token. Status: {response.status_code}, Response: {response.text}")
            return jsonify({'error': 'Failed to obtain access token'}), 400

        access_token = response.json().get('access_token')
        logger.info(f"Successfully obtained access token for shop: {shop}")
        
        # Get shop details
        shop_details = get_shop_details(shop, access_token)
        
        # Update shop record with all details
        update_data = {
            'access_token': access_token,
            'email': shop_details.get('email'),
            'shop_id': shop_details.get('id'),
            'shop_name': shop_details.get('name')
        }
        
        success = db.create_or_update_shop(shop, **update_data)
        
        if not success:
            logger.error(f"Failed to update shop record for: {shop}")
            return jsonify({'error': 'Failed to save shop data'}), 500
        
        logger.info(f"Successfully saved shop details for: {shop}")
        
        # Register webhooks for subscription changes and app uninstall
        webhook_registered = register_subscription_webhook(shop, access_token)
        uninstall_webhook_registered = register_uninstall_webhook(shop, access_token)
        
        if webhook_registered:
            logger.info(f"Successfully registered subscription webhook for shop: {shop}")
        else:
            logger.warning(f"Failed to register subscription webhook for shop: {shop}")
            
        if uninstall_webhook_registered:
            logger.info(f"Successfully registered uninstall webhook for shop: {shop}")
        else:
            logger.warning(f"Failed to register uninstall webhook for shop: {shop}")
        
        db.log_database_state()
        
        return redirect(url_for('check_subscription', shop=shop))
        
    except Exception as e:
        logger.error(f"Error in OAuth callback for shop {shop}: {str(e)}")
        return jsonify({'error': 'OAuth callback failed'}), 500

def check_subscription():
    shop = request.args.get('shop')
    logger.info(f"Checking subscription for shop: {shop}")
    
    try:
        shop_data = db.get_shop(shop)
        access_token = shop_data.get('access_token')
        
        if not access_token:
            logger.error(f"No access token found for shop: {shop}")
            return jsonify({'error': 'Shop not authenticated'}), 401

        # Get active subscriptions
        active_subscriptions = get_active_subscriptions(shop, access_token)
        
        if not active_subscriptions:
            logger.info(f"No active subscriptions found for shop: {shop}")
            store_handle = shop.replace('.myshopify.com', '')
            plan_selection_url = f'https://admin.shopify.com/store/{store_handle}/charges/{APP_HANDLE}/pricing_plans'
            
            return render_template('redirect_to_plans.html', url=plan_selection_url)

        # Save subscription data
        for subscription in active_subscriptions:
            db.create_or_update_subscription(shop, subscription)

        plan_name = active_subscriptions[0].get('name', 'Unknown Plan')
        logger.info(f"Active subscription found for {shop}: {plan_name}")
        
        session['shop'] = shop
        session['plan'] = plan_name
        session['email'] = shop_data.get('email', 'unknown@example.com')

        return redirect(url_for('home'))
        
    except Exception as e:
        logger.error(f"Error checking subscription for shop {shop}: {str(e)}")
        return jsonify({'error': 'Failed to check subscription'}), 500

def home():
    """Home page with embedded app handling and company ID verification"""
    # Check if this is a Shopify embedded app request
    shop = request.args.get('shop')
    host = request.args.get('host')
    hmac = request.args.get('hmac')
    
    logger.info(f"Home page accessed - Shop: {shop}, Host: {host}, HMAC: {hmac}")
    logger.info(f"Session data: {dict(session)}")
    
    # Get data from session and database
    shop_domain = session.get('shop',shop)
    plan = session.get('plan', 'No Plan Selected')
    email = session.get('email', 'No Email Provided')
    
    logger.info(f"Loading home page for shop: {shop_domain}")
    
    # Get complete shop data from database
    shop_data = db.get_shop(shop_domain)
    logger.info(f"Shop data from database: {json.dumps(shop_data, indent=2, default=str)}")
    
    if not shop_data:
        logger.error(f"No shop data found in database for: {shop_domain}")
        return redirect(url_for('install', shop=shop_domain))
    
    # Check company ID with third-party API before showing home page
    store_url = shop_data.get('store_url', shop_domain.replace('.myshopify.com', ''))
    logger.info(f"Checking company ID for store: {store_url}")
    
    try:
        company_check_response = requests.get(
            GET_COMPANY_ID_URL, 
            params={"store_url": shop_domain},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        logger.info(f"Company ID check response status: {company_check_response.status_code}")
        logger.info(f"Company ID check response: {company_check_response.text}")
        
        if company_check_response.status_code == 200:
            company_data = company_check_response.json()
            company_id = company_data.get('company_id')
            
            if company_id:
                logger.info(f"Company ID found: {company_id}")
                
                # Update shop data with company ID
                db.create_or_update_shop(shop_domain, company_id=company_id)
                
                # Show successful home page
                return render_template(
                    'dashboard.html', 
                    shop_domain=shop_domain,
                    shop_data=shop_data, 
                    email=email, 
                    plan=plan, 
                    store_url=store_url,
                    company_id=company_id
                )
            else:
                logger.warning(f"No company_id in successful response for store: {store_url}")
        
        # If we reach here, either API call failed or no company_id found
        logger.error(f"Store not found in AeroChat or API call failed for: {store_url}")
        
        return render_template(
            'store_not_found.html', 
            store_url=store_url, 
            shop_domain=shop_domain,
            status_code=company_check_response.status_code
        )
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout checking company ID for store: {store_url}")
        return render_template('connection_timeout.html')
        
    except Exception as e:
        logger.error(f"Exception checking company ID for store {store_url}: {str(e)}")
        return render_template('system_error.html')

def debug_shop(shop_domain):
    """Debug endpoint to check shop data"""
    shop_data = db.get_shop(shop_domain)
    subscription_data = db.get_active_subscription(shop_domain)
    
    return jsonify({
        'shop_data': shop_data,
        'subscription_data': subscription_data
    })

def fetch_pages():
    """Fetch all Shopify pages for a shop and save to DB with created/updated dates and store_id."""
    shop = request.args.get('shop') or session.get('shop')
    if not shop:
        return jsonify({'error': 'Missing shop parameter'}), 400

    try:
        shop_data = db.get_shop(shop)
        access_token = shop_data.get('access_token')
        if not access_token:
            return jsonify({'error': 'Shop not authenticated'}), 401

        total_saved = 0
        cursor = None
        last_store_id = None

        while True:
            result = get_pages(shop, access_token, cursor=cursor, limit=100)
            pages = result.get('pages', [])
            last_store_id = result.get('store_id') or last_store_id

            if pages:
                db.save_pages(shop, pages)
                total_saved += len(pages)

            if not result.get('has_next'):
                break
            cursor = result.get('end_cursor')

        return jsonify({'status': 'success', 'saved': total_saved, 'store_id': last_store_id}), 200
    except Exception as e:
        logger.error(f"Error fetching pages for {shop}: {str(e)}")
        return jsonify({'error': 'Failed to fetch pages'}), 500