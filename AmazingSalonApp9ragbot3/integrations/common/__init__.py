"""
SkinTwin Integration Common Module
Base classes and utilities for platform integrations
"""

from .base_connector import BaseConnector
from .exceptions import (
    IntegrationError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
    SyncError
)
from .models import (
    UnifiedAppointment,
    UnifiedClient,
    UnifiedProduct,
    UnifiedOrder,
    SyncStatus
)

__all__ = [
    'BaseConnector',
    'IntegrationError',
    'AuthenticationError',
    'RateLimitError',
    'ValidationError',
    'SyncError',
    'UnifiedAppointment',
    'UnifiedClient',
    'UnifiedProduct',
    'UnifiedOrder',
    'SyncStatus'
]
