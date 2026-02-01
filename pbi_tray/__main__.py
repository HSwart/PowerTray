"""
Power BI Tray Application - Main Entry Point

Usage:
    python -m pbi_tray
"""

from .config import state, load_settings
from .utils import log
from .tray import setup_tray


def main():
    """Main entry point for the application."""
    # Set Windows AppUserModelID for proper taskbar icon (must be early)
    try:
        import ctypes
        myappid = 'powerbi.tray.monitor.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass  # Non-Windows or error
    
    log("=" * 60)
    log("Power BI Semantic Model Refresh Status - System Tray Widget")
    log("=" * 60)
    
    # Load settings first
    load_settings()
    
    log("Configuration (from settings.json):")
    log(f"  WORKSPACE_ID = '{state.workspace_id}'")
    log(f"  DATASET_ID   = '{state.dataset_id}'")
    log(f"  Pipelines    = {len(state.pipelines)} configured")
    for pid, pinfo in state.pipelines.items():
        log(f"    - {pinfo['name']} ({pinfo['type']})")
    
    if not state.workspace_id or not state.dataset_id:
        log("⚠️  Workspace ID or Dataset ID not configured!")
        log("   Open Settings from the tray icon to configure.")
    
    log("Starting system tray icon...")
    log("Right-click the icon in system tray for options.")
    
    setup_tray()


if __name__ == "__main__":
    main()
