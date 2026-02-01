"""
System tray icon management for Power BI Tray application.
"""

import threading
import time
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from .config import state, load_settings, save_settings, TIMEZONES, APP_DIR
from .auth import is_authenticated, get_account_name, get_access_token_interactive
from .core import (
    update_refresh_status,
    get_status_display,
    get_status_emoji,
    get_model_display,
    get_todays_refresh_count,
    get_last_refresh_time_display,
    get_last_error_message,
    get_gateway_display,
    get_capacity_display,
    get_capacity_bg_display,
    get_capacity_int_display,
    refresh_loop,
)
from .api import trigger_refresh, cancel_refresh, get_next_scheduled_refresh
from .utils import log, format_datetime, format_duration, parse_datetime
from .utils.datetime_helpers import get_refresh_type_display


# Global icon reference
icon = None
_show_details_event = threading.Event()
_pending_show_details = False
_details_window_open = False  # Track if details window is currently open


def create_icon_image(status: str, capacity_data: dict = None) -> Image.Image:
    """Create a dynamic icon image based on refresh status and capacity metrics.
    
    The 3 bars represent:
    - Left bar: Background utilization % (blue)
    - Middle bar: Total utilization % (green/orange/red based on level)
    - Right bar: Interactive utilization % (orange)
    
    If no capacity data, falls back to static heights with status color.
    """
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Status colors for refresh status (used as fallback)
    status_colors = {
        "Completed": (0, 145, 128),      # Medium Green #009180
        "Success": (0, 145, 128),
        "Failed": (214, 0, 41),          # Red #D60029
        "Error": (214, 0, 41),
        "InProgress": (45, 100, 145),    # Medium Blue #2d6491
        "Unknown": (251, 192, 45),       # Yellow #fbc02d
        "Disabled": (100, 100, 100),
        "Cancelled": (100, 100, 100),
        "NotSignedIn": (251, 192, 45),   # Yellow
    }
    
    # Capacity-based colors
    COLOR_BG = (74, 144, 217)        # Blue for Background (#4a90d9)
    COLOR_INT = (45, 212, 191)       # Teal/Orange for Interactive (#2dd4bf)
    COLOR_GREEN = (0, 145, 128)      # Green - healthy (<80%)
    COLOR_ORANGE = (251, 146, 60)    # Orange - high (80-99%)
    COLOR_RED = (214, 0, 41)         # Red - critical (>=100%)
    
    margin = 4
    bar_width = (size - 2 * margin - 4) // 3
    corner_radius = 4
    min_height = 0.15  # Minimum bar height (15%) so bars are always visible
    
    if capacity_data and capacity_data.get("utilization") is not None:
        # Dynamic mode: bars represent capacity metrics
        bg_pct = capacity_data.get("background", 0)
        total_pct = capacity_data.get("utilization", 0)
        int_pct = capacity_data.get("interactive", 0)
        
        # Calculate heights (0-100% mapped to min_height-1.0)
        # Cap at 100% for display, but use actual value for color
        bg_height = max(min_height, min(bg_pct, 100) / 100)
        total_height = max(min_height, min(total_pct, 100) / 100)
        int_height = max(min_height, min(int_pct, 100) / 100)
        
        # Determine middle bar color based on total utilization
        if total_pct >= 100:
            total_color = COLOR_RED
        elif total_pct >= 80:
            total_color = COLOR_ORANGE
        else:
            total_color = COLOR_GREEN
        
        # Bar definitions: (height, color)
        bars = [
            (bg_height, COLOR_BG),       # Left: Background (blue)
            (total_height, total_color), # Middle: Total (status color)
            (int_height, COLOR_INT),     # Right: Interactive (teal)
        ]
    else:
        # Fallback mode: static heights with status color
        fallback_color = status_colors.get(status, (100, 100, 100))
        bars = [
            (0.5, fallback_color),
            (1.0, fallback_color),
            (0.7, fallback_color),
        ]
    
    # Draw the bars
    for i, (h, color) in enumerate(bars):
        x0 = margin + i * (bar_width + 2)
        y0 = int(size - margin - (size - 2 * margin) * h)
        x1 = x0 + bar_width
        y1 = size - margin
        
        draw.rounded_rectangle([x0, y0, x1, y1], radius=corner_radius, fill=color, corners=(True, True, False, False))
    
    return img


