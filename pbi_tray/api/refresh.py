"""
Dataset/Semantic Model refresh API operations.
"""

from ..config import state
from ..utils.logging import log
from .client import PowerBIClient


def get_refresh_history(top: int = 10) -> list | None:
    """
    Fetch the refresh history from Power BI API.
    
    Args:
        top: Number of recent refreshes to fetch
    
    Returns:
        List of refresh records or None on error
    """
    endpoint = f"/groups/{state.workspace_id}/datasets/{state.dataset_id}/refreshes?$top={top}"
    result = PowerBIClient.get_pbi(endpoint)
    
    if result:
        return result.get("value", [])
    return None


def get_refresh_details(request_id: str) -> dict | None:
    """
    Fetch detailed refresh execution info including tables.
    
    Args:
        request_id: The refresh request ID
    
    Returns:
        Detailed refresh info dict or None
    """
    endpoint = f"/groups/{state.workspace_id}/datasets/{state.dataset_id}/refreshes/{request_id}"
    return PowerBIClient.get_pbi(endpoint)


def trigger_refresh() -> tuple[bool, str]:
    """
    Trigger a Power BI dataset refresh.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    endpoint = f"/groups/{state.workspace_id}/datasets/{state.dataset_id}/refreshes"
    data = {"notifyOption": "NoNotification"}
    return PowerBIClient.post(endpoint, data=data)


def cancel_refresh(request_id: str = None) -> tuple[bool, str]:
    """
    Cancel an in-progress dataset refresh.
    
    Args:
        request_id: Optional specific refresh to cancel.
                   If None, finds the in-progress refresh.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    # If no request_id provided, try to find the in-progress refresh
    if not request_id:
        refreshes = get_refresh_history()
        if refreshes:
            for refresh in refreshes:
                if refresh.get("status", "").lower() == "unknown":  # In progress
                    request_id = refresh.get("requestId")
                    break
    
    if not request_id:
        return False, "No refresh in progress to cancel"
    
    endpoint = f"/groups/{state.workspace_id}/datasets/{state.dataset_id}/refreshes/{request_id}"
    success, message = PowerBIClient.delete(endpoint)
    
    if success:
        return True, "Refresh cancelled successfully"
    elif "Not found" in message:
        return False, "Refresh not found or already completed"
    return False, message
