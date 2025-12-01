# routes.py
from flask import request, jsonify, redirect, url_for, session, render_template
import requests
from urllib.parse import urlencode
from config import logger, API_KEY, API_SECRET, SCOPES, REDIRECT_URI, APP_HANDLE, THIRD_PARTY_API_URL, GET_COMPANY_ID_URL, json
from database import db
from utils import get_shop_details, get_active_subscriptions, get_pages, get_articles, get_total_pages_count, get_total_articles_count, get_total_products_count, get_total_collections_count, get_aerochat_script_id, save_aerochat_script_id
from webhooks import register_subscription_webhook, register_uninstall_webhook
from datetime import datetime
import time
def install():
    shop = request.args.get('shop')
    logger.info(f"Install request received for shop: {shop}")
    
    if not shop:
        logger.error("Install request missing shop parameter")
        return jsonify({'error': 'Shop parameter is required'}), 400
    
    try:
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
        email = shop_details.get('email')
        
        # Check if email is already associated with another store
        if email:
            existing_shop = db.get_shop_by_email(email, exclude_shop_domain=shop)
            if existing_shop:
                logger.warning(f"Email {email} is already associated with another store: {existing_shop.get('shop_domain')}")
                # Best-effort: revoke the access token so the app is removed from the store immediately
                # try:
                #     revoke_url = f'https://{shop}/admin/oauth/revoke'
                #     headers = {
                #         'X-Shopify-Access-Token': access_token,
                #         'Content-Type': 'application/json'
                #     }
                #     revoke_payload = { 'client_id': API_KEY }
                #     revoke_resp = requests.post(revoke_url, json=revoke_payload, headers=headers, timeout=10)
                #     logger.info(f"Token revoke attempt status: {revoke_resp.status_code} for shop {shop}")
                # except Exception as revoke_err:
                #     logger.warning(f"Failed to revoke access token for {shop}: {str(revoke_err)}")
                return render_template('duplicate_email_error.html', 
                                     email=email, 
                                     existing_shop=existing_shop)
        
        # Update shop record with all details (only if no duplicate email found)
        update_data = {
            'access_token': access_token,
            'email': email,
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
        
        
        
        # Log installation completion
        logger.info(f"App installation completed for shop: {shop}")
        
        #db.log_database_state()
        
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
        # Small delay to allow third-party record creation to finish on first load
        time.sleep(5)

        # Ensure script_id is saved if missing (existing behavior)
        if shop_data.get('script_id') is None:
            access_token = shop_data.get('access_token')
            script_id = get_aerochat_script_id(shop_domain)
            if script_id:
                # Save as Shopify metafield
                metafield_saved = save_aerochat_script_id(shop, access_token, script_id)
                if metafield_saved:
                    logger.info(f"Successfully saved script_id metafield for shop: {shop}")
                    # Also save script_id in our database for reference
                    db.create_or_update_shop(shop, script_id=script_id)
                else:
                    logger.warning(f"Failed to save script_id metafield for shop: {shop}")
            else:
                logger.warning(f"Could not fetch script_id for shop: {shop}")

        # Retry company ID lookup a few times before showing store_not_found
        max_retries = 3
        retry_delay_seconds = 4
        last_status_code = None

        for attempt in range(1, max_retries + 1):
            logger.info(f"Company ID check attempt {attempt}/{max_retries} for store: {store_url}")

            company_check_response = requests.get(
                GET_COMPANY_ID_URL, 
                params={"store_url": shop_domain},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            last_status_code = company_check_response.status_code
            logger.info(f"Company ID check response status: {company_check_response.status_code}")
            logger.info(f"Company ID check response: {company_check_response.text}")
            
            if company_check_response.status_code == 200:
                company_data = company_check_response.json()
                company_id = company_data.get('company_id')
                
                if company_id:
                    logger.info(f"Company ID found: {company_id} on attempt {attempt}")
                    #####
                    # Update shop data with company ID
                    db.create_or_update_shop(shop_domain, company_id=company_id)
                    
                    # Check if initial sync is completed
                    initial_sync_completed = shop_data.get('initial_sync_completed', False)
                    logger.info(f"Initial sync status for {shop_domain}: {initial_sync_completed}")
                    
                    # Get counts for dashboard
                    pages_synced = db.get_pages_count(shop_domain)
                    blogs_synced = db.get_articles_count(shop_domain)
                    products_count = db.get_products_count(shop_domain)
                    collections_count = db.get_collections_count(shop_domain)
                    
                    # Get total counts from Shopify store
                    access_token = shop_data.get('access_token')
                    pages_total = get_total_pages_count(shop_domain, access_token) if access_token else 0
                    blogs_total = get_total_articles_count(shop_domain, access_token) if access_token else 0
                    
                    # Call autologin API and redirect to public page
                    try:
                        autologin_response = requests.post(
                            'https://app.aerochat.ai/api/autologin',
                            json={'company_id': company_id},
                            headers={'Content-Type': 'application/json'},
                            timeout=10
                        )
                        
                        if autologin_response.status_code == 200:
                            autologin_data = autologin_response.json()
                            if autologin_data.get('status') and autologin_data.get('auto_login_link'):
                                logger.info(f"Autologin successful for company_id: {company_id}")
                                
                                # Store shop info in session for the public dashboard
                                session['public_shop_domain'] = shop_domain
                                session['public_store_name'] = shop_data.get('shop_name', store_url)
                                session['public_company_id'] = company_id
                                session['public_store_url'] = store_url
                                
                                # Redirect to the autologin link (without adding parameters)
                                return redirect(autologin_data['auto_login_link'])
                            else:
                                logger.error(f"Autologin API returned invalid response: {autologin_data}")
                        else:
                            logger.error(f"Autologin API failed with status: {autologin_response.status_code}")
                            
                    except Exception as e:
                        logger.error(f"Error calling autologin API: {str(e)}")
                    
                    # Fallback to dashboard if autologin fails
                    return render_template(
                        'dashboard.html', 
                        shop_domain=shop_domain,
                        shop_data=shop_data, 
                        email=email, 
                        plan=plan, 
                        store_url=store_url,
                        company_id=company_id,
                        pages_synced=pages_synced,
                        pages_total=pages_total,
                        blogs_synced=blogs_synced,
                        blogs_total=blogs_total,
                        products_count=products_count,
                        collections_count=collections_count,
                        initial_sync_completed=initial_sync_completed
                    )
                else:
                    logger.warning(f"No company_id in successful response for store: {store_url} on attempt {attempt}")
            else:
                logger.warning(f"Company ID API did not return 200 for store: {store_url} on attempt {attempt}")

            # If not the last attempt, wait briefly and try again
            if attempt < max_retries:
                logger.info(f"Retrying company ID lookup for {store_url} after {retry_delay_seconds} seconds")
                time.sleep(retry_delay_seconds)
        
        # If we reach here, either API calls failed or no company_id found after retries
        logger.error(f"Store not found in AeroChat or API call failed after {max_retries} attempts for: {store_url}")
        
        return render_template(
            'store_not_found.html', 
            store_url=store_url, 
            shop_domain=shop_domain,
            status_code=last_status_code
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

        company_id = db.get_shop(shop).get('company_id')
        sync_time = datetime.utcnow()

        all_ids = []
        while True:
            result = get_pages(shop, access_token, cursor=cursor, limit=100)
            pages = result.get('pages', [])
            last_store_id = result.get('store_id') or last_store_id

            if pages:
                # attach company_id to each page
                for p in pages:
                    if 'company_id' not in p:
                        p['company_id'] = company_id
                db.save_pages(shop, pages, company_id=company_id, sync_time=sync_time)
                total_saved += len(pages)
                all_ids.extend([str(p.get('id')) for p in pages])

            if not result.get('has_next'):
                break
            cursor = result.get('end_cursor')

        # delete pages not present anymore
        db.delete_pages_not_in_ids(shop, all_ids)

        return jsonify({'status': 'success', 'saved': total_saved, 'store_id': last_store_id, 'deleted_missing': True}), 200
    except Exception as e:
        logger.error(f"Error fetching pages for {shop}: {str(e)}")
        return jsonify({'error': 'Failed to fetch pages'}), 500

def _third_party_pages_base_url():
    try:
        return os.getenv('THIRD_PARTY_BASE')
    except Exception as e:
        logger.error(f"Failed to compute third-party base URL: {str(e)}")
        return None
import os
def _call_third_party_pages_bulk(company_id, pages, prev_sync_time=None):
    try:
        base =  os.getenv('THIRD_PARTY_BASE')
        print(base)
        if not base:
            return
        url = f"{base}/chat/api/v2/pages"
        payload = {
            'company_id': company_id,
            'pages': [
                {
                    'id': p.get('id'),
                    'title': p.get('title'),
                    'handle': p.get('handle'),
                    'body': p.get('body') or p.get('body_html'),
                    'created_at': p.get('created_at'),
                    'updated_at': p.get('updated_at'),
                    'published_at': p.get('published_at'),
                    'published': p.get('published')
                }
                for p in pages
            ],
            'previous_sync_time': prev_sync_time
        }
        r = requests.post(url, json=payload, timeout=20)
        logger.info(f"Third-party pages bulk sync status:{r} and {r.status_code}")
    except Exception as e:
        logger.error(f"Third-party pages bulk sync failed: {str(e)}")

def _call_third_party_page_delete(company_id, page_id):
    try:
        base = _third_party_pages_base_url()
        if not base:
            return
        url = f"{base}/chat/api/v2/pages"
        payload = {
            'action': 'delete',
            'company_id': company_id,
            'page': { 'id': page_id }
        }
        r = requests.post(url, json=payload, timeout=10)
        logger.info(f"Third-party pages delete status: {r.status_code} for id {page_id}")
    except Exception as e:
        logger.error(f"Third-party pages delete failed for {page_id}: {str(e)}")

def sync_pages():
    """Sync Shopify pages: upsert created/edited and delete removed pages. Adds company_id, last_sync_time, keeps chunk_ids."""
    shop = request.args.get('shop') or session.get('shop')
    if not shop:
        return jsonify({'error': 'Missing shop parameter'}), 400

    try:
        shop_data = db.get_shop(shop)
        access_token = shop_data.get('access_token')
        if not access_token:
            return jsonify({'error': 'Shop not authenticated'}), 401

        company_id = shop_data.get('company_id')
        sync_time = datetime.utcnow()
        total_saved = 0
        cursor = None
        all_ids = []

        existing_meta = db.get_pages_meta_for_shop(shop)
        existing_ids_before = set(existing_meta.keys())

        bulk_pages = []
        previous_sync_time = db.get_previous_pages_sync_time(shop)
        while True:
            result = get_pages(shop, access_token, cursor=cursor, limit=100)
            pages = result.get('pages', [])
            if pages:
                upsert_batch = []
                for p in pages:
                    p['company_id'] = company_id
                    pid = str(p.get('id'))
                    prev = existing_meta.get(pid)
                    # preserve existing chunk_ids by not overwriting when unchanged
                    if prev and prev.get('chunk_ids') is not None:
                        p['chunk_ids'] = prev['chunk_ids']
                    upsert_batch.append(p)
                    bulk_pages.append(p)

                if upsert_batch:
                    db.save_pages(shop, upsert_batch, company_id=company_id, sync_time=sync_time)
                    total_saved += len(upsert_batch)
                all_ids.extend([str(p.get('id')) for p in pages])
            if not result.get('has_next'):
                break
            cursor = result.get('end_cursor')

        # Bulk third-party sync for all fetched pages (create/update detection is handled on their side)
        if bulk_pages:
            prev_sync_iso = previous_sync_time.isoformat() if previous_sync_time else None
            _call_third_party_pages_bulk(company_id, bulk_pages, prev_sync_time=prev_sync_iso)

        # Determine deletions (anything existing not in fetched ids)
        to_delete_ids = list(existing_ids_before - set(all_ids))
        # Call third-party delete for each, before DB delete
        if to_delete_ids:
            # We need minimal page info to send to third-party; fetch rows first
            # Use a simple query via helper
            try:
                # Inline helper to fetch Page rows by ids without adding new public API
                from sqlalchemy.orm import Session
            except Exception:
                pass
        # Simpler approach: build minimal payloads from ids
        for pid in to_delete_ids:
            _call_third_party_page_delete(company_id, pid)

        deleted_count = db.delete_pages_not_in_ids(shop, all_ids)

        # Get updated counts after sync
        synced_count = db.get_pages_count(shop)
        total_count = get_total_pages_count(shop, access_token)

        return jsonify({
            'status': 'success', 
            'saved': total_saved, 
            'deleted': deleted_count, 
            'last_sync_time': sync_time.isoformat(),
            'synced_count': synced_count,
            'total_count': total_count
        }), 200
    except Exception as e:
        logger.error(f"Error syncing pages for {shop}: {str(e)}")
        return jsonify({'error': 'Failed to sync pages'}), 500

def _call_third_party_articles_bulk(company_id, articles, prev_sync_time=None):
    try:
        base = os.getenv('THIRD_PARTY_BASE')
        if not base:
            return
        url = f"{base}/chat/api/v2/articles"
        payload = {
            'company_id': company_id,
            'articles': [
                {
                    'id': a.get('id'),
                    'title': a.get('title'),
                    'handle': a.get('handle'),
                    'body': a.get('body') or a.get('body_html'),
                    'created_at': a.get('created_at'),
                    'updated_at': a.get('updated_at'),
                    'published_at': a.get('published_at'),
                    'published': a.get('published')
                }
                for a in articles
            ],
            'previous_sync_time': prev_sync_time
        }
        r = requests.post(url, json=payload, timeout=20)
        logger.info(f"Third-party articles bulk sync status:{r} and {r.status_code}")
    except Exception as e:
        logger.error(f"Third-party articles bulk sync failed: {str(e)}")

def _call_third_party_article_delete(company_id, article_id):
    try:
        base = os.getenv('THIRD_PARTY_BASE')
        if not base:
            return
        url = f"{base}/chat/api/v2/articles"
        payload = {
            'action': 'delete',
            'company_id': company_id,
            'article': { 'id': article_id }
        }
        r = requests.post(url, json=payload, timeout=10)
        logger.info(f"Third-party articles delete status: {r.status_code} for id {article_id}")
    except Exception as e:
        logger.error(f"Third-party articles delete failed for {article_id}: {str(e)}")

def sync_articles():
    """Sync Shopify articles: upsert created/edited and delete removed articles. Adds company_id, last_sync_time, keeps chunk_ids."""
    shop = request.args.get('shop') or session.get('shop')
    if not shop:
        return jsonify({'error': 'Missing shop parameter'}), 400

    try:
        shop_data = db.get_shop(shop)
        access_token = shop_data.get('access_token')
        if not access_token:
            return jsonify({'error': 'Shop not authenticated'}), 401

        company_id = shop_data.get('company_id')
        sync_time = datetime.utcnow()
        total_saved = 0
        cursor = None
        all_ids = []

        existing_meta = db.get_articles_meta_for_shop(shop)
        existing_ids_before = set(existing_meta.keys())

        bulk_articles = []
        previous_sync_time = db.get_previous_articles_sync_time(shop)
        while True:
            result = get_articles(shop, access_token, cursor=cursor, limit=100)
            articles = result.get('articles', [])
            if articles:
                upsert_batch = []
                for a in articles:
                    a['company_id'] = company_id
                    aid = str(a.get('id'))
                    prev = existing_meta.get(aid)
                    # preserve existing chunk_ids by not overwriting when unchanged
                    if prev and prev.get('chunk_ids') is not None:
                        a['chunk_ids'] = prev['chunk_ids']
                    upsert_batch.append(a)
                    bulk_articles.append(a)

                if upsert_batch:
                    db.save_articles(shop, upsert_batch, company_id=company_id, sync_time=sync_time)
                    total_saved += len(upsert_batch)
                all_ids.extend([str(a.get('id')) for a in articles])
            if not result.get('has_next'):
                break
            cursor = result.get('end_cursor')

        # Bulk third-party sync for all fetched articles (create/update detection is handled on their side)
        if bulk_articles:
            prev_sync_iso = previous_sync_time.isoformat() if previous_sync_time else None
            _call_third_party_articles_bulk(company_id, bulk_articles, prev_sync_time=prev_sync_iso)

        # Determine deletions (anything existing not in fetched ids)
        to_delete_ids = list(existing_ids_before - set(all_ids))
        # Call third-party delete for each, before DB delete
        for aid in to_delete_ids:
            _call_third_party_article_delete(company_id, aid)

        deleted_count = db.delete_articles_not_in_ids(shop, all_ids)

        # Get updated counts after sync
        synced_count = db.get_articles_count(shop)
        total_count = get_total_articles_count(shop, access_token)

        return jsonify({
            'status': 'success', 
            'saved': total_saved, 
            'deleted': deleted_count, 
            'last_sync_time': sync_time.isoformat(),
            'synced_count': synced_count,
            'total_count': total_count
        }), 200
    except Exception as e:
        logger.error(f"Error syncing articles for {shop}: {str(e)}")
        return jsonify({'error': 'Failed to sync articles'}), 500

def initial_sync_pages_and_articles(shop, access_token, company_id):
    """Perform initial sync of pages and articles during app installation. This is called only once."""
    logger.info(f"Starting initial sync for shop: {shop}")
    
    try:
        sync_time = datetime.utcnow()
        pages_saved = 0
        articles_saved = 0
        sync_errors = []
        
        # Sync pages with error handling
        logger.info(f"Syncing pages for {shop}")
        cursor = None
        all_page_ids = []
        page_sync_attempts = 0
        max_page_attempts = 3
        
        while True:
            try:
                result = get_pages(shop, access_token, cursor=cursor, limit=100)
                pages = result.get('pages', [])
                
                if pages:
                    # Add company_id to each page
                    for p in pages:
                        p['company_id'] = company_id
                    
                    # Save pages to database with retry logic
                    db_success = False
                    for attempt in range(max_page_attempts):
                        try:
                            db.save_pages(shop, pages, company_id=company_id, sync_time=sync_time)
                            db_success = True
                            break
                        except Exception as db_error:
                            logger.warning(f"Database save attempt {attempt + 1} failed for pages: {str(db_error)}")
                            if attempt == max_page_attempts - 1:
                                sync_errors.append(f"Failed to save pages after {max_page_attempts} attempts: {str(db_error)}")
                    
                    if db_success:
                        pages_saved += len(pages)
                        all_page_ids.extend([str(p.get('id')) for p in pages])
                        
                        # Call third-party API for pages with timeout handling
                        try:
                            _call_third_party_pages_bulk(company_id, pages, prev_sync_time=None)
                        except Exception as api_error:
                            logger.warning(f"Third-party API call failed for pages: {str(api_error)}")
                            sync_errors.append(f"Third-party API error for pages: {str(api_error)}")
                
                if not result.get('has_next'):
                    break
                cursor = result.get('end_cursor')
                
            except Exception as page_error:
                logger.error(f"Error syncing pages batch for {shop}: {str(page_error)}")
                sync_errors.append(f"Pages sync error: {str(page_error)}")
                # Continue with next batch or break if critical
                if page_sync_attempts >= max_page_attempts:
                    logger.error(f"Max page sync attempts reached for {shop}")
                    break
                page_sync_attempts += 1
        
        # Sync articles with error handling
        logger.info(f"Syncing articles for {shop}")
        cursor = None
        all_article_ids = []
        article_sync_attempts = 0
        max_article_attempts = 3
        
        while True:
            try:
                result = get_articles(shop, access_token, cursor=cursor, limit=100)
                articles = result.get('articles', [])
                
                if articles:
                    # Add company_id to each article
                    for a in articles:
                        a['company_id'] = company_id
                    
                    # Save articles to database with retry logic
                    db_success = False
                    for attempt in range(max_article_attempts):
                        try:
                            db.save_articles(shop, articles, company_id=company_id, sync_time=sync_time)
                            db_success = True
                            break
                        except Exception as db_error:
                            logger.warning(f"Database save attempt {attempt + 1} failed for articles: {str(db_error)}")
                            if attempt == max_article_attempts - 1:
                                sync_errors.append(f"Failed to save articles after {max_article_attempts} attempts: {str(db_error)}")
                    
                    if db_success:
                        articles_saved += len(articles)
                        all_article_ids.extend([str(a.get('id')) for a in articles])
                        
                        # Call third-party API for articles with timeout handling
                        try:
                            #_call_third_party_articles_bulk(company_id, articles, prev_sync_time=None)
                            logger.info("Skipping third-party API call for articles")
                        except Exception as api_error:
                            logger.warning(f"Third-party API call failed for articles: {str(api_error)}")
                            sync_errors.append(f"Third-party API error for articles: {str(api_error)}")
                
                if not result.get('has_next'):
                    break
                cursor = result.get('end_cursor')
                
            except Exception as article_error:
                logger.error(f"Error syncing articles batch for {shop}: {str(article_error)}")
                sync_errors.append(f"Articles sync error: {str(article_error)}")
                # Continue with next batch or break if critical
                if article_sync_attempts >= max_article_attempts:
                    logger.error(f"Max article sync attempts reached for {shop}")
                    break
                article_sync_attempts += 1
        
        # Mark initial sync as completed even if there were some errors
        # This prevents infinite retry loops during installation
        try:
            db.create_or_update_shop(shop, initial_sync_completed=True)
        except Exception as update_error:
            logger.error(f"Failed to mark initial sync as completed: {str(update_error)}")
            sync_errors.append(f"Failed to update sync status: {str(update_error)}")
        
        # Log results
        if sync_errors:
            logger.warning(f"Initial sync completed with errors for {shop}: {pages_saved} pages, {articles_saved} articles. Errors: {sync_errors}")
        else:
            logger.info(f"Initial sync completed successfully for {shop}: {pages_saved} pages, {articles_saved} articles")
        
        return {
            'success': True,
            'pages_saved': pages_saved,
            'articles_saved': articles_saved,
            'sync_time': sync_time.isoformat(),
            'errors': sync_errors if sync_errors else None
        }
        
    except Exception as e:
        logger.error(f"Critical error during initial sync for {shop}: {str(e)}")
        # Still mark as completed to prevent retry loops
        try:
            db.create_or_update_shop(shop, initial_sync_completed=True)
        except:
            pass
        return {
            'success': False,
            'error': str(e),
            'pages_saved': 0,
            'articles_saved': 0
        }

def public_dashboard():
    """Public dashboard page that shows the same content as regular dashboard but without store info"""
    # Get company_id from URL (this will be provided by AeroChat)
    company_id = request.args.get('company_id')
    
    logger.info(f"Public dashboard accessed - Company ID: {company_id}")
    
    if not company_id:
        logger.error("Public dashboard accessed without company_id")
        return jsonify({'error': 'Company ID is required'}), 400
    
    # Find shop data by company_id
    shop_data = db.get_shop_by_company_id(company_id)
    
    if not shop_data:
        logger.error(f"No shop data found for company_id: {company_id}")
        return jsonify({'error': 'Shop not found for this company'}), 404
    
    shop_domain = shop_data.get('store_url', 'unknown')
    store_name = shop_data.get('shop_name', 'Your Store')
    
    # Get counts for dashboard
    pages_synced = db.get_pages_count(shop_domain)
    blogs_synced = db.get_articles_count(shop_domain)
    products_count = db.get_products_count(shop_domain)
    collections_count = db.get_collections_count(shop_domain)
    
    # Get total counts from Shopify store if we have access token
    pages_total = 0
    blogs_total = 0
    if shop_data.get('access_token'):
        pages_total = get_total_pages_count(shop_domain, shop_data.get('access_token'))
        blogs_total = get_total_articles_count(shop_domain, shop_data.get('access_token'))
    
    return render_template(
        'public_dashboard.html',
        company_id=company_id,
        shop_domain=shop_domain,
        store_name=store_name,
        pages_synced=pages_synced,
        pages_total=pages_total,
        blogs_synced=blogs_synced,
        blogs_total=blogs_total,
        products_count=products_count,
        collections_count=collections_count
    )

def get_store_info():
    """API endpoint to get store information by company_id"""
    company_id = request.args.get('company_id')
    
    if not company_id:
        return jsonify({'error': 'Company ID is required'}), 400
    
    try:
        shop_data = db.get_shop_by_company_id(company_id)
        
        if not shop_data:
            return jsonify({'error': 'Shop not found for this company'}), 404
        
        # Get counts for dashboard
        shop_domain = shop_data.get('store_url', 'unknown')
        shop_domain = shop_domain+'.myshopify.com'
        pages_synced = db.get_pages_count(shop_domain)
        blogs_synced = db.get_articles_count(shop_domain)
        # For products and collections, return LIVE counts from Shopify (not DB)
        access_token = shop_data.get('access_token')
        products_count = get_total_products_count(shop_domain, access_token) if access_token else 0
        collections_count = get_total_collections_count(shop_domain, access_token) if access_token else 0
        
        # Get total counts from Shopify store if we have access token
        pages_total = 0
        blogs_total = 0
        if access_token:
            pages_total = get_total_pages_count(shop_domain, access_token)
            blogs_total = get_total_articles_count(shop_domain, access_token)
        
        return jsonify({
            'status': 'success',
            'data': {
                'company_id': company_id,
                'shop_domain': shop_domain,
                'store_name': shop_data.get('shop_name', 'Your Store'),
                'store_url': shop_data.get('store_url', ''),
                'pages_synced': pages_synced,
                'pages_total': pages_total,
                'blogs_synced': blogs_synced,
                'blogs_total': blogs_total,
                'products_count': products_count,
                'collections_count': collections_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting store info for company_id {company_id}: {str(e)}")
        return jsonify({'error': 'Failed to get store information'}), 500

def get_app_embed_url():
    """API endpoint to get Shopify app embed block enable URL"""
    company_id = request.args.get('company_id')
    
    if not company_id:
        return jsonify({'error': 'Company ID is required'}), 400
    
    try:
        shop_data = db.get_shop_by_company_id(company_id)
        
        if not shop_data:
            return jsonify({'error': 'Shop not found for this company'}), 404
        
        shop_domain = shop_data.get('shop_domain')
        if not shop_domain:
            return jsonify({'error': 'Shop domain not found'}), 404
        
        # Extract store handle from shop domain (remove .myshopify.com)
        store_handle = shop_domain.replace('.myshopify.com', '')
        
        # Generate the app embed block enable URL
        # Format: https://admin.shopify.com/store/{store_handle}/themes/current/editor?context=apps&activateAppId={APP_API_KEY}/{APP_EMBED_HANDLE}
        app_embed_url = f"https://admin.shopify.com/store/{store_handle}/themes/current/editor?context=apps&activateAppId={API_KEY}/aerochat"
        
        logger.info(f"Generated app embed URL for company_id {company_id}: {app_embed_url}")
        
        return jsonify({
            'status': 'success',
            'data': {
                'company_id': company_id,
                'shop_domain': shop_domain,
                'store_handle': store_handle,
                'app_embed_url': app_embed_url,
                'redirect_url': app_embed_url
            }
        })
        
    except Exception as e:
        logger.error(f"Error generating app embed URL for company_id {company_id}: {str(e)}")
        return jsonify({'error': 'Failed to generate app embed URL'}), 500

def api_initial_sync():
    """API endpoint to trigger initial sync of pages and articles. Only runs if initial_sync_completed is False."""
    shop = request.args.get('shop') or session.get('shop')
    
    if not shop:
        return jsonify({'error': 'Missing shop parameter'}), 400
    
    try:
        # Get shop data
        shop_data = db.get_shop(shop)
        if not shop_data:
            return jsonify({'error': 'Shop not found'}), 404
        
        # Check if initial sync is already completed
        initial_sync_completed = shop_data.get('initial_sync_completed', False)
        
        if initial_sync_completed:
            logger.info(f"Initial sync already completed for shop: {shop}")
            return jsonify({
                'status': 'success',
                'message': 'Initial sync already completed',
                'initial_sync_completed': True,
                'pages_saved': 0,
                'articles_saved': 0
            }), 200
        
        # Get access token
        access_token = shop_data.get('access_token')
        if not access_token:
            return jsonify({'error': 'Shop not authenticated'}), 401
        
        # Get company_id
        company_id = shop_data.get('company_id')
        if not company_id:
            # Try to get company_id from third-party API
            try:
                company_check_response = requests.get(
                    GET_COMPANY_ID_URL, 
                    params={"store_url": shop},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if company_check_response.status_code == 200:
                    company_data = company_check_response.json()
                    company_id = company_data.get('company_id')
                    if company_id:
                        # Update shop with company_id
                        db.create_or_update_shop(shop, company_id=company_id)
                        logger.info(f"Retrieved and saved company_id: {company_id} for shop: {shop}")
                else:
                    return jsonify({'error': 'Failed to get company_id from third-party API'}), 500
            except Exception as e:
                logger.error(f"Failed to get company_id for initial sync: {str(e)}")
                return jsonify({'error': 'Failed to get company_id'}), 500
        
        # Perform initial sync
        logger.info(f"Starting initial sync via API for shop: {shop}")
        sync_result = initial_sync_pages_and_articles(shop, access_token, company_id)
        
        if sync_result['success']:
            logger.info(f"Initial sync completed successfully via API for {shop}: {sync_result['pages_saved']} pages, {sync_result['articles_saved']} articles")
            
            response_data = {
                'status': 'success',
                'message': 'Initial sync completed successfully',
                'initial_sync_completed': True,
                'pages_saved': sync_result['pages_saved'],
                'articles_saved': sync_result['articles_saved'],
                'sync_time': sync_result['sync_time']
            }
            
            # Include errors if any
            if sync_result.get('errors'):
                response_data['warnings'] = sync_result['errors']
            
            return jsonify(response_data), 200
        else:
            logger.error(f"Initial sync failed via API for {shop}: {sync_result.get('error', 'Unknown error')}")
            return jsonify({
                'status': 'error',
                'message': 'Initial sync failed',
                'error': sync_result.get('error', 'Unknown error'),
                'initial_sync_completed': False
            }), 500
        
    except Exception as e:
        logger.error(f"Error in initial sync API for shop {shop}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error during initial sync',
            'error': str(e),
            'initial_sync_completed': False
        }), 500
