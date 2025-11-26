# config.py
import os
import logging
from datetime import datetime
import json
from dotenv import load_dotenv
import os

load_dotenv()  # <- this loads your .env into os.environ
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('shopify_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Shopify public app credentials - Load from environment variables
API_KEY = os.getenv('SHOPIFY_API_KEY', '9245b3af044f843540f65b7da58b6dca')
API_SECRET = os.getenv('SHOPIFY_API_SECRET', 'e043750d9bad8e80b92caf124f1dd2fa')
SCOPES = os.getenv('SHOPIFY_SCOPES', 'read_products,write_products,read_orders,write_orders')
REDIRECT_URI = os.getenv('SHOPIFY_REDIRECT_URI', 'https://191ce502050d.ngrok-free.app/oauth/callback')
APP_HANDLE = os.getenv('SHOPIFY_APP_HANDLE', 'aerochatapp')
THIRD_PARTY_BASE = os.getenv('THIRD_PARTY_BASE', 'https://app.aerochat.ai')
THIRD_PARTY_API_URL = f'{THIRD_PARTY_BASE}/chat/api/v1/shopify-create-user'
GET_COMPANY_ID_URL = f'{THIRD_PARTY_BASE}/chat/api/v1/get_company_id'

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://username:password@localhost/shopify_app')

# Flask configuration
SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())