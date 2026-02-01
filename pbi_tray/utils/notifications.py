"""
Windows toast notification utilities for Power BI Tray application.
"""

from pathlib import Path

from ..config import state, ICON_PATH


def show_notification(title: str, message: str, is_error: bool = False) -> None:
    """Show a Windows toast notification."""
    if not state.notifications_enabled:
        return
    
    try:
        from winotify import Notification, audio
        
        # Get icon path for notification
        icon_path = str(ICON_PATH) if ICON_PATH.exists() else ""
        
        toast = Notification(
            app_id="Power BI Refresh Monitor",
            title=title,
            msg=message,
            icon=icon_path
        )
        
        # Use different audio for success vs error
        if is_error:
            toast.set_audio(audio.Reminder, loop=False)
        else:
            toast.set_audio(audio.Default, loop=False)
        
        toast.show()
    except ImportError:
        print(f"Notification (winotify not installed): {title} - {message}")
    except Exception as e:
        print(f"Error showing notification: {e}")
