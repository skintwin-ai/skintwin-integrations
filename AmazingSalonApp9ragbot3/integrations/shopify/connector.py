"""
Shopify B2B API Connector
Handles all interactions with the Shopify Admin REST and GraphQL APIs
with focus on B2B features for wholesale operations
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


def _record_shopify_catalog(product):
    """A created or updated product records the same catalog a webhook would record."""
    recorded = _chain_stage().record_shopify_catalog(product)
    _reject_ledger(recorded, "product")
    return recorded


def _sku_text(record):
    """The sku a record already states. A blank one is absent."""
    if not isinstance(record, dict):
        return ""
    for key in ("sku", "sku_id", "skuId"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _variant_sku_rows(product):
    """Variant rows that name a sku. A blank sku is not one."""
    if not isinstance(product, dict):
        return []
    variants = product.get("variants")
    if not isinstance(variants, list):
        return []
    rows = []
    seen = set()
    for variant in variants:
        sku = _sku_text(variant)
        if not sku or sku in seen:
            continue
        seen.add(sku)
        rows.append(variant)
    return rows


def _saved_shopify_product(saved, requested):
    """A saved product that names a formula and omits variant skus catalogs the skus the request already named.

    A saved product that names its own sku keeps that sku. A product with no formula is recorded unchanged.
    """
    if not isinstance(saved, dict) or not isinstance(requested, dict):
        return saved
    if _chain_stage().formula_id_from_shopify(saved) is None:
        return saved
    if _variant_sku_rows(saved) or _sku_text(saved):
        return saved
    named = _variant_sku_rows(requested)
    if not named:
        return saved
    return {**saved, "variants": list(named)}


def _record_shopify_order(order):
    """A created or updated order records the same sale a webhook would record."""
    recorded = _chain_stage().record_shopify_order_update(order)
    _reject_ledger(recorded, "order")
    return recorded


def _record_saved_appointment_lines(saved, appointment_data, mapped):
    """A saved fulfilled order that omits its lines draws the sale the appointment already named.

    The mapper posts a pending order and drops that sale, including a partial refund.
    An appointment that is itself fulfilled was already recorded. An open saved order stays unchanged.
    """
    if not isinstance(saved, dict) or not isinstance(appointment_data, dict):
        return None
    if saved is mapped or saved is appointment_data:
        return None
    if str(appointment_data.get("fulfillment_status") or "").strip().lower() == "fulfilled":
        return None
    stamped = _saved_shopify_fulfilled_lines(saved, appointment_data)
    refunded = _saved_shopify_refunds(stamped, appointment_data)
    if refunded is saved:
        return None
    return _record_shopify_order(refunded)


def _stated_order_id(order):
    """The order number a payload already states. A blank one is absent."""
    if not isinstance(order, dict):
        return None
    for key in ("order_number", "name", "id"):
        value = order.get(key)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
            continue
        if value:
            return value
    return None


def _saved_shopify_order(saved, order_id):
    """A saved cancellation that omits its id returns the sale recorded for the id being saved.

    A saved order that names itself keeps that id. An open saved order is recorded unchanged.
    """
    if not isinstance(saved, dict) or order_id is None or _order_names_itself(saved):
        return saved
    restocked = str(saved.get("fulfillment_status") or "").strip().lower() == "restocked"
    financial = str(saved.get("financial_status") or "").strip().lower()
    returned = restocked or bool(
        saved.get("cancelled_at") or saved.get("cancel_reason") or financial in {"refunded", "voided"}
    )
    if not returned:
        return saved
    return {**saved, "id": order_id}


def _order_names_a_sale(order):
    """True when the order names a sale. Invalid lines stay invalid."""
    stage = _chain_stage()
    if not isinstance(order, dict):
        return False
    probe = dict(order)
    if not stage._order_label(probe, "order_number", "name", "id"):
        probe["id"] = "named"
    try:
        return bool(stage.shopify_fulfillment_commands(probe))
    except stage.StageRejection:
        return None


def _saved_shopify_fulfilled_lines(saved, requested):
    """A saved fulfilled order that omits its sale lines draws the lines the request already named.

    A saved order that names its own sale keeps those lines. An open or returned order is recorded unchanged.
    """
    if not isinstance(saved, dict) or not isinstance(requested, dict):
        return saved
    if str(saved.get("fulfillment_status") or "").strip().lower() != "fulfilled":
        return saved
    stage = _chain_stage()
    if stage._shopify_returned(saved):
        return saved
    if _order_names_a_sale(saved) is not False:
        return saved
    if _order_names_a_sale(requested) is not True:
        return saved
    lines = requested.get("line_items")
    if lines is None:
        lines = requested.get("items")
    if not isinstance(lines, list) or not lines:
        return saved
    stamped = {**saved, "line_items": list(lines)}
    if not saved.get("note_attributes") and requested.get("note_attributes"):
        stamped["note_attributes"] = requested.get("note_attributes")
    return stamped


def _saved_refund_lines(order) -> list:
    """Refund lines a saved order already states. A missing list is none."""
    if not isinstance(order, dict):
        return []
    refunds = order.get("refunds")
    if not isinstance(refunds, list):
        return []
    lines = []
    for refund in refunds:
        if not isinstance(refund, dict):
            continue
        items = refund.get("refund_line_items")
        if isinstance(items, list):
            lines.extend(items)
    return lines


def _stated_refund_id(value) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def _refund_line_names_sale(line) -> bool:
    """True when a refund line already names a sku or a line id."""
    if not isinstance(line, dict):
        return False
    if _stated_refund_id(line.get("line_item_id")) or _sku_text(line):
        return True
    item = line.get("line_item")
    return isinstance(item, dict) and (_stated_refund_id(item.get("id")) or bool(_sku_text(item)))


def _merge_refund_identity(saved_line, request_line):
    """Copy the sku and line id the request names onto a saved line that omits them.

    The saved quantity stays. A saved line that already names a sale stays as written.
    """
    if not isinstance(saved_line, dict) or _refund_line_names_sale(saved_line):
        return saved_line
    if not isinstance(request_line, dict) or not _refund_line_names_sale(request_line):
        return saved_line
    merged = dict(saved_line)
    if not _stated_refund_id(merged.get("line_item_id")) and _stated_refund_id(request_line.get("line_item_id")):
        merged["line_item_id"] = request_line["line_item_id"]
    requested_item = request_line.get("line_item") if isinstance(request_line.get("line_item"), dict) else None
    item = dict(merged["line_item"]) if isinstance(merged.get("line_item"), dict) else {}
    if requested_item is not None:
        if not _stated_refund_id(item.get("id")) and _stated_refund_id(requested_item.get("id")):
            item["id"] = requested_item["id"]
        if not _sku_text(item) and _sku_text(requested_item):
            item["sku"] = _sku_text(requested_item)
    if not _sku_text(item) and _sku_text(request_line):
        item["sku"] = _sku_text(request_line)
    if item:
        merged["line_item"] = item
    if merged == saved_line:
        return saved_line
    return merged


def _refunds_with_request_identity(saved, requested):
    """Saved refund lines that omit a sku or line id gain the identity the request already named."""
    request_lines = _saved_refund_lines(requested)
    refunds = saved.get("refunds")
    if not isinstance(refunds, list) or not request_lines:
        return None
    cursor = 0
    changed = False
    rebuilt = []
    for refund in refunds:
        if not isinstance(refund, dict):
            rebuilt.append(refund)
            continue
        items = refund.get("refund_line_items")
        if not isinstance(items, list):
            rebuilt.append(refund)
            continue
        merged_items = []
        for line in items:
            request_line = request_lines[cursor] if cursor < len(request_lines) else None
            cursor += 1
            merged = _merge_refund_identity(line, request_line)
            if merged is not line:
                changed = True
            merged_items.append(merged)
        rebuilt.append({**refund, "refund_line_items": merged_items})
    if not changed:
        return None
    return rebuilt


def _saved_shopify_refunds(saved, requested):
    """A saved partial refund that omits its refund lines returns the sale the request already named.

    A saved refund line that omits its sku or line id uses the identity the request already named, and keeps its quantity.
    A saved refund that names its own lines keeps those lines. An open saved order stays unchanged.
    """
    if not isinstance(saved, dict) or not isinstance(requested, dict):
        return saved
    if str(saved.get("fulfillment_status") or "").strip().lower() != "fulfilled":
        return saved
    if str(saved.get("financial_status") or "").strip().lower() != "partially_refunded":
        return saved
    stage = _chain_stage()
    if stage._shopify_returned(saved):
        return saved
    refunds = saved.get("refunds")
    if refunds is not None and not isinstance(refunds, list):
        return saved
    if not _saved_refund_lines(saved):
        requested_refunds = requested.get("refunds")
        if not isinstance(requested_refunds, list) or not requested_refunds:
            return saved
        stamped = {**saved, "refunds": list(requested_refunds)}
    else:
        enriched = _refunds_with_request_identity(saved, requested)
        if not enriched:
            return saved
        stamped = {**saved, "refunds": enriched}
    try:
        named = stage.shopify_refunded_line_commands(stamped)
    except stage.StageRejection:
        return saved
    if not named:
        return saved
    return stamped


def _draft_names_itself(draft) -> bool:
    if not isinstance(draft, dict):
        return False
    for key in ("order_id", "name", "id"):
        value = draft.get(key)
        if isinstance(value, str):
            if value.strip():
                return True
            continue
        if value:
            return True
    return False


def _record_shopify_draft(draft):
    """A completed draft records the same sale a webhook would record."""
    recorded = _chain_stage().record_draft_order(draft)
    _reject_ledger(recorded, "draft")
    return recorded


def _draft_label(draft):
    """The order id a draft already states. A blank one is absent."""
    if not isinstance(draft, dict):
        return None
    for key in ("order_id", "name", "id"):
        value = draft.get(key)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
            continue
        if value and not isinstance(value, bool):
            return value
    return None


def _saved_shopify_draft(saved, requested):
    """A completed draft that omits its id records the sale under the id the request already states.

    A saved draft that names itself keeps that id. An open saved draft is recorded unchanged.
    """
    if not isinstance(saved, dict) or _draft_names_itself(saved):
        return saved
    if str(saved.get("status") or "").strip().lower() != "completed":
        return saved
    known = _draft_label(requested)
    if known is None:
        return saved
    return {**saved, "id": known}


def _draft_names_a_sale(draft):
    """True when the draft names a completed sale. Invalid lines stay invalid."""
    stage = _chain_stage()
    if not isinstance(draft, dict):
        return False
    probe = dict(draft)
    if str(probe.get("status") or "").strip().lower() != "completed":
        probe["status"] = "completed"
    if not stage._order_label(probe, "order_id", "name", "id"):
        probe["id"] = "named"
    try:
        return bool(stage.draft_order_commands(probe))
    except stage.StageRejection:
        return None


def _saved_shopify_draft_lines(saved, requested):
    """A completed draft that omits its sale lines draws the lines the request already named.

    A saved draft that names its own sale keeps those lines. An open draft is recorded unchanged.
    """
    if not isinstance(saved, dict) or not isinstance(requested, dict):
        return saved
    if str(saved.get("status") or "").strip().lower() != "completed":
        return saved
    if _draft_names_a_sale(saved) is not False:
        return saved
    if _draft_names_a_sale(requested) is not True:
        return saved
    lines = requested.get("line_items")
    if lines is None:
        lines = requested.get("items")
    if not isinstance(lines, list) or not lines:
        return saved
    stamped = {**saved, "line_items": list(lines)}
    if not saved.get("note_attributes") and requested.get("note_attributes"):
        stamped["note_attributes"] = requested.get("note_attributes")
    return stamped


def _order_names_itself(order) -> bool:
    if not isinstance(order, dict):
        return False
    for key in ("order_number", "name", "id"):
        value = order.get(key)
        if isinstance(value, str):
            if value.strip():
                return True
            continue
        if value:
            return True
    return False


def _record_shopify_return(order, order_id=None):
    """A cancelled order records the same return a webhook would record."""
    if not isinstance(order, dict):
        order = {}
    else:
        order = dict(order)
    if order_id is not None and not _order_names_itself(order):
        order["id"] = order_id
    recorded = _chain_stage().record_shopify_returns(order)
    _reject_ledger(recorded, "return")
    return recorded


class ShopifyB2BConnector(BaseConnector):
    """
    Connector for Shopify Admin API with B2B features.
    
    Shopify API Documentation:
    - REST: https://shopify.dev/docs/api/admin-rest
    - GraphQL: https://shopify.dev/docs/api/admin-graphql
    - B2B: https://shopify.dev/docs/apps/build/b2b
    
    Note: B2B features require Shopify Plus plan.
    """
    
    PLATFORM_NAME = "shopify"
    API_VERSION = "2026-01"
    
    # REST API Endpoints
    ENDPOINTS = {
        'products': 'products.json',
        'product': 'products/{id}.json',
        'orders': 'orders.json',
        'order': 'orders/{id}.json',
        'customers': 'customers.json',
        'customer': 'customers/{id}.json',
        'draft_orders': 'draft_orders.json',
        'draft_order': 'draft_orders/{id}.json',
        'inventory_levels': 'inventory_levels.json',
        'locations': 'locations.json',
        'webhooks': 'webhooks.json'
    }
    
    def __init__(
        self,
        shop_name: str,
        access_token: str,
        api_version: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the Shopify B2B connector.
        
        Args:
            shop_name: Shopify store name (e.g., 'mystore' for mystore.myshopify.com)
            access_token: Shopify Admin API access token
            api_version: Optional API version override
        """
        self.shop_name = shop_name
        self.api_version = api_version or self.API_VERSION
        
        base_url = f"https://{shop_name}.myshopify.com/admin/api/{self.api_version}"
        
        super().__init__(
            base_url=base_url,
            api_key=access_token,
            rate_limit_per_minute=40,  # Standard Shopify rate limit
            **kwargs
        )
        
        # GraphQL endpoint
        self.graphql_url = f"https://{shop_name}.myshopify.com/admin/api/{self.api_version}/graphql.json"
        
        logger.info(f"Initialized Shopify B2B connector for store: {shop_name}")
    
    def authenticate(self) -> bool:
        """
        Verify authentication with Shopify API.
        
        Returns:
            bool: True if authentication is valid
        """
        try:
            # Test authentication by fetching shop info
            response = self.get('shop.json')
            return 'shop' in response
        except Exception as e:
            logger.error(f"Shopify authentication failed: {e}")
            raise AuthenticationError(
                f"Failed to authenticate with Shopify: {e}",
                platform=self.PLATFORM_NAME
            )
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for Shopify API requests."""
        return {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': self.api_key
        }
    
    def test_connection(self) -> bool:
        """Test the connection to Shopify API."""
        try:
            return self.authenticate()
        except Exception as e:
            logger.error(f"Shopify connection test failed: {e}")
            return False
    
    # ==================== GraphQL Operations ====================
    
    def graphql_query(self, query: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query.
        
        Args:
            query: GraphQL query string
            variables: Optional query variables
            
        Returns:
            Dict: GraphQL response data
        """
        self._check_rate_limit()
        
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        
        try:
            response = self.session.post(
                self.graphql_url,
                json=payload,
                headers=self.get_headers(),
                timeout=self.timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            if 'errors' in data:
                errors = data['errors']
                error_msg = '; '.join([e.get('message', str(e)) for e in errors])
                raise IntegrationError(
                    f"GraphQL error: {error_msg}",
                    platform=self.PLATFORM_NAME
                )
            
            return data.get('data', {})
            
        except Exception as e:
            logger.error(f"GraphQL query failed: {e}")
            raise IntegrationError(f"GraphQL query failed: {e}", platform=self.PLATFORM_NAME)
    
    # ==================== Product Operations ====================
    
    def get_products(
        self,
        limit: int = 50,
        since_id: Optional[int] = None,
        product_type: Optional[str] = None,
        vendor: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get products from Shopify.
        
        Args:
            limit: Maximum number of products to return
            since_id: Return products after this ID
            product_type: Filter by product type
            vendor: Filter by vendor
            
        Returns:
            List[Dict]: List of products
        """
        params = {'limit': limit}
        if since_id:
            params['since_id'] = since_id
        if product_type:
            params['product_type'] = product_type
        if vendor:
            params['vendor'] = vendor
        
        response = self.get(self.ENDPOINTS['products'], params=params)
        return response.get('products', [])
    
    def get_product(self, product_id: int) -> Dict[str, Any]:
        """
        Get a specific product by ID.
        
        Args:
            product_id: Shopify product ID
            
        Returns:
            Dict: Product data
        """
        endpoint = self.ENDPOINTS['product'].format(id=product_id)
        response = self.get(endpoint)
        return response.get('product', response)
    
    def create_product(self, product_data: Dict) -> Dict[str, Any]:
        """
        Create a new product.
        
        Args:
            product_data: Product details
            
        Returns:
            Dict: Created product data
        """
        _record_shopify_catalog(product_data)
        response = self.post(self.ENDPOINTS['products'], {'product': product_data})
        saved = response.get('product', response)
        if saved is not product_data:
            _record_shopify_catalog(_saved_shopify_product(saved, product_data))
        return saved
    
    def update_product(self, product_id: int, product_data: Dict) -> Dict[str, Any]:
        """
        Update an existing product.
        
        Args:
            product_id: Shopify product ID
            product_data: Updated product details
            
        Returns:
            Dict: Updated product data
        """
        _record_shopify_catalog(product_data)
        endpoint = self.ENDPOINTS['product'].format(id=product_id)
        response = self.put(endpoint, {'product': product_data})
        saved = response.get('product', response)
        if saved is not product_data:
            _record_shopify_catalog(_saved_shopify_product(saved, product_data))
        return saved
    
    def delete_product(self, product_id: int) -> bool:
        """
        Delete a product.
        
        Args:
            product_id: Shopify product ID
            
        Returns:
            bool: True if deletion was successful
        """
        endpoint = self.ENDPOINTS['product'].format(id=product_id)
        self.delete(endpoint)
        return True
    
    # ==================== Order Operations ====================
    
    def get_orders(
        self,
        limit: int = 50,
        status: str = 'any',
        since_id: Optional[int] = None,
        created_at_min: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get orders from Shopify.
        
        Args:
            limit: Maximum number of orders to return
            status: Order status filter (any, open, closed, cancelled)
            since_id: Return orders after this ID
            created_at_min: Return orders created after this time
            
        Returns:
            List[Dict]: List of orders
        """
        params = {'limit': limit, 'status': status}
        if since_id:
            params['since_id'] = since_id
        if created_at_min:
            params['created_at_min'] = created_at_min.isoformat()
        
        response = self.get(self.ENDPOINTS['orders'], params=params)
        return response.get('orders', [])
    
    def get_order(self, order_id: int) -> Dict[str, Any]:
        """
        Get a specific order by ID.
        
        Args:
            order_id: Shopify order ID
            
        Returns:
            Dict: Order data
        """
        endpoint = self.ENDPOINTS['order'].format(id=order_id)
        response = self.get(endpoint)
        return response.get('order', response)
    
    def create_order(self, order_data: Dict) -> Dict[str, Any]:
        """
        Create a new order.
        
        Args:
            order_data: Order details
            
        Returns:
            Dict: Created order data
        """
        _record_shopify_order(order_data)
        response = self.post(self.ENDPOINTS['orders'], {'order': order_data})
        saved = response.get('order', response)
        if saved is not order_data:
            recorded = _saved_shopify_order(saved, _stated_order_id(order_data))
            recorded = _saved_shopify_fulfilled_lines(recorded, order_data)
            _record_shopify_order(_saved_shopify_refunds(recorded, order_data))
        return saved
    
    def update_order(self, order_id: int, order_data: Dict) -> Dict[str, Any]:
        """
        Update an existing order.
        
        Args:
            order_id: Shopify order ID
            order_data: Updated order details
            
        Returns:
            Dict: Updated order data
        """
        _record_shopify_order(order_data)
        endpoint = self.ENDPOINTS['order'].format(id=order_id)
        response = self.put(endpoint, {'order': order_data})
        saved = response.get('order', response)
        if saved is not order_data:
            recorded = _saved_shopify_order(saved, order_id)
            recorded = _saved_shopify_fulfilled_lines(recorded, order_data)
            _record_shopify_order(_saved_shopify_refunds(recorded, order_data))
        return saved
    
    def cancel_order(self, order_id: int, reason: str = "other") -> Dict[str, Any]:
        """
        Cancel an order.
        
        Args:
            order_id: Shopify order ID
            reason: Cancellation reason
            
        Returns:
            Dict: Cancelled order data
        """
        endpoint = f"orders/{order_id}/cancel.json"
        response = self.post(endpoint, {'reason': reason})
        order = response.get('order', response) if isinstance(response, dict) else {}
        _record_shopify_return(order, order_id)
        return order if isinstance(order, dict) else response
    
    # ==================== Customer Operations ====================
    
    def get_customers(
        self,
        limit: int = 50,
        since_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get customers from Shopify.
        
        Args:
            limit: Maximum number of customers to return
            since_id: Return customers after this ID
            
        Returns:
            List[Dict]: List of customers
        """
        params = {'limit': limit}
        if since_id:
            params['since_id'] = since_id
        
        response = self.get(self.ENDPOINTS['customers'], params=params)
        return response.get('customers', [])
    
    def get_customer(self, customer_id: int) -> Dict[str, Any]:
        """
        Get a specific customer by ID.
        
        Args:
            customer_id: Shopify customer ID
            
        Returns:
            Dict: Customer data
        """
        endpoint = self.ENDPOINTS['customer'].format(id=customer_id)
        response = self.get(endpoint)
        return response.get('customer', response)
    
    def create_customer(self, customer_data: Dict) -> Dict[str, Any]:
        """
        Create a new customer.
        
        Args:
            customer_data: Customer details
            
        Returns:
            Dict: Created customer data
        """
        response = self.post(self.ENDPOINTS['customers'], {'customer': customer_data})
        return response.get('customer', response)
    
    def update_customer(self, customer_id: int, customer_data: Dict) -> Dict[str, Any]:
        """
        Update an existing customer.
        
        Args:
            customer_id: Shopify customer ID
            customer_data: Updated customer details
            
        Returns:
            Dict: Updated customer data
        """
        endpoint = self.ENDPOINTS['customer'].format(id=customer_id)
        response = self.put(endpoint, {'customer': customer_data})
        return response.get('customer', response)
    
    # ==================== B2B Company Operations (GraphQL) ====================
    
    def get_companies(self, first: int = 50) -> List[Dict[str, Any]]:
        """
        Get B2B companies using GraphQL.
        
        Args:
            first: Number of companies to return
            
        Returns:
            List[Dict]: List of companies
        """
        query = """
        query GetCompanies($first: Int!) {
            companies(first: $first) {
                edges {
                    node {
                        id
                        name
                        externalId
                        note
                        createdAt
                        updatedAt
                        locations(first: 10) {
                            edges {
                                node {
                                    id
                                    name
                                    externalId
                                    billingAddress {
                                        address1
                                        address2
                                        city
                                        province
                                        zip
                                        country
                                    }
                                    shippingAddress {
                                        address1
                                        address2
                                        city
                                        province
                                        zip
                                        country
                                    }
                                }
                            }
                        }
                        contacts(first: 10) {
                            edges {
                                node {
                                    id
                                    customer {
                                        id
                                        firstName
                                        lastName
                                        email
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        result = self.graphql_query(query, {'first': first})
        companies = result.get('companies', {}).get('edges', [])
        return [edge['node'] for edge in companies]
    
    def create_company(
        self,
        name: str,
        external_id: Optional[str] = None,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a B2B company using GraphQL.
        
        Args:
            name: Company name
            external_id: External reference ID
            note: Company note
            
        Returns:
            Dict: Created company data
        """
        mutation = """
        mutation CreateCompany($input: CompanyCreateInput!) {
            companyCreate(input: $input) {
                company {
                    id
                    name
                    externalId
                    note
                    createdAt
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        input_data = {'company': {'name': name}}
        if external_id:
            input_data['company']['externalId'] = external_id
        if note:
            input_data['company']['note'] = note
        
        result = self.graphql_query(mutation, {'input': input_data})
        
        create_result = result.get('companyCreate', {})
        if create_result.get('userErrors'):
            errors = create_result['userErrors']
            error_msg = '; '.join([e.get('message', str(e)) for e in errors])
            raise IntegrationError(f"Failed to create company: {error_msg}", platform=self.PLATFORM_NAME)
        
        return create_result.get('company', {})
    
    def create_company_location(
        self,
        company_id: str,
        name: str,
        billing_address: Optional[Dict] = None,
        shipping_address: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create a company location using GraphQL.
        
        Args:
            company_id: Company GraphQL ID
            name: Location name
            billing_address: Billing address details
            shipping_address: Shipping address details
            
        Returns:
            Dict: Created location data
        """
        mutation = """
        mutation CreateCompanyLocation($companyId: ID!, $input: CompanyLocationInput!) {
            companyLocationCreate(companyId: $companyId, input: $input) {
                companyLocation {
                    id
                    name
                    externalId
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        input_data = {'name': name}
        if billing_address:
            input_data['billingAddress'] = billing_address
        if shipping_address:
            input_data['shippingAddress'] = shipping_address
        
        result = self.graphql_query(mutation, {
            'companyId': company_id,
            'input': input_data
        })
        
        create_result = result.get('companyLocationCreate', {})
        if create_result.get('userErrors'):
            errors = create_result['userErrors']
            error_msg = '; '.join([e.get('message', str(e)) for e in errors])
            raise IntegrationError(f"Failed to create location: {error_msg}", platform=self.PLATFORM_NAME)
        
        return create_result.get('companyLocation', {})
    
    def assign_catalog_to_location(
        self,
        company_location_id: str,
        catalog_id: str
    ) -> bool:
        """
        Assign a catalog to a company location.
        
        Args:
            company_location_id: Company location GraphQL ID
            catalog_id: Catalog GraphQL ID
            
        Returns:
            bool: True if assignment was successful
        """
        mutation = """
        mutation AssignCatalog($companyLocationId: ID!, $catalogId: ID!) {
            companyLocationAssignCatalog(
                companyLocationId: $companyLocationId
                catalogId: $catalogId
            ) {
                companyLocation {
                    id
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        result = self.graphql_query(mutation, {
            'companyLocationId': company_location_id,
            'catalogId': catalog_id
        })
        
        assign_result = result.get('companyLocationAssignCatalog', {})
        if assign_result.get('userErrors'):
            errors = assign_result['userErrors']
            error_msg = '; '.join([e.get('message', str(e)) for e in errors])
            raise IntegrationError(f"Failed to assign catalog: {error_msg}", platform=self.PLATFORM_NAME)
        
        return True
    
    # ==================== Draft Order Operations (B2B) ====================
    
    def get_draft_orders(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get draft orders from Shopify.
        
        Args:
            limit: Maximum number of draft orders to return
            
        Returns:
            List[Dict]: List of draft orders
        """
        params = {'limit': limit}
        response = self.get(self.ENDPOINTS['draft_orders'], params=params)
        return response.get('draft_orders', [])
    
    def create_draft_order(self, draft_order_data: Dict) -> Dict[str, Any]:
        """
        Create a draft order (for B2B approval workflow).
        
        Args:
            draft_order_data: Draft order details
            
        Returns:
            Dict: Created draft order data
        """
        _record_shopify_draft(draft_order_data)
        response = self.post(
            self.ENDPOINTS['draft_orders'],
            {'draft_order': draft_order_data}
        )
        saved = response.get('draft_order', response)
        if saved is not draft_order_data:
            recorded = _saved_shopify_draft(saved, draft_order_data)
            _record_shopify_draft(_saved_shopify_draft_lines(recorded, draft_order_data))
        return saved
    
    def send_draft_order_invoice(
        self,
        draft_order_id: int,
        to: Optional[str] = None,
        subject: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send invoice for a draft order.
        
        Args:
            draft_order_id: Draft order ID
            to: Email recipient
            subject: Email subject
            custom_message: Custom message
            
        Returns:
            Dict: Invoice response
        """
        endpoint = f"draft_orders/{draft_order_id}/send_invoice.json"
        
        invoice_data = {}
        if to:
            invoice_data['to'] = to
        if subject:
            invoice_data['subject'] = subject
        if custom_message:
            invoice_data['custom_message'] = custom_message
        
        response = self.post(endpoint, {'draft_order_invoice': invoice_data})
        return response.get('draft_order_invoice', response)
    
    def complete_draft_order(
        self,
        draft_order_id: int,
        payment_pending: bool = False
    ) -> Dict[str, Any]:
        """
        Complete a draft order (convert to order).
        
        Args:
            draft_order_id: Draft order ID
            payment_pending: Whether payment is pending
            
        Returns:
            Dict: Completed order data
        """
        endpoint = f"draft_orders/{draft_order_id}/complete.json"
        response = self.put(endpoint, {'payment_pending': payment_pending})
        draft = response.get('draft_order', response) if isinstance(response, dict) else {}
        if isinstance(draft, dict) and not _draft_names_itself(draft):
            draft = dict(draft)
            if draft_order_id is not None:
                draft["id"] = draft_order_id
        _record_shopify_draft(draft)
        return draft
    
    # ==================== Webhook Operations ====================
    
    def create_webhook(
        self,
        topic: str,
        address: str,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Create a webhook subscription.
        
        Args:
            topic: Webhook topic (e.g., 'orders/create')
            address: Webhook callback URL
            format: Response format
            
        Returns:
            Dict: Created webhook data
        """
        webhook_data = {
            'topic': topic,
            'address': address,
            'format': format
        }
        
        response = self.post(self.ENDPOINTS['webhooks'], {'webhook': webhook_data})
        return response.get('webhook', response)
    
    def get_webhooks(self) -> List[Dict[str, Any]]:
        """
        Get all webhook subscriptions.
        
        Returns:
            List[Dict]: List of webhooks
        """
        response = self.get(self.ENDPOINTS['webhooks'])
        return response.get('webhooks', [])
    
    def delete_webhook(self, webhook_id: int) -> bool:
        """
        Delete a webhook subscription.
        
        Args:
            webhook_id: Webhook ID
            
        Returns:
            bool: True if deletion was successful
        """
        endpoint = f"webhooks/{webhook_id}.json"
        self.delete(endpoint)
        return True
    
    # ==================== Sync Operations ====================
    
    def sync_appointments(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Synchronize orders from Shopify (treated as appointments for services).
        
        Args:
            since: Only sync orders created since this time
            
        Returns:
            List[Dict]: List of synchronized orders
        """
        orders = self.get_orders(
            limit=250,
            status='any',
            created_at_min=since
        )
        
        logger.info(f"Synced {len(orders)} orders from Shopify")
        return orders
    
    def sync_clients(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Synchronize customers from Shopify.
        
        Args:
            since: Only sync customers modified since this time
            
        Returns:
            List[Dict]: List of synchronized customers
        """
        customers = self.get_customers(limit=250)
        
        logger.info(f"Synced {len(customers)} customers from Shopify")
        return customers
    
    def create_appointment(self, appointment_data: Dict) -> Dict:
        """
        Create an order on Shopify (appointment as order).
        
        Args:
            appointment_data: Appointment/order details
            
        Returns:
            Dict: Created order data
        """
        # The mapper posts a pending order and drops a sale this payload already names.
        _record_shopify_order(appointment_data)
        order_data = self._map_appointment_to_order(appointment_data)
        # A saved cancellation that omits its id still belongs to the order this appointment names.
        known = _stated_order_id(appointment_data)
        if known is not None and _stated_order_id(order_data) is None:
            order_data = {**order_data, "id": known}
        saved = self.create_order(order_data)
        _record_saved_appointment_lines(saved, appointment_data, order_data)
        return saved
    
    def update_appointment(self, appointment_id: str, appointment_data: Dict) -> Dict:
        """
        Update an order on Shopify.
        
        Args:
            appointment_id: Order ID
            appointment_data: Updated order details
            
        Returns:
            Dict: Updated order data
        """
        _record_shopify_order(appointment_data)
        order_data = self._map_appointment_to_order(appointment_data)
        saved = self.update_order(int(appointment_id), order_data)
        _record_saved_appointment_lines(saved, appointment_data, order_data)
        return saved
    
    def cancel_appointment(self, appointment_id: str) -> bool:
        """
        Cancel an order on Shopify.
        
        Args:
            appointment_id: Order ID
            
        Returns:
            bool: True if cancellation was successful
        """
        try:
            self.cancel_order(int(appointment_id), reason="customer")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel Shopify order {appointment_id}: {e}")
            return False
    
    def _map_appointment_to_order(self, appointment_data: Dict) -> Dict:
        """Map appointment data to Shopify order format."""
        order_data = {
            'line_items': [],
            'customer': {},
            'financial_status': 'pending',
            'send_receipt': True
        }
        
        # Map customer
        if appointment_data.get('client_email'):
            order_data['customer'] = {
                'first_name': appointment_data.get('client_first_name', ''),
                'last_name': appointment_data.get('client_last_name', ''),
                'email': appointment_data.get('client_email', '')
            }
        
        # Map line items
        for item in appointment_data.get('items', []):
            line_item = {
                'title': item.get('name', 'Service'),
                'quantity': item.get('quantity', 1),
                'price': str(item.get('price', 0))
            }
            if item.get('variant_id'):
                line_item['variant_id'] = item['variant_id']
            order_data['line_items'].append(line_item)
        
        # Map addresses
        if appointment_data.get('shipping_address'):
            order_data['shipping_address'] = appointment_data['shipping_address']
        if appointment_data.get('billing_address'):
            order_data['billing_address'] = appointment_data['billing_address']
        
        # Map notes
        if appointment_data.get('notes'):
            order_data['note'] = appointment_data['notes']
        
        return order_data
    
    # ==================== Data Mapping ====================
    
    def map_order_to_unified(self, shopify_order: Dict) -> UnifiedOrder:
        """
        Map a Shopify order to the unified order model.
        
        Args:
            shopify_order: Shopify order data
            
        Returns:
            UnifiedOrder: Unified order model
        """
        customer_data = shopify_order.get('customer', {})
        
        # Create client
        client = UnifiedClient(
            first_name=customer_data.get('first_name', ''),
            last_name=customer_data.get('last_name', ''),
            email=customer_data.get('email', ''),
            phone=customer_data.get('phone', '')
        )
        client.name = f"{client.first_name} {client.last_name}".strip()
        
        # Check for B2B
        company = shopify_order.get('company', {})
        if company:
            client.is_b2b = True
            client.company_name = company.get('name', '')
            client.company_id = str(company.get('id', ''))
        
        # Map line items
        items = []
        for line_item in shopify_order.get('line_items', []):
            items.append(UnifiedOrderItem(
                name=line_item.get('title', ''),
                sku=line_item.get('sku', ''),
                quantity=int(line_item.get('quantity', 1)),
                unit_price=float(line_item.get('price', 0)),
                total_price=float(line_item.get('price', 0)) * int(line_item.get('quantity', 1)),
                discount=float(line_item.get('total_discount', 0))
            ))
        
        # Map payment status
        financial_status_map = {
            'pending': PaymentStatus.PENDING,
            'authorized': PaymentStatus.PENDING,
            'partially_paid': PaymentStatus.PARTIALLY_PAID,
            'paid': PaymentStatus.PAID,
            'partially_refunded': PaymentStatus.PARTIALLY_PAID,
            'refunded': PaymentStatus.REFUNDED,
            'voided': PaymentStatus.REFUNDED
        }
        
        # Map shipping address
        shipping = shopify_order.get('shipping_address', {})
        shipping_address = {
            'first_name': shipping.get('first_name', ''),
            'last_name': shipping.get('last_name', ''),
            'address_1': shipping.get('address1', ''),
            'address_2': shipping.get('address2', ''),
            'city': shipping.get('city', ''),
            'province': shipping.get('province', ''),
            'postal_code': shipping.get('zip', ''),
            'country': shipping.get('country', '')
        }
        
        # Map billing address
        billing = shopify_order.get('billing_address', {})
        billing_address = {
            'first_name': billing.get('first_name', ''),
            'last_name': billing.get('last_name', ''),
            'address_1': billing.get('address1', ''),
            'address_2': billing.get('address2', ''),
            'city': billing.get('city', ''),
            'province': billing.get('province', ''),
            'postal_code': billing.get('zip', ''),
            'country': billing.get('country', '')
        }
        
        # Parse dates
        created_at = None
        updated_at = None
        if shopify_order.get('created_at'):
            created_at = datetime.fromisoformat(
                shopify_order['created_at'].replace('Z', '+00:00')
            )
        if shopify_order.get('updated_at'):
            updated_at = datetime.fromisoformat(
                shopify_order['updated_at'].replace('Z', '+00:00')
            )
        
        order = UnifiedOrder(
            order_number=shopify_order.get('name', str(shopify_order.get('id', ''))),
            client=client,
            company_id=client.company_id if client.is_b2b else None,
            is_b2b=client.is_b2b,
            items=items,
            subtotal=float(shopify_order.get('subtotal_price', 0)),
            tax=float(shopify_order.get('total_tax', 0)),
            shipping=float(shopify_order.get('total_shipping_price_set', {}).get('shop_money', {}).get('amount', 0)),
            discount=float(shopify_order.get('total_discounts', 0)),
            total=float(shopify_order.get('total_price', 0)),
            currency=shopify_order.get('currency', 'USD'),
            status=shopify_order.get('fulfillment_status', 'unfulfilled') or 'unfulfilled',
            payment_status=financial_status_map.get(
                shopify_order.get('financial_status', 'pending'),
                PaymentStatus.PENDING
            ),
            fulfillment_status=shopify_order.get('fulfillment_status', 'unfulfilled') or 'unfulfilled',
            shipping_address=shipping_address,
            billing_address=billing_address,
            notes=shopify_order.get('note', ''),
            created_at=created_at,
            updated_at=updated_at
        )
        
        # Add platform reference
        order.platform_refs.append(PlatformReference(
            platform=self.PLATFORM_NAME,
            external_id=str(shopify_order.get('id', '')),
            last_synced=datetime.utcnow(),
            sync_status=SyncStatus.SYNCED,
            metadata={
                'order_number': shopify_order.get('order_number'),
                'name': shopify_order.get('name')
            }
        ))
        
        return order
    
    def map_product_to_unified(self, shopify_product: Dict) -> UnifiedProduct:
        """
        Map a Shopify product to the unified product model.
        
        Args:
            shopify_product: Shopify product data
            
        Returns:
            UnifiedProduct: Unified product model
        """
        variants = shopify_product.get('variants', [])
        first_variant = variants[0] if variants else {}
        
        product = UnifiedProduct(
            name=shopify_product.get('title', ''),
            description=shopify_product.get('body_html', ''),
            sku=first_variant.get('sku', ''),
            price=float(first_variant.get('price', 0)),
            compare_at_price=float(first_variant.get('compare_at_price', 0)) if first_variant.get('compare_at_price') else None,
            quantity=sum(int(v.get('inventory_quantity', 0)) for v in variants),
            category=shopify_product.get('product_type', ''),
            tags=shopify_product.get('tags', '').split(', ') if shopify_product.get('tags') else [],
            vendor=shopify_product.get('vendor', '')
        )
        
        # Add images
        for image in shopify_product.get('images', []):
            product.images.append(image.get('src', ''))
        
        # Add platform reference
        product.platform_refs.append(PlatformReference(
            platform=self.PLATFORM_NAME,
            external_id=str(shopify_product.get('id', '')),
            last_synced=datetime.utcnow(),
            sync_status=SyncStatus.SYNCED,
            metadata={
                'handle': shopify_product.get('handle'),
                'variant_ids': [v.get('id') for v in variants]
            }
        ))
        
        return product
    
    def map_customer_to_unified(self, shopify_customer: Dict) -> UnifiedClient:
        """
        Map a Shopify customer to the unified client model.
        
        Args:
            shopify_customer: Shopify customer data
            
        Returns:
            UnifiedClient: Unified client model
        """
        default_address = shopify_customer.get('default_address', {})
        
        client = UnifiedClient(
            first_name=shopify_customer.get('first_name', ''),
            last_name=shopify_customer.get('last_name', ''),
            email=shopify_customer.get('email', ''),
            phone=shopify_customer.get('phone', ''),
            address_line1=default_address.get('address1', ''),
            address_line2=default_address.get('address2', ''),
            city=default_address.get('city', ''),
            state=default_address.get('province', ''),
            postal_code=default_address.get('zip', ''),
            country=default_address.get('country', ''),
            total_spent=float(shopify_customer.get('total_spent', 0))
        )
        client.name = f"{client.first_name} {client.last_name}".strip()
        
        # Add platform reference
        client.platform_refs.append(PlatformReference(
            platform=self.PLATFORM_NAME,
            external_id=str(shopify_customer.get('id', '')),
            last_synced=datetime.utcnow(),
            sync_status=SyncStatus.SYNCED
        ))
        
        return client
