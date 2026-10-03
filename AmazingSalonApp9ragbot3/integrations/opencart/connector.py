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


def _chain_stage():
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import chain_stage

    return chain_stage


def _reject_ledger(recorded, label: str):
    if isinstance(recorded, dict) and recorded.get("ok") is False:
        raise IntegrationError(recorded.get("error") or f"supply chain rejected the {label}")


def _record_named_opencart_sale(order, order_id=None):
    """An appointment that already names a shipped sale records the same sale a webhook would."""
    if not isinstance(order, dict):
        return None
    payload = dict(order)
    if order_id and not str(payload.get("order_id") or payload.get("id") or "").strip():
        payload["order_id"] = order_id
    _copy_opencart_status_id(payload)
    recorded = _chain_stage().record_opencart_fulfillments(payload)
    _reject_ledger(recorded, "order")
    return recorded


def _copy_opencart_status_id(payload):
    """A status id is the order status when the payload does not name one."""
    status = str(payload.get("status") or payload.get("new_status") or payload.get("order_status") or "").strip()
    if (
        not status
        and payload.get("status_id") is not None
        and payload.get("order_status_id") is None
        and payload.get("new_status_id") is None
    ):
        payload["order_status_id"] = payload["status_id"]


def _opencart_order_label(order):
    """The order id a payload already states. A blank one is absent."""
    if not isinstance(order, dict):
        return None
    for key in ("order_id", "order_number", "id"):
        value = order.get(key)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
            continue
        if value and not isinstance(value, bool):
            return value
    return None


def _opencart_names_a_sale(order):
    """True when the order names a shipped sale. Invalid lines stay invalid."""
    stage = _chain_stage()
    if not isinstance(order, dict):
        return False
    probe = dict(order)
    _copy_opencart_status_id(probe)
    if stage._opencart_returned(probe):
        return False
    if not stage._order_label(probe, "order_id", "order_number", "id"):
        probe["order_id"] = "named"
    status = stage._opencart_status(probe)
    if probe.get("fulfilled") is not True and status not in stage._OPENCART_SHIPPED:
        probe["status"] = "shipped"
    try:
        return bool(stage.opencart_fulfillment_commands(probe))
    except stage.StageRejection:
        return None


def _request_sale_lines(requested):
    """The product list a request already states. An empty list is absent."""
    if not isinstance(requested, dict):
        return []
    for key in ("products", "line_items", "items"):
        value = requested.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def _opencart_product_key(order):
    """The product list an order already states. A missing list is none."""
    if not isinstance(order, dict):
        return None
    for key in ("products", "line_items", "items"):
        if isinstance(order.get(key), list):
            return key
    return None


def _opencart_sku_text(item):
    """The sku a product already states. A model is that sku. A title is not."""
    if not isinstance(item, dict):
        return ""
    stage = _chain_stage()
    return stage._named_sku(item) or stage._named(item, "model")


def _opencart_sale_line_state(item):
    """True when the product names a sale. None when the product is present but invalid."""
    if not isinstance(item, dict):
        return False
    stage = _chain_stage()
    probe = {"order_id": "named", "status": "shipped", "products": [item]}
    try:
        return bool(stage.opencart_fulfillment_commands(probe))
    except stage.StageRejection:
        return None


def _opencart_skus_conflict(saved_line, request_line):
    """A saved sku or model that differs from the request does not take the request's quantity."""
    saved_sku = _opencart_sku_text(saved_line)
    request_sku = _opencart_sku_text(request_line)
    return bool(saved_sku and request_sku and saved_sku != request_sku)


def _opencart_resolved_sale_fields(item):
    stage = _chain_stage()
    if not isinstance(item, dict):
        return None, None, None, None
    return stage._shopify_line(stage._opencart_identity(item))


def _opencart_stated_amount(item):
    """The price or total a product already states. A blank one is absent."""
    if not isinstance(item, dict):
        return None
    price = item.get("price")
    if price is not None and not (isinstance(price, str) and not price.strip()):
        return ("price", price)
    total = item.get("total")
    if total is None or (isinstance(total, str) and not total.strip()):
        return None
    return ("total", total)


def _opencart_request_amount(saved_line, request_line):
    """The amount a request product names for this sku. A different model does not lend it."""
    stated = _opencart_stated_amount(request_line)
    if stated is None:
        return None
    saved_sku = _opencart_sku_text(saved_line)
    request_sku = _opencart_sku_text(request_line)
    if saved_sku:
        if request_sku != saved_sku:
            return None
    elif not request_sku:
        return None
    return stated


