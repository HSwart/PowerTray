"""
Logging utilities for Power BI Tray application.
"""

from datetime import datetime


def log(message: str) -> None:
    """Print a log message with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}")
