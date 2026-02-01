"""
Configuration management for Power BI Tray application.

Handles loading/saving settings, constants, and global state.
"""

import json
import threading
from pathlib import Path
from datetime import datetime, timezone


# =============================================================================
# FILE PATHS
# =============================================================================
APP_DIR = Path(__file__).parent.parent  # Points to PowerBI_Tray folder
SETTINGS_FILE = APP_DIR / "settings.json"
TOKEN_CACHE_FILE = APP_DIR / ".token_cache.json"
ASSETS_DIR = APP_DIR / "assets"  # Folder for icons and images
ICON_PATH = ASSETS_DIR / "PBI_mini.png"
ICO_PATH = ASSETS_DIR / "icon.ico"  # Windows .ico file for window/taskbar
ICONS_DIR = ASSETS_DIR  # UI icons are in assets folder


# =============================================================================
# API CONFIGURATION
# =============================================================================
POWER_BI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"

# Azure AD / MSAL configuration
CLIENT_ID = "1950a258-227b-4e31-a9cf-717495945fc2"  # Microsoft Azure PowerShell public client
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["https://analysis.windows.net/powerbi/api/.default"]


# =============================================================================
# TIMEZONES
# =============================================================================
TIMEZONES = {
    "UTC": 0,
    "GMT": 0,
    "EST (UTC-5)": -5,
    "EDT (UTC-4)": -4,
    "CST (UTC-6)": -6,
    "CDT (UTC-5)": -5,
    "MST (UTC-7)": -7,
    "MDT (UTC-6)": -6,
    "PST (UTC-8)": -8,
    "PDT (UTC-7)": -7,
    "SAST (UTC+2)": 2,
    "CET (UTC+1)": 1,
    "CEST (UTC+2)": 2,
    "IST (UTC+5:30)": 5.5,
    "JST (UTC+9)": 9,
    "AEST (UTC+10)": 10,
    "AEDT (UTC+11)": 11,
    "NZST (UTC+12)": 12,
}

# Windows timezone name mappings
WINDOWS_TZ_OFFSETS = {
    "Central Standard Time": -6,
    "Eastern Standard Time": -5,
    "Pacific Standard Time": -8,
    "South Africa Standard Time": 2,
    "GMT Standard Time": 0,
    "UTC": 0,
}


# =============================================================================
# DEFAULT CONFIGURATION
# =============================================================================
# These are placeholders - users must configure in settings.json
DEFAULT_WORKSPACE_ID = ""
DEFAULT_DATASET_ID = ""
DEFAULT_CAPACITY_METRICS_WORKSPACE = ""  # e.g., "Microsoft Fabric Capacity Metrics - YourCapacityName"
DEFAULT_PIPELINES = {}  # Configure pipelines in settings.json
DEFAULT_REFRESH_INTERVAL = 300  # 5 minutes
POLLING_INTERVAL_SECONDS = 300  # Alias for compatibility


# =============================================================================
# APPLICATION STATE (Global Singleton)
# =============================================================================
class AppState:
    """
    Centralized application state management.
    
    This class holds all mutable state that was previously scattered as
    global variables. It provides thread-safe access to shared state.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Configuration (loaded from settings.json)
        self.workspace_id: str = ""
        self.dataset_id: str = ""
        self.pipelines: dict = {}
        self.selected_timezone: str = "UTC"
        self.notifications_enabled: bool = True
        self.refresh_interval: int = DEFAULT_REFRESH_INTERVAL
        self.capacity_metrics_workspace: str = DEFAULT_CAPACITY_METRICS_WORKSPACE
        self.openai_api_key: str = ""  # OpenAI API key for AI insights
        self.ai_insights_enabled: bool = True  # Enable AI-powered failure analysis
        
        # Runtime state
        self.last_refresh_info: dict = {}
        self.refresh_history: list = []
        self.last_refresh_status: str = "Unknown"
        self.previous_refresh_status: str | None = None
        self.auth_error_message: str | None = None
        self.capacity_metrics: dict | None = None  # Current capacity metrics
        self.gateway_summary: dict | None = None  # Cached gateway status
        self.next_scheduled: list | None = None  # Cached next scheduled refresh times
        
        # Cached data
        self.semantic_model_name: str | None = None
        self.workspace_name: str | None = None
        
        # Network status
        self._network_available: bool = True
        self._last_network_check: float = 0
        self._network_check_interval: float = 30  # seconds
        
        # UI references
        self.icon = None  # pystray Icon instance
        
        self._initialized = True
    
    def reset(self):
        """Reset runtime state (useful for testing or re-initialization)."""
        self.last_refresh_info = {}
        self.refresh_history = []
        self.last_refresh_status = "Unknown"
        self.previous_refresh_status = None
        self.auth_error_message = None
        self.capacity_metrics = None
        self.gateway_summary = None
        self.next_scheduled = None
        self.semantic_model_name = None
        self.workspace_name = None


# Global state instance
state = AppState()


# =============================================================================
# SETTINGS MANAGEMENT
# =============================================================================
def load_settings() -> None:
    """Load settings from settings.json file."""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, "r") as f:
                settings = json.load(f)
                state.selected_timezone = settings.get("timezone", "UTC")
                state.notifications_enabled = settings.get("notifications_enabled", True)
                state.workspace_id = settings.get("workspace_id", DEFAULT_WORKSPACE_ID)
                state.dataset_id = settings.get("dataset_id", DEFAULT_DATASET_ID)
                state.capacity_metrics_workspace = settings.get("capacity_metrics_workspace", DEFAULT_CAPACITY_METRICS_WORKSPACE)
                state.pipelines = settings.get("pipelines", DEFAULT_PIPELINES)
                state.openai_api_key = settings.get("openai_api_key", "")
                state.ai_insights_enabled = settings.get("ai_insights_enabled", True)
        else:
            # First run - use defaults
            state.workspace_id = DEFAULT_WORKSPACE_ID
            state.dataset_id = DEFAULT_DATASET_ID
            state.pipelines = DEFAULT_PIPELINES.copy()
            save_settings()  # Create settings file with defaults
    except Exception as e:
        print(f"Error loading settings: {e}")
        # Fall back to defaults on error
        state.workspace_id = DEFAULT_WORKSPACE_ID
        state.dataset_id = DEFAULT_DATASET_ID
        state.pipelines = DEFAULT_PIPELINES.copy()


def save_settings() -> None:
    """Save current settings to settings.json file."""
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "workspace_id": state.workspace_id,
                "dataset_id": state.dataset_id,
                "capacity_metrics_workspace": state.capacity_metrics_workspace,
                "pipelines": state.pipelines,
                "timezone": state.selected_timezone,
                "notifications_enabled": state.notifications_enabled,
                "openai_api_key": state.openai_api_key,
                "ai_insights_enabled": state.ai_insights_enabled
            }, f, indent=2)
        print(f"Settings saved to {SETTINGS_FILE}")
    except Exception as e:
        print(f"Error saving settings: {e}")


def is_configured() -> bool:
    """Check if workspace and dataset are configured."""
    return bool(state.workspace_id) and bool(state.dataset_id)
