"""
Shopify B2B Integration Module
Provides connectivity to Shopify Admin API for B2B eCommerce operations
"""

from .connector import ShopifyB2BConnector
from .webhooks import ShopifyWebhookHandler
from .models import (
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCompany,
    ShopifyCompanyLocation,
    ShopifyDraftOrder
)

__all__ = [
    'ShopifyB2BConnector',
    'ShopifyWebhookHandler',
    'ShopifyProduct',
    'ShopifyOrder',
    'ShopifyCustomer',
    'ShopifyCompany',
    'ShopifyCompanyLocation',
    'ShopifyDraftOrder'
]