def update_icon():
    """Update the tray icon based on current status and capacity metrics."""
    global icon
    if icon:
        try:
            # Get capacity data from state if available
            capacity_data = state.capacity_metrics if hasattr(state, 'capacity_metrics') else None
            
            new_image = create_icon_image(state.last_refresh_status, capacity_data)
            icon.icon = new_image
            
            # Build informative multi-line tooltip
            tooltip_lines = [f"Power BI: {state.last_refresh_status}"]
            
            if capacity_data and capacity_data.get("utilization") is not None:
                util = capacity_data.get("utilization", 0)
                bg = capacity_data.get("background", 0)
                interactive = capacity_data.get("interactive", 0)
                
                tooltip_lines.append(f"Capacity: {util:.1f}%")
                tooltip_lines.append(f"  Background: {bg:.1f}%")
                tooltip_lines.append(f"  Interactive: {interactive:.1f}%")
            
            icon.title = "\n".join(tooltip_lines)
        except Exception as e:
            log(f"Error updating icon: {e}")


def update_menu():
    """Update the tray menu to reflect current status."""
    global icon
    if icon:
        try:
            icon.update_menu()
        except Exception as e:
            log(f"Error updating menu: {e}")


def on_show_details(icon_ref, item):
    """Show the details window - signal main thread."""
    global _pending_show_details
    _pending_show_details = True
    _show_details_event.set()
    log("Show Details clicked - signaling main thread...")


def set_timezone(tz_name: str):
    """Create a function to set timezone."""
    def handler(icon_ref, item):
        state.selected_timezone = tz_name
        save_settings()
        log(f"Timezone set to: {tz_name}")
        threading.Thread(target=update_refresh_status, daemon=True).start()
    return handler


def is_timezone_selected(tz_name: str):
    """Check if timezone is currently selected."""
    def check(item):
        return state.selected_timezone == tz_name
    return check


def on_exit(icon_ref, item):
    """Exit the application."""
    icon_ref.stop()


def on_sign_out(icon_ref, item):
    """Sign out and clear cached tokens."""
    from .auth import sign_out
    sign_out()
    log("Signed out. You will need to authenticate on next refresh.")


def on_sign_in(icon_ref, item):
    """Force interactive sign-in."""
    def do_sign_in():
        from .auth import sign_out
        sign_out()  # Clear existing tokens
        
        token = get_access_token_interactive()
        if token:
            log("Sign-in successful!")
            update_refresh_status()
        else:
            log("Sign-in was cancelled or failed.")
    
    threading.Thread(target=do_sign_in, daemon=True).start()


def on_refresh_now(icon_ref, item):
    """Trigger a refresh."""
    def do_refresh():
        success, message = trigger_refresh()
        if success:
            from .utils import show_notification
            show_notification("⟳ Refresh Started", "A new refresh has been triggered.")
            time.sleep(3)
            update_refresh_status()
        else:
            from .utils import show_notification
            show_notification("Refresh Failed", message, is_error=True)
    
    threading.Thread(target=do_refresh, daemon=True).start()


def on_cancel_refresh(icon_ref, item):
    """Cancel an in-progress refresh."""
    def do_cancel():
        success, message = cancel_refresh()
        if success:
            from .utils import show_notification
            show_notification("Refresh Cancelled", "The in-progress refresh was cancelled.")
            time.sleep(2)
            update_refresh_status()
        else:
            from .utils import show_notification
            show_notification("Cancel Failed", message, is_error=True)
    
    threading.Thread(target=do_cancel, daemon=True).start()


def on_check_status(icon_ref, item):
    """Manually check status."""
    threading.Thread(target=update_refresh_status, daemon=True).start()


