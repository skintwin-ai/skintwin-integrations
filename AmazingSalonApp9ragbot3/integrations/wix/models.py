"""
Wix-Specific Data Models
Models for Wix Bookings API data structures
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class WixLocation:
    """Wix location model."""
    id: str = ""
    name: str = ""
    formatted_address: str = ""
    location_type: str = "OWNER_BUSINESS"  # OWNER_BUSINESS, OWNER_CUSTOM, CUSTOM


@dataclass
class WixResource:
    """Wix resource (staff member) model."""
    id: str = ""
    name: str = ""
    schedule_id: str = ""


@dataclass
class WixSlot:
    """Wix time slot model."""
    service_id: str = ""
    schedule_id: str = ""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    timezone: str = "UTC"
    resource: Optional[WixResource] = None
    location: Optional[WixLocation] = None


@dataclass
class WixContactDetails:
    """Wix contact details model."""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    country_code: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        return {
            'firstName': self.first_name,
            'lastName': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'countryCode': self.country_code
        }


@dataclass
class WixBookedEntity:
    """Wix booked entity model."""
    slot: Optional[WixSlot] = None
    title: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class WixBooking:
    """
    Wix Booking model.
    Represents a booking in the Wix Bookings system.
    """
    id: str = ""
    revision: str = "1"
    
    # Booked entity
    booked_entity: Optional[WixBookedEntity] = None
    
    # Contact
    contact_details: Optional[WixContactDetails] = None
    
    # Participants
    total_participants: int = 1
    
    # Status
    status: str = "CREATED"  # CREATED, CONFIRMED, PENDING, CANCELED, DECLINED
    payment_status: str = "NOT_PAID"  # NOT_PAID, PAID, PARTIALLY_PAID, REFUNDED
    
    # Payment
    selected_payment_option: str = "OFFLINE"  # ONLINE, OFFLINE, MEMBERSHIP, PACKAGE
    
    # Additional fields
    additional_fields: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    created_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Creator
    created_by: Dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'WixBooking':
        """Create a WixBooking from API response data."""
        booked_entity_data = data.get('bookedEntity', {})
        slot_data = booked_entity_data.get('slot', {})
        contact_data = data.get('contactDetails', {})
        
        # Parse slot
        slot = WixSlot(
            service_id=slot_data.get('serviceId', ''),
            schedule_id=slot_data.get('scheduleId', ''),
            timezone=slot_data.get('timezone', 'UTC')
        )
        
        if slot_data.get('startDate'):
            slot.start_date = datetime.fromisoformat(
                slot_data['startDate'].replace('Z', '+00:00')
            )
        if slot_data.get('endDate'):
            slot.end_date = datetime.fromisoformat(
                slot_data['endDate'].replace('Z', '+00:00')
            )
        
        # Parse resource
        resource_data = slot_data.get('resource', {})
        if resource_data:
            slot.resource = WixResource(
                id=resource_data.get('id', ''),
                name=resource_data.get('name', ''),
                schedule_id=resource_data.get('scheduleId', '')
            )
        
        # Parse location
        location_data = slot_data.get('location', {})
        if location_data:
            slot.location = WixLocation(
                id=location_data.get('id', ''),
                name=location_data.get('name', ''),
                formatted_address=location_data.get('formattedAddress', ''),
                location_type=location_data.get('locationType', 'OWNER_BUSINESS')
            )
        
        # Parse booked entity
        booked_entity = WixBookedEntity(
            slot=slot,
            title=booked_entity_data.get('title', ''),
            tags=booked_entity_data.get('tags', [])
        )
        
        # Parse contact details
        contact = WixContactDetails(
            first_name=contact_data.get('firstName', ''),
            last_name=contact_data.get('lastName', ''),
            email=contact_data.get('email', ''),
            phone=contact_data.get('phone', ''),
            country_code=contact_data.get('countryCode', '')
        )
        
        # Parse timestamps
        created_date = None
        updated_date = None
        start_date = None
        end_date = None
        
        if data.get('createdDate'):
            created_date = datetime.fromisoformat(
                data['createdDate'].replace('Z', '+00:00')
            )
        if data.get('updatedDate'):
            updated_date = datetime.fromisoformat(
                data['updatedDate'].replace('Z', '+00:00')
            )
        if data.get('startDate'):
            start_date = datetime.fromisoformat(
                data['startDate'].replace('Z', '+00:00')
            )
        if data.get('endDate'):
            end_date = datetime.fromisoformat(
                data['endDate'].replace('Z', '+00:00')
            )
        
        return cls(
            id=data.get('id', ''),
            revision=data.get('revision', '1'),
            booked_entity=booked_entity,
            contact_details=contact,
            total_participants=data.get('totalParticipants', 1),
            status=data.get('status', 'CREATED'),
            payment_status=data.get('paymentStatus', 'NOT_PAID'),
            selected_payment_option=data.get('selectedPaymentOption', 'OFFLINE'),
            additional_fields=data.get('additionalFields', {}),
            created_date=created_date,
            updated_date=updated_date,
            start_date=start_date,
            end_date=end_date,
            created_by=data.get('createdBy', {})
        )
    
    def to_api_request(self) -> Dict[str, Any]:
        """Convert to API request format."""
        request = {
            'bookedEntity': {
                'slot': {
                    'serviceId': self.booked_entity.slot.service_id if self.booked_entity and self.booked_entity.slot else '',
                    'scheduleId': self.booked_entity.slot.schedule_id if self.booked_entity and self.booked_entity.slot else '',
                    'timezone': self.booked_entity.slot.timezone if self.booked_entity and self.booked_entity.slot else 'UTC'
                }
            },
            'contactDetails': self.contact_details.to_dict() if self.contact_details else {},
            'totalParticipants': self.total_participants,
            'selectedPaymentOption': self.selected_payment_option
        }
        
        if self.booked_entity and self.booked_entity.slot:
            slot = self.booked_entity.slot
            
            if slot.start_date:
                request['bookedEntity']['slot']['startDate'] = slot.start_date.isoformat()
            if slot.end_date:
                request['bookedEntity']['slot']['endDate'] = slot.end_date.isoformat()
            
            if slot.resource:
                request['bookedEntity']['slot']['resource'] = {
                    'id': slot.resource.id,
                    'name': slot.resource.name,
                    'scheduleId': slot.resource.schedule_id
                }
            
            if slot.location:
                request['bookedEntity']['slot']['location'] = {
                    'id': slot.location.id,
                    'name': slot.location.name,
                    'formattedAddress': slot.location.formatted_address,
                    'locationType': slot.location.location_type
                }
        
        if self.id:
            request['id'] = self.id
            request['revision'] = self.revision
        
        return request


@dataclass
class WixService:
    """Wix Service model."""
    id: str = ""
    name: str = ""
    description: str = ""
    tag_line: str = ""
    
    # Type
    service_type: str = "APPOINTMENT"  # APPOINTMENT, CLASS, COURSE
    
    # Schedule
    schedule_id: str = ""
    
    # Payment
    payment_type: str = "FIXED"  # FIXED, VARIED, NO_FEE
    price: float = 0.0
    currency: str = "USD"
    
    # Duration
    duration_minutes: int = 60
    
    # Category
    category_id: str = ""
    category_name: str = ""
    
    # Media
    main_media_url: str = ""
    
    # Status
    hidden: bool = False
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'WixService':
        """Create a WixService from API response data."""
        payment = data.get('payment', {})
        schedule = data.get('schedule', {})
        category = data.get('category', {})
        
        # Extract price
        price = 0.0
        if payment.get('rateType') == 'FIXED':
            fixed = payment.get('fixed', {})
            price = float(fixed.get('price', {}).get('value', 0))
        
        # Extract duration
        duration = 60
        constraints = schedule.get('availabilityConstraints', {})
        if constraints.get('slotDurations'):
            duration = constraints['slotDurations'][0]
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            tag_line=data.get('tagLine', ''),
            service_type=data.get('type', 'APPOINTMENT'),
            schedule_id=data.get('scheduleId', ''),
            payment_type=payment.get('rateType', 'FIXED'),
            price=price,
            currency=payment.get('fixed', {}).get('price', {}).get('currency', 'USD'),
            duration_minutes=duration,
            category_id=category.get('id', ''),
            category_name=category.get('name', ''),
            main_media_url=data.get('mainMedia', {}).get('image', {}).get('url', ''),
            hidden=data.get('hidden', False)
        )


@dataclass
class WixStaffMember:
    """Wix Staff Member model."""
    id: str = ""
    name: str = ""
    email: str = ""
    phone: str = ""
    
    # Schedule
    schedule_id: str = ""
    
    # Services
    service_ids: List[str] = field(default_factory=list)
    
    # Media
    image_url: str = ""
    
    # Description
    description: str = ""
    
    @classmethod
    def from_api_response(cls, data: Dict) -> 'WixStaffMember':
        """Create a WixStaffMember from API response data."""
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            schedule_id=data.get('scheduleId', ''),
            service_ids=data.get('serviceIds', []),
            image_url=data.get('mainMedia', {}).get('image', {}).get('url', ''),
            description=data.get('description', '')
        )
