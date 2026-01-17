"""
Wix Bookings Integration Module
Provides connectivity to Wix Appointment Bookings API
"""

from .connector import WixBookingsConnector
from .webhooks import WixWebhookHandler
from .models import WixBooking, WixService, WixStaffMember

__all__ = [
    'WixBookingsConnector',
    'WixWebhookHandler',
    'WixBooking',
    'WixService',
    'WixStaffMember'
]
