# utils.py
import requests
import hmac
import hashlib
import base64
import json
from config import logger, API_SECRET

def get_shop_details(shop, access_token):
    """Get comprehensive shop details including email, ID, and name"""
    logger.info(f"Fetching shop details for: {shop}")
    
    try:
        graphql_url = f'https://{shop}/admin/api/2025-01/graphql.json'
        headers = {
            'Content-Type': 'application/json', 
            'X-Shopify-Access-Token': access_token
        }
        
        query = '''
        query {
            shop {
                id
                name
                email
                myshopifyDomain
                url
            }
        }
        '''
        
        response = requests.post(graphql_url, json={'query': query}, headers=headers)
        logger.info(f"Shop details API response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Failed to get shop details: {response.text}")
            return {}
            
        result = response.json()
        
        if 'errors' in result:
            logger.error(f"GraphQL errors in shop details: {result['errors']}")
            return {}
        
        shop_data = result.get('data', {}).get('shop', {})
        logger.info(f"Shop details retrieved: {json.dumps(shop_data, indent=2)}")
        
        return shop_data
        
    except Exception as e:
        logger.error(f"Exception getting shop details for {shop}: {str(e)}")
        return {}

def get_active_subscriptions(shop, access_token):
    """Get active subscriptions for a shop"""
    logger.info(f"Fetching active subscriptions for: {shop}")
    
    try:
        graphql_url = f'https://{shop}/admin/api/2025-01/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

        query = '''
        query {
  currentAppInstallation {
    activeSubscriptions {
      id
      name
      status
      createdAt
      lineItems {
        id
        plan {
          pricingDetails {
            __typename
            ... on AppRecurringPricing {
              interval
              price {
                amount
                currencyCode
              }
            }
          }
        }
      }
    }
  }
}

'''

        response = requests.post(graphql_url, json={'query': query}, headers=headers)
        logger.info(f"Subscriptions API response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Failed to get subscriptions: {response.text}")
            return []
            
        result = response.json()

        if 'errors' in result:
            logger.error(f"GraphQL errors in subscriptions: {result['errors']}")
            return []

        subscriptions = result.get('data', {}).get('currentAppInstallation', {}).get('activeSubscriptions', [])
        logger.info(f"Active subscriptions found: {len(subscriptions)}")
        
        for i, sub in enumerate(subscriptions):
            logger.info(f"Subscription {i+1}: {json.dumps(sub, indent=2)}")
        
        return subscriptions
        
    except Exception as e:
        logger.error(f"Exception getting subscriptions for {shop}: {str(e)}")
        return []

def get_pages(shop, access_token, cursor=None, limit=100):
    """Fetch pages from Shopify via GraphQL with optional pagination cursor."""
    logger.info(f"Fetching pages for: {shop}, after: {cursor}")
    try:
        graphql_url = f'https://{shop}/admin/api/2025-01/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

        query = '''
        query getPages($first: Int!, $after: String) {
          pages(first: $first, after: $after) {
            edges {
              cursor
              node {
                id
                title
                handle
                body
                createdAt
                updatedAt
                publishedAt
              }
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
          shop { id }
        }
        '''

        variables = { 'first': limit }
        if cursor:
            variables['after'] = cursor

        response = requests.post(graphql_url, json={'query': query, 'variables': variables}, headers=headers)
        logger.info(f"Pages API response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Failed to get pages: {response.text}")
            return {'pages': [], 'has_next': False, 'end_cursor': None, 'store_id': None}

        result = response.json()
        if 'errors' in result:
            logger.error(f"GraphQL errors in pages: {result['errors']}")
            return {'pages': [], 'has_next': False, 'end_cursor': None, 'store_id': None}

        data = result.get('data', {})
        edges = data.get('pages', {}).get('edges', [])
        page_info = data.get('pages', {}).get('pageInfo', {})
        shop_id = data.get('shop', {}).get('id')

        pages = []
        for edge in edges:
            node = edge.get('node', {})
            pages.append({
                'id': node.get('id'),
                'title': node.get('title'),
                'handle': node.get('handle'),
                'body': node.get('body'),
                'created_at': node.get('createdAt'),
                'updated_at': node.get('updatedAt'),
                'published_at': node.get('publishedAt'),
                'published': bool(node.get('publishedAt')),
                'store_id': shop_id,
            })

        has_next = page_info.get('hasNextPage', False)
        end_cursor = page_info.get('endCursor')

        return {'pages': pages, 'has_next': has_next, 'end_cursor': end_cursor, 'store_id': shop_id}
    except Exception as e:
        logger.error(f"Exception getting pages for {shop}: {str(e)}")
        return {'pages': [], 'has_next': False, 'end_cursor': None, 'store_id': None}

