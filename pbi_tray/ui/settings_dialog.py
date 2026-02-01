"""
Settings Dialog for Power BI Tray application.
"""

import threading
import customtkinter as ctk
from PIL import Image, ImageTk

from ..config import state, TIMEZONES, save_settings, ICO_PATH, ICONS_DIR
from ..auth import is_authenticated, get_account_name, get_access_token_interactive, sign_out
from .theme import COLORS


def show_settings_dialog(parent_window, on_close_callback=None):
    """Show the settings dialog."""
    settings_window = ctk.CTkToplevel(parent_window)
    settings_window.title("Settings")
    settings_window.geometry("500x600")
    settings_window.resizable(False, True)
    settings_window.configure(fg_color=COLORS["bg_dark"])
    settings_window.transient(parent_window)
    settings_window.grab_set()
    settings_window.focus_force()
    settings_window.attributes("-topmost", True)
    
    # Set window icon
    if ICO_PATH.exists():
        try:
            settings_window.iconbitmap(str(ICO_PATH))
        except Exception as e:
            print(f"Settings icon error: {e}")
    
    # Title with icon
    title_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
    title_frame.pack(padx=20, pady=(20, 15), anchor="w", fill="x")
    
    # Load settings icon
    settings_icon_path = ICONS_DIR / "settings.png"
    if settings_icon_path.exists():
        try:
            settings_img = Image.open(settings_icon_path).resize((24, 24), Image.Resampling.LANCZOS)
            settings_icon = ctk.CTkImage(light_image=settings_img, dark_image=settings_img, size=(24, 24))
            ctk.CTkLabel(
                title_frame,
                image=settings_icon,
                text=""
            ).pack(side="left", padx=(0, 10))
            # Keep reference to prevent garbage collection
            settings_window._settings_icon = settings_icon
        except Exception as e:
            print(f"Error loading settings icon: {e}")
    
    ctk.CTkLabel(
        title_frame,
        text="Settings",
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=COLORS["text_primary"]
    ).pack(side="left")
    
    # Scrollable content
    scroll_frame = ctk.CTkScrollableFrame(settings_window, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True, padx=5, pady=(0, 10))
    
    # === CONNECTION SETTINGS ===
    ctk.CTkLabel(
        scroll_frame,
        text="Connection",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=COLORS["accent_blue"]
    ).pack(padx=15, pady=(5, 5), anchor="w")
    
    conn_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
    conn_frame.pack(fill="x", padx=15, pady=(0, 10))
    
    # Workspace ID
    ctk.CTkLabel(
        conn_frame,
        text="Workspace ID",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"]
    ).pack(padx=12, pady=(10, 2), anchor="w")
    workspace_var = ctk.StringVar(value=state.workspace_id)
    ctk.CTkEntry(
        conn_frame,
        textvariable=workspace_var,
        width=420,
        height=32,
        placeholder_text="Enter Workspace GUID"
    ).pack(padx=12, pady=(0, 5))
    
    # Dataset ID
    ctk.CTkLabel(
        conn_frame,
        text="Dataset ID",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"]
    ).pack(padx=12, pady=(5, 2), anchor="w")
    dataset_var = ctk.StringVar(value=state.dataset_id)
    ctk.CTkEntry(
        conn_frame,
        textvariable=dataset_var,
        width=420,
        height=32,
        placeholder_text="Enter Dataset GUID"
    ).pack(padx=12, pady=(0, 10))
    
    # === CAPACITY METRICS ===
    ctk.CTkLabel(
        scroll_frame,
        text="Capacity Metrics (Optional)",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=COLORS["accent_blue"]
    ).pack(padx=15, pady=(10, 5), anchor="w")
    
    ctk.CTkLabel(
        scroll_frame,
        text="Workspace ID for Fabric capacity metrics dataset",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"]
    ).pack(padx=15, pady=(0, 5), anchor="w")
    
    metrics_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
    metrics_frame.pack(fill="x", padx=15, pady=(0, 10))
    
    # Capacity Metrics Workspace ID
    ctk.CTkLabel(
        metrics_frame,
        text="Workspace ID",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"]
    ).pack(padx=12, pady=(10, 2), anchor="w")
    capacity_workspace_var = ctk.StringVar(value=state.capacity_metrics_workspace)
    ctk.CTkEntry(
        metrics_frame,
        textvariable=capacity_workspace_var,
        width=420,
        height=32,
        placeholder_text="Enter Capacity Metrics Workspace GUID"
    ).pack(padx=12, pady=(0, 10))
    
    # === PIPELINE SETTINGS ===
    ctk.CTkLabel(
        scroll_frame,
        text="Pipelines (Optional)",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=COLORS["accent_blue"]
    ).pack(padx=15, pady=(10, 5), anchor="w")
    
    ctk.CTkLabel(
        scroll_frame,
        text="Configure Fabric pipelines that trigger refreshes",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"]
    ).pack(padx=15, pady=(0, 5), anchor="w")
    
    pipeline_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
    pipeline_frame.pack(fill="x", padx=15, pady=(0, 10))
    
    # Pipeline column headers
    header_frame = ctk.CTkFrame(pipeline_frame, fg_color="transparent")
    header_frame.pack(fill="x", padx=10, pady=(10, 0))
    
    ctk.CTkLabel(
        header_frame,
        text="Pipeline ID",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"],
        width=200
    ).pack(side="left", padx=(0, 5))
    
    ctk.CTkLabel(
        header_frame,
        text="Name",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"],
        width=100
    ).pack(side="left", padx=(0, 5))
    
    ctk.CTkLabel(
        header_frame,
        text="Type",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"],
        width=70
    ).pack(side="left", padx=(0, 5))
    
    # Store pipeline entries
    pipeline_entries = []
    
    def add_pipeline_row(pipeline_id="", name="", description="", ptype="partial"):
        row_frame = ctk.CTkFrame(pipeline_frame, fg_color="transparent")
        row_frame.pack(fill="x", padx=10, pady=5)
        
        # Pipeline ID
        id_var = ctk.StringVar(value=pipeline_id)
        ctk.CTkEntry(
            row_frame,
            textvariable=id_var,
            width=200,
            height=28,
            placeholder_text="Pipeline GUID"
        ).pack(side="left", padx=(0, 5))
        
        # Name
        name_var = ctk.StringVar(value=name)
        ctk.CTkEntry(
            row_frame,
            textvariable=name_var,
            width=100,
            height=28,
            placeholder_text="Name"
        ).pack(side="left", padx=(0, 5))
        
        # Type
        type_var = ctk.StringVar(value=ptype)
        ctk.CTkComboBox(
            row_frame,
            values=["full", "partial"],
            variable=type_var,
            width=70,
            height=28
        ).pack(side="left", padx=(0, 5))
        
        # Remove button
        def remove_row():
            entry = (id_var, name_var, type_var, row_frame)
            if entry in pipeline_entries:
                pipeline_entries.remove(entry)
            row_frame.destroy()
        
        ctk.CTkButton(
            row_frame,
            text="✕",
            width=28,
            height=28,
            fg_color="#4a4a4a",
            hover_color=COLORS["accent_red"],
            command=remove_row
        ).pack(side="left")
        
        pipeline_entries.append((id_var, name_var, type_var, row_frame))
    
    # Add existing pipelines
    for pid, pinfo in state.pipelines.items():
        add_pipeline_row(
            pid,
            pinfo.get("name", ""),
            pinfo.get("description", ""),
            pinfo.get("type", "partial")
        )
    
    # Add new pipeline button
    add_btn_frame = ctk.CTkFrame(pipeline_frame, fg_color="transparent")
    add_btn_frame.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkButton(
        add_btn_frame,
        text="+ Add Pipeline",
        width=120,
        height=28,
        fg_color="#4a4a4a",
        hover_color="#5a5a5a",
        command=lambda: add_pipeline_row()
    ).pack(side="left")
    
    # === DISPLAY SETTINGS ===
    ctk.CTkLabel(
        scroll_frame,
        text="Display",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=COLORS["accent_blue"]
    ).pack(padx=15, pady=(10, 5), anchor="w")
    
    display_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
    display_frame.pack(fill="x", padx=15, pady=(0, 10))
    
    # Timezone
    ctk.CTkLabel(
        display_frame,
        text="Timezone",
        font=ctk.CTkFont(size=10),
        text_color=COLORS["text_muted"]
    ).pack(padx=12, pady=(10, 2), anchor="w")
    tz_var = ctk.StringVar(value=state.selected_timezone)
    ctk.CTkComboBox(
        display_frame,
        values=list(TIMEZONES.keys()),
        variable=tz_var,
        width=420,
        height=32
    ).pack(padx=12, pady=(0, 5))
    
    # Notifications toggle
    notif_var = ctk.BooleanVar(value=state.notifications_enabled)
    ctk.CTkCheckBox(
        display_frame,
        text="Enable toast notifications",
        variable=notif_var,
        font=ctk.CTkFont(size=11)
    ).pack(padx=12, pady=(5, 10), anchor="w")
    
    # === ACCOUNT SECTION ===
    ctk.CTkLabel(
        scroll_frame,
        text="Account",
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=COLORS["accent_blue"]
    ).pack(padx=15, pady=(10, 5), anchor="w")
    
    account_frame = ctk.CTkFrame(scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
    account_frame.pack(fill="x", padx=15, pady=(0, 10))
    
    account_inner = ctk.CTkFrame(account_frame, fg_color="transparent")
    account_inner.pack(fill="x", padx=12, pady=10)
    
    if is_authenticated():
        ctk.CTkLabel(
            account_inner,
            text=f"👤 {get_account_name() or 'Signed in'}",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"]
        ).pack(side="left")
        
        def do_signout():
            sign_out()
            settings_window.destroy()
            if on_close_callback:
                on_close_callback()
        
        ctk.CTkButton(
            account_inner,
            text="Sign Out",
            width=70,
            height=24,
            corner_radius=4,
            font=ctk.CTkFont(size=10),
            fg_color="#4a4a4a",
            hover_color="#5a5a5a",
            command=do_signout
        ).pack(side="right")
    else:
        ctk.CTkLabel(
            account_inner,
            text="🔐 Not signed in",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"]
        ).pack(side="left")
        
        def do_signin():
            settings_window.destroy()
            
            def sign_in_thread():
                token = get_access_token_interactive()
                if token:
                    from ..core import update_refresh_status
                    update_refresh_status()
            
            threading.Thread(target=sign_in_thread, daemon=True).start()
            if on_close_callback:
                on_close_callback()
        
        ctk.CTkButton(
            account_inner,
            text="Sign In",
            width=70,
            height=24,
            corner_radius=4,
            font=ctk.CTkFont(size=10),
            command=do_signin
        ).pack(side="right")
    
    # === SAVE BUTTON ===
    def save_action():
        # Update state
        state.workspace_id = workspace_var.get().strip()
        state.dataset_id = dataset_var.get().strip()
        state.capacity_metrics_workspace = capacity_workspace_var.get().strip()
        state.selected_timezone = tz_var.get()
        state.notifications_enabled = notif_var.get()
        
        # Build pipelines dict
        new_pipelines = {}
        for id_var, name_var, type_var, _ in pipeline_entries:
            pid = id_var.get().strip()
            pname = name_var.get().strip()
            ptype = type_var.get()
            if pid:  # Only add if ID is provided
                new_pipelines[pid] = {
                    "name": pname or "Unnamed Pipeline",
                    "description": f"{'Full' if ptype == 'full' else 'Partial'} refresh",
                    "type": ptype
                }
        state.pipelines = new_pipelines
        
        # Clear cached names (will be re-fetched)
        state.semantic_model_name = None
        state.workspace_name = None
        
        save_settings()
        settings_window.destroy()
        
        # Refresh status with new settings
        def refresh():
            from ..core import update_refresh_status
            update_refresh_status()
        
        threading.Thread(target=refresh, daemon=True).start()
        
        if on_close_callback:
            on_close_callback()
    
    btn_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
    btn_frame.pack(fill="x", padx=15, pady=(5, 15))
    
    ctk.CTkButton(
        btn_frame,
        text="Save Settings",
        width=150,
        height=36,
        command=save_action
    ).pack(side="left")
    
    ctk.CTkButton(
        btn_frame,
        text="Cancel",
        width=80,
        height=36,
        fg_color="#4a4a4a",
        hover_color="#5a5a5a",
        command=settings_window.destroy
    ).pack(side="left", padx=(10, 0))
    
    # Center on parent
    settings_window.update_idletasks()
    try:
        x = parent_window.winfo_x() + 50
        y = parent_window.winfo_y() + 50
        settings_window.geometry(f"+{x}+{y}")
    except:
        pass
