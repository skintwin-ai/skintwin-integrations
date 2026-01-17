"""
OpenCart-Specific Data Models
Models for OpenCart API data structures
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class OpenCartAddress:
    """OpenCart address model."""
    address_id: int = 0
    firstname: str = ""
    lastname: str = ""
    company: str = ""
    address_1: str = ""
    address_2: str = ""
    city: str = ""
    postcode: str = ""
    country_id: int = 0
    country: str = ""
    zone_id: int = 0
    zone: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'address_id': self.address_id,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'company': self.company,
            'address_1': self.address_1,
            'address_2': self.address_2,
            'city': self.city,
            'postcode': self.postcode,
            'country_id': self.country_id,
            'country': self.country,
            'zone_id': self.zone_id,
            'zone': self.zone
        }


@dataclass
class OpenCartCustomer:
    """OpenCart customer model."""
    customer_id: int = 0
    customer_group_id: int = 1
    store_id: int = 0
    language_id: int = 1
    
    firstname: str = ""
    lastname: str = ""
    email: str = ""
    telephone: str = ""
    fax: str = ""
    
    # Password (hashed)
    password: str = ""
    salt: str = ""
    
    # Address
    address_id: int = 0
    addresses: List[OpenCartAddress] = field(default_factory=list)
    
    # Status
    status: int = 1
    safe: int = 0
    
    # Newsletter
    newsletter: int = 0
    
    # IP tracking
    ip: str = ""
    
    # Timestamps
    date_added: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'OpenCartCustomer':
        """Create an OpenCartCustomer from API response data."""
        addresses = []
        for addr_data in data.get('addresses', []):
            addresses.append(OpenCartAddress(
                address_id=addr_data.get('address_id', 0),
                firstname=addr_data.get('firstname', ''),
                lastname=addr_data.get('lastname', ''),
                company=addr_data.get('company', ''),
                address_1=addr_data.get('address_1', ''),
                address_2=addr_data.get('address_2', ''),
                city=addr_data.get('city', ''),
                postcode=addr_data.get('postcode', ''),
                country_id=addr_data.get('country_id', 0),
                country=addr_data.get('country', ''),
                zone_id=addr_data.get('zone_id', 0),
                zone=addr_data.get('zone', '')
            ))
        
        date_added = None
        if data.get('date_added'):
            try:
                date_added = datetime.fromisoformat(data['date_added'])
            except ValueError:
                pass
        
        return cls(
            customer_id=data.get('customer_id', 0),
            customer_group_id=data.get('customer_group_id', 1),
            store_id=data.get('store_id', 0),
            language_id=data.get('language_id', 1),
            firstname=data.get('firstname', ''),
            lastname=data.get('lastname', ''),
            email=data.get('email', ''),
            telephone=data.get('telephone', ''),
            fax=data.get('fax', ''),
            address_id=data.get('address_id', 0),
            addresses=addresses,
            status=data.get('status', 1),
            safe=data.get('safe', 0),
            newsletter=data.get('newsletter', 0),
            ip=data.get('ip', ''),
            date_added=date_added
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'customer_id': self.customer_id,
            'customer_group_id': self.customer_group_id,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'email': self.email,
            'telephone': self.telephone,
            'status': self.status,
            'newsletter': self.newsletter
        }


@dataclass
class OpenCartProductOption:
    """OpenCart product option model."""
    product_option_id: int = 0
    product_option_value_id: int = 0
    option_id: int = 0
    option_value_id: int = 0
    name: str = ""
    value: str = ""
    type: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'product_option_id': self.product_option_id,
            'product_option_value_id': self.product_option_value_id,
            'name': self.name,
            'value': self.value,
            'type': self.type
        }


@dataclass
class OpenCartProduct:
    """OpenCart product model."""
    product_id: int = 0
    model: str = ""
    sku: str = ""
    upc: str = ""
    ean: str = ""
    jan: str = ""
    isbn: str = ""
    mpn: str = ""
    
    # Pricing
    price: float = 0.0
    special: Optional[float] = None
    tax_class_id: int = 0
    
    # Stock
    quantity: int = 0
    stock_status_id: int = 0
    stock_status: str = ""
    minimum: int = 1
    subtract: int = 1
    
    # Shipping
    shipping: int = 1
    weight: float = 0.0
    weight_class_id: int = 0
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0
    length_class_id: int = 0
    
    # Content
    name: str = ""
    description: str = ""
    meta_title: str = ""
    meta_description: str = ""
    meta_keyword: str = ""
    tag: str = ""
    
    # Images
    image: str = ""
    images: List[str] = field(default_factory=list)
    
    # Categories
    categories: List[int] = field(default_factory=list)
    
    # Manufacturer
    manufacturer_id: int = 0
    manufacturer: str = ""
    
    # Options
    options: List[OpenCartProductOption] = field(default_factory=list)
    
    # Status
    status: int = 1
    sort_order: int = 0
    
    # Dates
    date_available: Optional[datetime] = None
    date_added: Optional[datetime] = None
    date_modified: Optional[datetime] = None
    
    # SEO
    seo_url: str = ""
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'OpenCartProduct':
        """Create an OpenCartProduct from API response data."""
        images = data.get('images', [])
        if isinstance(images, list):
            images = [img.get('image', img) if isinstance(img, dict) else img for img in images]
        
        options = []
        for opt_data in data.get('options', []):
            options.append(OpenCartProductOption(
                product_option_id=opt_data.get('product_option_id', 0),
                product_option_value_id=opt_data.get('product_option_value_id', 0),
                option_id=opt_data.get('option_id', 0),
                option_value_id=opt_data.get('option_value_id', 0),
                name=opt_data.get('name', ''),
                value=opt_data.get('value', ''),
                type=opt_data.get('type', '')
            ))
        
        return cls(
            product_id=data.get('product_id', 0),
            model=data.get('model', ''),
            sku=data.get('sku', ''),
            upc=data.get('upc', ''),
            ean=data.get('ean', ''),
            jan=data.get('jan', ''),
            isbn=data.get('isbn', ''),
            mpn=data.get('mpn', ''),
            price=float(data.get('price', 0)),
            special=float(data['special']) if data.get('special') else None,
            tax_class_id=data.get('tax_class_id', 0),
            quantity=int(data.get('quantity', 0)),
            stock_status_id=data.get('stock_status_id', 0),
            stock_status=data.get('stock_status', ''),
            minimum=data.get('minimum', 1),
            subtract=data.get('subtract', 1),
            shipping=data.get('shipping', 1),
            weight=float(data.get('weight', 0)),
            weight_class_id=data.get('weight_class_id', 0),
            length=float(data.get('length', 0)),
            width=float(data.get('width', 0)),
            height=float(data.get('height', 0)),
            length_class_id=data.get('length_class_id', 0),
            name=data.get('name', ''),
            description=data.get('description', ''),
            meta_title=data.get('meta_title', ''),
            meta_description=data.get('meta_description', ''),
            meta_keyword=data.get('meta_keyword', ''),
            tag=data.get('tag', ''),
            image=data.get('image', ''),
            images=images,
            categories=data.get('categories', []),
            manufacturer_id=data.get('manufacturer_id', 0),
            manufacturer=data.get('manufacturer', ''),
            options=options,
            status=data.get('status', 1),
            sort_order=data.get('sort_order', 0),
            seo_url=data.get('seo_url', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'product_id': self.product_id,
            'model': self.model,
            'sku': self.sku,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'special': self.special,
            'quantity': self.quantity,
            'stock_status': self.stock_status,
            'image': self.image,
            'manufacturer': self.manufacturer,
            'status': self.status
        }


@dataclass
class OpenCartOrderProduct:
    """OpenCart order product model."""
    order_product_id: int = 0
    order_id: int = 0
    product_id: int = 0
    name: str = ""
    model: str = ""
    quantity: int = 1
    price: float = 0.0
    total: float = 0.0
    tax: float = 0.0
    reward: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_product_id': self.order_product_id,
            'product_id': self.product_id,
            'name': self.name,
            'model': self.model,
            'quantity': self.quantity,
            'price': self.price,
            'total': self.total,
            'tax': self.tax
        }


@dataclass
class OpenCartOrderTotal:
    """OpenCart order total model."""
    order_total_id: int = 0
    order_id: int = 0
    code: str = ""
    title: str = ""
    value: float = 0.0
    sort_order: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'title': self.title,
            'value': self.value
        }


@dataclass
class OpenCartOrder:
    """OpenCart order model."""
    order_id: int = 0
    invoice_no: int = 0
    invoice_prefix: str = ""
    store_id: int = 0
    store_name: str = ""
    store_url: str = ""
    
    # Customer
    customer_id: int = 0
    customer_group_id: int = 1
    firstname: str = ""
    lastname: str = ""
    email: str = ""
    telephone: str = ""
    fax: str = ""
    
    # Payment address
    payment_firstname: str = ""
    payment_lastname: str = ""
    payment_company: str = ""
    payment_address_1: str = ""
    payment_address_2: str = ""
    payment_city: str = ""
    payment_postcode: str = ""
    payment_country: str = ""
    payment_country_id: int = 0
    payment_zone: str = ""
    payment_zone_id: int = 0
    payment_method: str = ""
    payment_code: str = ""
    
    # Shipping address
    shipping_firstname: str = ""
    shipping_lastname: str = ""
    shipping_company: str = ""
    shipping_address_1: str = ""
    shipping_address_2: str = ""
    shipping_city: str = ""
    shipping_postcode: str = ""
    shipping_country: str = ""
    shipping_country_id: int = 0
    shipping_zone: str = ""
    shipping_zone_id: int = 0
    shipping_method: str = ""
    shipping_code: str = ""
    
    # Order details
    comment: str = ""
    total: float = 0.0
    order_status_id: int = 0
    order_status: str = ""
    
    # Currency
    currency_id: int = 0
    currency_code: str = "USD"
    currency_value: float = 1.0
    
    # Products and totals
    products: List[OpenCartOrderProduct] = field(default_factory=list)
    totals: List[OpenCartOrderTotal] = field(default_factory=list)
    
    # Tracking
    ip: str = ""
    forwarded_ip: str = ""
    user_agent: str = ""
    accept_language: str = ""
    
    # Dates
    date_added: Optional[datetime] = None
    date_modified: Optional[datetime] = None
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'OpenCartOrder':
        """Create an OpenCartOrder from API response data."""
        products = []
        for prod_data in data.get('products', []):
            products.append(OpenCartOrderProduct(
                order_product_id=prod_data.get('order_product_id', 0),
                order_id=prod_data.get('order_id', 0),
                product_id=prod_data.get('product_id', 0),
                name=prod_data.get('name', ''),
                model=prod_data.get('model', ''),
                quantity=int(prod_data.get('quantity', 1)),
                price=float(prod_data.get('price', 0)),
                total=float(prod_data.get('total', 0)),
                tax=float(prod_data.get('tax', 0)),
                reward=prod_data.get('reward', 0)
            ))
        
        totals = []
        for total_data in data.get('totals', []):
            totals.append(OpenCartOrderTotal(
                order_total_id=total_data.get('order_total_id', 0),
                order_id=total_data.get('order_id', 0),
                code=total_data.get('code', ''),
                title=total_data.get('title', ''),
                value=float(total_data.get('value', 0)),
                sort_order=total_data.get('sort_order', 0)
            ))
        
        date_added = None
        date_modified = None
        if data.get('date_added'):
            try:
                date_added = datetime.fromisoformat(data['date_added'])
            except ValueError:
                pass
        if data.get('date_modified'):
            try:
                date_modified = datetime.fromisoformat(data['date_modified'])
            except ValueError:
                pass
        
        return cls(
            order_id=data.get('order_id', 0),
            invoice_no=data.get('invoice_no', 0),
            invoice_prefix=data.get('invoice_prefix', ''),
            store_id=data.get('store_id', 0),
            store_name=data.get('store_name', ''),
            store_url=data.get('store_url', ''),
            customer_id=data.get('customer_id', 0),
            customer_group_id=data.get('customer_group_id', 1),
            firstname=data.get('firstname', ''),
            lastname=data.get('lastname', ''),
            email=data.get('email', ''),
            telephone=data.get('telephone', ''),
            fax=data.get('fax', ''),
            payment_firstname=data.get('payment_firstname', ''),
            payment_lastname=data.get('payment_lastname', ''),
            payment_company=data.get('payment_company', ''),
            payment_address_1=data.get('payment_address_1', ''),
            payment_address_2=data.get('payment_address_2', ''),
            payment_city=data.get('payment_city', ''),
            payment_postcode=data.get('payment_postcode', ''),
            payment_country=data.get('payment_country', ''),
            payment_country_id=data.get('payment_country_id', 0),
            payment_zone=data.get('payment_zone', ''),
            payment_zone_id=data.get('payment_zone_id', 0),
            payment_method=data.get('payment_method', ''),
            payment_code=data.get('payment_code', ''),
            shipping_firstname=data.get('shipping_firstname', ''),
            shipping_lastname=data.get('shipping_lastname', ''),
            shipping_company=data.get('shipping_company', ''),
            shipping_address_1=data.get('shipping_address_1', ''),
            shipping_address_2=data.get('shipping_address_2', ''),
            shipping_city=data.get('shipping_city', ''),
            shipping_postcode=data.get('shipping_postcode', ''),
            shipping_country=data.get('shipping_country', ''),
            shipping_country_id=data.get('shipping_country_id', 0),
            shipping_zone=data.get('shipping_zone', ''),
            shipping_zone_id=data.get('shipping_zone_id', 0),
            shipping_method=data.get('shipping_method', ''),
            shipping_code=data.get('shipping_code', ''),
            comment=data.get('comment', ''),
            total=float(data.get('total', 0)),
            order_status_id=data.get('order_status_id', 0),
            order_status=data.get('order_status', ''),
            currency_id=data.get('currency_id', 0),
            currency_code=data.get('currency_code', 'USD'),
            currency_value=float(data.get('currency_value', 1.0)),
            products=products,
            totals=totals,
            ip=data.get('ip', ''),
            forwarded_ip=data.get('forwarded_ip', ''),
            user_agent=data.get('user_agent', ''),
            accept_language=data.get('accept_language', ''),
            date_added=date_added,
            date_modified=date_modified
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_id': self.order_id,
            'invoice_no': self.invoice_no,
            'customer_id': self.customer_id,
            'firstname': self.firstname,
            'lastname': self.lastname,
            'email': self.email,
            'telephone': self.telephone,
            'total': self.total,
            'order_status_id': self.order_status_id,
            'order_status': self.order_status,
            'currency_code': self.currency_code,
            'products': [p.to_dict() for p in self.products],
            'totals': [t.to_dict() for t in self.totals],
            'payment_method': self.payment_method,
            'shipping_method': self.shipping_method
        }