def get_articles(shop, access_token, cursor=None, limit=100):
    """Fetch articles from Shopify via GraphQL with optional pagination cursor."""
    logger.info(f"Fetching articles for: {shop}, after: {cursor}")
    try:
        graphql_url = f'https://{shop}/admin/api/2025-01/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

        query = '''
        query getArticles($first: Int!, $after: String) {
  articles(first: $first, after: $after) {
    edges {
      cursor
      node {
        id
        title
        handle
        body  # Returns the article's content as HTML
        createdAt
        updatedAt
        publishedAt
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
  shop { id }
}

        '''

        variables = { 'first': limit }
        if cursor:
            variables['after'] = cursor

        response = requests.post(graphql_url, json={'query': query, 'variables': variables}, headers=headers)
        logger.info(f"Articles API response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Failed to get articles: {response.text}")
            return {'articles': [], 'has_next': False, 'end_cursor': None, 'store_id': None}

        result = response.json()
        if 'errors' in result:
            logger.error(f"GraphQL errors in articles: {result['errors']}")
            return {'articles': [], 'has_next': False, 'end_cursor': None, 'store_id': None}

        data = result.get('data', {})
        edges = data.get('articles', {}).get('edges', [])
        page_info = data.get('articles', {}).get('pageInfo', {})
        shop_id = data.get('shop', {}).get('id')

        articles = []
        for edge in edges:
            node = edge.get('node', {})
            articles.append({
                'id': node.get('id'),
                'title': node.get('title'),
                'handle': node.get('handle'),
                'body': node.get('body'),
                'created_at': node.get('createdAt'),
                'updated_at': node.get('updatedAt'),
                'published_at': node.get('publishedAt'),
                'published': bool(node.get('publishedAt')),
                'store_id': shop_id,
            })

        has_next = page_info.get('hasNextPage', False)
        end_cursor = page_info.get('endCursor')

        return {'articles': articles, 'has_next': has_next, 'end_cursor': end_cursor, 'store_id': shop_id}
    except Exception as e:
        logger.error(f"Exception getting articles for {shop}: {str(e)}")
        return {'articles': [], 'has_next': False, 'end_cursor': None, 'store_id': None}

def get_total_pages_count(shop, access_token):
    """Get total count of pages in Shopify store"""
    logger.info(f"Getting total pages count for: {shop}")
    try:
        graphql_url = f'https://{shop}/admin/api/2025-01/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

        query = '''
        query {
          pages(first: 50) {
            edges {
              node {
                id
              }
            }
          }
        }
        '''

        response = requests.post(graphql_url, json={'query': query}, headers=headers)
        logger.info(f"Total pages count API response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Failed to get total pages count: {response.text}")
            return 0

        result = response.json()
        if 'errors' in result:
            logger.error(f"GraphQL errors in total pages count: {result['errors']}")
            return 0

        edges = result.get('data', {}).get('pages', {}).get('edges', [])
        total_count = len(edges)
        logger.info(f"Total pages count for {shop}: {total_count}")
        
        return total_count
    except Exception as e:
        logger.error(f"Exception getting total pages count for {shop}: {str(e)}")
        return 0

def get_total_articles_count(shop, access_token):
    """Get total count of articles in Shopify store"""
    logger.info(f"Getting total articles count for: {shop}")
    try:
        graphql_url = f'https://{shop}/admin/api/2025-01/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

        query = '''
        query {
          articles(first: 50) {
            edges {
              node {
                id
              }
            }
          }
        }
        '''

        response = requests.post(graphql_url, json={'query': query}, headers=headers)
        logger.info(f"Total articles count API response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Failed to get total articles count: {response.text}")
            return 0

        result = response.json()
        if 'errors' in result:
            logger.error(f"GraphQL errors in total articles count: {result['errors']}")
            return 0

        edges = result.get('data', {}).get('articles', {}).get('edges', [])
        total_count = len(edges)
        logger.info(f"Total articles count for {shop}: {total_count}")
        
        return total_count
    except Exception as e:
        logger.error(f"Exception getting total articles count for {shop}: {str(e)}")
        return 0

