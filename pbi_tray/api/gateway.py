"""
Gateway monitoring API operations.
"""

import json
from datetime import datetime, timezone

from ..config import state
from ..utils.logging import log
from .client import PowerBIClient


# Cache for gateway info
_gateway_cache = {
    "data": None,
    "last_fetch": None,
    "cache_duration": 300  # 5 minutes
}


def get_gateways() -> list | None:
    """
    Fetch all gateways the user has access to, with fallback to dataset discovery.
    
    Returns:
        List of gateway dicts or None on error
    """
    global _gateway_cache
    
    # Check cache first
    now = datetime.now(timezone.utc)
    if _gateway_cache["data"] is not None and _gateway_cache["last_fetch"]:
        age = (now - _gateway_cache["last_fetch"]).total_seconds()
        if age < _gateway_cache["cache_duration"]:
            return _gateway_cache["data"]  # Cache hit, return silently
    
    gateways = []
    
    # First try standard gateways API
    result = PowerBIClient.get_pbi("/gateways")
    if result:
        gateways = result.get("value", [])
        log(f"Gateway API returned {len(gateways)} gateways")
    
    # If no gateways from standard API, try dataset-specific discovery
    if not gateways:
        log("No gateways from standard API, trying dataset gateway discovery...")
        discovered = _get_dataset_gateway_binding()
        if discovered:
            gateways = discovered
            log(f"Using {len(gateways)} gateways from dataset discovery")
    
    # Cache the result (even if empty - to avoid repeated API calls)
    _gateway_cache["data"] = gateways
    _gateway_cache["last_fetch"] = now
    
    return gateways


def _get_dataset_gateway_binding() -> list | None:
    """Get the gateways bound to the current dataset."""
    endpoint = f"/groups/{state.workspace_id}/datasets/{state.dataset_id}/Default.DiscoverGateways"
    log(f"Discovering dataset gateways...")
    
    result = PowerBIClient.get_pbi(endpoint)
    if result:
        gateways = result.get("value", [])
        log(f"Dataset gateway discovery returned {len(gateways)} gateways")
        if gateways:
            log(f"Gateway sample: {json.dumps(gateways[0])[:500]}")
        return gateways
    return None


def _get_dataset_datasources() -> list | None:
    """Get the datasources used by the current dataset."""
    endpoint = f"/groups/{state.workspace_id}/datasets/{state.dataset_id}/datasources"
    result = PowerBIClient.get_pbi(endpoint)
    
    if result:
        return result.get("value", [])
    return None


def get_gateway_status_summary() -> dict | None:
    """
    Get a summary of gateway status for display.
    
    Returns:
        Dict with status, message, online/offline counts, and details
    """
    gateways = get_gateways()
    
    if gateways is None:
        return None
    
    if not gateways:
        # No gateways found - check if this is a cloud-only dataset
        log("No gateways found, checking if cloud-only...")
        datasources = _get_dataset_datasources()
        if datasources:
            # Check if any datasources use gateways
            gateway_sources = [ds for ds in datasources if ds.get("gatewayId")]
            if not gateway_sources:
                log("Dataset has no gateway-connected datasources (cloud-only)")
                return {"status": "cloud", "message": "Cloud datasources only", "details": []}
        return {"status": "none", "message": "No gateways", "details": []}
    
    # Check status of each gateway
    online_count = 0
    offline_count = 0
    details = []
    
    for gw in gateways:
        gw_name = gw.get("name", "Unknown")
        gw_type = gw.get("type", "Unknown")
        
        # Gateway types: Personal, Resource, OnPremises, VirtualNetwork
        type_display = {
            "Personal": "Personal",
            "Resource": "Enterprise",
            "OnPremises": "On-Premises",
            "VirtualNetwork": "VNet"
        }.get(gw_type, gw_type)
        
        # Check cluster members for status
        cluster_info = gw.get("gatewayClusterInfo", {})
        members = cluster_info.get("members", [])
        
        if members:
            # Check member status
            member_online = 0
            member_total = len(members)
            for member in members:
                # Status: Live, Offline, Unknown
                if member.get("status", "").lower() == "live":
                    member_online += 1
            
            if member_online == member_total:
                status = "online"
                online_count += 1
            elif member_online > 0:
                status = "partial"
                online_count += 1  # Count as online if any member is up
            else:
                status = "offline"
                offline_count += 1
            
            status_text = f"{member_online}/{member_total} online"
        else:
            # Personal gateway or no cluster - check gateway status directly
            gw_status = gw.get("publicKey", {})  # If has publicKey, likely configured
            if gw_status:
                status = "online"
                online_count += 1
                status_text = "Available"
            else:
                status = "unknown"
                status_text = "Status unknown"
        
        details.append({
            "name": gw_name,
            "type": type_display,
            "status": status,
            "status_text": status_text,
            "members": members
        })
    
    # Determine overall status
    if offline_count > 0 and online_count == 0:
        overall_status = "offline"
        message = f"⚠ All gateways offline ({offline_count})"
    elif offline_count > 0:
        overall_status = "partial"
        message = f"⚠ {offline_count} offline, {online_count} online"
    else:
        overall_status = "online"
        message = f"✓ {online_count} gateway{'s' if online_count != 1 else ''} online"
    
    return {
        "status": overall_status,
        "message": message,
        "online": online_count,
        "offline": offline_count,
        "total": len(gateways),
        "details": details
    }


def get_gateway_display() -> str | None:
    """Get gateway status for menu display."""
    summary = get_gateway_status_summary()
    if not summary:
        return None
    if summary["status"] == "none":
        return None
    if summary["status"] == "cloud":
        return "☁️ Cloud only"
    return summary["message"]


def has_gateway_warning() -> bool:
    """Check if there's a gateway issue."""
    summary = get_gateway_status_summary()
    if not summary:
        return False
    return summary["status"] in ("offline", "partial")
