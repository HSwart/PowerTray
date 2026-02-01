"""
Dataset and Workspace info API operations.
"""

from ..config import state
from ..utils.logging import log
from .client import PowerBIClient


def get_semantic_model_name() -> str | None:
    """
    Fetch and cache the semantic model name from Power BI API.
    
    Returns:
        The semantic model name or None on error
    """
    # Return cached name if available
    if state.semantic_model_name:
        return state.semantic_model_name
    
    endpoint = f"/groups/{state.workspace_id}/datasets/{state.dataset_id}"
    result = PowerBIClient.get_pbi(endpoint)
    
    if result:
        state.semantic_model_name = result.get("name", "Power BI Dataset")
        return state.semantic_model_name
    return None


def get_workspace_name() -> str | None:
    """
    Fetch and cache the workspace name from Power BI API.
    
    Returns:
        The workspace name or None on error
    """
    if state.workspace_name:
        return state.workspace_name
    
    endpoint = f"/groups/{state.workspace_id}"
    result = PowerBIClient.get_pbi(endpoint)
    
    if result:
        state.workspace_name = result.get("name", "Unknown Workspace")
        return state.workspace_name
    return None


def get_dataset_info() -> dict | None:
    """
    Fetch extended dataset info including configured by, size, etc.
    
    Returns:
        Dataset info dict or None on error
    """
    endpoint = f"/groups/{state.workspace_id}/datasets/{state.dataset_id}"
    return PowerBIClient.get_pbi(endpoint)
