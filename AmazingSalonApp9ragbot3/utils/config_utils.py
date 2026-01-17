"""
Utility functions for system configuration management
"""
import os
import json
import time
from database import db_sql
from database_models_config import SystemConfig
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError, OperationalError
from datetime import datetime

class ConfigManager:
    """Manager for system configuration"""
    
    _cache = {}  # In-memory cache of settings
    _cache_timestamp = None
    _cache_lifetime = 300  # Cache lifetime in seconds (5 minutes)
    
    @classmethod
    def _refresh_cache_if_needed(cls):
        """Refresh cache if expired or doesn't exist"""
        current_time = time.time()
        
        # Check if cache needs refreshing
        if (not cls._cache_timestamp or 
            not cls._cache or 
            current_time - cls._cache_timestamp > cls._cache_lifetime):
            
            try:
                # Query all configuration values
                all_configs = db_sql.session.query(SystemConfig).all()
                
                # Reset the cache
                cls._cache = {}
                
                # Populate the cache
                for config in all_configs:
                    cls._cache[config.key] = {
                        'value': config.value,
                        'description': config.description,
                        'category': config.category,
                        'is_sensitive': config.is_sensitive,
                        'updated_at': config.updated_at
                    }
                
                # Update cache timestamp
                cls._cache_timestamp = current_time
                
            except (SQLAlchemyError, ProgrammingError, OperationalError) as e:
                print(f"Warning: Could not refresh config cache: {e}")
                # If there's an error, we'll continue using the existing cache if available,
                # or return default values
    
    @classmethod
    def get(cls, key, default=None):
        """Get a configuration value by key"""
        # Try to refresh the cache
        cls._refresh_cache_if_needed()
        
        # Check if key exists in cache
        if key in cls._cache:
            return cls._cache[key]['value']
        
        try:
            # Try to get from database
            config = db_sql.session.query(SystemConfig).filter_by(key=key).first()
            
            if config:
                # Update cache
                cls._cache[key] = {
                    'value': config.value,
                    'description': config.description,
                    'category': config.category,
                    'is_sensitive': config.is_sensitive,
                    'updated_at': config.updated_at
                }
                
                return config.value
        except (SQLAlchemyError, ProgrammingError, OperationalError) as e:
            print(f"Warning: Could not get config '{key}' from database: {e}")
        
        # If we get here, the key doesn't exist or there was an error
        return default
    
    @classmethod
    def get_all(cls, category=None):
        """Get all configuration settings, optionally filtered by category"""
        # Try to refresh the cache
        cls._refresh_cache_if_needed()
        
        try:
            # Query settings from database
            query = db_sql.session.query(SystemConfig)
            
            if category:
                query = query.filter_by(category=category)
            
            all_configs = query.all()
            
            return all_configs
            
        except (SQLAlchemyError, ProgrammingError, OperationalError) as e:
            print(f"Warning: Could not get all configs from database: {e}")
            
            # If the table doesn't exist yet, we'll return an empty list
            return []
    
    @classmethod
    def set(cls, key, value, description=None, category='general', is_sensitive=False, created_by=None):
        """Set a configuration value"""
        def update_config():
            # Check if the key already exists
            config = db_sql.session.query(SystemConfig).filter_by(key=key).first()
            
            if config:
                # Update existing config
                config.value = value
                if description:
                    config.description = description
                config.category = category
                config.is_sensitive = is_sensitive
                config.updated_at = datetime.utcnow()
            else:
                # Create new config
                config = SystemConfig(
                    key=key,
                    value=value,
                    description=description,
                    category=category,
                    is_sensitive=is_sensitive,
                    created_by=created_by
                )
                db_sql.session.add(config)
            
            # Commit the changes
            db_sql.session.commit()
            
            # Update the cache
            cls._cache[key] = {
                'value': value,
                'description': description,
                'category': category,
                'is_sensitive': is_sensitive,
                'updated_at': datetime.utcnow()
            }
        
        try:
            update_config()
            return True
        except (SQLAlchemyError, ProgrammingError, OperationalError) as e:
            print(f"Warning: Could not set config '{key}': {e}")
            db_sql.session.rollback()
            return False
    
    @classmethod
    def delete(cls, key):
        """Delete a configuration entry"""
        def delete_config():
            # Check if the key exists
            config = db_sql.session.query(SystemConfig).filter_by(key=key).first()
            
            if config:
                # Delete the config
                db_sql.session.delete(config)
                db_sql.session.commit()
                
                # Remove from cache
                if key in cls._cache:
                    del cls._cache[key]
                
                return True
            
            return False
        
        try:
            return delete_config()
        except (SQLAlchemyError, ProgrammingError, OperationalError) as e:
            print(f"Warning: Could not delete config '{key}': {e}")
            db_sql.session.rollback()
            return False
    
    @classmethod
    def export_to_env(cls):
        """Export configuration to environment variables"""
        # Try to refresh the cache
        cls._refresh_cache_if_needed()
        
        # Export all configs to environment variables
        for key, data in cls._cache.items():
            # Use uppercase with CONFIG_ prefix for environment variables
            env_key = f"CONFIG_{key.upper()}"
            os.environ[env_key] = data['value']
    
    @classmethod
    def get_stripe_public_key(cls):
        """Get Stripe public key"""
        return cls.get('stripe_public_key')
    
    @classmethod
    def get_stripe_secret_key(cls):
        """Get Stripe secret key"""
        return cls.get('stripe_secret_key')
    
    @classmethod
    def get_paystack_public_key(cls):
        """Get Paystack public key"""
        return cls.get('paystack_public_key')
    
    @classmethod
    def get_paystack_secret_key(cls):
        """Get Paystack secret key"""
        return cls.get('paystack_secret_key')
    
    @classmethod
    def set_stripe_keys(cls, public_key, secret_key, created_by=None):
        """Set Stripe API keys"""
        public_key_set = cls.set(
            'stripe_public_key', 
            public_key, 
            'Stripe publishable API key', 
            'payment', 
            False,  # Public key is not sensitive
            created_by
        )
        
        secret_key_set = cls.set(
            'stripe_secret_key', 
            secret_key, 
            'Stripe secret API key', 
            'payment', 
            True,  # Secret key is sensitive
            created_by
        )
        
        return public_key_set and secret_key_set
        
    @classmethod
    def set_paystack_keys(cls, public_key, secret_key, created_by=None):
        """Set Paystack API keys"""
        public_key_set = cls.set(
            'paystack_public_key', 
            public_key, 
            'Paystack publishable API key', 
            'payment', 
            False,  # Public key is not sensitive
            created_by
        )
        
        secret_key_set = cls.set(
            'paystack_secret_key', 
            secret_key, 
            'Paystack secret API key', 
            'payment', 
            True,  # Secret key is sensitive
            created_by
        )
        
        return public_key_set and secret_key_set
    
    @classmethod
    def get_loyalty_points_ratio(cls):
        """Get loyalty points to dollar conversion ratio"""
        ratio = cls.get('points_to_dollar_ratio')
        
        # Default is 0.1 (10 points = $1)
        if not ratio:
            cls.set('points_to_dollar_ratio', '0.1', 'Loyalty points to dollar conversion ratio', 'loyalty')
            return 0.1
        
        try:
            return float(ratio)
        except (ValueError, TypeError):
            return 0.1
    
    @classmethod
    def get_points_per_dollar(cls):
        """Get loyalty points earned per dollar spent"""
        points = cls.get('loyalty_points_per_dollar')
        
        # Default is 1 (1 point per $1 spent)
        if not points:
            cls.set('loyalty_points_per_dollar', '1', 'Loyalty points earned per dollar spent', 'loyalty')
            return 1
        
        try:
            return int(points)
        except (ValueError, TypeError):
            return 1
    
    @classmethod
    def get_default_payment_provider(cls):
        """Get the default payment provider (stripe or paystack)"""
        provider = cls.get('default_payment_provider')
        
        # Default to stripe if not set
        if not provider:
            cls.set('default_payment_provider', 'stripe', 'Default payment provider', 'payment')
            return 'stripe'
        
        return provider
    
    @classmethod
    def set_default_payment_provider(cls, provider, created_by=None):
        """Set the default payment provider"""
        if provider not in ['stripe', 'paystack']:
            return False
            
        return cls.set(
            'default_payment_provider', 
            provider, 
            'Default payment provider', 
            'payment', 
            False,
            created_by
        )
    
    @classmethod
    def get_business_info(cls):
        """Get business information dictionary"""
        name = cls.get('business_name', 'Salon Management System')
        email = cls.get('business_email', 'contact@salon-management.app')
        phone = cls.get('business_phone', '+1-555-123-4567')
        
        # Set defaults if not found
        if not name:
            cls.set('business_name', 'Salon Management System', 'Business name', 'business')
            name = 'Salon Management System'
        
        if not email:
            cls.set('business_email', 'contact@salon-management.app', 'Business email address', 'business')
            email = 'contact@salon-management.app'
        
        if not phone:
            cls.set('business_phone', '+1-555-123-4567', 'Business phone number', 'business')
            phone = '+1-555-123-4567'
        
        return {
            'name': name,
            'email': email,
            'phone': phone
        }