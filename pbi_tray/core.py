"""
Core business logic for Power BI Tray application.

This module contains the main refresh status update logic and helper functions.
"""

import time
from datetime import datetime

from .config import state, POLLING_INTERVAL_SECONDS
from .auth import is_authenticated, get_access_token_silent
from .api import (
    get_refresh_history,
    get_semantic_model_name,
    get_workspace_name,
    get_gateway_status_summary,
    get_next_scheduled_refresh,
    CapacityMetrics,
)
from .utils import log, format_datetime, parse_datetime, show_notification


def update_refresh_status():
    """Fetch and update the refresh status from Power BI API."""
    log("Checking refresh status...")
    
    # Try to get token silently
    token = get_access_token_silent()
    
    if not token:
        state.last_refresh_status = "NotSignedIn"
        log("Not signed in - skipping refresh check")
        _update_tray_icon()
        return
    
    try:
        # Fetch model and workspace names if not cached
        if not state.semantic_model_name:
            state.semantic_model_name = get_semantic_model_name()
        if not state.workspace_name:
            state.workspace_name = get_workspace_name()
        
        # Fetch refresh history
        history = get_refresh_history()
        
        if history is None:
            log("Failed to fetch refresh history")
            return
        
        state.refresh_history = history
        
        if history:
            latest = history[0]
            new_status = latest.get("status", "Unknown")
            end_time = latest.get("endTime")
            
            # Check if this is a new refresh completion
            old_status = state.last_refresh_status
            old_end_time = state.last_refresh_info.get("endTime")
            
            state.last_refresh_status = new_status
            state.last_refresh_info = latest
            
            # Notify on status change (except first load)
            if old_status and old_status != new_status:
                if new_status == "Completed":
                    show_notification(
                        "✅ Refresh Completed",
                        f"Last refresh completed at {format_datetime(parse_datetime(end_time))}"
                    )
                elif new_status == "Failed":
                    error_msg = latest.get("serviceExceptionJson", "Unknown error")
                    show_notification(
                        "❌ Refresh Failed",
                        f"Error: {error_msg[:100]}...",
                        is_error=True
                    )
            
            log(f"Status: {new_status}, End: {end_time}")
        else:
            state.last_refresh_status = "Unknown"
            state.last_refresh_info = {}
            log("No refresh history found")
        
        # Update gateway status (cache in state for details window)
        state.gateway_summary = get_gateway_status_summary()
        
        # Update next scheduled refresh times (cache for details window)
        state.next_scheduled = get_next_scheduled_refresh()
        
        # Update capacity metrics (if workspace configured)
        if state.capacity_metrics_workspace:
            try:
                metrics = CapacityMetrics(state.capacity_metrics_workspace)
                util = metrics.get_utilization()
                if util:
                    raw_pct = util.get("[UtilizationPct]", util.get("UtilizationPct", 0)) or 0
                    pct = raw_pct * 100
                    bg_pct = (util.get("[BackgroundPct]", util.get("BackgroundPct", 0)) or 0) * 100
                    int_pct = (util.get("[InteractivePct]", util.get("InteractivePct", 0)) or 0) * 100
                    
                    state.capacity_metrics = {
                        "utilization": pct,
                        "background": bg_pct,
                        "interactive": int_pct,
                    }
                    log(f"Capacity: {pct:.1f}% (BG: {bg_pct:.1f}%, Int: {int_pct:.1f}%)")
                else:
                    state.capacity_metrics = None
            except Exception as e:
                log(f"Error updating capacity metrics: {e}")
                state.capacity_metrics = None
        
    except Exception as e:
        log(f"Error updating refresh status: {e}")
        import traceback
        traceback.print_exc()
    
    # Update tray icon
    _update_tray_icon()


def _update_tray_icon():
    """Update the system tray icon to reflect current status."""
    from .tray import update_icon, update_menu
    update_icon()
    update_menu()


def refresh_loop():
    """Background loop to periodically check refresh status."""
    log("Starting background refresh loop...")
    
    # Initial check
    update_refresh_status()
    
    while True:
        try:
            time.sleep(POLLING_INTERVAL_SECONDS)
            update_refresh_status()
        except Exception as e:
            log(f"Error in refresh loop: {e}")
            time.sleep(60)  # Wait longer on error


def get_status_display() -> str:
    """Get display string for current status."""
    status = state.last_refresh_status
    if status == "NotSignedIn":
        return "Sign In Required"
    return status


def get_status_emoji(status: str) -> str:
    """Get emoji for status."""
    status_lower = status.lower() if status else ""
    emojis = {
        "completed": "✅",
        "success": "✅",
        "failed": "❌",
        "error": "❌",
        "inprogress": "🔄",
        "unknown": "❓",
        "disabled": "⏸️",
        "cancelled": "⏹️",
        "notsignedin": "🔐",
    }
    return emojis.get(status_lower, "❓")


def get_model_display() -> str:
    """Get display string for model name."""
    name = state.semantic_model_name or "Power BI Dataset"
    if len(name) > 30:
        return name[:27] + "..."
    return name


def get_todays_refresh_count() -> int:
    """Count refreshes that completed today."""
    today = datetime.now().date()
    count = 0
    for refresh in state.refresh_history:
        end_time = parse_datetime(refresh.get("endTime"))
        if end_time and end_time.date() == today:
            count += 1
    return count


def get_last_refresh_time_display() -> str:
    """Get formatted last refresh time."""
    if state.last_refresh_status == "NotSignedIn":
        return "Sign in to view"
    end_time = state.last_refresh_info.get("endTime")
    if end_time:
        return format_datetime(parse_datetime(end_time))
    return "Not checked yet"


def get_last_error_message() -> str | None:
    """Get the last error message if status is Failed."""
    if state.last_refresh_status != "Failed":
        return None
    
    error = state.last_refresh_info.get("serviceExceptionJson")
    if error:
        # Truncate long errors
        if len(error) > 100:
            return error[:97] + "..."
        return error
    return "Unknown error"


def get_gateway_display() -> str | None:
    """Get gateway status display string."""
    summary = get_gateway_status_summary()
    if not summary:
        return None
    
    status = summary.get("status", "unknown")
    if status == "none":
        return None
    if status == "cloud":
        return "☁️ Cloud only"
    if status == "online":
        return f"🌐 {summary['online']}/{summary['total']} online"
    if status == "partial":
        return f"⚠️ {summary['online']}/{summary['total']} online"
    if status == "offline":
        return f"❌ All offline"
    return None


def get_capacity_display() -> str | None:
    """Get capacity metrics display string."""
    if not state.capacity_metrics:
        return None
    
    util = state.capacity_metrics.get("utilization", 0)
    bg = state.capacity_metrics.get("background", 0)
    int_pct = state.capacity_metrics.get("interactive", 0)
    
    # Color code based on utilization
    if util >= 80:
        icon = "🔴"  # High utilization
    elif util >= 60:
        icon = "🟡"  # Medium utilization
    else:
        icon = "🟢"  # Low utilization
    
    return f"{icon} {util:.1f}%"


def get_capacity_bg_display() -> str:
    """Get capacity background percentage."""
    if not state.capacity_metrics:
        return "--"
    return f"{state.capacity_metrics.get('background', 0):.1f}%"


def get_capacity_int_display() -> str:
    """Get capacity interactive percentage."""
    if not state.capacity_metrics:
        return "--"
    return f"{state.capacity_metrics.get('interactive', 0):.1f}%"
