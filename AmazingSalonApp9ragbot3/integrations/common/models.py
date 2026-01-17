"""
Unified Data Models for Cross-Platform Synchronization
These models provide a common interface for data exchange between platforms.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SyncStatus(Enum):
    """Status of synchronization for an entity."""
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class AppointmentStatus(Enum):
    """Unified appointment status across platforms."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class PaymentStatus(Enum):
    """Unified payment status across platforms."""
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    REFUNDED = "refunded"
    FAILED = "failed"


@dataclass
class PlatformReference:
    """Reference to an entity on an external platform."""
    platform: str  # 'wix', 'opencart', 'shopify'
    external_id: str
    last_synced: Optional[datetime] = None
    sync_status: SyncStatus = SyncStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UnifiedClient:
    """Unified client/customer model."""
    id: Optional[int] = None
    name: str = ""
    email: str = ""
    phone: str = ""
    
    # Additional contact details
    first_name: str = ""
    last_name: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    
    # Loyalty and preferences
    loyalty_points: int = 0
    total_spent: float = 0.0
    tier: str = "Bronze"
    
    # Skincare preferences
    skin_type: str = "normal"
    skin_concern: str = "hydration"
    sensitivity_level: str = "low"
    
    # B2B fields (for Shopify B2B)
    company_name: Optional[str] = None
    company_id: Optional[str] = None
    is_b2b: bool = False
    
    # Platform references
    platform_refs: List[PlatformReference] = field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def get_platform_ref(self, platform: str) -> Optional[PlatformReference]:
        """Get the reference for a specific platform."""
        for ref in self.platform_refs:
            if ref.platform == platform:
                return ref
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'address': {
                'line1': self.address_line1,
                'line2': self.address_line2,
                'city': self.city,
                'state': self.state,
                'postal_code': self.postal_code,
                'country': self.country
            },
            'loyalty_points': self.loyalty_points,
            'total_spent': self.total_spent,
            'tier': self.tier,
            'skin_type': self.skin_type,
            'skin_concern': self.skin_concern,
            'sensitivity_level': self.sensitivity_level,
            'company_name': self.company_name,
            'is_b2b': self.is_b2b
        }


@dataclass
class UnifiedService:
    """Unified service model."""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    price: float = 0.0
    duration: int = 60  # minutes
    category: str = ""
    
    # Platform references
    platform_refs: List[PlatformReference] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'duration': self.duration,
            'category': self.category
        }


@dataclass
class UnifiedAppointment:
    """Unified appointment/booking model."""
    id: Optional[int] = None
    
    # Client and service
    client_id: Optional[int] = None
    client: Optional[UnifiedClient] = None
    service_id: Optional[int] = None
    service: Optional[UnifiedService] = None
    staff_id: Optional[int] = None
    staff_name: str = ""
    
    # Scheduling
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    timezone: str = "UTC"
    
    # Location
    location_id: Optional[str] = None
    location_name: str = ""
    location_address: str = ""
    
    # Status
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    payment_status: PaymentStatus = PaymentStatus.PENDING
    
    # Notes and metadata
    notes: str = ""
    internal_notes: str = ""
    
    # Platform references
    platform_refs: List[PlatformReference] = field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def get_platform_ref(self, platform: str) -> Optional[PlatformReference]:
        """Get the reference for a specific platform."""
        for ref in self.platform_refs:
            if ref.platform == platform:
                return ref
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'client_id': self.client_id,
            'service_id': self.service_id,
            'staff_id': self.staff_id,
            'staff_name': self.staff_name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'timezone': self.timezone,
            'location_id': self.location_id,
            'location_name': self.location_name,
            'location_address': self.location_address,
            'status': self.status.value,
            'payment_status': self.payment_status.value,
            'notes': self.notes
        }


@dataclass
class UnifiedProduct:
    """Unified product model for inventory sync."""
    id: Optional[int] = None
    name: str = ""
    description: str = ""
    sku: str = ""
    price: float = 0.0
    compare_at_price: Optional[float] = None
    cost: Optional[float] = None
    
    # Inventory
    quantity: int = 0
    reorder_level: int = 10
    track_inventory: bool = True
    
    # Categorization
    category: str = ""
    tags: List[str] = field(default_factory=list)
    vendor: str = ""
    
    # Images
    images: List[str] = field(default_factory=list)
    
    # B2B pricing (for Shopify B2B)
    b2b_prices: Dict[str, float] = field(default_factory=dict)  # company_id -> price
    
    # Platform references
    platform_refs: List[PlatformReference] = field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def get_platform_ref(self, platform: str) -> Optional[PlatformReference]:
        """Get the reference for a specific platform."""
        for ref in self.platform_refs:
            if ref.platform == platform:
                return ref
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'sku': self.sku,
            'price': self.price,
            'compare_at_price': self.compare_at_price,
            'cost': self.cost,
            'quantity': self.quantity,
            'reorder_level': self.reorder_level,
            'category': self.category,
            'tags': self.tags,
            'vendor': self.vendor,
            'images': self.images
        }


@dataclass
class UnifiedOrderItem:
    """Unified order line item."""
    product_id: Optional[int] = None
    product: Optional[UnifiedProduct] = None
    service_id: Optional[int] = None
    service: Optional[UnifiedService] = None
    
    name: str = ""
    sku: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    total_price: float = 0.0
    discount: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'product_id': self.product_id,
            'service_id': self.service_id,
            'name': self.name,
            'sku': self.sku,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total_price': self.total_price,
            'discount': self.discount
        }


@dataclass
class UnifiedOrder:
    """Unified order model."""
    id: Optional[int] = None
    order_number: str = ""
    
    # Customer
    client_id: Optional[int] = None
    client: Optional[UnifiedClient] = None
    
    # B2B fields
    company_id: Optional[str] = None
    company_location_id: Optional[str] = None
    is_b2b: bool = False
    
    # Items
    items: List[UnifiedOrderItem] = field(default_factory=list)
    
    # Pricing
    subtotal: float = 0.0
    tax: float = 0.0
    shipping: float = 0.0
    discount: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    
    # Status
    status: str = "pending"
    payment_status: PaymentStatus = PaymentStatus.PENDING
    fulfillment_status: str = "unfulfilled"
    
    # Shipping
    shipping_address: Dict[str, str] = field(default_factory=dict)
    billing_address: Dict[str, str] = field(default_factory=dict)
    
    # Notes
    notes: str = ""
    
    # Platform references
    platform_refs: List[PlatformReference] = field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def get_platform_ref(self, platform: str) -> Optional[PlatformReference]:
        """Get the reference for a specific platform."""
        for ref in self.platform_refs:
            if ref.platform == platform:
                return ref
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'order_number': self.order_number,
            'client_id': self.client_id,
            'company_id': self.company_id,
            'is_b2b': self.is_b2b,
            'items': [item.to_dict() for item in self.items],
            'subtotal': self.subtotal,
            'tax': self.tax,
            'shipping': self.shipping,
            'discount': self.discount,
            'total': self.total,
            'currency': self.currency,
            'status': self.status,
            'payment_status': self.payment_status.value,
            'fulfillment_status': self.fulfillment_status,
            'shipping_address': self.shipping_address,
            'billing_address': self.billing_address,
            'notes': self.notes
        }
