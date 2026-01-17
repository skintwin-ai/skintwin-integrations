"""
OpenCart Webhook Handler
Processes incoming webhooks from OpenCart
Note: OpenCart requires custom extensions for webhook support
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from ..common.exceptions import WebhookError

logger = logging.getLogger(__name__)


class OpenCartWebhookHandler:
    """
    Handler for OpenCart webhook events.
    
    Note: OpenCart doesn't have native webhook support.
    This handler is designed to work with custom webhook extensions
    such as:
    - OpenCart Webhooks by iSenseLabs
    - Custom OCMOD webhook extensions
    """
    
    # Webhook event types (custom extension dependent)
    EVENT_TYPES = {
        'order/created': 'on_order_created',
        'order/updated': 'on_order_updated',
        'order/status_changed': 'on_order_status_changed',
        'product/created': 'on_product_created',
        'product/updated': 'on_product_updated',
        'product/deleted': 'on_product_deleted',
        'customer/created': 'on_customer_created',
        'customer/updated': 'on_customer_updated',
        'stock/low': 'on_low_stock'
    }
    
    def __init__(self, webhook_secret: Optional[str] = None):
        """
        Initialize the webhook handler.
        
        Args:
            webhook_secret: Optional secret key for webhook verification
        """
        self.webhook_secret = webhook_secret
        self._handlers: Dict[str, Callable] = {}
        
        logger.info("Initialized OpenCart webhook handler")
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the webhook signature.
        
        Args:
            payload: Raw request body
            signature: Signature from X-OpenCart-Signature header
            
        Returns:
            bool: True if signature is valid
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True
        
        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def register_handler(self, event_type: str, handler: Callable):
        """
        Register a handler for a specific event type.
        
        Args:
            event_type: Event type (e.g., 'order/created')
            handler: Callback function to handle the event
        """
        self._handlers[event_type] = handler
        logger.info(f"Registered handler for OpenCart event: {event_type}")
    
    def process_webhook(
        self,
        payload: bytes,
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an incoming webhook.
        
        Args:
            payload: Raw request body
            signature: Optional signature for verification
            
        Returns:
            Dict: Processing result
        """
        # Verify signature if provided
        if signature and not self.verify_signature(payload, signature):
            raise WebhookError("Invalid webhook signature", event_type="unknown")
        
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as e:
            raise WebhookError(f"Invalid JSON payload: {e}", event_type="unknown")
        
        event_type = data.get('event', data.get('type', 'unknown'))
        event_data = data.get('data', data)
        
        logger.info(f"Processing OpenCart webhook: {event_type}")
        
        # Call registered handler
        handler = self._handlers.get(event_type)
        if handler:
            try:
                result = handler(event_data)
                return {
                    'status': 'processed',
                    'event_type': event_type,
                    'result': result
                }
            except Exception as e:
                logger.error(f"Error processing webhook {event_type}: {e}")
                raise WebhookError(f"Handler error: {e}", event_type=event_type)
        else:
            logger.warning(f"No handler registered for event: {event_type}")
            return {
                'status': 'ignored',
                'event_type': event_type,
                'message': 'No handler registered'
            }
    
    # Default event handlers
    
    def on_order_created(self, data: Dict) -> Dict:
        """Handle order created event."""
        order_id = data.get('order_id')
        logger.info(f"OpenCart order created: {order_id}")
        return {'action': 'create', 'order_id': order_id}
    
    def on_order_updated(self, data: Dict) -> Dict:
        """Handle order updated event."""
        order_id = data.get('order_id')
        logger.info(f"OpenCart order updated: {order_id}")
        return {'action': 'update', 'order_id': order_id}
    
    def on_order_status_changed(self, data: Dict) -> Dict:
        """Handle order status changed event."""
        order_id = data.get('order_id')
        old_status = data.get('old_status_id')
        new_status = data.get('new_status_id')
        logger.info(f"OpenCart order {order_id} status changed: {old_status} -> {new_status}")
        return {
            'action': 'status_change',
            'order_id': order_id,
            'old_status': old_status,
            'new_status': new_status
        }
    
    def on_product_created(self, data: Dict) -> Dict:
        """Handle product created event."""
        product_id = data.get('product_id')
        logger.info(f"OpenCart product created: {product_id}")
        return {'action': 'create', 'product_id': product_id}
    
    def on_product_updated(self, data: Dict) -> Dict:
        """Handle product updated event."""
        product_id = data.get('product_id')
        logger.info(f"OpenCart product updated: {product_id}")
        return {'action': 'update', 'product_id': product_id}
    
    def on_product_deleted(self, data: Dict) -> Dict:
        """Handle product deleted event."""
        product_id = data.get('product_id')
        logger.info(f"OpenCart product deleted: {product_id}")
        return {'action': 'delete', 'product_id': product_id}
    
    def on_customer_created(self, data: Dict) -> Dict:
        """Handle customer created event."""
        customer_id = data.get('customer_id')
        logger.info(f"OpenCart customer created: {customer_id}")
        return {'action': 'create', 'customer_id': customer_id}
    
    def on_customer_updated(self, data: Dict) -> Dict:
        """Handle customer updated event."""
        customer_id = data.get('customer_id')
        logger.info(f"OpenCart customer updated: {customer_id}")
        return {'action': 'update', 'customer_id': customer_id}
    
    def on_low_stock(self, data: Dict) -> Dict:
        """Handle low stock alert event."""
        product_id = data.get('product_id')
        quantity = data.get('quantity')
        logger.warning(f"OpenCart low stock alert: Product {product_id} has {quantity} units")
        return {
            'action': 'low_stock_alert',
            'product_id': product_id,
            'quantity': quantity
        }


def create_opencart_webhook_blueprint(handler: OpenCartWebhookHandler):
    """
    Create a Flask blueprint for OpenCart webhooks.
    
    Args:
        handler: OpenCartWebhookHandler instance
        
    Returns:
        Blueprint: Flask blueprint for webhook routes
    """
    from flask import Blueprint, request, jsonify
    
    bp = Blueprint('opencart_webhooks', __name__, url_prefix='/webhooks/opencart')
    
    @bp.route('/order', methods=['POST'])
    def handle_order_webhook():
        """Handle OpenCart order webhooks."""
        try:
            signature = request.headers.get('X-OpenCart-Signature')
            result = handler.process_webhook(request.data, signature)
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    @bp.route('/product', methods=['POST'])
    def handle_product_webhook():
        """Handle OpenCart product webhooks."""
        try:
            signature = request.headers.get('X-OpenCart-Signature')
            result = handler.process_webhook(request.data, signature)
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    @bp.route('/customer', methods=['POST'])
    def handle_customer_webhook():
        """Handle OpenCart customer webhooks."""
        try:
            signature = request.headers.get('X-OpenCart-Signature')
            result = handler.process_webhook(request.data, signature)
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    @bp.route('/stock', methods=['POST'])
    def handle_stock_webhook():
        """Handle OpenCart stock alert webhooks."""
        try:
            signature = request.headers.get('X-OpenCart-Signature')
            result = handler.process_webhook(request.data, signature)
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    return bp