def _stamp_opencart_sale_line(saved_line, request_line):
    """Copy the sku, quantity, and price a saved product omits from the request product at that index.

    A saved product that already names a sale keeps its quantity. A missing price still comes from the
    request product with the same sku or model. A different sku or model does not lend its quantity
    or its price. A word such as "lots" is a quantity and stays.
    """
    if not isinstance(saved_line, dict) or not isinstance(request_line, dict):
        return saved_line
    if _opencart_skus_conflict(saved_line, request_line):
        return saved_line
    amount = _opencart_request_amount(saved_line, request_line)
    if _opencart_sale_line_state(saved_line) is True:
        if amount is None or _opencart_stated_amount(saved_line) is not None:
            return saved_line
        key, value = amount
        return {**saved_line, key: value}
    if _opencart_sale_line_state(request_line) is not True:
        return saved_line
    saved_location, saved_milligrams, saved_kind, saved_practitioner = _opencart_resolved_sale_fields(
        saved_line
    )
    request_location, request_milligrams, request_kind, request_practitioner = _opencart_resolved_sale_fields(
        request_line
    )
    stamped = dict(saved_line)
    changed = False
    if not _opencart_sku_text(stamped):
        sku = _opencart_sku_text(request_line)
        if sku:
            stamped["sku"] = sku
            changed = True
    if saved_location is None and isinstance(request_location, str) and request_location.strip():
        stamped["location"] = request_location.strip()
        changed = True
    if saved_milligrams is None and request_milligrams is not None:
        stamped["milligrams"] = request_milligrams
        changed = True
    if not saved_kind and request_kind:
        stamped["kind"] = request_kind
        changed = True
    if not saved_practitioner and request_practitioner:
        stamped["practitioner_id"] = request_practitioner
        changed = True
    if _opencart_stated_amount(stamped) is None and amount is not None:
        key, value = amount
        stamped[key] = value
        changed = True
    if not changed:
        return saved_line
    return stamped


def _stamp_omitted_opencart_lines(saved, requested):
    """Saved products that omit a sku or quantity take that identity from the same request product.

    A saved product that names its own sale stays. A blank request sku does not move onto another product.
    """
    key = _opencart_product_key(saved)
    if key is None:
        return None
    saved_lines = saved.get(key)
    requested_lines = _request_sale_lines(requested)
    if not saved_lines or not requested_lines:
        return None
    stamped = []
    changed = False
    for index, line in enumerate(saved_lines):
        request_line = requested_lines[index] if index < len(requested_lines) else None
        next_line = _stamp_opencart_sale_line(line, request_line)
        if next_line is not line:
            changed = True
        stamped.append(next_line)
    if not changed:
        return None
    return stamped


def _opencart_saved_lines(saved, requested):
    """A saved shipment that omits its products draws the products the request already named.

    A saved product that already names a sale keeps that product. A saved product that omits its sku,
    model, or quantity takes them from the request product at that index. An open or returned order
    is unchanged.
    """
    if not isinstance(saved, dict) or not isinstance(requested, dict):
        return saved
    stage = _chain_stage()
    payload = dict(saved)
    _copy_opencart_status_id(payload)
    if stage._opencart_returned(payload):
        return saved
    status = stage._opencart_status(payload)
    if payload.get("fulfilled") is not True and status not in stage._OPENCART_SHIPPED:
        return saved
    if _opencart_names_a_sale(payload) is not False:
        lines = _stamp_omitted_opencart_lines(payload, requested)
        if lines is None:
            return saved
        key = _opencart_product_key(payload)
        if key is None:
            return saved
        payload[key] = lines
        return payload
    if _opencart_names_a_sale(requested) is not True:
        return saved
    lines = _request_sale_lines(requested)
    if not lines:
        return saved
    if payload.get("products") is not None:
        payload["products"] = list(lines)
    elif payload.get("line_items") is not None:
        payload["line_items"] = list(lines)
    elif payload.get("items") is not None:
        payload["items"] = list(lines)
    else:
        payload["products"] = list(lines)
    return payload


def _record_saved_opencart_order(saved, order_id, requested=None):
    """A saved cancellation that omits its id returns the sale recorded for the order being created.

    A saved shipment that omits its products draws the products the request already named.
    A saved order that names itself keeps that id. An open saved order is recorded unchanged.
    """
    if not isinstance(saved, dict):
        return None
    payload = dict(saved)
    _copy_opencart_status_id(payload)
    if (
        order_id is not None
        and _opencart_order_label(payload) is None
        and _chain_stage()._opencart_returned(payload)
    ):
        payload["order_id"] = order_id
    if requested is not None:
        payload = _opencart_saved_lines(payload, requested)
    return _record_named_opencart_sale(payload)


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
        _record_named_opencart_sale(appointment_data)
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
        
        # Create order. A sale on the created order is the same sale a webhook would record.
        # A cancellation that omits its id returns the sale this order already recorded.
        created = self.create_order()
        if created is not appointment_data:
            _record_saved_opencart_order(
                created,
                _opencart_order_label(appointment_data),
                appointment_data,
            )
        return created
    
    def update_appointment(self, appointment_id: str, appointment_data: Dict) -> Dict:
        """
        Update an order on OpenCart.
        
        Args:
            appointment_id: Order ID
            appointment_data: Updated order details
            
        Returns:
            Dict: Updated order data
        """
        _record_named_opencart_sale(appointment_data, appointment_id)
        # OpenCart doesn't have direct order update
        # Update via order history
        if appointment_data.get('status'):
            saved = self.update_order_history(
                order_id=int(appointment_id),
                order_status_id=appointment_data.get('status_id', 1),
                comment=appointment_data.get('notes', '')
            )
            if saved is not appointment_data:
                recorded = _opencart_saved_lines(saved, appointment_data) if isinstance(saved, dict) else saved
                _record_named_opencart_sale(recorded, appointment_id)
            return saved
        
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
        except Exception as e:
            logger.error(f"Failed to cancel OpenCart order {appointment_id}: {e}")
            return False
        _record_named_opencart_sale({"order_id": appointment_id, "order_status_id": 7})
        return True
    
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
