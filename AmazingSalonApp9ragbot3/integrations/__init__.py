"""
SkinTwin Platform Integrations
Unified integration layer for Wix Bookings, OpenCart, and Shopify B2B
"""

from .gateway import IntegrationGateway, create_gateway_blueprint
from .webhook_router import WebhookRouter, create_webhook_router_blueprint, SyncEventHandler

from .wix import WixBookingsConnector, WixWebhookHandler
from .opencart import OpenCartConnector, OpenCartWebhookHandler
from .shopify import ShopifyB2BConnector, ShopifyWebhookHandler

from .common.models import (
    UnifiedAppointment,
    UnifiedClient,
    UnifiedProduct,
    UnifiedOrder,
    UnifiedOrderItem,
    UnifiedService,
    PlatformReference,
    SyncStatus,
    PaymentStatus
)

from .common.exceptions import (
    IntegrationError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    WebhookError,
    ConfigurationError
)

__version__ = '1.0.0'

__all__ = [
    # Gateway
    'IntegrationGateway',
    'create_gateway_blueprint',
    
    # Webhook Router
    'WebhookRouter',
    'create_webhook_router_blueprint',
    'SyncEventHandler',
    
    # Connectors
    'WixBookingsConnector',
    'OpenCartConnector',
    'ShopifyB2BConnector',
    
    # Webhook Handlers
    'WixWebhookHandler',
    'OpenCartWebhookHandler',
    'ShopifyWebhookHandler',
    
    # Models
    'UnifiedAppointment',
    'UnifiedClient',
    'UnifiedProduct',
    'UnifiedOrder',
    'UnifiedOrderItem',
    'UnifiedService',
    'PlatformReference',
    'SyncStatus',
    'PaymentStatus',
    
    # Exceptions
    'IntegrationError',
    'AuthenticationError',
    'RateLimitError',
    'ValidationError',
    'WebhookError',
    'ConfigurationError'
]


def create_integration_app(config: dict):
    """
    Factory function to create a fully configured integration setup.
    
    Args:
        config: Configuration dictionary with platform credentials
        
    Returns:
        tuple: (IntegrationGateway, WebhookRouter) instances
    """
    # Create gateway
    gateway = IntegrationGateway()
    gateway.initialize_from_config(config)
    
    # Create webhook router
    router = WebhookRouter()
    router.initialize_handlers(config)
    
    # Create and register sync handler
    sync_handler = SyncEventHandler(gateway)
    sync_handler.register_with_router(router)
    
    return gateway, router


def register_integration_blueprints(app, gateway: IntegrationGateway, router: WebhookRouter):
    """
    Register all integration blueprints with a Flask app.
    
    Args:
        app: Flask application instance
        gateway: IntegrationGateway instance
        router: WebhookRouter instance
    """
    app.register_blueprint(create_gateway_blueprint(gateway))
    app.register_blueprint(create_webhook_router_blueprint(router))
