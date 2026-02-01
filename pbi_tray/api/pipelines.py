"""
Fabric Pipeline API operations.
"""

from datetime import datetime, timezone

from ..config import state, FABRIC_API_BASE
from ..utils.logging import log
from ..utils.datetime_helpers import calculate_next_run
from .client import PowerBIClient


def get_pipeline_runs(pipeline_id: str, top: int = 5) -> list | None:
    """
    Get recent runs for a specific pipeline.
    
    Args:
        pipeline_id: The pipeline GUID
        top: Maximum number of runs to return
    
    Returns:
        List of pipeline run records or None
    """
    endpoint = f"/workspaces/{state.workspace_id}/dataPipelines/{pipeline_id}/jobs?jobType=Pipeline"
    result = PowerBIClient.get_fabric(endpoint)
    
    if result:
        return result.get("value", [])[:top]
    return None


def get_all_pipeline_runs() -> list:
    """
    Get recent runs from all configured pipelines.
    
    Returns:
        List of pipeline runs sorted by start time (newest first)
    """
    all_runs = []
    
    for pipeline_id, pipeline_info in state.pipelines.items():
        runs = get_pipeline_runs(pipeline_id)
        if runs:
            for run in runs:
                run["_pipeline_id"] = pipeline_id
                run["_pipeline_name"] = pipeline_info["name"]
                run["_pipeline_type"] = pipeline_info["type"]
                all_runs.append(run)
    
    # Sort by start time descending
    all_runs.sort(key=lambda x: x.get("startTimeUtc", ""), reverse=True)
    return all_runs[:10]


def get_last_pipeline_run() -> dict | None:
    """Get the most recent pipeline run info."""
    runs = get_all_pipeline_runs()
    if runs:
        return runs[0]
    return None


def get_pipeline_schedules(pipeline_id: str) -> list | None:
    """
    Get schedules for a specific pipeline.
    
    Args:
        pipeline_id: The pipeline GUID
    
    Returns:
        List of schedule configs or None
    """
    endpoint = f"/workspaces/{state.workspace_id}/items/{pipeline_id}/jobs/Pipeline/schedules"
    result = PowerBIClient.get_fabric(endpoint)
    
    if result:
        return result.get("value", [])
    return None


def get_all_pipeline_schedules() -> list:
    """
    Get schedules for all configured pipelines with next run times.
    
    Returns:
        List of dicts with name, type, and next_run datetime
    """
    results = []
    
    for pipeline_id, pipeline_info in state.pipelines.items():
        schedules = get_pipeline_schedules(pipeline_id)
        next_run = None
        
        if schedules:
            # Find the next scheduled run from enabled schedules
            for schedule in schedules:
                if not schedule.get("enabled", False):
                    continue
                
                config = schedule.get("configuration", {})
                calculated_next = calculate_next_run(config)
                
                if calculated_next:
                    if next_run is None or calculated_next < next_run:
                        next_run = calculated_next
        
        results.append({
            "name": pipeline_info["name"],
            "type": pipeline_info["type"],
            "next_run": next_run
        })
    
    # Sort by next run time
    results.sort(key=lambda x: x["next_run"] if x["next_run"] else datetime.max.replace(tzinfo=timezone.utc))
    return results


def get_next_scheduled_refresh() -> list | None:
    """
    Get next scheduled run times for each pipeline.
    
    Returns:
        List of schedule info dicts or None if no pipelines configured
    """
    if not state.pipelines:
        return None
    
    schedules = get_all_pipeline_schedules()
    if not schedules:
        # Fallback to just showing pipeline names
        pipeline_names = [p["name"] for p in state.pipelines.values()]
        return [{"name": name, "next_run": None} for name in pipeline_names]
    
    return schedules


def get_pipeline_info_for_display() -> str | None:
    """
    Get formatted pipeline info for the UI.
    
    Returns:
        Formatted string with status icon and pipeline name, or None
    """
    runs = get_all_pipeline_runs()
    if not runs:
        return None
    
    last_run = runs[0]
    pipeline_name = last_run.get("_pipeline_name", "Unknown")
    status = last_run.get("status", "Unknown")
    
    # Format status
    status_map = {
        "Completed": "✓",
        "InProgress": "⟳",
        "Failed": "✗",
        "Cancelled": "○"
    }
    status_icon = status_map.get(status, "")
    
    return f"{status_icon} {pipeline_name}"
