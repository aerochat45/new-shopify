# database.py
from threading import Lock
from config import logger, datetime, json

# Enhanced in-memory database with table-like structure
class ShopifyAppDatabase:
    def __init__(self):
        self.shops_table = {}  # Main shops table
        self.subscriptions_table = {}  # Subscriptions table
        self.lock = Lock()

    def create_or_update_shop(self, shop_domain, **kwargs):
        """Create or update shop record with all details"""
        with self.lock:
            try:
                if shop_domain not in self.shops_table:
                    self.shops_table[shop_domain] = {
                        'shop_domain': shop_domain,
                        'shop_id': None,
                        'shop_name': None,
                        'email': None,
                        'access_token': None,
                        'store_url': shop_domain.replace('.myshopify.com', ''),
                        'company_id': None,
                        'status': 'active',
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }
                    logger.info(f"Created new shop record for: {shop_domain}")
                
                # Update with provided data
                for key, value in kwargs.items():
                    if value is not None:
                        self.shops_table[shop_domain][key] = value
                
                self.shops_table[shop_domain]['updated_at'] = datetime.now().isoformat()
                
                logger.info(f"Updated shop record for {shop_domain}: {kwargs}")
                return True
                
            except Exception as e:
                logger.error(f"Error creating/updating shop {shop_domain}: {str(e)}")
                return False

    def get_shop(self, shop_domain):
        """Get complete shop record"""
        with self.lock:
            shop_data = self.shops_table.get(shop_domain, {})
            logger.info(f"Retrieved shop data for {shop_domain}: {bool(shop_data)}")
            return shop_data

    def create_or_update_subscription(self, shop_domain, subscription_data):
        """Create or update subscription record"""
        with self.lock:
            try:
                if shop_domain not in self.subscriptions_table:
                    self.subscriptions_table[shop_domain] = {}
                
                subscription_id = subscription_data.get('id', 'unknown')
                self.subscriptions_table[shop_domain][subscription_id] = {
                    'subscription_id': subscription_id,
                    'shop_domain': shop_domain,
                    'name': subscription_data.get('name'),
                    'status': subscription_data.get('status'),
                    'interval': subscription_data.get('interval'),
                    'price': subscription_data.get('price'),
                    'created_at': subscription_data.get('created_at'),
                    'updated_at': datetime.now().isoformat()
                }
                
                logger.info(f"Updated subscription for {shop_domain}: {subscription_data}")
                return True
                
            except Exception as e:
                logger.error(f"Error updating subscription for {shop_domain}: {str(e)}")
                return False

    def get_active_subscription(self, shop_domain):
        """Get active subscription for a shop"""
        with self.lock:
            shop_subscriptions = self.subscriptions_table.get(shop_domain, {})
            for sub_id, sub_data in shop_subscriptions.items():
                if sub_data.get('status') == 'ACTIVE':
                    return sub_data
            return None
    def log_database_state(self):
        """Log current database state for debugging"""
        logger.info("=== DATABASE STATE ===")
        logger.info(f"Shops table: {json.dumps(self.shops_table, indent=2, default=str)}")
        logger.info(f"Subscriptions table: {json.dumps(self.subscriptions_table, indent=2, default=str)}")
        logger.info("=== END DATABASE STATE ===")

