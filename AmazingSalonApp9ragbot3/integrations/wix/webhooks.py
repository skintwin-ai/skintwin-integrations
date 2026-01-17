"""
Wix Webhook Handler
Processes incoming webhooks from Wix Bookings
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from ..common.exceptions import WebhookError

logger = logging.getLogger(__name__)


class WixWebhookHandler:
    """
    Handler for Wix webhook events.
    
    Wix sends webhooks for various booking events including:
    - Booking created
    - Booking updated
    - Booking cancelled
    - Service changes
    """
    
    # Webhook event types
    EVENT_TYPES = {
        'booking/created': 'on_booking_created',
        'booking/updated': 'on_booking_updated',
        'booking/canceled': 'on_booking_cancelled',
        'booking/confirmed': 'on_booking_confirmed',
        'booking/declined': 'on_booking_declined',
        'service/created': 'on_service_created',
        'service/updated': 'on_service_updated',
        'service/deleted': 'on_service_deleted',
        'staff/created': 'on_staff_created',
        'staff/updated': 'on_staff_updated',
        'staff/deleted': 'on_staff_deleted'
    }
    
    def __init__(self, webhook_secret: str):
        """
        Initialize the webhook handler.
        
        Args:
            webhook_secret: Secret key for webhook signature verification
        """
        self.webhook_secret = webhook_secret
        self._handlers: Dict[str, Callable] = {}
        
        logger.info("Initialized Wix webhook handler")
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify the webhook signature.
        
        Args:
            payload: Raw request body
            signature: Signature from X-Wix-Signature header
            
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
            event_type: Event type (e.g., 'booking/created')
            handler: Callback function to handle the event
        """
        if event_type not in self.EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}")
        
        self._handlers[event_type] = handler
        logger.info(f"Registered handler for Wix event: {event_type}")
    
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
        
        event_type = data.get('eventType', data.get('type', 'unknown'))
        event_data = data.get('data', data)
        
        logger.info(f"Processing Wix webhook: {event_type}")
        
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
    
    # Default event handlers (can be overridden)
    
    def on_booking_created(self, data: Dict) -> Dict:
        """Handle booking created event."""
        booking = data.get('booking', data)
        logger.info(f"Booking created: {booking.get('id')}")
        return {'action': 'create', 'booking_id': booking.get('id')}
    
    def on_booking_updated(self, data: Dict) -> Dict:
        """Handle booking updated event."""
        booking = data.get('booking', data)
        logger.info(f"Booking updated: {booking.get('id')}")
        return {'action': 'update', 'booking_id': booking.get('id')}
    
    def on_booking_cancelled(self, data: Dict) -> Dict:
        """Handle booking cancelled event."""
        booking = data.get('booking', data)
        logger.info(f"Booking cancelled: {booking.get('id')}")
        return {'action': 'cancel', 'booking_id': booking.get('id')}
    
    def on_booking_confirmed(self, data: Dict) -> Dict:
        """Handle booking confirmed event."""
        booking = data.get('booking', data)
        logger.info(f"Booking confirmed: {booking.get('id')}")
        return {'action': 'confirm', 'booking_id': booking.get('id')}
    
    def on_booking_declined(self, data: Dict) -> Dict:
        """Handle booking declined event."""
        booking = data.get('booking', data)
        logger.info(f"Booking declined: {booking.get('id')}")
        return {'action': 'decline', 'booking_id': booking.get('id')}


def create_wix_webhook_blueprint(handler: WixWebhookHandler):
    """
    Create a Flask blueprint for Wix webhooks.
    
    Args:
        handler: WixWebhookHandler instance
        
    Returns:
        Blueprint: Flask blueprint for webhook routes
    """
    from flask import Blueprint, request, jsonify
    
    bp = Blueprint('wix_webhooks', __name__, url_prefix='/webhooks/wix')
    
    @bp.route('/booking', methods=['POST'])
    def handle_booking_webhook():
        """Handle Wix booking webhooks."""
        try:
            signature = request.headers.get('X-Wix-Signature')
            result = handler.process_webhook(request.data, signature)
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    @bp.route('/service', methods=['POST'])
    def handle_service_webhook():
        """Handle Wix service webhooks."""
        try:
            signature = request.headers.get('X-Wix-Signature')
            result = handler.process_webhook(request.data, signature)
            return jsonify(result), 200
        except WebhookError as e:
            logger.error(f"Webhook error: {e}")
            return jsonify({'error': str(e)}), 400
        except Exception as e:
            logger.error(f"Unexpected webhook error: {e}")
            return jsonify({'error': 'Internal error'}), 500
    
    return bp
