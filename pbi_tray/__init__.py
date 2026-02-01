"""
Power BI Tray - System Tray Widget for Power BI Refresh Monitoring

A Windows system tray application that monitors Power BI semantic model
refresh status with visual notifications and detailed history.
"""

__version__ = "1.0.0"
__author__ = "Power BI Tray Team"
from .config import state, load_settings, save_settings
from .tray import setup_tray

__all__ = [
    "state",
    "load_settings",
    "save_settings",
    "setup_tray",
]