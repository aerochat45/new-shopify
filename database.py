# database.py
from threading import Lock
from config import logger, datetime, json
import os
from sqlalchemy import create_engine, Column, String, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text
import uuid

# Database Models
Base = declarative_base()

class Shop(Base):
    __tablename__ = 'shops1'
    
    shop_domain = Column(String(255), primary_key=True)
    shop_id = Column(String(100))
    shop_name = Column(String(255))
    email = Column(String(255))
    access_token = Column(Text)
    store_url = Column(String(255))
    company_id = Column(String(100))
    status = Column(String(50), default='active')
    initial_sync_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Subscription(Base):
    __tablename__ = 'subscriptions1'
    
    id = Column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id = Column(String(100))
    shop_domain = Column(String(255))
    name = Column(String(255))
    status = Column(String(50))
    interval = Column(String(50))
    price = Column(String(50))
    created_at = Column(DateTime)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Page(Base):
    __tablename__ = 'pages1'

    id = Column(String(100), primary_key=True)  # Shopify GraphQL ID or numeric ID as string
    shop_domain = Column(String(255), index=True)
    title = Column(String(512))
    handle = Column(String(512))
    body_html = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    store_id = Column(String(100))
    company_id = Column(String(100))
    last_sync_time = Column(DateTime)
    chunk_ids = Column(JSON)
    published = Column(Boolean, default=True)
    published_at = Column(DateTime)

class Article(Base):
    __tablename__ = 'articles'

    id = Column(String(100), primary_key=True)  # Shopify GraphQL ID or numeric ID as string
    shop_domain = Column(String(255), index=True)
    title = Column(String(512))
    handle = Column(String(512))
    body_html = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    store_id = Column(String(100))
    company_id = Column(String(100))
    last_sync_time = Column(DateTime)
    chunk_ids = Column(JSON)
    published = Column(Boolean, default=True)
    published_at = Column(DateTime)

