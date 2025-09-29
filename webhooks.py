# webhooks.py
import requests
from flask import request, jsonify
from config import logger, datetime, json, API_SECRET, REDIRECT_URI
from database import db

def register_uninstall_webhook(shop, access_token):
    """Register webhook for app uninstallation"""
    logger.info(f"Registering uninstall webhook for: {shop}")
    
    try:
        graphql_url = f'https://{shop}/admin/api/2025-01/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

        # Check if uninstall webhook already exists
        check_query = '''
        query {
            webhookSubscriptions(first: 10, topics: [APP_UNINSTALLED]) {
                edges {
                    node {
                        id
                        callbackUrl
                    }
                }
            }
        }
        '''

        response = requests.post(graphql_url, json={'query': check_query}, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            existing_webhooks = result.get('data', {}).get('webhookSubscriptions', {}).get('edges', [])
            
            webhook_url = f"{REDIRECT_URI.replace('/oauth/callback', '/webhooks/uninstall')}"
            
            # Check if our webhook already exists
            for webhook_edge in existing_webhooks:
                webhook = webhook_edge.get('node', {})
                if webhook.get('callbackUrl') == webhook_url:
                    logger.info(f"Uninstall webhook already exists for {shop}: {webhook.get('id')}")
                    return True

        # Create new uninstall webhook
        mutation = '''
        mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
            webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
                webhookSubscription {
                    id
                    callbackUrl
                    topic
                }
                userErrors {
                    field
                    message
                }
            }
        }
        '''

        variables = {
            'topic': 'APP_UNINSTALLED',
            'webhookSubscription': {
                'callbackUrl': webhook_url,
                'format': 'JSON'
            }
        }

        logger.info(f"Creating uninstall webhook with URL: {webhook_url}")
        
        response = requests.post(
            graphql_url, 
            json={'query': mutation, 'variables': variables}, 
            headers=headers
        )

        if response.status_code != 200:
            logger.error(f"Failed to create uninstall webhook: {response.text}")
            return False

        result = response.json()
        
        if 'errors' in result:
            logger.error(f"GraphQL errors creating uninstall webhook: {result['errors']}")
            return False

        webhook_data = result.get('data', {}).get('webhookSubscriptionCreate', {})
        user_errors = webhook_data.get('userErrors', [])
        
        if user_errors:
            logger.error(f"User errors creating uninstall webhook: {user_errors}")
            return False

        webhook_subscription = webhook_data.get('webhookSubscription')
        if webhook_subscription:
            logger.info(f"Successfully created uninstall webhook: {webhook_subscription}")
            return True
        else:
            logger.error("No uninstall webhook subscription returned in response")
            return False

    except Exception as e:
        logger.error(f"Exception registering uninstall webhook for {shop}: {str(e)}")
        return False

def register_subscription_webhook(shop, access_token):
    """Register webhook for subscription changes"""
    logger.info(f"Registering subscription webhook for: {shop}")
    
    try:
        graphql_url = f'https://{shop}/admin/api/2025-01/graphql.json'
        headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

        # First, check if webhook already exists
        check_query = '''
        query {
            webhookSubscriptions(first: 10, topics: [APP_SUBSCRIPTIONS_UPDATE]) {
                edges {
                    node {
                        id
                        callbackUrl
                    }
                }
            }
        }
        '''

        response = requests.post(graphql_url, json={'query': check_query}, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            existing_webhooks = result.get('data', {}).get('webhookSubscriptions', {}).get('edges', [])
            
            webhook_url = f"{REDIRECT_URI.replace('/oauth/callback', '/webhooks/subscription')}"
            
            # Check if our webhook already exists
            for webhook_edge in existing_webhooks:
                webhook = webhook_edge.get('node', {})
                if webhook.get('callbackUrl') == webhook_url:
                    logger.info(f"Webhook already exists for {shop}: {webhook.get('id')}")
                    return True

        # Create new webhook if it doesn't exist
        mutation = '''
        mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
            webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
                webhookSubscription {
                    id
                    callbackUrl
                    topic
                }
                userErrors {
                    field
                    message
                }
            }
        }
        '''

        variables = {
            'topic': 'APP_SUBSCRIPTIONS_UPDATE',
            'webhookSubscription': {
                'callbackUrl': webhook_url,
                'format': 'JSON'
            }
        }

        logger.info(f"Creating webhook with URL: {webhook_url}")
        
        response = requests.post(
            graphql_url, 
            json={'query': mutation, 'variables': variables}, 
            headers=headers
        )

        logger.info(f"Webhook creation response status: {response.status_code}")
        logger.info(f"Webhook creation response: {response.text}")

        if response.status_code != 200:
            logger.error(f"Failed to create webhook: {response.text}")
            return False

        result = response.json()
        
        if 'errors' in result:
            logger.error(f"GraphQL errors creating webhook: {result['errors']}")
            return False

        webhook_data = result.get('data', {}).get('webhookSubscriptionCreate', {})
        user_errors = webhook_data.get('userErrors', [])
        
        if user_errors:
            logger.error(f"User errors creating webhook: {user_errors}")
            return False

        webhook_subscription = webhook_data.get('webhookSubscription')
        if webhook_subscription:
            logger.info(f"Successfully created webhook: {webhook_subscription}")
            return True
        else:
            logger.error("No webhook subscription returned in response")
            return False

    except Exception as e:
        logger.error(f"Exception registering webhook for {shop}: {str(e)}")
        return False