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
        response = self.post(self.ENDPOINTS['products'], {'product': product_data})
        return response.get('product', response)
    
    def update_product(self, product_id: int, product_data: Dict) -> Dict[str, Any]:
        """
        Update an existing product.
        
        Args:
            product_id: Shopify product ID
            product_data: Updated product details
            
        Returns:
            Dict: Updated product data
        """
        endpoint = self.ENDPOINTS['product'].format(id=product_id)
        response = self.put(endpoint, {'product': product_data})
        return response.get('product', response)
    
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
        response = self.post(self.ENDPOINTS['orders'], {'order': order_data})
        return response.get('order', response)
    
    def update_order(self, order_id: int, order_data: Dict) -> Dict[str, Any]:
        """
        Update an existing order.
        
        Args:
            order_id: Shopify order ID
            order_data: Updated order details
            
        Returns:
            Dict: Updated order data
        """
        endpoint = self.ENDPOINTS['order'].format(id=order_id)
        response = self.put(endpoint, {'order': order_data})
        return response.get('order', response)
    
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
        return response.get('order', response)
    
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
        response = self.post(
            self.ENDPOINTS['draft_orders'],
            {'draft_order': draft_order_data}
        )
        return response.get('draft_order', response)
    
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
        return response.get('draft_order', response)
    
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
        # Map appointment data to Shopify order format
        order_data = self._map_appointment_to_order(appointment_data)
        return self.create_order(order_data)
    
    def update_appointment(self, appointment_id: str, appointment_data: Dict) -> Dict:
        """
        Update an order on Shopify.
        
        Args:
            appointment_id: Order ID
            appointment_data: Updated order details
            
        Returns:
            Dict: Updated order data
        """
        order_data = self._map_appointment_to_order(appointment_data)
        return self.update_order(int(appointment_id), order_data)
    
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
