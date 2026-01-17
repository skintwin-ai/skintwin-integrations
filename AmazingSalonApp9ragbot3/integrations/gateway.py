"""
Unified API Gateway
Central orchestration layer for all platform integrations
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from .common.base_connector import BaseConnector
from .common.exceptions import IntegrationError, ConfigurationError
from .common.models import (
    UnifiedAppointment,
    UnifiedClient,
    UnifiedProduct,
    UnifiedOrder,
    PlatformReference,
    SyncStatus
)

from .wix import WixBookingsConnector
from .opencart import OpenCartConnector
from .shopify import ShopifyB2BConnector

logger = logging.getLogger(__name__)


class IntegrationGateway:
    """
    Unified API Gateway for managing all platform integrations.
    
    This gateway provides a single interface for:
    - Managing multiple platform connectors
    - Synchronizing data across platforms
    - Routing operations to appropriate connectors
    - Handling cross-platform data mapping
    """
    
    CONNECTOR_CLASSES = {
        'wix': WixBookingsConnector,
        'opencart': OpenCartConnector,
        'shopify': ShopifyB2BConnector
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the integration gateway.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self._connectors: Dict[str, BaseConnector] = {}
        self._initialized = False
        
        logger.info("Initialized Integration Gateway")
    
    def register_connector(
        self,
        platform: str,
        connector: BaseConnector
    ):
        """
        Register a platform connector.
        
        Args:
            platform: Platform identifier
            connector: Connector instance
        """
        self._connectors[platform] = connector
        logger.info(f"Registered connector for platform: {platform}")
    
    def get_connector(self, platform: str) -> Optional[BaseConnector]:
        """
        Get a registered connector by platform.
        
        Args:
            platform: Platform identifier
            
        Returns:
            BaseConnector: The connector instance, or None if not found
        """
        return self._connectors.get(platform)
    
    def initialize_from_config(self, config: Dict):
        """
        Initialize connectors from configuration.
        
        Args:
            config: Configuration dictionary with platform credentials
        """
        for platform, settings in config.get('platforms', {}).items():
            if not settings.get('enabled', True):
                logger.info(f"Skipping disabled platform: {platform}")
                continue
            
            connector_class = self.CONNECTOR_CLASSES.get(platform)
            if not connector_class:
                logger.warning(f"Unknown platform: {platform}")
                continue
            
            try:
                connector = self._create_connector(platform, settings)
                self.register_connector(platform, connector)
            except Exception as e:
                logger.error(f"Failed to initialize {platform} connector: {e}")
        
        self._initialized = True
        logger.info(f"Gateway initialized with {len(self._connectors)} connectors")
    
    def _create_connector(
        self,
        platform: str,
        settings: Dict
    ) -> BaseConnector:
        """
        Create a connector instance from settings.
        
        Args:
            platform: Platform identifier
            settings: Platform-specific settings
            
        Returns:
            BaseConnector: The created connector
        """
        if platform == 'wix':
            return WixBookingsConnector(
                site_id=settings['site_id'],
                api_key=settings['api_key'],
                account_id=settings.get('account_id')
            )
        elif platform == 'opencart':
            return OpenCartConnector(
                store_url=settings['store_url'],
                api_username=settings['api_username'],
                api_key=settings['api_key']
            )
        elif platform == 'shopify':
            return ShopifyB2BConnector(
                shop_name=settings['shop_name'],
                access_token=settings['access_token'],
                api_version=settings.get('api_version')
            )
        else:
            raise ConfigurationError(f"Unknown platform: {platform}")
    
    def test_connections(self) -> Dict[str, bool]:
        """
        Test all registered connector connections.
        
        Returns:
            Dict[str, bool]: Connection status for each platform
        """
        results = {}
        for platform, connector in self._connectors.items():
            try:
                results[platform] = connector.test_connection()
            except Exception as e:
                logger.error(f"Connection test failed for {platform}: {e}")
                results[platform] = False
        
        return results
    
    # ==================== Appointment Operations ====================
    
    def sync_appointments(
        self,
        platforms: Optional[List[str]] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, List[UnifiedAppointment]]:
        """
        Synchronize appointments from all or specified platforms.
        
        Args:
            platforms: List of platforms to sync (None for all)
            since: Only sync appointments modified since this time
            
        Returns:
            Dict[str, List[UnifiedAppointment]]: Appointments by platform
        """
        results = {}
        target_platforms = platforms or list(self._connectors.keys())
        
        for platform in target_platforms:
            connector = self._connectors.get(platform)
            if not connector:
                logger.warning(f"No connector for platform: {platform}")
                continue
            
            try:
                raw_appointments = connector.sync_appointments(since)
                
                # Map to unified model
                unified = []
                for raw in raw_appointments:
                    if platform == 'wix':
                        unified.append(connector.map_booking_to_unified(raw))
                    elif platform == 'shopify':
                        unified.append(connector.map_order_to_unified(raw))
                    # OpenCart orders are mapped similarly
                    elif platform == 'opencart':
                        unified.append(connector.map_order_to_unified(raw))
                
                results[platform] = unified
                logger.info(f"Synced {len(unified)} appointments from {platform}")
                
            except Exception as e:
                logger.error(f"Failed to sync appointments from {platform}: {e}")
                results[platform] = []
        
        return results
    
    def create_appointment(
        self,
        appointment: UnifiedAppointment,
        platforms: Optional[List[str]] = None
    ) -> Dict[str, Dict]:
        """
        Create an appointment across specified platforms.
        
        Args:
            appointment: Unified appointment data
            platforms: List of platforms to create on (None for all)
            
        Returns:
            Dict[str, Dict]: Created appointment data by platform
        """
        results = {}
        target_platforms = platforms or list(self._connectors.keys())
        
        appointment_data = appointment.to_dict()
        
        for platform in target_platforms:
            connector = self._connectors.get(platform)
            if not connector:
                continue
            
            try:
                result = connector.create_appointment(appointment_data)
                results[platform] = result
                
                # Add platform reference
                appointment.platform_refs.append(PlatformReference(
                    platform=platform,
                    external_id=str(result.get('id', '')),
                    last_synced=datetime.utcnow(),
                    sync_status=SyncStatus.SYNCED
                ))
                
                logger.info(f"Created appointment on {platform}: {result.get('id')}")
                
            except Exception as e:
                logger.error(f"Failed to create appointment on {platform}: {e}")
                results[platform] = {'error': str(e)}
        
        return results
    
    def update_appointment(
        self,
        appointment: UnifiedAppointment,
        platforms: Optional[List[str]] = None
    ) -> Dict[str, Dict]:
        """
        Update an appointment across specified platforms.
        
        Args:
            appointment: Unified appointment data with platform references
            platforms: List of platforms to update on (None for all with refs)
            
        Returns:
            Dict[str, Dict]: Updated appointment data by platform
        """
        results = {}
        
        for ref in appointment.platform_refs:
            if platforms and ref.platform not in platforms:
                continue
            
            connector = self._connectors.get(ref.platform)
            if not connector:
                continue
            
            try:
                result = connector.update_appointment(
                    ref.external_id,
                    appointment.to_dict()
                )
                results[ref.platform] = result
                ref.last_synced = datetime.utcnow()
                ref.sync_status = SyncStatus.SYNCED
                
                logger.info(f"Updated appointment on {ref.platform}: {ref.external_id}")
                
            except Exception as e:
                logger.error(f"Failed to update appointment on {ref.platform}: {e}")
                ref.sync_status = SyncStatus.FAILED
                results[ref.platform] = {'error': str(e)}
        
        return results
    
    def cancel_appointment(
        self,
        appointment: UnifiedAppointment,
        platforms: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """
        Cancel an appointment across specified platforms.
        
        Args:
            appointment: Unified appointment data with platform references
            platforms: List of platforms to cancel on (None for all with refs)
            
        Returns:
            Dict[str, bool]: Cancellation status by platform
        """
        results = {}
        
        for ref in appointment.platform_refs:
            if platforms and ref.platform not in platforms:
                continue
            
            connector = self._connectors.get(ref.platform)
            if not connector:
                continue
            
            try:
                success = connector.cancel_appointment(ref.external_id)
                results[ref.platform] = success
                
                if success:
                    ref.last_synced = datetime.utcnow()
                    ref.sync_status = SyncStatus.SYNCED
                    logger.info(f"Cancelled appointment on {ref.platform}: {ref.external_id}")
                else:
                    ref.sync_status = SyncStatus.FAILED
                    
            except Exception as e:
                logger.error(f"Failed to cancel appointment on {ref.platform}: {e}")
                ref.sync_status = SyncStatus.FAILED
                results[ref.platform] = False
        
        return results
    
    # ==================== Client Operations ====================
    
    def sync_clients(
        self,
        platforms: Optional[List[str]] = None,
        since: Optional[datetime] = None
    ) -> Dict[str, List[UnifiedClient]]:
        """
        Synchronize clients from all or specified platforms.
        
        Args:
            platforms: List of platforms to sync (None for all)
            since: Only sync clients modified since this time
            
        Returns:
            Dict[str, List[UnifiedClient]]: Clients by platform
        """
        results = {}
        target_platforms = platforms or list(self._connectors.keys())
        
        for platform in target_platforms:
            connector = self._connectors.get(platform)
            if not connector:
                continue
            
            try:
                raw_clients = connector.sync_clients(since)
                
                # Map to unified model
                unified = []
                for raw in raw_clients:
                    if platform == 'shopify':
                        unified.append(connector.map_customer_to_unified(raw))
                    # Add mappings for other platforms as needed
                
                results[platform] = unified
                logger.info(f"Synced {len(unified)} clients from {platform}")
                
            except Exception as e:
                logger.error(f"Failed to sync clients from {platform}: {e}")
                results[platform] = []
        
        return results
    
    # ==================== Product Operations ====================
    
    def sync_products(
        self,
        platforms: Optional[List[str]] = None
    ) -> Dict[str, List[UnifiedProduct]]:
        """
        Synchronize products from all or specified platforms.
        
        Args:
            platforms: List of platforms to sync (None for all)
            
        Returns:
            Dict[str, List[UnifiedProduct]]: Products by platform
        """
        results = {}
        target_platforms = platforms or list(self._connectors.keys())
        
        for platform in target_platforms:
            connector = self._connectors.get(platform)
            if not connector:
                continue
            
            try:
                if platform == 'shopify':
                    raw_products = connector.get_products()
                    unified = [connector.map_product_to_unified(p) for p in raw_products]
                    results[platform] = unified
                    logger.info(f"Synced {len(unified)} products from {platform}")
                else:
                    results[platform] = []
                    
            except Exception as e:
                logger.error(f"Failed to sync products from {platform}: {e}")
                results[platform] = []
        
        return results
    
    # ==================== B2B Operations (Shopify) ====================
    
    def get_b2b_companies(self) -> List[Dict]:
        """
        Get B2B companies from Shopify.
        
        Returns:
            List[Dict]: List of companies
        """
        shopify = self._connectors.get('shopify')
        if not shopify or not isinstance(shopify, ShopifyB2BConnector):
            logger.warning("Shopify B2B connector not available")
            return []
        
        try:
            return shopify.get_companies()
        except Exception as e:
            logger.error(f"Failed to get B2B companies: {e}")
            return []
    
    def create_b2b_company(
        self,
        name: str,
        external_id: Optional[str] = None,
        note: Optional[str] = None
    ) -> Dict:
        """
        Create a B2B company on Shopify.
        
        Args:
            name: Company name
            external_id: External reference ID
            note: Company note
            
        Returns:
            Dict: Created company data
        """
        shopify = self._connectors.get('shopify')
        if not shopify or not isinstance(shopify, ShopifyB2BConnector):
            raise IntegrationError("Shopify B2B connector not available")
        
        return shopify.create_company(name, external_id, note)
    
    def create_draft_order(self, draft_order_data: Dict) -> Dict:
        """
        Create a draft order on Shopify (B2B approval workflow).
        
        Args:
            draft_order_data: Draft order details
            
        Returns:
            Dict: Created draft order data
        """
        shopify = self._connectors.get('shopify')
        if not shopify or not isinstance(shopify, ShopifyB2BConnector):
            raise IntegrationError("Shopify B2B connector not available")
        
        return shopify.create_draft_order(draft_order_data)
    
    # ==================== Webhook Registration ====================
    
    def register_webhooks(self, callback_base_url: str) -> Dict[str, List[Dict]]:
        """
        Register webhooks for all platforms.
        
        Args:
            callback_base_url: Base URL for webhook callbacks
            
        Returns:
            Dict[str, List[Dict]]: Registered webhooks by platform
        """
        results = {}
        
        # Shopify webhooks
        shopify = self._connectors.get('shopify')
        if shopify and isinstance(shopify, ShopifyB2BConnector):
            topics = [
                'orders/create',
                'orders/updated',
                'orders/cancelled',
                'products/create',
                'products/update',
                'customers/create',
                'customers/update',
                'draft_orders/create',
                'draft_orders/update'
            ]
            
            results['shopify'] = []
            for topic in topics:
                try:
                    webhook = shopify.create_webhook(
                        topic=topic,
                        address=f"{callback_base_url}/webhooks/shopify"
                    )
                    results['shopify'].append(webhook)
                except Exception as e:
                    logger.error(f"Failed to register Shopify webhook {topic}: {e}")
        
        # Note: Wix and OpenCart webhook registration would be similar
        # but may require different approaches based on their APIs
        
        return results
    
    # ==================== Health Check ====================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on all integrations.
        
        Returns:
            Dict: Health status for all components
        """
        status = {
            'gateway': 'healthy',
            'initialized': self._initialized,
            'connectors': {},
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for platform, connector in self._connectors.items():
            try:
                connected = connector.test_connection()
                status['connectors'][platform] = {
                    'status': 'connected' if connected else 'disconnected',
                    'type': connector.__class__.__name__
                }
            except Exception as e:
                status['connectors'][platform] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Overall status
        all_connected = all(
            c.get('status') == 'connected'
            for c in status['connectors'].values()
        )
        status['gateway'] = 'healthy' if all_connected else 'degraded'
        
        return status


def create_gateway_blueprint(gateway: IntegrationGateway):
    """
    Create a Flask blueprint for the integration gateway API.
    
    Args:
        gateway: IntegrationGateway instance
        
    Returns:
        Blueprint: Flask blueprint for gateway routes
    """
    from flask import Blueprint, request, jsonify
    
    bp = Blueprint('integration_gateway', __name__, url_prefix='/api/integrations')
    
    @bp.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint."""
        return jsonify(gateway.health_check())
    
    @bp.route('/test-connections', methods=['GET'])
    def test_connections():
        """Test all platform connections."""
        return jsonify(gateway.test_connections())
    
    @bp.route('/appointments/sync', methods=['POST'])
    def sync_appointments():
        """Sync appointments from platforms."""
        data = request.get_json() or {}
        platforms = data.get('platforms')
        since = data.get('since')
        
        if since:
            since = datetime.fromisoformat(since)
        
        results = gateway.sync_appointments(platforms, since)
        
        # Convert to serializable format
        serialized = {}
        for platform, appointments in results.items():
            serialized[platform] = [a.to_dict() for a in appointments]
        
        return jsonify(serialized)
    
    @bp.route('/clients/sync', methods=['POST'])
    def sync_clients():
        """Sync clients from platforms."""
        data = request.get_json() or {}
        platforms = data.get('platforms')
        since = data.get('since')
        
        if since:
            since = datetime.fromisoformat(since)
        
        results = gateway.sync_clients(platforms, since)
        
        # Convert to serializable format
        serialized = {}
        for platform, clients in results.items():
            serialized[platform] = [c.to_dict() for c in clients]
        
        return jsonify(serialized)
    
    @bp.route('/products/sync', methods=['POST'])
    def sync_products():
        """Sync products from platforms."""
        data = request.get_json() or {}
        platforms = data.get('platforms')
        
        results = gateway.sync_products(platforms)
        
        # Convert to serializable format
        serialized = {}
        for platform, products in results.items():
            serialized[platform] = [p.to_dict() for p in products]
        
        return jsonify(serialized)
    
    @bp.route('/b2b/companies', methods=['GET'])
    def get_companies():
        """Get B2B companies."""
        return jsonify(gateway.get_b2b_companies())
    
    @bp.route('/b2b/companies', methods=['POST'])
    def create_company():
        """Create a B2B company."""
        data = request.get_json()
        result = gateway.create_b2b_company(
            name=data['name'],
            external_id=data.get('external_id'),
            note=data.get('note')
        )
        return jsonify(result), 201
    
    return bp
