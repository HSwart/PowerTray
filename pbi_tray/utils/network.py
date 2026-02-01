"""
Network utility functions for Power BI Tray application.
"""

import socket
import time

from ..config import state
from .logging import log


def is_network_available() -> bool:
    """Check if network is available by attempting DNS resolution."""
    current_time = time.time()
    
    # Use cached result if checked recently
    if current_time - state._last_network_check < state._network_check_interval:
        return state._network_available
    
    state._last_network_check = current_time
    
    try:
        # Try to resolve a reliable host
        socket.setdefaulttimeout(3)
        socket.gethostbyname("login.microsoftonline.com")
        
        if not state._network_available:
            log("Network connectivity restored")
        state._network_available = True
        return True
    except socket.error:
        if state._network_available:
            log("Network unavailable - skipping API calls until connectivity restored")
        state._network_available = False
        return False