def on_toggle_notifications(icon_ref, item):
    """Toggle notifications."""
    state.notifications_enabled = not state.notifications_enabled
    save_settings()
    log(f"Notifications {'enabled' if state.notifications_enabled else 'disabled'}")


def get_last_pipeline_display() -> str | None:
    """Get the pipeline that triggered the last refresh."""
    refresh_type = state.last_refresh_info.get("refreshType", "")
    if refresh_type == "DataFactory":
        # Try to match with configured pipelines
        for pid, pinfo in state.pipelines.items():
            return pinfo.get("name", "Pipeline")
    return None


def get_next_refresh_display() -> str | None:
    """Get the next scheduled refresh time."""
    schedules = get_next_scheduled_refresh()
    if schedules:
        sched = schedules[0]
        next_run = sched.get("next_run")
        if next_run:
            return format_datetime(next_run)
    return None


def create_menu() -> pystray.Menu:
    """Create the system tray menu with all options."""
    
    # Build timezone submenu
    tz_items = []
    for tz_name in TIMEZONES.keys():
        tz_items.append(
            pystray.MenuItem(
                tz_name,
                set_timezone(tz_name),
                checked=is_timezone_selected(tz_name),
                radio=True
            )
        )
    
    # Build history submenu
    def get_history_items():
        if state.last_refresh_status == "NotSignedIn":
            return [pystray.MenuItem("Sign in to view history", None, enabled=False)]
        if not state.refresh_history:
            return [pystray.MenuItem("No history available", None, enabled=False)]
        items = []
        for refresh in state.refresh_history:
            status = refresh.get("status", "Unknown")
            end_time = format_datetime(parse_datetime(refresh.get("endTime")))
            refresh_type = get_refresh_type_display(refresh.get("refreshType"))
            duration = format_duration(refresh.get("startTime"), refresh.get("endTime"))
            label = f"{get_status_emoji(status)} {end_time} | {refresh_type} | {duration}"
            items.append(pystray.MenuItem(label, None, enabled=False))
        return items
    
    # Check functions for conditional menu items
    def needs_sign_in(item):
        return state.last_refresh_status == "NotSignedIn"
    
    def is_signed_in_check(item):
        return state.last_refresh_status != "NotSignedIn"
    
    def is_refresh_in_progress(item):
        return state.last_refresh_status == "InProgress"
    
    def is_refresh_not_in_progress(item):
        return state.last_refresh_status != "InProgress" and state.last_refresh_status != "NotSignedIn"
    
    def notifications_checked(item):
        return state.notifications_enabled
    
    def has_error(item):
        return get_last_error_message() is not None
    
    def has_ai_analysis(item):
        """Check if AI analysis is available for the last failed refresh."""
        return (state.last_refresh_status == "Failed" and 
                state.last_refresh_info.get("ai_analysis") is not None)
    
    def get_ai_summary():
        """Get AI analysis summary for menu display."""
        if state.last_refresh_status != "Failed":
            return None
        analysis = state.last_refresh_info.get("ai_analysis", {})
        if not analysis:
            return None
        summary = analysis.get("summary", "")
        if len(summary) > 60:
            summary = summary[:57] + "..."
        return summary
    
    def get_ai_suggestion():
        """Get first AI suggestion for menu display."""
        if state.last_refresh_status != "Failed":
            return None
        analysis = state.last_refresh_info.get("ai_analysis", {})
        if not analysis:
            return None
        suggestions = analysis.get("suggestions", [])
        if suggestions:
            tip = suggestions[0]
            if len(tip) > 55:
                tip = tip[:52] + "..."
            return f"💡 {tip}"
        return None
    
    def get_ai_severity():
        """Get AI severity level."""
        if state.last_refresh_status != "Failed":
            return None
        analysis = state.last_refresh_info.get("ai_analysis", {})
        if not analysis:
            return None
        severity = analysis.get("severity", "medium")
        icons = {"low": "⚠️", "medium": "🔶", "high": "🔴", "critical": "🚨"}
        return icons.get(severity, "🔶")
    
    def has_next_refresh(item):
        return get_next_refresh_display() is not None
    
    def has_pipeline_info(item):
        return get_last_pipeline_display() is not None
    
    def is_signed_in(item):
        """Check if user is currently signed in."""
        return is_authenticated()
    
    def is_not_signed_in(item):
        """Check if user is not signed in."""
        return not is_authenticated()
    
    def get_capacity_items():
        """Generate capacity menu items dynamically."""
        log(f"get_capacity_items called, state.capacity_metrics = {state.capacity_metrics}")
        if not state.capacity_metrics:
            return [pystray.MenuItem("Loading...", None, enabled=False)]
        
        util = state.capacity_metrics.get("utilization", 0)
        bg = state.capacity_metrics.get("background", 0)
        int_pct = state.capacity_metrics.get("interactive", 0)
        
        if util >= 80:
            icon = "🔴"
        elif util >= 60:
            icon = "🟡"
        else:
            icon = "🟢"
        
        return [
            pystray.MenuItem(f"{icon} {util:.1f}% Total", None, enabled=False),
            pystray.MenuItem(f"  • Background: {bg:.1f}%", None, enabled=False),
            pystray.MenuItem(f"  • Interactive: {int_pct:.1f}%", None, enabled=False),
        ]
    
    menu = pystray.Menu(
        # Model name at top (compact header)
        pystray.MenuItem(
            lambda text: f"📊 {get_model_display()}",
            None,
            enabled=False
        ),
        pystray.Menu.SEPARATOR,
        
        # PRIMARY ACTION - Show Details (disabled when already open)
        pystray.MenuItem(
            "Show Details...",
            on_show_details,
            default=True,
            enabled=lambda item: not _details_window_open
        ),
        pystray.Menu.SEPARATOR,
        
        # Status with today's count
        pystray.MenuItem(
            lambda text: f"Status: {get_status_display()} ({get_todays_refresh_count()} today)",
            None,
            enabled=False
        ),
        
        # Error message (only if failed)
        pystray.MenuItem(
            lambda text: f"⚠ {get_last_error_message() or ''}",
            None,
            enabled=False,
            visible=has_error
        ),
        
        # AI Insights (only if failed and AI analysis available)
        pystray.MenuItem(
            lambda text: f"{get_ai_severity()} AI: {get_ai_summary()}",
            None,
            enabled=False,
            visible=has_ai_analysis
        ),
        pystray.MenuItem(
            lambda text: get_ai_suggestion() or "",
            None,
            enabled=False,
            visible=lambda item: has_ai_analysis(item) and get_ai_suggestion() is not None
        ),
        
        # Sign In button - shown prominently when not signed in
        pystray.MenuItem(
            "→ Click here to Sign In",
            on_sign_in,
            visible=lambda item: state.last_refresh_status == "NotSignedIn"
        ),
        
        # Last refresh time
        pystray.MenuItem(
            lambda text: f"Last: {get_last_refresh_time_display()} • {format_duration(state.last_refresh_info.get('startTime'), state.last_refresh_info.get('endTime'))}",
            None,
            enabled=False,
            visible=lambda item: state.last_refresh_status != "NotSignedIn"
        ),
        
        # Pipeline that triggered (compact)
        pystray.MenuItem(
            lambda text: f"Pipeline: {get_last_pipeline_display() or 'N/A'}",
            None,
            enabled=False,
            visible=has_pipeline_info
        ),
        
        # Next scheduled refresh
        pystray.MenuItem(
            lambda text: f"Next: {get_next_refresh_display() or 'Not scheduled'}",
            None,
            enabled=False,
            visible=has_next_refresh
        ),
        
        # Gateway status (warning icon if issues)
        pystray.MenuItem(
            lambda text: f"Gateway: {get_gateway_display() or 'Checking...'}",
            None,
            enabled=False,
            visible=lambda item: get_gateway_display() is not None
        ),
        pystray.Menu.SEPARATOR,
        
        # Capacity metrics - use helper functions like other status items
        pystray.MenuItem(
            lambda text: f"Capacity: {get_capacity_display()}" if get_capacity_display() else "Capacity: Loading...",
            None,
            enabled=False
        ),
        pystray.MenuItem(
            lambda text: f"  ├ Background: {get_capacity_bg_display()}",
            None,
            enabled=False
        ),
        pystray.MenuItem(
            lambda text: f"  └ Interactive: {get_capacity_int_display()}",
            None,
            enabled=False
        ),
        pystray.Menu.SEPARATOR,
        
        # Recent history submenu
        pystray.MenuItem(
            "Recent History",
            pystray.Menu(lambda: get_history_items())
        ),
        
        # Settings submenu
        pystray.MenuItem(
            "Settings",
            pystray.Menu(
                pystray.MenuItem(
                    lambda text: f"Timezone ({state.selected_timezone})",
                    pystray.Menu(*tz_items)
                ),
                pystray.MenuItem(
                    "Notifications",
                    on_toggle_notifications,
                    checked=notifications_checked
                ),
            )
        ),
        
        # Account submenu
        pystray.MenuItem(
            "Account",
            pystray.Menu(
                pystray.MenuItem(
                    lambda text: f"Signed in as: {get_account_name() or 'Not signed in'}",
                    None,
                    enabled=False
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sign In", on_sign_in, visible=is_not_signed_in),
                pystray.MenuItem("Sign Out", on_sign_out, visible=is_signed_in),
            )
        ),
        pystray.Menu.SEPARATOR,
        
        # Actions submenu - prevents accidental refresh triggers
        pystray.MenuItem(
            "Actions",
            pystray.Menu(
                pystray.MenuItem(
                    "Trigger Refresh",
                    on_refresh_now,
                    visible=is_refresh_not_in_progress
                ),
                pystray.MenuItem(
                    "Cancel Refresh",
                    on_cancel_refresh,
                    visible=is_refresh_in_progress
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Check Status", on_check_status),
            )
        ),
        pystray.Menu.SEPARATOR,
        
        # Exit at bottom
        pystray.MenuItem("Exit", on_exit)
    )
    
    return menu


def setup_tray():
    """Set up and run the system tray icon."""
    global icon, _pending_show_details
    
    # Load settings
    load_settings()
    
    # Create the full menu
    menu = create_menu()
    
    # Create initial icon
    initial_image = create_icon_image("Unknown")
    
    icon = pystray.Icon(
        "pbi_refresh",
        initial_image,
        "Power BI Refresh Status",
        menu
    )
    
    # Start background refresh thread
    refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
    refresh_thread.start()
    
    # Run icon in detached mode (separate thread) for faster window response
    log("Starting icon (detached mode)...")
    icon.run_detached()
    
    # Wait for icon to become visible
    while not icon.visible:
        time.sleep(0.1)
    log("Icon is visible and ready")
    
    # Track if we should keep running
    _running = True
    
    # Main loop - check for events on main thread with minimal delay
    try:
        while _running and icon.visible:
            # Check for show details event (non-blocking with short sleep)
            if _pending_show_details:
                _pending_show_details = False
                global _details_window_open
                _details_window_open = True
                log("Opening DetailsWindow...")
                try:
                    # Create fresh window each time
                    from .ui import DetailsWindow
                    details = DetailsWindow()
                    details.show()
                    log("DetailsWindow closed")
                except Exception as e:
                    log(f"Error showing details window: {e}")
                    import traceback
                    traceback.print_exc()
                finally:
                    _details_window_open = False
                    update_menu()  # Refresh menu to re-enable after window closes
            else:
                time.sleep(0.05)  # 50ms polling - responsive but light on CPU
    except KeyboardInterrupt:
        print("\nKeyboard interrupt - exiting...")
    finally:
        if icon.visible:
            icon.stop()
        log("Tray icon stopped")
