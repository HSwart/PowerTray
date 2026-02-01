"""
UI Theme and color definitions for Power BI Tray application.

Brand Colors:
- Dark Blue: #00334e
- Medium Blue: #2d6491
- Red: #D60029
- Dark Green: #184d47
- Medium Green: #009180
- Yellow: #fbc02d
"""

# Dark theme color palette
COLORS = {
    # Dark theme backgrounds
    "bg_dark": "#1a1a1a",
    "bg_card": "#252525",
    "bg_header": "#2d2d2d",
    
    # Brand accent colors for buttons/actions
    "accent_blue": "#2d6491",        # Medium Blue
    "accent_green": "#009180",       # Medium Green (success)
    "accent_red": "#D60029",         # Red (action/error)
    "accent_orange": "#fbc02d",      # Yellow (warning/attention)
    "accent_purple": "#00334e",      # Dark Blue
    
    # Text colors
    "text_primary": "#FFFFFF",
    "text_secondary": "#888888",
    "text_muted": "#666666",
    "border": "#3a3a3a",
}

# Status-specific colors
STATUS_COLORS = {
    "completed": "#009180",          # Medium Green
    "success": "#009180",            # Medium Green
    "failed": "#D60029",             # Red
    "error": "#D60029",              # Red
    "unknown": "#fbc02d",            # Yellow (warning)
    "inprogress": "#2d6491",         # Medium Blue
    "disabled": "#666666",           # Muted gray
    "cancelled": "#666666",          # Muted gray
    "notsignedin": "#fbc02d",        # Yellow (attention)
}


def get_status_color(status: str | None) -> str:
    """Get color for a given status string."""
    status_key = (status or "").lower().replace(" ", "").replace("-", "")
    return STATUS_COLORS.get(status_key, "#6B7280")
