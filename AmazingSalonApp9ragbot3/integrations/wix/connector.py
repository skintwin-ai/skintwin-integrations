"""
Wix Bookings API Connector
Handles all interactions with the Wix Bookings REST API
"""

import logging
from datetime import datetime, timedelta
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
    UnifiedService,
    AppointmentStatus,
    PaymentStatus,
    PlatformReference,
    SyncStatus
)

logger = logging.getLogger(__name__)


class WixBookingsConnector(BaseConnector):
    """
    Connector for Wix Bookings API.
    
    Wix Bookings API Documentation:
    https://dev.wix.com/docs/api-reference/business-solutions/bookings/introduction
    """
    
    PLATFORM_NAME = "wix"
    BASE_URL = "https://www.wixapis.com"
    
    # API Endpoints
    ENDPOINTS = {
        'bookings': '/bookings/v2/bookings',
        'services': '/bookings/v2/services',
        'staff': '/bookings/v1/staff-members',
        'availability': '/bookings/v2/availability/slots',
        'calendar': '/calendar/v3/events',
        'contacts': '/contacts/v4/contacts'
    }
    
    def __init__(
        self,
        site_id: str,
        api_key: str,
        account_id: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the Wix Bookings connector.
        
        Args:
            site_id: Wix site ID
            api_key: Wix API key
            account_id: Optional Wix account ID
        """
        super().__init__(
            base_url=self.BASE_URL,
            api_key=api_key,
            rate_limit_per_minute=100,  # Wix rate limit
            **kwargs
        )
        
        self.site_id = site_id
        self.account_id = account_id
        
        logger.info(f"Initialized Wix Bookings connector for site: {site_id}")
    
    def authenticate(self) -> bool:
        """
        Authenticate with Wix API.
        Wix uses API key authentication in headers.
        
        Returns:
            bool: True if authentication is valid
        """
        try:
            # Test authentication by fetching services
            response = self.get(self.ENDPOINTS['services'])
            return 'services' in response or response.get('status') == 'success'
        except Exception as e:
            logger.error(f"Wix authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with Wix: {e}", platform=self.PLATFORM_NAME)
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for Wix API requests."""
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self.api_key,
            'wix-site-id': self.site_id
        }
        
        if self.account_id:
            headers['wix-account-id'] = self.account_id
        
        return headers
    
    def test_connection(self) -> bool:
        """Test the connection to Wix API."""
        try:
            return self.authenticate()
        except Exception as e:
            logger.error(f"Wix connection test failed: {e}")
            return False
    
    # ==================== Services ====================
    
    def get_services(self) -> List[Dict[str, Any]]:
        """
        Get all services from Wix Bookings.
        
        Returns:
            List[Dict]: List of services
        """
        try:
            response = self.get(self.ENDPOINTS['services'])
            return response.get('services', [])
        except Exception as e:
            logger.error(f"Failed to fetch Wix services: {e}")
            raise IntegrationError(f"Failed to fetch services: {e}", platform=self.PLATFORM_NAME)
    
    def get_service(self, service_id: str) -> Dict[str, Any]:
        """
        Get a specific service by ID.
        
        Args:
            service_id: Wix service ID
            
        Returns:
            Dict: Service data
        """
        try:
            response = self.get(f"{self.ENDPOINTS['services']}/{service_id}")
            return response.get('service', response)
        except Exception as e:
            logger.error(f"Failed to fetch Wix service {service_id}: {e}")
            raise IntegrationError(f"Failed to fetch service: {e}", platform=self.PLATFORM_NAME)
    
    def map_service_to_unified(self, wix_service: Dict) -> UnifiedService:
        """
        Map a Wix service to the unified service model.
        
        Args:
            wix_service: Wix service data
            
        Returns:
            UnifiedService: Unified service model
        """
        payment = wix_service.get('payment', {})
        schedule = wix_service.get('schedule', {})
        
        # Extract duration from schedule
        duration = 60  # default
        if schedule.get('availabilityConstraints'):
            duration = schedule['availabilityConstraints'].get('slotDurations', [60])[0]
        
        # Extract price
        price = 0.0
        if payment.get('rateType') == 'FIXED':
            fixed_price = payment.get('fixed', {})
            price = float(fixed_price.get('price', {}).get('value', 0))
        
        service = UnifiedService(
            name=wix_service.get('name', ''),
            description=wix_service.get('description', ''),
            price=price,
            duration=duration,
            category=wix_service.get('category', {}).get('name', '')
        )
        
        # Add platform reference
        service.platform_refs.append(PlatformReference(
            platform=self.PLATFORM_NAME,
            external_id=wix_service.get('id', ''),
            last_synced=datetime.utcnow(),
            sync_status=SyncStatus.SYNCED,
            metadata={'scheduleId': wix_service.get('scheduleId')}
        ))
        
        return service
    
    # ==================== Staff Members ====================
    
    def get_staff_members(self) -> List[Dict[str, Any]]:
        """
        Get all staff members from Wix Bookings.
        
        Returns:
            List[Dict]: List of staff members
        """
        try:
            response = self.get(self.ENDPOINTS['staff'])
            return response.get('staffMembers', [])
        except Exception as e:
            logger.error(f"Failed to fetch Wix staff members: {e}")
            raise IntegrationError(f"Failed to fetch staff members: {e}", platform=self.PLATFORM_NAME)
    
    # ==================== Availability ====================
    
    def get_availability(
        self,
        service_id: str,
        start_date: datetime,
        end_date: datetime,
        staff_id: Optional[str] = None,
        location_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get available time slots for a service.
        
        Args:
            service_id: Wix service ID
            start_date: Start of availability window
            end_date: End of availability window
            staff_id: Optional staff member filter
            location_id: Optional location filter
            
        Returns:
            List[Dict]: Available time slots
        """
        try:
            query = {
                'query': {
                    'filter': {
                        'serviceId': service_id,
                        'startDate': start_date.isoformat(),
                        'endDate': end_date.isoformat()
                    }
                }
            }
            
            if staff_id:
                query['query']['filter']['resourceId'] = staff_id
            
            if location_id:
                query['query']['filter']['locationId'] = location_id
            
            response = self.post(self.ENDPOINTS['availability'], query)
            return response.get('availabilityEntries', [])
        except Exception as e:
            logger.error(f"Failed to fetch Wix availability: {e}")
            raise IntegrationError(f"Failed to fetch availability: {e}", platform=self.PLATFORM_NAME)
    
    # ==================== Bookings ====================
    
    def sync_appointments(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Synchronize bookings from Wix.
        
        Args:
            since: Only sync bookings modified since this time
            
        Returns:
            List[Dict]: List of synchronized bookings
        """
        try:
            query = {'query': {}}
            
            if since:
                query['query']['filter'] = {
                    'updatedDate': {'$gte': since.isoformat()}
                }
            
            response = self.post(f"{self.ENDPOINTS['bookings']}/query", query)
            bookings = response.get('bookings', [])
            
            logger.info(f"Synced {len(bookings)} bookings from Wix")
            return bookings
        except Exception as e:
            logger.error(f"Failed to sync Wix bookings: {e}")
            raise IntegrationError(f"Failed to sync bookings: {e}", platform=self.PLATFORM_NAME)
    
    def sync_clients(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Synchronize contacts from Wix.
        
        Args:
            since: Only sync contacts modified since this time
            
        Returns:
            List[Dict]: List of synchronized contacts
        """
        try:
            query = {'query': {}}
            
            if since:
                query['query']['filter'] = {
                    'lastActivity.activityDate': {'$gte': since.isoformat()}
                }
            
            response = self.post(f"{self.ENDPOINTS['contacts']}/query", query)
            contacts = response.get('contacts', [])
            
            logger.info(f"Synced {len(contacts)} contacts from Wix")
            return contacts
        except Exception as e:
            logger.error(f"Failed to sync Wix contacts: {e}")
            raise IntegrationError(f"Failed to sync contacts: {e}", platform=self.PLATFORM_NAME)
    
    def get_booking(self, booking_id: str) -> Dict[str, Any]:
        """
        Get a specific booking by ID.
        
        Args:
            booking_id: Wix booking ID
            
        Returns:
            Dict: Booking data
        """
        try:
            response = self.get(f"{self.ENDPOINTS['bookings']}/{booking_id}")
            return response.get('booking', response)
        except Exception as e:
            logger.error(f"Failed to fetch Wix booking {booking_id}: {e}")
            raise IntegrationError(f"Failed to fetch booking: {e}", platform=self.PLATFORM_NAME)
    
    def create_appointment(self, appointment_data: Dict) -> Dict:
        """
        Create a booking on Wix.
        
        Args:
            appointment_data: Appointment details in unified format
            
        Returns:
            Dict: Created booking data
        """
        try:
            # Map unified appointment to Wix booking format
            wix_booking = self._map_to_wix_booking(appointment_data)
            
            response = self.post(self.ENDPOINTS['bookings'], {
                'booking': wix_booking,
                'flowControlSettings': {
                    'skipAvailabilityValidation': False,
                    'skipBusinessConfirmation': False
                },
                'participantNotification': {
                    'notifyParticipants': True
                }
            })
            
            created_booking = response.get('booking', response)
            logger.info(f"Created Wix booking: {created_booking.get('id')}")
            
            return created_booking
        except Exception as e:
            logger.error(f"Failed to create Wix booking: {e}")
            raise IntegrationError(f"Failed to create booking: {e}", platform=self.PLATFORM_NAME)
    
    def update_appointment(self, appointment_id: str, appointment_data: Dict) -> Dict:
        """
        Update a booking on Wix.
        
        Args:
            appointment_id: Wix booking ID
            appointment_data: Updated appointment details
            
        Returns:
            Dict: Updated booking data
        """
        try:
            # Get current booking for revision
            current = self.get_booking(appointment_id)
            revision = current.get('revision', '1')
            
            # Map unified appointment to Wix booking format
            wix_booking = self._map_to_wix_booking(appointment_data)
            wix_booking['id'] = appointment_id
            wix_booking['revision'] = revision
            
            response = self.put(f"{self.ENDPOINTS['bookings']}/{appointment_id}", {
                'booking': wix_booking
            })
            
            updated_booking = response.get('booking', response)
            logger.info(f"Updated Wix booking: {appointment_id}")
            
            return updated_booking
        except Exception as e:
            logger.error(f"Failed to update Wix booking {appointment_id}: {e}")
            raise IntegrationError(f"Failed to update booking: {e}", platform=self.PLATFORM_NAME)
    
    def cancel_appointment(self, appointment_id: str) -> bool:
        """
        Cancel a booking on Wix.
        
        Args:
            appointment_id: Wix booking ID
            
        Returns:
            bool: True if cancellation was successful
        """
        try:
            response = self.post(f"{self.ENDPOINTS['bookings']}/{appointment_id}/cancel", {
                'participantNotification': {
                    'notifyParticipants': True
                }
            })
            
            logger.info(f"Cancelled Wix booking: {appointment_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel Wix booking {appointment_id}: {e}")
            raise IntegrationError(f"Failed to cancel booking: {e}", platform=self.PLATFORM_NAME)
    
    def confirm_appointment(self, appointment_id: str) -> Dict:
        """
        Confirm a booking on Wix.
        
        Args:
            appointment_id: Wix booking ID
            
        Returns:
            Dict: Confirmed booking data
        """
        try:
            response = self.post(f"{self.ENDPOINTS['bookings']}/{appointment_id}/confirm", {
                'participantNotification': {
                    'notifyParticipants': True
                }
            })
            
            logger.info(f"Confirmed Wix booking: {appointment_id}")
            return response.get('booking', response)
        except Exception as e:
            logger.error(f"Failed to confirm Wix booking {appointment_id}: {e}")
            raise IntegrationError(f"Failed to confirm booking: {e}", platform=self.PLATFORM_NAME)
    
    def _map_to_wix_booking(self, appointment_data: Dict) -> Dict:
        """
        Map unified appointment data to Wix booking format.
        
        Args:
            appointment_data: Unified appointment data
            
        Returns:
            Dict: Wix booking format
        """
        wix_booking = {
            'bookedEntity': {
                'slot': {
                    'serviceId': appointment_data.get('service_id'),
                    'startDate': appointment_data.get('start_time'),
                    'endDate': appointment_data.get('end_time'),
                    'timezone': appointment_data.get('timezone', 'UTC')
                }
            },
            'contactDetails': {
                'firstName': appointment_data.get('client_first_name', ''),
                'lastName': appointment_data.get('client_last_name', ''),
                'email': appointment_data.get('client_email', ''),
                'phone': appointment_data.get('client_phone', '')
            },
            'totalParticipants': 1
        }
        
        # Add staff member if specified
        if appointment_data.get('staff_id'):
            wix_booking['bookedEntity']['slot']['resource'] = {
                'id': appointment_data['staff_id']
            }
        
        # Add location if specified
        if appointment_data.get('location_id'):
            wix_booking['bookedEntity']['slot']['location'] = {
                'id': appointment_data['location_id']
            }
        
        # Add schedule ID if available
        if appointment_data.get('schedule_id'):
            wix_booking['bookedEntity']['slot']['scheduleId'] = appointment_data['schedule_id']
        
        return wix_booking
    
    def map_booking_to_unified(self, wix_booking: Dict) -> UnifiedAppointment:
        """
        Map a Wix booking to the unified appointment model.
        
        Args:
            wix_booking: Wix booking data
            
        Returns:
            UnifiedAppointment: Unified appointment model
        """
        booked_entity = wix_booking.get('bookedEntity', {})
        slot = booked_entity.get('slot', {})
        contact = wix_booking.get('contactDetails', {})
        
        # Map status
        status_map = {
            'CREATED': AppointmentStatus.SCHEDULED,
            'CONFIRMED': AppointmentStatus.CONFIRMED,
            'PENDING': AppointmentStatus.SCHEDULED,
            'CANCELED': AppointmentStatus.CANCELLED,
            'DECLINED': AppointmentStatus.CANCELLED
        }
        
        payment_status_map = {
            'NOT_PAID': PaymentStatus.PENDING,
            'PAID': PaymentStatus.PAID,
            'PARTIALLY_PAID': PaymentStatus.PARTIALLY_PAID,
            'REFUNDED': PaymentStatus.REFUNDED
        }
        
        # Create client
        client = UnifiedClient(
            first_name=contact.get('firstName', ''),
            last_name=contact.get('lastName', ''),
            email=contact.get('email', ''),
            phone=contact.get('phone', '')
        )
        client.name = f"{client.first_name} {client.last_name}".strip()
        
        # Parse dates
        start_time = None
        end_time = None
        if slot.get('startDate'):
            start_time = datetime.fromisoformat(slot['startDate'].replace('Z', '+00:00'))
        if slot.get('endDate'):
            end_time = datetime.fromisoformat(slot['endDate'].replace('Z', '+00:00'))
        
        # Create appointment
        appointment = UnifiedAppointment(
            client=client,
            start_time=start_time,
            end_time=end_time,
            timezone=slot.get('timezone', 'UTC'),
            status=status_map.get(wix_booking.get('status'), AppointmentStatus.SCHEDULED),
            payment_status=payment_status_map.get(
                wix_booking.get('paymentStatus'),
                PaymentStatus.PENDING
            ),
            notes=wix_booking.get('additionalFields', {}).get('notes', ''),
            created_at=datetime.fromisoformat(
                wix_booking.get('createdDate', datetime.utcnow().isoformat()).replace('Z', '+00:00')
            ),
            updated_at=datetime.fromisoformat(
                wix_booking.get('updatedDate', datetime.utcnow().isoformat()).replace('Z', '+00:00')
            )
        )
        
        # Add location
        location = slot.get('location', {})
        appointment.location_id = location.get('id')
        appointment.location_name = location.get('name', '')
        appointment.location_address = location.get('formattedAddress', '')
        
        # Add staff
        resource = slot.get('resource', {})
        appointment.staff_name = resource.get('name', '')
        
        # Add platform reference
        appointment.platform_refs.append(PlatformReference(
            platform=self.PLATFORM_NAME,
            external_id=wix_booking.get('id', ''),
            last_synced=datetime.utcnow(),
            sync_status=SyncStatus.SYNCED,
            metadata={
                'serviceId': slot.get('serviceId'),
                'scheduleId': slot.get('scheduleId'),
                'revision': wix_booking.get('revision')
            }
        ))
        
        return appointment
