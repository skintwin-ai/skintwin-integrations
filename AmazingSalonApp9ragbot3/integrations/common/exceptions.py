"""
Custom Exceptions for SkinTwin Integrations
"""


class IntegrationError(Exception):
    """Base exception for all integration errors."""
    
    def __init__(self, message: str, platform: str = None, details: dict = None):
        self.message = message
        self.platform = platform
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self):
        if self.platform:
            return f"[{self.platform}] {self.message}"
        return self.message


class AuthenticationError(IntegrationError):
    """Raised when authentication with a platform fails."""
    pass


class RateLimitError(IntegrationError):
    """Raised when rate limits are exceeded."""
    
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ValidationError(IntegrationError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: str = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field


class SyncError(IntegrationError):
    """Raised when data synchronization fails."""
    
    def __init__(self, message: str, entity_type: str = None, entity_id: str = None, **kwargs):
        super().__init__(message, **kwargs)
        self.entity_type = entity_type
        self.entity_id = entity_id


class WebhookError(IntegrationError):
    """Raised when webhook processing fails."""
    
    def __init__(self, message: str, event_type: str = None, **kwargs):
        super().__init__(message, **kwargs)
        self.event_type = event_type


class ConfigurationError(IntegrationError):
    """Raised when integration configuration is invalid or missing."""
    pass
