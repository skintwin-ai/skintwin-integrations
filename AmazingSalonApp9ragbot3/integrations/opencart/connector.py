"""
OpenCart API Connector
Handles all interactions with the OpenCart REST API
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..common.base_connector import BaseConnector
from ..common.exceptions import (
    AuthenticationError,
    IntegrationError,
    ValidationError
)
from ..common.models import (
    UnifiedAppointment,
    UnifiedClient,
    UnifiedProduct,
    UnifiedOrder,
    UnifiedOrderItem,
    PaymentStatus,
    PlatformReference,
    SyncStatus
)

logger = logging.getLogger(__name__)


class OpenCartConnector(BaseConnector):
    """
    Connector for OpenCart REST API.
    
    OpenCart API Documentation:
    https://docs.opencart.com/system/users/api/
    """
    
    PLATFORM_NAME = "opencart"
    
    # API Endpoints
    ENDPOINTS = {
        'login': 'api/login',
        'cart_add': 'api/cart/add',
        'cart_edit': 'api/cart/edit',
        'cart_remove': 'api/cart/remove',
        'cart_products': 'api/cart/products',
        'customer': 'api/customer',
        'order_add': 'api/order/add',
        'order_edit': 'api/order/edit',
        'order_history': 'api/order/history',
        'shipping_address': 'api/shipping/address',
        'shipping_methods': 'api/shipping/methods',
        'shipping_method': 'api/shipping/method',
        'payment_address': 'api/payment/address',
        'payment_methods': 'api/payment/methods',
        'payment_method': 'api/payment/method',
        'coupon': 'api/coupon',
        'voucher': 'api/voucher',
        'reward': 'api/reward',
        'currency': 'api/currency'
    }
    
    def __init__(
        self,
        store_url: str,
        api_username: str,
        api_key: str,
        **kwargs
    ):
        """
        Initialize the OpenCart connector.
        
        Args:
            store_url: OpenCart store URL
            api_username: API username (from System > Users > API)
            api_key: API key (256 character key)
        """
        # Ensure URL ends with index.php
        if not store_url.endswith('/'):
            store_url += '/'
        
        super().__init__(
            base_url=store_url,
            api_key=api_key,
            rate_limit_per_minute=60,
            **kwargs
        )
        
        self.api_username = api_username
        self._api_token: Optional[str] = None
        
        logger.info(f"Initialized OpenCart connector for store: {store_url}")
    
    def authenticate(self) -> bool:
        """
        Authenticate with OpenCart API.
        Establishes a session and obtains an API token.
        
        Returns:
            bool: True if authentication was successful
        """
        try:
            response = self.session.post(
                f"{self.base_url}index.php?route={self.ENDPOINTS['login']}",
                data={
                    'username': self.api_username,
                    'key': self.api_key
                },
                timeout=self.timeout
            )
            
            data = response.json()
            
            if 'api_token' in data:
                self._api_token = data['api_token']
                logger.info("OpenCart authentication successful")
                return True
            elif 'error' in data:
                raise AuthenticationError(
                    f"OpenCart authentication failed: {data['error']}",
                    platform=self.PLATFORM_NAME
                )
            else:
                raise AuthenticationError(
                    "OpenCart authentication failed: No token received",
                    platform=self.PLATFORM_NAME
                )
                
        except Exception as e:
            logger.error(f"OpenCart authentication failed: {e}")
            raise AuthenticationError(
                f"Failed to authenticate with OpenCart: {e}",
                platform=self.PLATFORM_NAME
            )
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for OpenCart API requests."""
        return {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the OpenCart API.
        OpenCart uses form-encoded data and api_token as query parameter.
        """
        self._check_rate_limit()
        
        # Ensure we have a valid token
        if not self._api_token:
            self.authenticate()
        
        # Build URL with api_token
        url = f"{self.base_url}index.php?route={endpoint}"
        
        # Add api_token to params
        if params is None:
            params = {}
        params['api_token'] = self._api_token
        
        request_headers = self.get_headers()
        if headers:
            request_headers.update(headers)
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(
                    url,
                    params=params,
                    headers=request_headers,
                    timeout=self.timeout
                )
            else:
                response = self.session.post(
                    url,
                    params=params,
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout
                )
            
            # Handle authentication errors
            if response.status_code == 401:
                logger.warning("OpenCart token expired, re-authenticating")
                self._api_token = None
                if self.authenticate():
                    return self._make_request(method, endpoint, data, params, headers)
                raise AuthenticationError("Failed to re-authenticate with OpenCart")
            
            response.raise_for_status()
            
            try:
                result = response.json()
                
                # Check for API errors
                if 'error' in result:
                    raise IntegrationError(
                        f"OpenCart API error: {result['error']}",
                        platform=self.PLATFORM_NAME
                    )
                
                return result
            except ValueError:
                return {'status': 'success', 'raw': response.text}
                
        except Exception as e:
            logger.error(f"OpenCart request failed: {e}")
            raise IntegrationError(f"Request to {url} failed: {e}", platform=self.PLATFORM_NAME)
    
    def test_connection(self) -> bool:
        """Test the connection to OpenCart API."""
        try:
            return self.authenticate()
        except Exception as e:
            logger.error(f"OpenCart connection test failed: {e}")
            return False
    
    # ==================== Cart Operations ====================
    
    def add_to_cart(
        self,
        product_id: int,
        quantity: int = 1,
        options: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Add a product to the cart.
        
        Args:
            product_id: Product ID
            quantity: Quantity to add
            options: Product options
            
        Returns:
            Dict: Cart response
        """
        data = {
            'product_id': str(product_id),
            'quantity': str(quantity)
        }
        
        if options:
            data['option'] = options
        
        return self._make_request('POST', self.ENDPOINTS['cart_add'], data=data)
    
    def edit_cart(self, cart_id: int, quantity: int) -> Dict[str, Any]:
        """
        Edit cart item quantity.
        
        Args:
            cart_id: Cart item ID
            quantity: New quantity
            
        Returns:
            Dict: Cart response
        """
        return self._make_request('POST', self.ENDPOINTS['cart_edit'], data={
            'key': str(cart_id),
            'quantity': str(quantity)
        })
    
    def remove_from_cart(self, cart_id: int) -> Dict[str, Any]:
        """
        Remove item from cart.
        
        Args:
            cart_id: Cart item ID
            
        Returns:
            Dict: Cart response
        """
        return self._make_request('POST', self.ENDPOINTS['cart_remove'], data={
            'key': str(cart_id)
        })
    
    def get_cart(self) -> Dict[str, Any]:
        """
        Get current cart contents.
        
        Returns:
            Dict: Cart contents
        """
        return self._make_request('POST', self.ENDPOINTS['cart_products'])
    
    # ==================== Customer Operations ====================
    
    def set_customer(
        self,
        first_name: str,
        last_name: str,
        email: str,
        telephone: str
    ) -> Dict[str, Any]:
        """
        Set customer for current session.
        
        Args:
            first_name: Customer first name
            last_name: Customer last name
            email: Customer email
            telephone: Customer phone number
            
        Returns:
            Dict: Customer response
        """
        return self._make_request('POST', self.ENDPOINTS['customer'], data={
            'firstname': first_name,
            'lastname': last_name,
            'email': email,
            'telephone': telephone
        })
    
    def sync_clients(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Synchronize customers from OpenCart.
        Note: OpenCart API doesn't have a direct customer list endpoint.
        This would require a custom extension or direct database access.
        
        Args:
            since: Only sync customers modified since this time
            
        Returns:
            List[Dict]: List of synchronized customers
        """
        logger.warning("OpenCart standard API doesn't support customer listing. "
                      "Consider using a custom extension.")
        return []
    
    # ==================== Order Operations ====================
    
    def create_order(self) -> Dict[str, Any]:
        """
        Create an order from current cart and session data.
        Requires customer, shipping, and payment to be set first.
        
        Returns:
            Dict: Created order data
        """
        return self._make_request('POST', self.ENDPOINTS['order_add'])
    
    def update_order_history(
        self,
        order_id: int,
        order_status_id: int,
        comment: str = "",
        notify: bool = False
    ) -> Dict[str, Any]:
        """
        Add history entry to an order.
        
        Args:
            order_id: Order ID
            order_status_id: New status ID
            comment: Optional comment
            notify: Whether to notify customer
            
        Returns:
            Dict: Order history response
        """
        return self._make_request('POST', self.ENDPOINTS['order_history'], data={
            'order_id': str(order_id),
            'order_status_id': str(order_status_id),
            'comment': comment,
            'notify': '1' if notify else '0'
        })
    
    def sync_appointments(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Synchronize orders from OpenCart (treated as appointments for services).
        Note: Requires custom extension for order listing.
        
        Args:
            since: Only sync orders modified since this time
            
        Returns:
            List[Dict]: List of synchronized orders
        """
        logger.warning("OpenCart standard API doesn't support order listing. "
                      "Consider using a custom extension.")
        return []
    
    def create_appointment(self, appointment_data: Dict) -> Dict:
        """
        Create an order on OpenCart (appointment as order).
        
        Args:
            appointment_data: Appointment/order details
            
        Returns:
            Dict: Created order data
        """
        # Set customer
        self.set_customer(
            first_name=appointment_data.get('client_first_name', ''),
            last_name=appointment_data.get('client_last_name', ''),
            email=appointment_data.get('client_email', ''),
            telephone=appointment_data.get('client_phone', '')
        )
        
        # Add products/services to cart
        for item in appointment_data.get('items', []):
            self.add_to_cart(
                product_id=item.get('product_id'),
                quantity=item.get('quantity', 1)
            )
        
        # Set shipping address if provided
        if appointment_data.get('shipping_address'):
            self.set_shipping_address(appointment_data['shipping_address'])
        
        # Set payment address if provided
        if appointment_data.get('billing_address'):
            self.set_payment_address(appointment_data['billing_address'])
        
        # Create order
        return self.create_order()
    
    def update_appointment(self, appointment_id: str, appointment_data: Dict) -> Dict:
        """
        Update an order on OpenCart.
        
        Args:
            appointment_id: Order ID
            appointment_data: Updated order details
            
        Returns:
            Dict: Updated order data
        """
        # OpenCart doesn't have direct order update
        # Update via order history
        if appointment_data.get('status'):
            return self.update_order_history(
                order_id=int(appointment_id),
                order_status_id=appointment_data.get('status_id', 1),
                comment=appointment_data.get('notes', '')
            )
        
        return {'order_id': appointment_id, 'status': 'updated'}
    
    def cancel_appointment(self, appointment_id: str) -> bool:
        """
        Cancel an order on OpenCart.
        
        Args:
            appointment_id: Order ID
            
        Returns:
            bool: True if cancellation was successful
        """
        try:
            # Status ID 7 is typically "Canceled" in OpenCart
            self.update_order_history(
                order_id=int(appointment_id),
                order_status_id=7,
                comment="Order cancelled via integration",
                notify=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to cancel OpenCart order {appointment_id}: {e}")
            return False
    
    # ==================== Shipping Operations ====================
    
    def set_shipping_address(self, address: Dict) -> Dict[str, Any]:
        """
        Set shipping address for current session.
        
        Args:
            address: Address details
            
        Returns:
            Dict: Response
        """
        return self._make_request('POST', self.ENDPOINTS['shipping_address'], data={
            'firstname': address.get('first_name', ''),
            'lastname': address.get('last_name', ''),
            'address_1': address.get('address_1', ''),
            'address_2': address.get('address_2', ''),
            'city': address.get('city', ''),
            'postcode': address.get('postcode', ''),
            'country_id': address.get('country_id', ''),
            'zone_id': address.get('zone_id', '')
        })
    
    def get_shipping_methods(self) -> Dict[str, Any]:
        """
        Get available shipping methods.
        
        Returns:
            Dict: Available shipping methods
        """
        return self._make_request('POST', self.ENDPOINTS['shipping_methods'])
    
    def set_shipping_method(self, shipping_method: str) -> Dict[str, Any]:
        """
        Set shipping method for current session.
        
        Args:
            shipping_method: Shipping method code (e.g., 'flat.flat')
            
        Returns:
            Dict: Response
        """
        return self._make_request('POST', self.ENDPOINTS['shipping_method'], data={
            'shipping_method': shipping_method
        })
    
    # ==================== Payment Operations ====================
    
    def set_payment_address(self, address: Dict) -> Dict[str, Any]:
        """
        Set payment/billing address for current session.
        
        Args:
            address: Address details
            
        Returns:
            Dict: Response
        """
        return self._make_request('POST', self.ENDPOINTS['payment_address'], data={
            'firstname': address.get('first_name', ''),
            'lastname': address.get('last_name', ''),
            'address_1': address.get('address_1', ''),
            'address_2': address.get('address_2', ''),
            'city': address.get('city', ''),
            'postcode': address.get('postcode', ''),
            'country_id': address.get('country_id', ''),
            'zone_id': address.get('zone_id', '')
        })
    
    def get_payment_methods(self) -> Dict[str, Any]:
        """
        Get available payment methods.
        
        Returns:
            Dict: Available payment methods
        """
        return self._make_request('POST', self.ENDPOINTS['payment_methods'])
    
    def set_payment_method(self, payment_method: str) -> Dict[str, Any]:
        """
        Set payment method for current session.
        
        Args:
            payment_method: Payment method code (e.g., 'cod')
            
        Returns:
            Dict: Response
        """
        return self._make_request('POST', self.ENDPOINTS['payment_method'], data={
            'payment_method': payment_method
        })
    
    # ==================== Coupon/Voucher Operations ====================
    
    def apply_coupon(self, coupon_code: str) -> Dict[str, Any]:
        """
        Apply a coupon code.
        
        Args:
            coupon_code: Coupon code
            
        Returns:
            Dict: Response
        """
        return self._make_request('POST', self.ENDPOINTS['coupon'], data={
            'coupon': coupon_code
        })
    
    def apply_voucher(self, voucher_code: str) -> Dict[str, Any]:
        """
        Apply a voucher code.
        
        Args:
            voucher_code: Voucher code
            
        Returns:
            Dict: Response
        """
        return self._make_request('POST', self.ENDPOINTS['voucher'], data={
            'voucher': voucher_code
        })
    
    # ==================== Currency Operations ====================
    
    def set_currency(self, currency_code: str) -> Dict[str, Any]:
        """
        Set session currency.
        
        Args:
            currency_code: Currency code (e.g., 'USD')
            
        Returns:
            Dict: Response
        """
        return self._make_request('POST', self.ENDPOINTS['currency'], data={
            'currency': currency_code
        })
    
    # ==================== Data Mapping ====================
    
    def map_order_to_unified(self, oc_order: Dict) -> UnifiedOrder:
        """
        Map an OpenCart order to the unified order model.
        
        Args:
            oc_order: OpenCart order data
            
        Returns:
            UnifiedOrder: Unified order model
        """
        # Create client
        client = UnifiedClient(
            first_name=oc_order.get('firstname', ''),
            last_name=oc_order.get('lastname', ''),
            email=oc_order.get('email', ''),
            phone=oc_order.get('telephone', '')
        )
        client.name = f"{client.first_name} {client.last_name}".strip()
        
        # Map items
        items = []
        for product in oc_order.get('products', []):
            items.append(UnifiedOrderItem(
                name=product.get('name', ''),
                sku=product.get('model', ''),
                quantity=int(product.get('quantity', 1)),
                unit_price=float(product.get('price', 0)),
                total_price=float(product.get('total', 0))
            ))
        
        # Map payment status
        status_map = {
            1: PaymentStatus.PENDING,      # Pending
            2: PaymentStatus.PENDING,      # Processing
            3: PaymentStatus.PAID,         # Shipped
            5: PaymentStatus.PAID,         # Complete
            7: PaymentStatus.REFUNDED,     # Canceled
            11: PaymentStatus.REFUNDED     # Refunded
        }
        
        order = UnifiedOrder(
            order_number=str(oc_order.get('order_id', '')),
            client=client,
            items=items,
            subtotal=float(oc_order.get('total', 0)),
            total=float(oc_order.get('total', 0)),
            currency=oc_order.get('currency_code', 'USD'),
            status=oc_order.get('order_status', 'pending'),
            payment_status=status_map.get(
                oc_order.get('order_status_id', 1),
                PaymentStatus.PENDING
            ),
            shipping_address={
                'first_name': oc_order.get('shipping_firstname', ''),
                'last_name': oc_order.get('shipping_lastname', ''),
                'address_1': oc_order.get('shipping_address_1', ''),
                'city': oc_order.get('shipping_city', ''),
                'postcode': oc_order.get('shipping_postcode', ''),
                'country': oc_order.get('shipping_country', '')
            },
            billing_address={
                'first_name': oc_order.get('payment_firstname', ''),
                'last_name': oc_order.get('payment_lastname', ''),
                'address_1': oc_order.get('payment_address_1', ''),
                'city': oc_order.get('payment_city', ''),
                'postcode': oc_order.get('payment_postcode', ''),
                'country': oc_order.get('payment_country', '')
            }
        )
        
        # Add platform reference
        order.platform_refs.append(PlatformReference(
            platform=self.PLATFORM_NAME,
            external_id=str(oc_order.get('order_id', '')),
            last_synced=datetime.utcnow(),
            sync_status=SyncStatus.SYNCED
        ))
        
        return order
    
    def map_product_to_unified(self, oc_product: Dict) -> UnifiedProduct:
        """
        Map an OpenCart product to the unified product model.
        
        Args:
            oc_product: OpenCart product data
            
        Returns:
            UnifiedProduct: Unified product model
        """
        product = UnifiedProduct(
            name=oc_product.get('name', ''),
            description=oc_product.get('description', ''),
            sku=oc_product.get('model', ''),
            price=float(oc_product.get('price', 0)),
            quantity=int(oc_product.get('quantity', 0)),
            category=oc_product.get('category', ''),
            vendor=oc_product.get('manufacturer', '')
        )
        
        # Add images
        if oc_product.get('image'):
            product.images.append(oc_product['image'])
        
        # Add platform reference
        product.platform_refs.append(PlatformReference(
            platform=self.PLATFORM_NAME,
            external_id=str(oc_product.get('product_id', '')),
            last_synced=datetime.utcnow(),
            sync_status=SyncStatus.SYNCED
        ))
        
        return product
