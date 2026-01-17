"""
Base Connector Abstract Class
Provides common functionality for all platform integrations
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    IntegrationError,
    AuthenticationError,
    RateLimitError
)

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """
    Abstract base class for platform connectors.
    Provides common HTTP client functionality, retry logic, and rate limiting.
    """
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        rate_limit_per_minute: int = 60
    ):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_per_minute = rate_limit_per_minute
        
        # Rate limiting state
        self._request_timestamps: List[float] = []
        
        # Initialize HTTP session with retry logic
        self.session = self._create_session()
        
        # Authentication state
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        
        logger.info(f"Initialized {self.__class__.__name__} connector for {base_url}")
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _check_rate_limit(self):
        """Check and enforce rate limiting."""
        current_time = time.time()
        window_start = current_time - 60  # 1 minute window
        
        # Remove timestamps outside the window
        self._request_timestamps = [
            ts for ts in self._request_timestamps if ts > window_start
        ]
        
        if len(self._request_timestamps) >= self.rate_limit_per_minute:
            # Calculate wait time
            oldest_in_window = min(self._request_timestamps)
            wait_time = 60 - (current_time - oldest_in_window)
            
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
        
        self._request_timestamps.append(current_time)
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the platform.
        Must be implemented by subclasses.
        
        Returns:
            bool: True if authentication was successful
        """
        pass
    
    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """
        Get the headers required for API requests.
        Must be implemented by subclasses.
        
        Returns:
            Dict[str, str]: Headers dictionary
        """
        pass
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the platform API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Dict: Response data
            
        Raises:
            IntegrationError: If the request fails
        """
        self._check_rate_limit()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = self.get_headers()
        
        if headers:
            request_headers.update(headers)
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                headers=request_headers,
                timeout=self.timeout
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited, retrying after {retry_after} seconds")
                time.sleep(retry_after)
                return self._make_request(method, endpoint, data, params, headers)
            
            # Handle authentication errors
            if response.status_code == 401:
                logger.warning("Authentication failed, attempting to re-authenticate")
                if self.authenticate():
                    return self._make_request(method, endpoint, data, params, headers)
                raise AuthenticationError("Failed to authenticate with platform")
            
            # Raise for other errors
            response.raise_for_status()
            
            # Return JSON response or empty dict
            try:
                return response.json()
            except ValueError:
                return {'status': 'success', 'raw': response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise IntegrationError(f"Request to {url} failed: {e}")
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request."""
        return self._make_request('GET', endpoint, params=params)
    
    def post(self, endpoint: str, data: Dict) -> Dict[str, Any]:
        """Make a POST request."""
        return self._make_request('POST', endpoint, data=data)
    
    def put(self, endpoint: str, data: Dict) -> Dict[str, Any]:
        """Make a PUT request."""
        return self._make_request('PUT', endpoint, data=data)
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make a DELETE request."""
        return self._make_request('DELETE', endpoint)
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test the connection to the platform.
        
        Returns:
            bool: True if connection is successful
        """
        pass
    
    @abstractmethod
    def sync_appointments(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Synchronize appointments from the platform.
        
        Args:
            since: Only sync appointments modified since this time
            
        Returns:
            List[Dict]: List of synchronized appointments
        """
        pass
    
    @abstractmethod
    def sync_clients(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Synchronize clients/customers from the platform.
        
        Args:
            since: Only sync clients modified since this time
            
        Returns:
            List[Dict]: List of synchronized clients
        """
        pass
    
    @abstractmethod
    def create_appointment(self, appointment_data: Dict) -> Dict:
        """
        Create an appointment on the platform.
        
        Args:
            appointment_data: Appointment details
            
        Returns:
            Dict: Created appointment data
        """
        pass
    
    @abstractmethod
    def update_appointment(self, appointment_id: str, appointment_data: Dict) -> Dict:
        """
        Update an appointment on the platform.
        
        Args:
            appointment_id: Platform appointment ID
            appointment_data: Updated appointment details
            
        Returns:
            Dict: Updated appointment data
        """
        pass
    
    @abstractmethod
    def cancel_appointment(self, appointment_id: str) -> bool:
        """
        Cancel an appointment on the platform.
        
        Args:
            appointment_id: Platform appointment ID
            
        Returns:
            bool: True if cancellation was successful
        """
        pass
