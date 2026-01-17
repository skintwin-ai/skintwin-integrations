"""
Unified Webhook Router
Central routing and processing for all platform webhooks
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from flask import Blueprint, request, jsonify

from .common.exceptions import WebhookError
from .wix.webhooks import WixWebhookHandler
from .opencart.webhooks import OpenCartWebhookHandler
from .shopify.webhooks import ShopifyWebhookHandler

logger = logging.getLogger(__name__)


class WebhookRouter:
    """
    Unified webhook router for all platform integrations.
    
    This router:
    - Routes incoming webhooks to appropriate handlers
    - Provides a unified event system for cross-platform events
    - Handles webhook verification and security
    - Logs and tracks all webhook activity
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the webhook router.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._handlers: Dict[str, Any] = {}
        self._event_listeners: Dict[str, List[Callable]] = {}
        self._webhook_log: List[Dict] = []
        
        logger.info("Initialized Webhook Router")
    
    def register_handler(self, platform: str, handler: Any):
        """
        Register a platform-specific webhook handler.
        
        Args:
            platform: Platform identifier
            handler: Platform webhook handler instance
        """
        self._handlers[platform] = handler
        logger.info(f"Registered webhook handler for: {platform}")
    
    def initialize_handlers(self, config: Dict):
        """
        Initialize webhook handlers from configuration.
        
        Args:
            config: Configuration with webhook secrets
        """
        platforms_config = config.get('platforms', {})
        
        # Wix handler
        if 'wix' in platforms_config:
            wix_config = platforms_config['wix']
            self._handlers['wix'] = WixWebhookHandler(
                webhook_secret=wix_config.get('webhook_secret', '')
            )
        
        # OpenCart handler
        if 'opencart' in platforms_config:
            opencart_config = platforms_config['opencart']
            self._handlers['opencart'] = OpenCartWebhookHandler(
                webhook_secret=opencart_config.get('webhook_secret', '')
            )
        
        # Shopify handler
        if 'shopify' in platforms_config:
            shopify_config = platforms_config['shopify']
            self._handlers['shopify'] = ShopifyWebhookHandler(
                webhook_secret=shopify_config.get('webhook_secret', '')
            )
        
        logger.info(f"Initialized {len(self._handlers)} webhook handlers")
    
    def add_event_listener(self, event_type: str, callback: Callable):
        """
        Add a listener for unified events.
        
        Args:
            event_type: Event type to listen for
            callback: Callback function
        """
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
        
        self._event_listeners[event_type].append(callback)
        logger.info(f"Added listener for event: {event_type}")
    
    def remove_event_listener(self, event_type: str, callback: Callable):
        """
        Remove an event listener.
        
        Args:
            event_type: Event type
            callback: Callback function to remove
        """
        if event_type in self._event_listeners:
            self._event_listeners[event_type] = [
                cb for cb in self._event_listeners[event_type]
                if cb != callback
            ]
    
    def _emit_event(self, event_type: str, data: Dict):
        """
        Emit a unified event to all listeners.
        
        Args:
            event_type: Event type
            data: Event data
        """
        listeners = self._event_listeners.get(event_type, [])
        for callback in listeners:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Event listener error for {event_type}: {e}")
        
        # Also emit to wildcard listeners
        for callback in self._event_listeners.get('*', []):
            try:
                callback({'type': event_type, 'data': data})
            except Exception as e:
                logger.error(f"Wildcard listener error: {e}")
    
    def process_webhook(
        self,
        platform: str,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Process an incoming webhook.
        
        Args:
            platform: Platform identifier
            payload: Raw webhook payload
            headers: Request headers
            
        Returns:
            Dict: Processing result
        """
        handler = self._handlers.get(platform)
        if not handler:
            raise WebhookError(f"No handler for platform: {platform}")
        
        # Log the webhook
        log_entry = {
            'platform': platform,
            'timestamp': datetime.utcnow().isoformat(),
            'headers': dict(headers),
            'status': 'processing'
        }
        self._webhook_log.append(log_entry)
        
        try:
            # Process based on platform
            if platform == 'wix':
                result = self._process_wix_webhook(handler, payload, headers)
            elif platform == 'opencart':
                result = self._process_opencart_webhook(handler, payload, headers)
            elif platform == 'shopify':
                result = self._process_shopify_webhook(handler, payload, headers)
            else:
                raise WebhookError(f"Unknown platform: {platform}")
            
            log_entry['status'] = 'processed'
            log_entry['result'] = result
            
            # Emit unified event
            unified_event = self._map_to_unified_event(platform, result)
            if unified_event:
                self._emit_event(unified_event['type'], unified_event['data'])
            
            return result
            
        except Exception as e:
            log_entry['status'] = 'error'
            log_entry['error'] = str(e)
            raise
    
    def _process_wix_webhook(
        self,
        handler: WixWebhookHandler,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Dict:
        """Process a Wix webhook."""
        signature = headers.get('X-Wix-Signature', '')
        
        return handler.process_webhook(
            payload=payload,
            signature=signature
        )
    
    def _process_opencart_webhook(
        self,
        handler: OpenCartWebhookHandler,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Dict:
        """Process an OpenCart webhook."""
        signature = headers.get('X-OpenCart-Signature', '')
        event_type = headers.get('X-OpenCart-Event', '')
        
        return handler.process_webhook(
            payload=payload,
            event_type=event_type,
            signature=signature
        )
    
    def _process_shopify_webhook(
        self,
        handler: ShopifyWebhookHandler,
        payload: bytes,
        headers: Dict[str, str]
    ) -> Dict:
        """Process a Shopify webhook."""
        topic = headers.get('X-Shopify-Topic', '')
        signature = headers.get('X-Shopify-Hmac-SHA256', '')
        shop_domain = headers.get('X-Shopify-Shop-Domain', '')
        
        return handler.process_webhook(
            payload=payload,
            topic=topic,
            signature=signature,
            shop_domain=shop_domain
        )
    
    def _map_to_unified_event(
        self,
        platform: str,
        result: Dict
    ) -> Optional[Dict]:
        """
        Map platform-specific result to unified event.
        
        Args:
            platform: Platform identifier
            result: Platform-specific result
            
        Returns:
            Dict: Unified event or None
        """
        if result.get('status') != 'processed':
            return None
        
        topic = result.get('topic', result.get('event_type', ''))
        
        # Map to unified event types
        event_mapping = {
            # Appointments/Bookings
            'bookings/created': 'appointment.created',
            'bookings/updated': 'appointment.updated',
            'bookings/cancelled': 'appointment.cancelled',
            'orders/create': 'order.created',
            'orders/updated': 'order.updated',
            'orders/cancelled': 'order.cancelled',
            'order/created': 'order.created',
            'order/updated': 'order.updated',
            
            # Products
            'products/create': 'product.created',
            'products/update': 'product.updated',
            'products/delete': 'product.deleted',
            'product/created': 'product.created',
            'product/updated': 'product.updated',
            
            # Customers
            'customers/create': 'customer.created',
            'customers/update': 'customer.updated',
            'customers/delete': 'customer.deleted',
            'customer/created': 'customer.created',
            'customer/updated': 'customer.updated',
            
            # B2B
            'draft_orders/create': 'draft_order.created',
            'draft_orders/update': 'draft_order.updated'
        }
        
        unified_type = event_mapping.get(topic)
        if not unified_type:
            return None
        
        return {
            'type': unified_type,
            'data': {
                'platform': platform,
                'original_topic': topic,
                'result': result.get('result', {}),
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    def get_webhook_log(
        self,
        limit: int = 100,
        platform: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent webhook log entries.
        
        Args:
            limit: Maximum entries to return
            platform: Filter by platform
            
        Returns:
            List[Dict]: Log entries
        """
        logs = self._webhook_log
        
        if platform:
            logs = [l for l in logs if l.get('platform') == platform]
        
        return logs[-limit:]


def create_webhook_router_blueprint(router: WebhookRouter) -> Blueprint:
    """
    Create a Flask blueprint for the webhook router.
    
    Args:
        router: WebhookRouter instance
        
    Returns:
        Blueprint: Flask blueprint for webhook routes
    """
    bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')
    
    @bp.route('/wix', methods=['POST'])
    def handle_wix_webhook():
        """Handle Wix webhooks."""
        try:
            result = router.process_webhook(
                platform='wix',
                payload=request.data,
                headers=dict(request.headers)
            )
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"Wix webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected Wix webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    @bp.route('/opencart', methods=['POST'])
    def handle_opencart_webhook():
        """Handle OpenCart webhooks."""
        try:
            result = router.process_webhook(
                platform='opencart',
                payload=request.data,
                headers=dict(request.headers)
            )
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"OpenCart webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected OpenCart webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    @bp.route('/shopify', methods=['POST'])
    def handle_shopify_webhook():
        """Handle Shopify webhooks."""
        try:
            result = router.process_webhook(
                platform='shopify',
                payload=request.data,
                headers=dict(request.headers)
            )
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"Shopify webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected Shopify webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    @bp.route('/log', methods=['GET'])
    def get_webhook_log():
        """Get webhook log."""
        limit = request.args.get('limit', 100, type=int)
        platform = request.args.get('platform')
        
        return jsonify(router.get_webhook_log(limit, platform))
    
    return bp


# ==================== Event Handlers ====================

class SyncEventHandler:
    """
    Event handler for synchronizing data across platforms.
    
    Listens to webhook events and triggers cross-platform sync operations.
    """
    
    def __init__(self, gateway):
        """
        Initialize the sync event handler.
        
        Args:
            gateway: IntegrationGateway instance
        """
        self.gateway = gateway
        logger.info("Initialized Sync Event Handler")
    
    def on_appointment_created(self, data: Dict):
        """Handle appointment created event."""
        platform = data.get('platform')
        logger.info(f"Appointment created on {platform}, syncing...")
        # Implement cross-platform sync logic here
    
    def on_appointment_updated(self, data: Dict):
        """Handle appointment updated event."""
        platform = data.get('platform')
        logger.info(f"Appointment updated on {platform}, syncing...")
        # Implement cross-platform sync logic here
    
    def on_order_created(self, data: Dict):
        """Handle order created event."""
        platform = data.get('platform')
        logger.info(f"Order created on {platform}")
        # Implement order processing logic here
    
    def on_customer_created(self, data: Dict):
        """Handle customer created event."""
        platform = data.get('platform')
        logger.info(f"Customer created on {platform}, syncing...")
        # Implement cross-platform customer sync here
    
    def on_product_updated(self, data: Dict):
        """Handle product updated event."""
        platform = data.get('platform')
        logger.info(f"Product updated on {platform}, syncing inventory...")
        # Implement inventory sync logic here
    
    def register_with_router(self, router: WebhookRouter):
        """
        Register event handlers with the webhook router.
        
        Args:
            router: WebhookRouter instance
        """
        router.add_event_listener('appointment.created', self.on_appointment_created)
        router.add_event_listener('appointment.updated', self.on_appointment_updated)
        router.add_event_listener('order.created', self.on_order_created)
        router.add_event_listener('customer.created', self.on_customer_created)
        router.add_event_listener('product.updated', self.on_product_updated)
        
        logger.info("Registered sync event handlers with router")