# Enhanced SQLAlchemy database with table-like structure
class ShopifyAppDatabase:
    def __init__(self):
        self.lock = Lock()
        self._setup_database()

    def _setup_database(self):
        """Setup database connection and create tables"""
        try:
            # Get database URL from environment variable
            from config import DATABASE_URL
            database_url = DATABASE_URL
            if not database_url:
                # Fallback for Supabase format
                supabase_url = os.getenv('SUPABASE_URL', 'localhost')
                supabase_key = os.getenv('SUPABASE_ANON_KEY', '')
                db_password = os.getenv('SUPABASE_PASSWORD', '')
                db_user = os.getenv('SUPABASE_USER', 'postgres')
                db_name = os.getenv('SUPABASE_DB_NAME', 'postgres')
                
                if 'localhost' not in supabase_url:
                    # Extract hostname from Supabase URL
                    hostname = supabase_url.replace('https://', '').replace('http://', '')
                    database_url = f"postgresql://{db_user}:{db_password}@db.{hostname}:5432/{db_name}"
                else:
                    database_url = f"postgresql://{db_user}:{db_password}@localhost:5432/{db_name}"
            
            # Handle postgres:// vs postgresql:// URL schemes
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
            self.engine = create_engine(
                database_url,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                echo=False  # Set to True for SQL debugging
            )
            
            # Create tables
            Base.metadata.create_all(self.engine)
            
            # Create session factory
            self.SessionFactory = scoped_session(sessionmaker(bind=self.engine))
            
            logger.info("Database connection established successfully")
            
        except Exception as e:
            logger.error(f"Database setup failed: {str(e)}")
            raise

    def _get_session(self):
        """Get database session"""
        return self.SessionFactory()

    def create_or_update_shop(self, shop_domain, **kwargs):
        """Create or update shop record with all details"""
        with self.lock:
            session = self._get_session()
            try:
                # Get or create shop
                shop = session.query(Shop).filter_by(shop_domain=shop_domain).first()
                
                if not shop:
                    shop = Shop(
                        shop_domain=shop_domain,
                        store_url=shop_domain.replace('.myshopify.com', ''),
                        status='active',
                        created_at=datetime.now()
                    )
                    session.add(shop)
                    logger.info(f"Created new shop record for: {shop_domain}")
                
                # Update with provided data
                for key, value in kwargs.items():
                    if value is not None and hasattr(shop, key):
                        setattr(shop, key, value)
                
                shop.updated_at = datetime.now()
                
                session.commit()
                logger.info(f"Updated shop record for {shop_domain}: {kwargs}")
                return True
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error creating/updating shop {shop_domain}: {str(e)}")
                return False
            finally:
                session.close()

    def get_shop(self, shop_domain):
        """Get complete shop record"""
        with self.lock:
            session = self._get_session()
            try:
                shop = session.query(Shop).filter_by(shop_domain=shop_domain).first()
                
                if shop:
                    # Convert to dictionary to match original interface
                    shop_data = {
                        'shop_domain': shop.shop_domain,
                        'shop_id': shop.shop_id,
                        'shop_name': shop.shop_name,
                        'email': shop.email,
                        'access_token': shop.access_token,
                        'store_url': shop.store_url,
                        'company_id': shop.company_id,
                        'status': shop.status,
                        'initial_sync_completed': shop.initial_sync_completed,
                        'created_at': shop.created_at.isoformat() if shop.created_at else None,
                        'updated_at': shop.updated_at.isoformat() if shop.updated_at else None
                    }
                else:
                    shop_data = {}
                
                logger.info(f"Retrieved shop data for {shop_domain}: {bool(shop_data)}")
                return shop_data
                
            except Exception as e:
                logger.error(f"Error retrieving shop {shop_domain}: {str(e)}")
                return {}
            finally:
                session.close()

    def get_shop_by_company_id(self, company_id):
        """Get shop record by company_id"""
        with self.lock:
            session = self._get_session()
            try:
                shop = session.query(Shop).filter_by(company_id=company_id).first()
                
                if shop:
                    # Convert to dictionary to match original interface
                    shop_data = {
                        'shop_domain': shop.shop_domain,
                        'shop_id': shop.shop_id,
                        'shop_name': shop.shop_name,
                        'email': shop.email,
                        'access_token': shop.access_token,
                        'store_url': shop.store_url,
                        'company_id': shop.company_id,
                        'status': shop.status,
                        'initial_sync_completed': shop.initial_sync_completed,
                        'created_at': shop.created_at.isoformat() if shop.created_at else None,
                        'updated_at': shop.updated_at.isoformat() if shop.updated_at else None
                    }
                else:
                    shop_data = {}
                
                logger.info(f"Retrieved shop data by company_id {company_id}: {bool(shop_data)}")
                return shop_data
                
            except Exception as e:
                logger.error(f"Error retrieving shop by company_id {company_id}: {str(e)}")
                return {}
            finally:
                session.close()

    def create_or_update_subscription(self, shop_domain, subscription_data):
        """Create or update subscription record"""
        with self.lock:
            session = self._get_session()
            try:
                subscription_id = subscription_data.get('id', 'unknown')
                
                # Get or create subscription
                subscription = session.query(Subscription).filter_by(
                    shop_domain=shop_domain,
                    subscription_id=subscription_id
                ).first()
                
                if not subscription:
                    subscription = Subscription(
                        subscription_id=subscription_id,
                        shop_domain=shop_domain
                    )
                    session.add(subscription)
                
                # Update subscription data
                subscription.name = subscription_data.get('name')
                subscription.status = subscription_data.get('status')
                subscription.interval = subscription_data.get('interval')
                subscription.price = subscription_data.get('price')
                
                # Handle created_at from subscription_data
                if subscription_data.get('created_at'):
                    if isinstance(subscription_data['created_at'], str):
                        try:
                            subscription.created_at = datetime.fromisoformat(subscription_data['created_at'].replace('Z', '+00:00'))
                        except:
                            subscription.created_at = datetime.now()
                    else:
                        subscription.created_at = subscription_data['created_at']
                else:
                    subscription.created_at = datetime.now()
                
                subscription.updated_at = datetime.now()
                
                session.commit()
                logger.info(f"Updated subscription for {shop_domain}: {subscription_data}")
                return True
                
            except Exception as e:
                session.rollback()
                logger.error(f"Error updating subscription for {shop_domain}: {str(e)}")
                return False
            finally:
                session.close()

    def get_active_subscription(self, shop_domain):
        """Get active subscription for a shop"""
        with self.lock:
            session = self._get_session()
            try:
                subscription = session.query(Subscription).filter_by(
                    shop_domain=shop_domain,
                    status='ACTIVE'
                ).first()
                
                if subscription:
                    return {
                        'subscription_id': subscription.subscription_id,
                        'shop_domain': subscription.shop_domain,
                        'name': subscription.name,
                        'status': subscription.status,
                        'interval': subscription.interval,
                        'price': subscription.price,
                        'created_at': subscription.created_at.isoformat() if subscription.created_at else None,
                        'updated_at': subscription.updated_at.isoformat() if subscription.updated_at else None
                    }
                
                return None
                
            except Exception as e:
                logger.error(f"Error getting active subscription for {shop_domain}: {str(e)}")
                return None
            finally:
                session.close()

    def delete_shop_and_subscriptions(self, shop_domain):
        """Delete a shop and all related subscriptions by shop_domain"""
        with self.lock:
            session = self._get_session()
            try:
                # Delete related subscriptions first due to potential FK constraints
                session.query(Subscription).filter_by(shop_domain=shop_domain).delete(synchronize_session=False)
                session.query(Shop).filter_by(shop_domain=shop_domain).delete(synchronize_session=False)
                session.commit()
                logger.info(f"Deleted shop and subscriptions for {shop_domain}")
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting shop data for {shop_domain}: {str(e)}")
                return False
            finally:
                session.close()

    def save_pages(self, shop_domain, pages, company_id=None, sync_time=None):
        """Upsert pages for a shop. Pages items may contain keys: id, title, handle, body or body_html, created_at, updated_at, store_id, chunk_ids"""
        with self.lock:
            session = self._get_session()
            try:
                for page in pages:
                    page_id = str(page.get('id'))
                    existing = session.query(Page).filter_by(id=page_id).first()
                    if not existing:
                        existing = Page(id=page_id, shop_domain=shop_domain)
                        session.add(existing)

                    existing.title = page.get('title')
                    existing.handle = page.get('handle')
                    # accept either key
                    existing.body_html = page.get('body_html') or page.get('body')

                    created_at_val = page.get('created_at')
                    updated_at_val = page.get('updated_at')

                    if isinstance(created_at_val, str):
                        try:
                            created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
                        except:
                            created_at_val = None
                    if isinstance(updated_at_val, str):
                        try:
                            updated_at_val = datetime.fromisoformat(updated_at_val.replace('Z', '+00:00'))
                        except:
                            updated_at_val = None

                    existing.created_at = created_at_val
                    existing.updated_at = updated_at_val
                    existing.store_id = page.get('store_id')
                    existing.company_id = page.get('company_id') or company_id
                    existing.last_sync_time = sync_time or datetime.utcnow()
                    # default chunk_ids to [] if not provided
                    chunk_ids_value = page.get('chunk_ids')
                    if chunk_ids_value is None and existing.chunk_ids is None:
                        chunk_ids_value = []
                    if chunk_ids_value is not None:
                        existing.chunk_ids = chunk_ids_value
                    # published fields
                    published_at_val = page.get('published_at')
                    if isinstance(published_at_val, str):
                        try:
                            published_at_val = datetime.fromisoformat(published_at_val.replace('Z', '+00:00'))
                        except:
                            published_at_val = None
                    existing.published_at = published_at_val
                    if page.get('published') is not None:
                        existing.published = bool(page.get('published'))
                    elif published_at_val is not None:
                        existing.published = True

                session.commit()
                logger.info(f"Saved/updated {len(pages)} pages for {shop_domain}")
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"Error saving pages for {shop_domain}: {str(e)}")
                return False
            finally:
                session.close()

    def get_page_ids_for_shop(self, shop_domain):
        with self.lock:
            session = self._get_session()
            try:
                return [row.id for row in session.query(Page.id).filter_by(shop_domain=shop_domain).all()]
            finally:
                session.close()

    def get_pages_meta_for_shop(self, shop_domain):
        """Return a dict of page_id -> { 'updated_at': dt, 'chunk_ids': json }"""
        with self.lock:
            session = self._get_session()
            try:
                rows = session.query(Page.id, Page.updated_at, Page.chunk_ids).filter_by(shop_domain=shop_domain).all()
                meta = {}
                for pid, updated_at, chunk_ids in rows:
                    meta[str(pid)] = {
                        'updated_at': updated_at,
                        'chunk_ids': chunk_ids,
                    }
                return meta
            finally:
                session.close()

    def update_last_sync_time_for_ids(self, shop_domain, page_ids, sync_time):
        with self.lock:
            session = self._get_session()
            try:
                updated = session.query(Page).filter(Page.shop_domain == shop_domain, Page.id.in_(page_ids)).update({Page.last_sync_time: sync_time}, synchronize_session=False)
                session.commit()
                logger.info(f"Updated last_sync_time for {updated} pages for {shop_domain}")
                return updated
            except Exception as e:
                session.rollback()
                logger.error(f"Error updating last_sync_time for {shop_domain}: {str(e)}")
                return 0
            finally:
                session.close()

    def get_previous_pages_sync_time(self, shop_domain):
        """Return the most recent last_sync_time for any page of the shop, or None."""
        with self.lock:
            session = self._get_session()
            try:
                from sqlalchemy import func
                result = session.query(func.max(Page.last_sync_time)).filter_by(shop_domain=shop_domain).scalar()
                return result
            finally:
                session.close()
    def delete_pages_not_in_ids(self, shop_domain, keep_ids):
        with self.lock:
            session = self._get_session()
            try:
                deleted = session.query(Page).filter(Page.shop_domain == shop_domain, ~Page.id.in_(keep_ids)).delete(synchronize_session=False)
                session.commit()
                logger.info(f"Deleted {deleted} pages for {shop_domain} not present in latest sync")
                return deleted
            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting missing pages for {shop_domain}: {str(e)}")
                return 0
            finally:
                session.close()

    def save_articles(self, shop_domain, articles, company_id=None, sync_time=None):
        """Upsert articles for a shop. Articles items may contain keys: id, title, handle, body or body_html, created_at, updated_at, store_id, chunk_ids"""
        with self.lock:
            session = self._get_session()
            try:
                for article in articles:
                    article_id = str(article.get('id'))
                    existing = session.query(Article).filter_by(id=article_id).first()
                    if not existing:
                        existing = Article(id=article_id, shop_domain=shop_domain)
                        session.add(existing)

                    existing.title = article.get('title')
                    existing.handle = article.get('handle')
                    # accept either key
                    existing.body_html = article.get('body_html') or article.get('body')

                    created_at_val = article.get('created_at')
                    updated_at_val = article.get('updated_at')

                    if isinstance(created_at_val, str):
                        try:
                            created_at_val = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
                        except:
                            created_at_val = None
                    if isinstance(updated_at_val, str):
                        try:
                            updated_at_val = datetime.fromisoformat(updated_at_val.replace('Z', '+00:00'))
                        except:
                            updated_at_val = None

                    existing.created_at = created_at_val
                    existing.updated_at = updated_at_val
                    existing.store_id = article.get('store_id')
                    existing.company_id = article.get('company_id') or company_id
                    existing.last_sync_time = sync_time or datetime.utcnow()
                    # default chunk_ids to [] if not provided
                    chunk_ids_value = article.get('chunk_ids')
                    if chunk_ids_value is None and existing.chunk_ids is None:
                        chunk_ids_value = []
                    if chunk_ids_value is not None:
                        existing.chunk_ids = chunk_ids_value
                    # published fields
                    published_at_val = article.get('published_at')
                    if isinstance(published_at_val, str):
                        try:
                            published_at_val = datetime.fromisoformat(published_at_val.replace('Z', '+00:00'))
                        except:
                            published_at_val = None
                    existing.published_at = published_at_val
                    if article.get('published') is not None:
                        existing.published = bool(article.get('published'))
                    elif published_at_val is not None:
                        existing.published = True

                session.commit()
                logger.info(f"Saved/updated {len(articles)} articles for {shop_domain}")
                return True
            except Exception as e:
                session.rollback()
                logger.error(f"Error saving articles for {shop_domain}: {str(e)}")
                return False
            finally:
                session.close()

    def get_articles_meta_for_shop(self, shop_domain):
        """Return a dict of article_id -> { 'updated_at': dt, 'chunk_ids': json }"""
        with self.lock:
            session = self._get_session()
            try:
                rows = session.query(Article.id, Article.updated_at, Article.chunk_ids).filter_by(shop_domain=shop_domain).all()
                meta = {}
                for aid, updated_at, chunk_ids in rows:
                    meta[str(aid)] = {
                        'updated_at': updated_at,
                        'chunk_ids': chunk_ids,
                    }
                return meta
            finally:
                session.close()

    def get_previous_articles_sync_time(self, shop_domain):
        """Return the most recent last_sync_time for any article of the shop, or None."""
        with self.lock:
            session = self._get_session()
            try:
                from sqlalchemy import func
                result = session.query(func.max(Article.last_sync_time)).filter_by(shop_domain=shop_domain).scalar()
                return result
            finally:
                session.close()

    def delete_articles_not_in_ids(self, shop_domain, keep_ids):
        with self.lock:
            session = self._get_session()
            try:
                deleted = session.query(Article).filter(Article.shop_domain == shop_domain, ~Article.id.in_(keep_ids)).delete(synchronize_session=False)
                session.commit()
                logger.info(f"Deleted {deleted} articles for {shop_domain} not present in latest sync")
                return deleted
            except Exception as e:
                session.rollback()
                logger.error(f"Error deleting missing articles for {shop_domain}: {str(e)}")
                return 0
            finally:
                session.close()

    def log_database_state(self):
        """Log current database state for debugging"""
        session = self._get_session()
        try:
            shops = session.query(Shop).all()
            subscriptions = session.query(Subscription).all()
            
            shops_data = {}
            for shop in shops:
                shops_data[shop.shop_domain] = {
                    'shop_domain': shop.shop_domain,
                    'shop_id': shop.shop_id,
                    'shop_name': shop.shop_name,
                    'email': shop.email,
                    'access_token': shop.access_token and '***HIDDEN***',  # Don't log sensitive data
                    'store_url': shop.store_url,
                    'company_id': shop.company_id,
                    'status': shop.status,
                    'created_at': shop.created_at,
                    'updated_at': shop.updated_at
                }
            
            subscriptions_data = {}
            for sub in subscriptions:
                if sub.shop_domain not in subscriptions_data:
                    subscriptions_data[sub.shop_domain] = {}
                subscriptions_data[sub.shop_domain][sub.subscription_id] = {
                    'subscription_id': sub.subscription_id,
                    'shop_domain': sub.shop_domain,
                    'name': sub.name,
                    'status': sub.status,
                    'interval': sub.interval,
                    'price': sub.price,
                    'created_at': sub.created_at,
                    'updated_at': sub.updated_at
                }
            
            logger.info("=== DATABASE STATE ===")
            logger.info(f"Shops table: {json.dumps(shops_data, indent=2, default=str)}")
            logger.info(f"Subscriptions table: {json.dumps(subscriptions_data, indent=2, default=str)}")
            logger.info("=== END DATABASE STATE ===")
            
        except Exception as e:
            logger.error(f"Error logging database state: {str(e)}")
        finally:
            session.close()

    def get_pages_count(self, shop_domain):
        """Get count of pages for a shop"""
        try:
            session = self.SessionFactory()
            count = session.query(Page).filter(Page.shop_domain == shop_domain).count()
            session.close()
            return count
        except Exception as e:
            logger.error(f"Error getting pages count for {shop_domain}: {str(e)}")
            return 0

    def get_articles_count(self, shop_domain):
        """Get count of articles for a shop"""
        try:
            session = self.SessionFactory()
            count = session.query(Article).filter(Article.shop_domain == shop_domain).count()
            session.close()
            return count
        except Exception as e:
            logger.error(f"Error getting articles count for {shop_domain}: {str(e)}")
            return 0

    def get_products_count(self, shop_domain):
        """Get static count of products for a shop (managed separately)"""
        try:
            # Products are managed separately, return a static count
            # You could fetch this from Shopify API if needed, but for now return static
            return 0  # or fetch from Shopify API for display purposes
        except Exception as e:
            logger.error(f"Error getting products count for {shop_domain}: {str(e)}")
            return 0

    def get_collections_count(self, shop_domain):
        """Get static count of collections for a shop (managed separately)"""
        try:
            # Collections are managed separately, return a static count
            # You could fetch this from Shopify API if needed, but for now return static
            return 0  # or fetch from Shopify API for display purposes
        except Exception as e:
            logger.error(f"Error getting collections count for {shop_domain}: {str(e)}")
            return 0

    def __del__(self):
        """Cleanup database connections"""
        try:
            if hasattr(self, 'SessionFactory'):
                self.SessionFactory.remove()
            if hasattr(self, 'engine'):
                self.engine.dispose()
        except:
            pass
        

db = ShopifyAppDatabase()