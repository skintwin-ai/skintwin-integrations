"""
Shopify Webhook Handler
Processes incoming webhooks from Shopify
"""

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from ..common.exceptions import WebhookError

logger = logging.getLogger(__name__)


class ShopifyWebhookHandler:
    """
    Handler for Shopify webhook events.
    
    Shopify sends webhooks for various events including:
    - Orders: create, update, cancel, fulfill
    - Products: create, update, delete
    - Customers: create, update, delete
    - Draft Orders: create, update, delete
    - Companies (B2B): create, update, delete
    """
    
    # Webhook topics
    TOPICS = {
        # Orders
        'orders/create': 'on_order_created',
        'orders/updated': 'on_order_updated',
        'orders/cancelled': 'on_order_cancelled',
        'orders/fulfilled': 'on_order_fulfilled',
        'orders/paid': 'on_order_paid',
        
        # Products
        'products/create': 'on_product_created',
        'products/update': 'on_product_updated',
        'products/delete': 'on_product_deleted',
        
        # Customers
        'customers/create': 'on_customer_created',
        'customers/update': 'on_customer_updated',
        'customers/delete': 'on_customer_deleted',
        
        # Draft Orders (B2B)
        'draft_orders/create': 'on_draft_order_created',
        'draft_orders/update': 'on_draft_order_updated',
        'draft_orders/delete': 'on_draft_order_deleted',
        
        # Inventory
        'inventory_levels/update': 'on_inventory_updated',
        
        # App
        'app/uninstalled': 'on_app_uninstalled'
    }
    
    def __init__(self, webhook_secret: str):
        """
        Initialize the webhook handler.
        
        Args:
            webhook_secret: Shopify webhook secret for HMAC verification
        """
        self.webhook_secret = webhook_secret
        self._handlers: Dict[str, Callable] = {}
        
        logger.info("Initialized Shopify webhook handler")
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the webhook HMAC signature.
        
        Args:
            payload: Raw request body
            signature: Signature from X-Shopify-Hmac-SHA256 header
            
        Returns:
            bool: True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True
        
        computed_hmac = base64.b64encode(
            hmac.new(
                self.webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).digest()
        ).decode()
        
        return hmac.compare_digest(computed_hmac, signature)
    
    def register_handler(self, topic: str, handler: Callable):
        """
        Register a handler for a specific webhook topic.
        
        Args:
            topic: Webhook topic (e.g., 'orders/create')
            handler: Callback function to handle the event
        """
        if topic not in self.TOPICS:
            logger.warning(f"Unknown webhook topic: {topic}")
        
        self._handlers[topic] = handler
        logger.info(f"Registered handler for Shopify topic: {topic}")
    
    def process_webhook(
        self,
        payload: bytes,
        topic: str,
        signature: Optional[str] = None,
        shop_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an incoming webhook.
        
        Args:
            payload: Raw request body
            topic: Webhook topic from X-Shopify-Topic header
            signature: HMAC signature from X-Shopify-Hmac-SHA256 header
            shop_domain: Shop domain from X-Shopify-Shop-Domain header
            
        Returns:
            Dict: Processing result
        """
        # Verify signature
        if signature and not self.verify_signature(payload, signature):
            raise WebhookError("Invalid webhook signature", event_type=topic)
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise WebhookError(f"Invalid JSON payload: {e}", event_type=topic)
        
        logger.info(f"Processing Shopify webhook: {topic} from {shop_domain}")
        
        # Call registered handler
        handler = self._handlers.get(topic)
        if handler:
            try:
                result = handler(data, shop_domain)
                return {
                    'status': 'processed',
                    'topic': topic,
                    'shop': shop_domain,
                    'result': result
                }
            except Exception as e:
                logger.error(f"Error processing webhook {topic}: {e}")
                raise WebhookError(f"Handler error: {e}", event_type=topic)
        else:
            # Try default handler based on topic
            default_handler = getattr(self, self.TOPICS.get(topic, ''), None)
            if default_handler:
                result = default_handler(data)
                return {
                    'status': 'processed',
                    'topic': topic,
                    'shop': shop_domain,
                    'result': result
                }
            
            logger.warning(f"No handler registered for topic: {topic}")
            return {
                'status': 'ignored',
                'topic': topic,
                'shop': shop_domain,
                'message': 'No handler registered'
            }
    
    # ==================== Order Handlers ====================
    
    def on_order_created(self, data: Dict) -> Dict:
        """Handle order created event."""
        order_id = data.get('id')
        order_number = data.get('order_number')
        logger.info(f"Shopify order created: #{order_number} (ID: {order_id})")
        return {
            'action': 'create',
            'order_id': order_id,
            'order_number': order_number
        }
    
    def on_order_updated(self, data: Dict) -> Dict:
        """Handle order updated event."""
        order_id = data.get('id')
        order_number = data.get('order_number')
        logger.info(f"Shopify order updated: #{order_number} (ID: {order_id})")
        return {
            'action': 'update',
            'order_id': order_id,
            'order_number': order_number
        }
    
    def on_order_cancelled(self, data: Dict) -> Dict:
        """Handle order cancelled event."""
        order_id = data.get('id')
        order_number = data.get('order_number')
        logger.info(f"Shopify order cancelled: #{order_number} (ID: {order_id})")
        return {
            'action': 'cancel',
            'order_id': order_id,
            'order_number': order_number
        }
    
    def on_order_fulfilled(self, data: Dict) -> Dict:
        """Handle order fulfilled event."""
        order_id = data.get('id')
        order_number = data.get('order_number')
        logger.info(f"Shopify order fulfilled: #{order_number} (ID: {order_id})")
        return {
            'action': 'fulfill',
            'order_id': order_id,
            'order_number': order_number
        }
    
    def on_order_paid(self, data: Dict) -> Dict:
        """Handle order paid event."""
        order_id = data.get('id')
        order_number = data.get('order_number')
        logger.info(f"Shopify order paid: #{order_number} (ID: {order_id})")
        return {
            'action': 'paid',
            'order_id': order_id,
            'order_number': order_number
        }
    
    # ==================== Product Handlers ====================
    
    def on_product_created(self, data: Dict) -> Dict:
        """Handle product created event."""
        product_id = data.get('id')
        title = data.get('title')
        logger.info(f"Shopify product created: {title} (ID: {product_id})")
        return {
            'action': 'create',
            'product_id': product_id,
            'title': title
        }
    
    def on_product_updated(self, data: Dict) -> Dict:
        """Handle product updated event."""
        product_id = data.get('id')
        title = data.get('title')
        logger.info(f"Shopify product updated: {title} (ID: {product_id})")
        return {
            'action': 'update',
            'product_id': product_id,
            'title': title
        }
    
    def on_product_deleted(self, data: Dict) -> Dict:
        """Handle product deleted event."""
        product_id = data.get('id')
        logger.info(f"Shopify product deleted: ID {product_id}")
        return {
            'action': 'delete',
            'product_id': product_id
        }
    
    # ==================== Customer Handlers ====================
    
    def on_customer_created(self, data: Dict) -> Dict:
        """Handle customer created event."""
        customer_id = data.get('id')
        email = data.get('email')
        logger.info(f"Shopify customer created: {email} (ID: {customer_id})")
        return {
            'action': 'create',
            'customer_id': customer_id,
            'email': email
        }
    
    def on_customer_updated(self, data: Dict) -> Dict:
        """Handle customer updated event."""
        customer_id = data.get('id')
        email = data.get('email')
        logger.info(f"Shopify customer updated: {email} (ID: {customer_id})")
        return {
            'action': 'update',
            'customer_id': customer_id,
            'email': email
        }
    
    def on_customer_deleted(self, data: Dict) -> Dict:
        """Handle customer deleted event."""
        customer_id = data.get('id')
        logger.info(f"Shopify customer deleted: ID {customer_id}")
        return {
            'action': 'delete',
            'customer_id': customer_id
        }
    
    # ==================== Draft Order Handlers (B2B) ====================
    
    def on_draft_order_created(self, data: Dict) -> Dict:
        """Handle draft order created event."""
        draft_order_id = data.get('id')
        name = data.get('name')
        logger.info(f"Shopify draft order created: {name} (ID: {draft_order_id})")
        return {
            'action': 'create',
            'draft_order_id': draft_order_id,
            'name': name
        }
    
    def on_draft_order_updated(self, data: Dict) -> Dict:
        """Handle draft order updated event."""
        draft_order_id = data.get('id')
        name = data.get('name')
        logger.info(f"Shopify draft order updated: {name} (ID: {draft_order_id})")
        return {
            'action': 'update',
            'draft_order_id': draft_order_id,
            'name': name
        }
    
    def on_draft_order_deleted(self, data: Dict) -> Dict:
        """Handle draft order deleted event."""
        draft_order_id = data.get('id')
        logger.info(f"Shopify draft order deleted: ID {draft_order_id}")
        return {
            'action': 'delete',
            'draft_order_id': draft_order_id
        }
    
    # ==================== Inventory Handlers ====================
    
    def on_inventory_updated(self, data: Dict) -> Dict:
        """Handle inventory level updated event."""
        inventory_item_id = data.get('inventory_item_id')
        location_id = data.get('location_id')
        available = data.get('available')
        logger.info(f"Shopify inventory updated: Item {inventory_item_id} at location {location_id}: {available}")
        return {
            'action': 'inventory_update',
            'inventory_item_id': inventory_item_id,
            'location_id': location_id,
            'available': available
        }
    
    # ==================== App Handlers ====================
    
    def on_app_uninstalled(self, data: Dict) -> Dict:
        """Handle app uninstalled event."""
        shop_id = data.get('id')
        logger.warning(f"Shopify app uninstalled from shop: {shop_id}")
        return {
            'action': 'uninstall',
            'shop_id': shop_id
        }


def create_shopify_webhook_blueprint(handler: ShopifyWebhookHandler):
    """
    Create a Flask blueprint for Shopify webhooks.
    
    Args:
        handler: ShopifyWebhookHandler instance
        
    Returns:
        Blueprint: Flask blueprint for webhook routes
    """
    from flask import Blueprint, request, jsonify
    
    bp = Blueprint('shopify_webhooks', __name__, url_prefix='/webhooks/shopify')
    
    @bp.route('/', methods=['POST'])
    def handle_webhook():
        """Handle all Shopify webhooks."""
        try:
            topic = request.headers.get('X-Shopify-Topic')
            signature = request.headers.get('X-Shopify-Hmac-SHA256')
            shop_domain = request.headers.get('X-Shopify-Shop-Domain')
            
            if not topic:
                return jsonify({'error': 'Missing X-Shopify-Topic header'}), 400
            
            result = handler.process_webhook(
                payload=request.data,
                topic=topic,
                signature=signature,
                shop_domain=shop_domain
            )
            
            return jsonify(result), 200
            
        except WebhookError as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    @bp.route('/orders', methods=['POST'])
    def handle_order_webhook():
        """Handle Shopify order webhooks."""
        return handle_webhook()
    
    @bp.route('/products', methods=['POST'])
    def handle_product_webhook():
        """Handle Shopify product webhooks."""
        return handle_webhook()
    
    @bp.route('/customers', methods=['POST'])
    def handle_customer_webhook():
        """Handle Shopify customer webhooks."""
        return handle_webhook()
    
    @bp.route('/draft_orders', methods=['POST'])
    def handle_draft_order_webhook():
        """Handle Shopify draft order webhooks (B2B)."""
        return handle_webhook()
    
    return bp