def get_total_products_count(shop, access_token):
    """Get total count of products in Shopify store via GraphQL"""
    logger.info(f"Getting total products count for: {shop}")
    try:
        query = '''
        query {
          productsCount(limit: null) {
            count
          }
        }
        '''
        url = f'https://{shop}/admin/api/2025-07/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }
        response = requests.post(url, json={'query': query}, headers=headers, timeout=15)
        logger.info(f"Total products count API response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Failed to get total products count: {response.text}")
            return 0

        data = response.json().get('data', {})
        count = int(data.get('productsCount', {}).get('count', 0))
        logger.info(f"Total products count for {shop}: {count}")
        return count
    except Exception as e:
        logger.error(f"Exception getting total products count for {shop}: {str(e)}")
        return 0


def get_total_collections_count(shop, access_token):
    """Get total count of collections (custom + smart) via GraphQL"""
    logger.info(f"Getting total collections count for: {shop}")
    try:
        query = '''
        query {
            collectionsCount(limit: null) {
                count
            }
            }
        '''
        url = f'https://{shop}/admin/api/2025-07/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }
        response = requests.post(url, json={'query': query}, headers=headers, timeout=15)

        if response.status_code != 200:
            logger.error(f"Failed to get collections count: {response.text}")
            return 0

        data = response.json().get('data', {})
        count = int(data.get('collectionsCount', {}).get('count', 0))
        logger.info(f"Total collections count for {shop}: {count}")
        return count
    except Exception as e:
        logger.error(f"Exception getting total collections count for {shop}: {str(e)}")
        return 0


def verify_shopify_hmac(query_params, hmac_to_verify):
    """Verify Shopify HMAC for embedded app requests"""
    try:
        # Remove hmac and signature from params
        params = {key: value for key, value in query_params.items() 
                 if key not in ['hmac', 'signature']}
        
        # Sort parameters and create query string
        sorted_params = sorted(params.items())
        query_string = '&'.join([f"{key}={value}" for key, value in sorted_params])
        
        # Calculate HMAC
        calculated_hmac = hmac.new(
            API_SECRET.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(calculated_hmac, hmac_to_verify)
    except Exception as e:
        logger.error(f"Error verifying HMAC: {str(e)}")
        return False

def get_aerochat_script_id(shop_domain):
    """
    Fetch the AeroChat script_id for a shop from the AeroChat API.
    
    :param shop_domain: merchant's shop domain, e.g. "example.myshopify.com"
    :return: script_id string or None if not found
    """
    logger.info(f"Fetching AeroChat script_id for: {shop_domain}")
    try:
        from config import THIRD_PARTY_BASE
        from urllib.parse import urlparse, parse_qs
        
        endpoint = f'{THIRD_PARTY_BASE}/chat/api/v1/get-script-url'
        response = requests.post(
            endpoint,
            json={'shop': shop_domain},
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        logger.info(f"Script ID API response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            script_url = data.get('url', '')
            
            # Extract script_id from URL
            # URL format: https://app.aerochat.ai/static/shopify-chatbox.js?script={script_key}&color={color}
            if script_url:
                parsed_url = urlparse(script_url)
                query_params = parse_qs(parsed_url.query)
                script_id = query_params.get('script', [None])[0]
                
                if script_id:
                    logger.info(f"Successfully extracted script_id: {script_id} for {shop_domain}")
                    return script_id
                else:
                    logger.warning(f"Script parameter not found in URL: {script_url}")
                    return None
            else:
                logger.warning(f"Script URL is empty")
                return None
        else:
            logger.error(f"Failed to get script_id: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Exception getting script_id for {shop_domain}: {str(e)}")
        return None

def save_aerochat_script_id(shop, access_token, script_id):
    """
    Save the AeroChat script_id as a shop metafield in Shopify.
    
    :param shop: merchant's shop domain, e.g. "example.myshopify.com"
    :param access_token: OAuth access token for that merchant
    :param script_id: unique AeroChat script id, e.g. "69dad98387e71b4e101a0167bdcbfca5"
    :return: metafield data dict or None if failed
    """
    logger.info(f"Saving AeroChat script_id metafield for: {shop}")
    try:
        url = f"https://{shop}/admin/api/2025-01/metafields.json"

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        }

        payload = {
            "metafield": {
                "namespace": "aerochat",
                "key": "script_id",
                "type": "single_line_text_field",
                "value": script_id,
                "owner_resource": "shop"
            }
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 201:
            metafield_data = response.json().get("metafield")
            logger.info(f"Successfully saved metafield for {shop}: {metafield_data.get('id')}")
            return metafield_data
        else:
            logger.error(f"Failed to save metafield for {shop}. Status: {response.status_code}, Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Exception saving metafield for {shop}: {str(e)}")
        return None