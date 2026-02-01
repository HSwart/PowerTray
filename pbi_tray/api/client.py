"""
Base API client for Power BI REST API calls.
"""

import requests
from typing import Any

from ..auth import get_access_token_silent
from ..config import POWER_BI_API_BASE, FABRIC_API_BASE, state
from ..utils.logging import log


class PowerBIClient:
    """
    HTTP client for Power BI and Fabric REST APIs.
    
    Provides common functionality for making authenticated API requests.
    """
    
    DEFAULT_TIMEOUT = 30
    
    @staticmethod
    def _get_headers() -> dict | None:
        """Get authorization headers with current token."""
        token = get_access_token_silent()
        if not token:
            return None
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    @classmethod
    def get(cls, endpoint: str, base_url: str = POWER_BI_API_BASE, **kwargs) -> dict | None:
        """
        Make an authenticated GET request.
        
        Args:
            endpoint: API endpoint path (e.g., "/groups/{id}/datasets")
            base_url: Base URL (defaults to Power BI API)
            **kwargs: Additional arguments to pass to requests.get()
        
        Returns:
            JSON response dict or None on error
        """
        headers = cls._get_headers()
        if not headers:
            return None
        
        try:
            url = f"{base_url}{endpoint}"
            timeout = kwargs.pop("timeout", cls.DEFAULT_TIMEOUT)
            response = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            # Network error - expected when laptop sleeps
            return None
        except requests.exceptions.HTTPError as e:
            log(f"HTTP error {e.response.status_code}: {e.response.text[:500]}")
            return None
        except Exception as e:
            # Only log non-network errors
            if "NameResolutionError" not in str(e) and "getaddrinfo failed" not in str(e):
                log(f"API error: {e}")
            return None
    
    @classmethod
    def post(cls, endpoint: str, data: dict = None, base_url: str = POWER_BI_API_BASE, **kwargs) -> tuple[bool, str]:
        """
        Make an authenticated POST request.
        
        Args:
            endpoint: API endpoint path
            data: JSON body data
            base_url: Base URL
            **kwargs: Additional arguments
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        headers = cls._get_headers()
        if not headers:
            return False, "Not signed in"
        
        try:
            url = f"{base_url}{endpoint}"
            timeout = kwargs.pop("timeout", cls.DEFAULT_TIMEOUT)
            response = requests.post(url, headers=headers, json=data, timeout=timeout, **kwargs)
            
            if response.status_code in (200, 201, 202):
                return True, "Success"
            else:
                return False, f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            return False, f"Error: {e}"
    
    @classmethod
    def post_json(cls, endpoint: str, data: dict = None, base_url: str = POWER_BI_API_BASE, **kwargs) -> dict | None:
        """
        Make an authenticated POST request and return JSON response.
        
        Args:
            endpoint: API endpoint path
            data: JSON body data
            base_url: Base URL
            **kwargs: Additional arguments
        
        Returns:
            JSON response dict or None on error
        """
        headers = cls._get_headers()
        if not headers:
            return None
        
        try:
            url = f"{base_url}/{endpoint}"
            timeout = kwargs.pop("timeout", cls.DEFAULT_TIMEOUT)
            response = requests.post(url, headers=headers, json=data, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            log(f"HTTP error {e.response.status_code}: {e.response.text[:800]}")
            return None
        except Exception as e:
            log(f"API error: {e}")
            return None
    
    @classmethod
    def delete(cls, endpoint: str, base_url: str = POWER_BI_API_BASE, **kwargs) -> tuple[bool, str]:
        """
        Make an authenticated DELETE request.
        
        Args:
            endpoint: API endpoint path
            base_url: Base URL
            **kwargs: Additional arguments
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        headers = cls._get_headers()
        if not headers:
            return False, "Not signed in"
        
        try:
            url = f"{base_url}{endpoint}"
            timeout = kwargs.pop("timeout", cls.DEFAULT_TIMEOUT)
            response = requests.delete(url, headers=headers, timeout=timeout, **kwargs)
            
            if response.status_code in (200, 202, 204):
                return True, "Success"
            elif response.status_code == 404:
                return False, "Not found"
            else:
                return False, f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            return False, f"Error: {e}"
    
    @classmethod
    def get_pbi(cls, endpoint: str, **kwargs) -> dict | None:
        """Shortcut for Power BI API GET requests."""
        return cls.get(endpoint, base_url=POWER_BI_API_BASE, **kwargs)
    
    @classmethod
    def get_fabric(cls, endpoint: str, **kwargs) -> dict | None:
        """Shortcut for Fabric API GET requests."""
        return cls.get(endpoint, base_url=FABRIC_API_BASE, **kwargs)
