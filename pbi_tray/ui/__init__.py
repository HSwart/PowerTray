"""
UI components for Power BI Tray application.
"""

from .theme import COLORS, STATUS_COLORS, get_status_color
from .details_window import DetailsWindow
from .settings_dialog import show_settings_dialog

__all__ = [
    "COLORS",
    "STATUS_COLORS",
    "get_status_color",
    "DetailsWindow",
    "show_settings_dialog",
]
