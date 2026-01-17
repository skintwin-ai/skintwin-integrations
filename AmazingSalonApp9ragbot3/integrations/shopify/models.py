"""
Shopify-Specific Data Models
Models for Shopify Admin API data structures with B2B support
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ShopifyAddress:
    """Shopify address model."""
    address1: str = ""
    address2: str = ""
    city: str = ""
    province: str = ""
    province_code: str = ""
    country: str = ""
    country_code: str = ""
    zip: str = ""
    phone: str = ""
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    company: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'address1': self.address1,
            'address2': self.address2,
            'city': self.city,
            'province': self.province,
            'province_code': self.province_code,
            'country': self.country,
            'country_code': self.country_code,
            'zip': self.zip,
            'phone': self.phone,
            'name': self.name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company': self.company
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ShopifyAddress':
        return cls(
            address1=data.get('address1', ''),
            address2=data.get('address2', ''),
            city=data.get('city', ''),
            province=data.get('province', ''),
            province_code=data.get('province_code', ''),
            country=data.get('country', ''),
            country_code=data.get('country_code', ''),
            zip=data.get('zip', ''),
            phone=data.get('phone', ''),
            name=data.get('name', ''),
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            company=data.get('company', '')
        )


@dataclass
class ShopifyCustomer:
    """Shopify customer model."""
    id: int = 0
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    
    # Status
    accepts_marketing: bool = False
    verified_email: bool = False
    state: str = "enabled"
    
    # Tags and notes
    tags: str = ""
    note: str = ""
    
    # Addresses
    default_address: Optional[ShopifyAddress] = None
    addresses: List[ShopifyAddress] = field(default_factory=list)
    
    # Stats
    orders_count: int = 0
    total_spent: str = "0.00"
    
    # Tax
    tax_exempt: bool = False
    tax_exemptions: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'ShopifyCustomer':
        """Create a ShopifyCustomer from API response data."""
        default_address = None
        if data.get('default_address'):
            default_address = ShopifyAddress.from_dict(data['default_address'])
        
        addresses = []
        for addr_data in data.get('addresses', []):
            addresses.append(ShopifyAddress.from_dict(addr_data))
        
        created_at = None
        updated_at = None
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if data.get('updated_at'):
            updated_at = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        
        return cls(
            id=data.get('id', 0),
            email=data.get('email', ''),
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            phone=data.get('phone', ''),
            accepts_marketing=data.get('accepts_marketing', False),
            verified_email=data.get('verified_email', False),
            state=data.get('state', 'enabled'),
            tags=data.get('tags', ''),
            note=data.get('note', ''),
            default_address=default_address,
            addresses=addresses,
            orders_count=data.get('orders_count', 0),
            total_spent=data.get('total_spent', '0.00'),
            tax_exempt=data.get('tax_exempt', False),
            tax_exemptions=data.get('tax_exemptions', []),
            created_at=created_at,
            updated_at=updated_at
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'accepts_marketing': self.accepts_marketing,
            'tags': self.tags,
            'note': self.note,
            'tax_exempt': self.tax_exempt
        }


@dataclass
class ShopifyProductVariant:
    """Shopify product variant model."""
    id: int = 0
    product_id: int = 0
    title: str = ""
    price: str = "0.00"
    compare_at_price: Optional[str] = None
    sku: str = ""
    barcode: str = ""
    position: int = 1
    
    # Inventory
    inventory_item_id: int = 0
    inventory_quantity: int = 0
    inventory_management: str = "shopify"
    inventory_policy: str = "deny"
    
    # Fulfillment
    fulfillment_service: str = "manual"
    requires_shipping: bool = True
    
    # Weight
    weight: float = 0.0
    weight_unit: str = "kg"
    
    # Options
    option1: Optional[str] = None
    option2: Optional[str] = None
    option3: Optional[str] = None
    
    # Image
    image_id: Optional[int] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'price': self.price,
            'compare_at_price': self.compare_at_price,
            'sku': self.sku,
            'barcode': self.barcode,
            'inventory_quantity': self.inventory_quantity,
            'weight': self.weight,
            'weight_unit': self.weight_unit
        }


@dataclass
class ShopifyProduct:
    """Shopify product model."""
    id: int = 0
    title: str = ""
    body_html: str = ""
    vendor: str = ""
    product_type: str = ""
    handle: str = ""
    
    # Status
    status: str = "active"  # active, archived, draft
    published_at: Optional[datetime] = None
    
    # Tags
    tags: str = ""
    
    # Variants
    variants: List[ShopifyProductVariant] = field(default_factory=list)
    
    # Options
    options: List[Dict[str, Any]] = field(default_factory=list)
    
    # Images
    images: List[Dict[str, Any]] = field(default_factory=list)
    image: Optional[Dict[str, Any]] = None
    
    # Template
    template_suffix: str = ""
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'ShopifyProduct':
        """Create a ShopifyProduct from API response data."""
        variants = []
        for var_data in data.get('variants', []):
            variant = ShopifyProductVariant(
                id=var_data.get('id', 0),
                product_id=var_data.get('product_id', 0),
                title=var_data.get('title', ''),
                price=var_data.get('price', '0.00'),
                compare_at_price=var_data.get('compare_at_price'),
                sku=var_data.get('sku', ''),
                barcode=var_data.get('barcode', ''),
                position=var_data.get('position', 1),
                inventory_item_id=var_data.get('inventory_item_id', 0),
                inventory_quantity=var_data.get('inventory_quantity', 0),
                inventory_management=var_data.get('inventory_management', 'shopify'),
                inventory_policy=var_data.get('inventory_policy', 'deny'),
                fulfillment_service=var_data.get('fulfillment_service', 'manual'),
                requires_shipping=var_data.get('requires_shipping', True),
                weight=float(var_data.get('weight', 0)),
                weight_unit=var_data.get('weight_unit', 'kg'),
                option1=var_data.get('option1'),
                option2=var_data.get('option2'),
                option3=var_data.get('option3'),
                image_id=var_data.get('image_id')
            )
            variants.append(variant)
        
        created_at = None
        updated_at = None
        published_at = None
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if data.get('updated_at'):
            updated_at = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        if data.get('published_at'):
            published_at = datetime.fromisoformat(data['published_at'].replace('Z', '+00:00'))
        
        return cls(
            id=data.get('id', 0),
            title=data.get('title', ''),
            body_html=data.get('body_html', ''),
            vendor=data.get('vendor', ''),
            product_type=data.get('product_type', ''),
            handle=data.get('handle', ''),
            status=data.get('status', 'active'),
            published_at=published_at,
            tags=data.get('tags', ''),
            variants=variants,
            options=data.get('options', []),
            images=data.get('images', []),
            image=data.get('image'),
            template_suffix=data.get('template_suffix', ''),
            created_at=created_at,
            updated_at=updated_at
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'body_html': self.body_html,
            'vendor': self.vendor,
            'product_type': self.product_type,
            'handle': self.handle,
            'status': self.status,
            'tags': self.tags,
            'variants': [v.to_dict() for v in self.variants]
        }


@dataclass
class ShopifyLineItem:
    """Shopify order line item model."""
    id: int = 0
    variant_id: Optional[int] = None
    product_id: Optional[int] = None
    title: str = ""
    variant_title: str = ""
    sku: str = ""
    vendor: str = ""
    quantity: int = 1
    price: str = "0.00"
    total_discount: str = "0.00"
    fulfillment_status: Optional[str] = None
    requires_shipping: bool = True
    taxable: bool = True
    gift_card: bool = False
    name: str = ""
    
    # Tax
    tax_lines: List[Dict[str, Any]] = field(default_factory=list)
    
    # Properties
    properties: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'variant_id': self.variant_id,
            'product_id': self.product_id,
            'title': self.title,
            'sku': self.sku,
            'quantity': self.quantity,
            'price': self.price,
            'total_discount': self.total_discount
        }


@dataclass
class ShopifyOrder:
    """Shopify order model."""
    id: int = 0
    name: str = ""
    order_number: int = 0
    
    # Customer
    customer: Optional[ShopifyCustomer] = None
    email: str = ""
    phone: str = ""
    
    # B2B
    company: Optional[Dict[str, Any]] = None
    
    # Addresses
    billing_address: Optional[ShopifyAddress] = None
    shipping_address: Optional[ShopifyAddress] = None
    
    # Line items
    line_items: List[ShopifyLineItem] = field(default_factory=list)
    
    # Pricing
    currency: str = "USD"
    subtotal_price: str = "0.00"
    total_tax: str = "0.00"
    total_discounts: str = "0.00"
    total_price: str = "0.00"
    
    # Status
    financial_status: str = "pending"
    fulfillment_status: Optional[str] = None
    
    # Payment
    gateway: str = ""
    payment_gateway_names: List[str] = field(default_factory=list)
    
    # Fulfillment
    fulfillments: List[Dict[str, Any]] = field(default_factory=list)
    
    # Notes
    note: str = ""
    note_attributes: List[Dict[str, str]] = field(default_factory=list)
    
    # Tags
    tags: str = ""
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'ShopifyOrder':
        """Create a ShopifyOrder from API response data."""
        customer = None
        if data.get('customer'):
            customer = ShopifyCustomer.from_api_response(data['customer'])
        
        billing_address = None
        if data.get('billing_address'):
            billing_address = ShopifyAddress.from_dict(data['billing_address'])
        
        shipping_address = None
        if data.get('shipping_address'):
            shipping_address = ShopifyAddress.from_dict(data['shipping_address'])
        
        line_items = []
        for item_data in data.get('line_items', []):
            item = ShopifyLineItem(
                id=item_data.get('id', 0),
                variant_id=item_data.get('variant_id'),
                product_id=item_data.get('product_id'),
                title=item_data.get('title', ''),
                variant_title=item_data.get('variant_title', ''),
                sku=item_data.get('sku', ''),
                vendor=item_data.get('vendor', ''),
                quantity=item_data.get('quantity', 1),
                price=item_data.get('price', '0.00'),
                total_discount=item_data.get('total_discount', '0.00'),
                fulfillment_status=item_data.get('fulfillment_status'),
                requires_shipping=item_data.get('requires_shipping', True),
                taxable=item_data.get('taxable', True),
                gift_card=item_data.get('gift_card', False),
                name=item_data.get('name', ''),
                tax_lines=item_data.get('tax_lines', []),
                properties=item_data.get('properties', [])
            )
            line_items.append(item)
        
        # Parse timestamps
        created_at = None
        updated_at = None
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if data.get('updated_at'):
            updated_at = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        
        return cls(
            id=data.get('id', 0),
            name=data.get('name', ''),
            order_number=data.get('order_number', 0),
            customer=customer,
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            company=data.get('company'),
            billing_address=billing_address,
            shipping_address=shipping_address,
            line_items=line_items,
            currency=data.get('currency', 'USD'),
            subtotal_price=data.get('subtotal_price', '0.00'),
            total_tax=data.get('total_tax', '0.00'),
            total_discounts=data.get('total_discounts', '0.00'),
            total_price=data.get('total_price', '0.00'),
            financial_status=data.get('financial_status', 'pending'),
            fulfillment_status=data.get('fulfillment_status'),
            gateway=data.get('gateway', ''),
            payment_gateway_names=data.get('payment_gateway_names', []),
            fulfillments=data.get('fulfillments', []),
            note=data.get('note', ''),
            note_attributes=data.get('note_attributes', []),
            tags=data.get('tags', ''),
            created_at=created_at,
            updated_at=updated_at
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'order_number': self.order_number,
            'email': self.email,
            'total_price': self.total_price,
            'financial_status': self.financial_status,
            'fulfillment_status': self.fulfillment_status,
            'line_items': [item.to_dict() for item in self.line_items]
        }


# ==================== B2B Models ====================

@dataclass
class ShopifyCompanyContact:
    """Shopify B2B company contact model."""
    id: str = ""
    customer_id: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    is_main_contact: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'is_main_contact': self.is_main_contact
        }


@dataclass
class ShopifyCompanyLocation:
    """Shopify B2B company location model."""
    id: str = ""
    name: str = ""
    external_id: str = ""
    
    # Addresses
    billing_address: Optional[ShopifyAddress] = None
    shipping_address: Optional[ShopifyAddress] = None
    
    # Catalog
    catalog_id: Optional[str] = None
    
    # Payment terms
    payment_terms_template_id: Optional[str] = None
    
    # Tax
    tax_exemptions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'external_id': self.external_id,
            'billing_address': self.billing_address.to_dict() if self.billing_address else None,
            'shipping_address': self.shipping_address.to_dict() if self.shipping_address else None,
            'catalog_id': self.catalog_id
        }


@dataclass
class ShopifyCompany:
    """Shopify B2B company model."""
    id: str = ""
    name: str = ""
    external_id: str = ""
    note: str = ""
    
    # Locations
    locations: List[ShopifyCompanyLocation] = field(default_factory=list)
    
    # Contacts
    contacts: List[ShopifyCompanyContact] = field(default_factory=list)
    
    # Main contact
    main_contact_id: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_graphql_response(cls, data: Dict) -> 'ShopifyCompany':
        """Create a ShopifyCompany from GraphQL response data."""
        locations = []
        for edge in data.get('locations', {}).get('edges', []):
            loc_data = edge.get('node', {})
            
            billing_addr = None
            if loc_data.get('billingAddress'):
                billing_addr = ShopifyAddress(
                    address1=loc_data['billingAddress'].get('address1', ''),
                    address2=loc_data['billingAddress'].get('address2', ''),
                    city=loc_data['billingAddress'].get('city', ''),
                    province=loc_data['billingAddress'].get('province', ''),
                    zip=loc_data['billingAddress'].get('zip', ''),
                    country=loc_data['billingAddress'].get('country', '')
                )
            
            shipping_addr = None
            if loc_data.get('shippingAddress'):
                shipping_addr = ShopifyAddress(
                    address1=loc_data['shippingAddress'].get('address1', ''),
                    address2=loc_data['shippingAddress'].get('address2', ''),
                    city=loc_data['shippingAddress'].get('city', ''),
                    province=loc_data['shippingAddress'].get('province', ''),
                    zip=loc_data['shippingAddress'].get('zip', ''),
                    country=loc_data['shippingAddress'].get('country', '')
                )
            
            locations.append(ShopifyCompanyLocation(
                id=loc_data.get('id', ''),
                name=loc_data.get('name', ''),
                external_id=loc_data.get('externalId', ''),
                billing_address=billing_addr,
                shipping_address=shipping_addr
            ))
        
        contacts = []
        for edge in data.get('contacts', {}).get('edges', []):
            contact_data = edge.get('node', {})
            customer_data = contact_data.get('customer', {})
            
            contacts.append(ShopifyCompanyContact(
                id=contact_data.get('id', ''),
                customer_id=customer_data.get('id', ''),
                first_name=customer_data.get('firstName', ''),
                last_name=customer_data.get('lastName', ''),
                email=customer_data.get('email', '')
            ))
        
        created_at = None
        updated_at = None
        if data.get('createdAt'):
            created_at = datetime.fromisoformat(data['createdAt'].replace('Z', '+00:00'))
        if data.get('updatedAt'):
            updated_at = datetime.fromisoformat(data['updatedAt'].replace('Z', '+00:00'))
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            external_id=data.get('externalId', ''),
            note=data.get('note', ''),
            locations=locations,
            contacts=contacts,
            created_at=created_at,
            updated_at=updated_at
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'external_id': self.external_id,
            'note': self.note,
            'locations': [loc.to_dict() for loc in self.locations],
            'contacts': [contact.to_dict() for contact in self.contacts]
        }


@dataclass
class ShopifyDraftOrder:
    """Shopify draft order model (for B2B approval workflow)."""
    id: int = 0
    name: str = ""
    
    # Customer
    customer: Optional[ShopifyCustomer] = None
    email: str = ""
    
    # B2B
    company: Optional[Dict[str, Any]] = None
    
    # Addresses
    billing_address: Optional[ShopifyAddress] = None
    shipping_address: Optional[ShopifyAddress] = None
    
    # Line items
    line_items: List[ShopifyLineItem] = field(default_factory=list)
    
    # Pricing
    currency: str = "USD"
    subtotal_price: str = "0.00"
    total_tax: str = "0.00"
    total_price: str = "0.00"
    
    # Status
    status: str = "open"  # open, invoice_sent, completed
    
    # Invoice
    invoice_sent_at: Optional[datetime] = None
    invoice_url: str = ""
    
    # Notes
    note: str = ""
    note_attributes: List[Dict[str, str]] = field(default_factory=list)
    
    # Tags
    tags: str = ""
    
    # Completed order
    order_id: Optional[int] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'ShopifyDraftOrder':
        """Create a ShopifyDraftOrder from API response data."""
        customer = None
        if data.get('customer'):
            customer = ShopifyCustomer.from_api_response(data['customer'])
        
        billing_address = None
        if data.get('billing_address'):
            billing_address = ShopifyAddress.from_dict(data['billing_address'])
        
        shipping_address = None
        if data.get('shipping_address'):
            shipping_address = ShopifyAddress.from_dict(data['shipping_address'])
        
        line_items = []
        for item_data in data.get('line_items', []):
            item = ShopifyLineItem(
                id=item_data.get('id', 0),
                variant_id=item_data.get('variant_id'),
                product_id=item_data.get('product_id'),
                title=item_data.get('title', ''),
                sku=item_data.get('sku', ''),
                quantity=item_data.get('quantity', 1),
                price=item_data.get('price', '0.00')
            )
            line_items.append(item)
        
        created_at = None
        updated_at = None
        if data.get('created_at'):
            created_at = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        if data.get('updated_at'):
            updated_at = datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))
        
        return cls(
            id=data.get('id', 0),
            name=data.get('name', ''),
            customer=customer,
            email=data.get('email', ''),
            company=data.get('company'),
            billing_address=billing_address,
            shipping_address=shipping_address,
            line_items=line_items,
            currency=data.get('currency', 'USD'),
            subtotal_price=data.get('subtotal_price', '0.00'),
            total_tax=data.get('total_tax', '0.00'),
            total_price=data.get('total_price', '0.00'),
            status=data.get('status', 'open'),
            invoice_sent_at=datetime.fromisoformat(data['invoice_sent_at'].replace('Z', '+00:00')) if data.get('invoice_sent_at') else None,
            invoice_url=data.get('invoice_url', ''),
            note=data.get('note', ''),
            note_attributes=data.get('note_attributes', []),
            tags=data.get('tags', ''),
            order_id=data.get('order_id'),
            created_at=created_at,
            updated_at=updated_at,
            completed_at=datetime.fromisoformat(data['completed_at'].replace('Z', '+00:00')) if data.get('completed_at') else None
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'total_price': self.total_price,
            'status': self.status,
            'line_items': [item.to_dict() for item in self.line_items],
            'order_id': self.order_id
        }
