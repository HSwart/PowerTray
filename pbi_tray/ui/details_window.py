"""
Details Window - Main popup window showing refresh status and history.
"""

import threading
import time
import webbrowser
from datetime import datetime, timezone

import customtkinter as ctk
from PIL import Image, ImageTk

from ..config import state, ICON_PATH, ICO_PATH, ICONS_DIR, TIMEZONES, save_settings
from ..auth import is_authenticated, get_account_name, get_access_token_interactive, sign_out
from ..api import (
    get_refresh_details,
    trigger_refresh,
    cancel_refresh,
    get_semantic_model_name,
    get_workspace_name,
    CapacityMetrics,
    format_cu_seconds,
)
from ..utils import log, format_datetime, format_duration, parse_datetime, show_notification
from ..utils.datetime_helpers import format_time_only, get_refresh_type_display
from .theme import COLORS, STATUS_COLORS, get_status_color
from .insights_window import show_insights_window


class DetailsWindow:
    """A compact, visual details popup window showing refresh status and history."""
    
    def __init__(self):
        self.window = None
        self.pbi_icon = None
        self.expanded_rows = {}  # Track expanded state: request_id -> details_frame
        self.capacity_data = None  # Store passed-in capacity data
        self._capacity_update_thread = None
        self._capacity_update_stop = threading.Event()
        self._window_open = False  # Thread-safe flag for window state
        
        # Capture current capacity data from state if available
        if state.capacity_metrics:
            self.capacity_data = state.capacity_metrics.copy()
    
    def show(self):
        """Show the details window."""
        if self._window_open and self.window is not None:
            try:
                self.window.lift()
                self.window.focus_force()
                return
            except:
                self._window_open = False
        
        self._create_window()
    
    def _create_window(self):
        """Create the compact visual details window with 2-column layout."""
        model_name = state.semantic_model_name or "Power BI Dataset"
        
        # Set Windows AppUserModelID for proper taskbar icon (must be before window creation)
        try:
            import ctypes
            myappid = 'powerbi.tray.monitor.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass  # Non-Windows or error
        
        self.window = ctk.CTk()
        self.window.title(model_name)
        self.window.geometry("700x820")  # Wider but shorter with 2 columns
        self.window.resizable(True, True)
        self.window.minsize(650, 500)
        self.window.configure(fg_color=COLORS["bg_dark"])
        
        # Set window icon (use .ico for proper Windows taskbar support)
        if ICO_PATH.exists():
            try:
                self.window.iconbitmap(str(ICO_PATH))
            except Exception as e:
                print(f"Icon error: {e}")
        elif ICON_PATH.exists():
            try:
                icon_img = Image.open(ICON_PATH).resize((32, 32), Image.Resampling.LANCZOS)
                self.pbi_icon = ImageTk.PhotoImage(icon_img)
                self.window.iconphoto(True, self.pbi_icon)
            except Exception as e:
                print(f"Icon fallback error: {e}")
        
        # ===== STATIC HEADER =====
        self._create_header(model_name)
        
        # ===== TWO COLUMN GRID LAYOUT =====
        grid_frame = ctk.CTkFrame(
            self.window, 
            corner_radius=0,
            fg_color=COLORS["bg_dark"]
        )
        grid_frame.pack(fill="x", padx=0, pady=0)
        
        # Configure grid: 2 columns, 2 rows with equal weights
        grid_frame.grid_columnconfigure(0, weight=1, uniform="col")
        grid_frame.grid_columnconfigure(1, weight=1, uniform="col")
        grid_frame.grid_rowconfigure(0, weight=1, uniform="row")
        grid_frame.grid_rowconfigure(1, weight=1, uniform="row")
        
        # ROW 0: Status Overview (left) | Gateways (right)
        status_card = self._create_status_overview(grid_frame, use_grid=True)
        if status_card:
            status_card.grid(row=0, column=0, sticky="nsew", padx=(12, 6), pady=6)
        
        gateway_card = self._create_gateway_info(grid_frame, use_grid=True)
        if gateway_card:
            gateway_card.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=6)
        
        # ROW 1: Pipelines (left) | Capacity (right)
        pipeline_card = self._create_quick_info(grid_frame, use_grid=True)
        if pipeline_card:
            pipeline_card.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=6)
        
        if state.capacity_metrics_workspace:
            capacity_card = self._create_capacity_info(grid_frame, use_grid=True)
            if capacity_card:
                capacity_card.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=6)
        
        # Sign-in prompt (only if not authenticated) - spans full width below columns
        if not is_authenticated():
            self._create_signin_prompt(self.window)
        
        # History Section (ONLY this is scrollable)
        self._create_history_table(self.window)
        
        # ===== STATIC FOOTER =====
        self._create_footer()
        
        # Center window on screen
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - 350  # Center wider window
        y = (self.window.winfo_screenheight() // 2) - 410
        self.window.geometry(f"+{x}+{y}")
        
        # Bring window to front
        self.window.lift()
        self.window.focus_force()
        
        # Handle window close
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self._window_open = True
        
        # Suppress Tcl/Tk background errors
        def _suppress_bgerror(message):
            if "invalid command name" not in message:
                log(f"Tk error: {message}")
        
        self.window.tk.createcommand('bgerror', _suppress_bgerror)
        
        # Start background capacity metrics update thread (every 5 minutes)
        if state.capacity_metrics_workspace:
            self._capacity_update_stop.clear()
            self._capacity_update_thread = threading.Thread(
                target=self._background_capacity_update,
                daemon=True
            )
            self._capacity_update_thread.start()
        
        log("Starting mainloop...")
        self.window.mainloop()
        log("mainloop exited")
    
    def _create_header(self, model_name):
        """Create static header with workspace, model name and status."""
        ws_name = state.workspace_name or "Workspace"
        
        header = ctk.CTkFrame(
            self.window, 
            height=80,
            corner_radius=0,
            fg_color=COLORS["bg_header"]
        )
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        # Left side: Icon and names
        left_frame = ctk.CTkFrame(header, fg_color="transparent")
        left_frame.pack(side="left", fill="y", padx=15)
        
        # Try to show PBI icon
        if ICON_PATH.exists():
            try:
                pbi_img = Image.open(ICON_PATH).resize((32, 32), Image.Resampling.LANCZOS)
                pbi_ctk = ctk.CTkImage(light_image=pbi_img, dark_image=pbi_img, size=(32, 32))
                ctk.CTkLabel(left_frame, image=pbi_ctk, text="").pack(side="left", pady=22, padx=(0, 10))
            except:
                ctk.CTkLabel(left_frame, text="📊", font=ctk.CTkFont(size=24)).pack(side="left", pady=22, padx=(0, 10))
        else:
            ctk.CTkLabel(left_frame, text="📊", font=ctk.CTkFont(size=24)).pack(side="left", pady=22, padx=(0, 10))
        
        # Names container
        names_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        names_frame.pack(side="left", fill="y", pady=14)
        
        # Workspace name (smaller, muted)
        ws_display = ws_name[:35] + "..." if len(ws_name) > 35 else ws_name
        ctk.CTkLabel(
            names_frame,
            text=ws_display,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"]
        ).pack(anchor="w")
        
        # Model name (larger, bold)
        display_name = model_name[:30] + "..." if len(model_name) > 30 else model_name
        ctk.CTkLabel(
            names_frame,
            text=display_name,
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w")
        
        # Right side: Status badge
        status_color = get_status_color(state.last_refresh_status)
        status_text = state.last_refresh_status.replace("NotSignedIn", "Sign In")
        
        status_badge = ctk.CTkFrame(header, fg_color=status_color, corner_radius=8)
        status_badge.pack(side="right", padx=15, pady=28)
        
        ctk.CTkLabel(
            status_badge,
            text=status_text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white"
        ).pack(padx=8, pady=3)
    
    def _create_status_overview(self, parent, use_grid=False):
        """Create combined status overview with time and info."""
        frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=COLORS["bg_card"])
        if not use_grid:
            frame.pack(fill="x", padx=12, pady=(10, 6))
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=8)
        
        # Row 1: Time and subtitle
        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x")
        
        time_display = self._get_last_refresh_time_display()
        ctk.CTkLabel(
            row1,
            text=time_display,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(side="left")
        
        ctk.CTkLabel(
            row1,
            text=f"• {state.selected_timezone}",
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"]
        ).pack(side="left", padx=(8, 0))
        
        # Row 2: Type | Duration | Checked
        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x", pady=(4, 0))
        
        info_items = [
            get_refresh_type_display(state.last_refresh_info.get('refreshType', 'N/A')),
            format_duration(state.last_refresh_info.get('startTime'), state.last_refresh_info.get('endTime')),
            f"Checked {datetime.now().strftime('%H:%M')}",
        ]
        
        ctk.CTkLabel(
            row2,
            text="  •  ".join(info_items),
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_secondary"]
        ).pack(side="left")
        
        # Row 3: Time until next refresh (countdown)
        if state.next_scheduled:
            # Find the soonest next run
            soonest = None
            soonest_name = None
            for sched in state.next_scheduled:
                next_run = sched.get("next_run")
                if next_run:
                    if soonest is None or next_run < soonest:
                        soonest = next_run
                        soonest_name = sched.get("name", "Pipeline")
            
            if soonest:
                now = datetime.now(timezone.utc)
                diff = soonest - now
                
                if diff.total_seconds() > 0:
                    row3 = ctk.CTkFrame(inner, fg_color="transparent")
                    row3.pack(fill="x", pady=(6, 0))
                    
                    # Calculate human-readable time
                    total_mins = int(diff.total_seconds() / 60)
                    if total_mins < 60:
                        time_text = f"{total_mins} min"
                    else:
                        hours = total_mins // 60
                        mins = total_mins % 60
                        time_text = f"{hours}h {mins}m" if mins > 0 else f"{hours}h"
                    
                    short_name = (soonest_name or "refresh").replace(" Refresh", "").replace("Intra-Daily", "Intra").replace("Full Daily", "Full")
                    
                    ctk.CTkLabel(
                        row3,
                        text=f"Next {short_name} in",
                        font=ctk.CTkFont(size=12),
                        text_color=COLORS["text_muted"]
                    ).pack(side="left")
                    
                    ctk.CTkLabel(
                        row3,
                        text=time_text,
                        font=ctk.CTkFont(size=12, weight="bold"),
                        text_color=COLORS["accent_blue"]
                    ).pack(side="left", padx=(5, 0))
        
        return frame if use_grid else None
    
    def _create_quick_info(self, parent, use_grid=False):
        """Create pipeline info section."""
        if not state.pipelines:
            return None
        
        frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=COLORS["bg_card"])
        if not use_grid:
            frame.pack(fill="x", padx=12, pady=6)
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 5))
        
        # Pipeline icon
        pipeline_icon_path = ICONS_DIR / "pipelines.png"
        if pipeline_icon_path.exists():
            try:
                pipe_img = Image.open(pipeline_icon_path).resize((20, 20), Image.Resampling.LANCZOS)
                pipe_ctk = ctk.CTkImage(light_image=pipe_img, dark_image=pipe_img, size=(20, 20))
                ctk.CTkLabel(header, image=pipe_ctk, text="").pack(side="left", padx=(0, 6))
            except:
                pass
        ctk.CTkLabel(header, text="Refresh Pipelines", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(side="left")
        
        ctk.CTkFrame(frame, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=12, pady=2)
        
        # Pipeline items
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=12, pady=(0, 10))
        
        # Build a lookup of next run times by pipeline name
        next_run_lookup = {}
        if state.next_scheduled:
            for sched in state.next_scheduled:
                next_run_lookup[sched.get("name", "")] = sched.get("next_run")
        
        for pipeline_id, pipeline_info in state.pipelines.items():
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=3)
            
            type_color = COLORS["accent_blue"] if pipeline_info["type"] == "full" else COLORS["accent_orange"]
            type_label = "Full" if pipeline_info["type"] == "full" else "Partial"
            
            # Left side: type badge and name
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True)
            
            ctk.CTkLabel(left, text=f"● {type_label}", font=ctk.CTkFont(size=11),
                        text_color=type_color, width=55).pack(side="left")
            ctk.CTkLabel(left, text=pipeline_info["name"], font=ctk.CTkFont(size=12),
                        text_color=COLORS["text_primary"]).pack(side="left")
            
            # Right side: next run time
            next_run = next_run_lookup.get(pipeline_info["name"])
            if next_run:
                next_time_str = format_time_only(next_run)
                ctk.CTkLabel(row, text=f"Next: {next_time_str}", font=ctk.CTkFont(size=11),
                            text_color=COLORS["text_muted"]).pack(side="right")
            else:
                ctk.CTkLabel(row, text="Not scheduled", font=ctk.CTkFont(size=11),
                            text_color=COLORS["text_muted"]).pack(side="right")
        
        return frame if use_grid else None
    
    def _create_gateway_info(self, parent, use_grid=False):
        """Create gateway status section using cached data."""
        summary = state.gateway_summary  # Use cached data from state
        
        if not summary or summary["status"] == "none":
            return None
        
        if summary["status"] == "cloud":
            frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=COLORS["bg_card"])
            if not use_grid:
                frame.pack(fill="x", padx=12, pady=6)
            header = ctk.CTkFrame(frame, fg_color="transparent")
            header.pack(fill="x", padx=12, pady=10)
            ctk.CTkLabel(header, text="☁️ Cloud Datasources", font=ctk.CTkFont(size=14, weight="bold"),
                        text_color=COLORS["text_primary"]).pack(side="left")
            ctk.CTkLabel(header, text="No gateway required", font=ctk.CTkFont(size=11),
                        text_color=COLORS["text_muted"]).pack(side="right")
            return frame if use_grid else None
        
        border_color = {
            "offline": COLORS["accent_red"],
            "partial": COLORS["accent_orange"]
        }.get(summary["status"], COLORS["bg_card"])
        
        frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=COLORS["bg_card"],
                            border_width=1 if summary["status"] not in ("online", "cloud") else 0,
                            border_color=border_color)
        if not use_grid:
            frame.pack(fill="x", padx=12, pady=6)
        
        # Header with status
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 5))
        
        # Gateway icon
        gateway_icon_path = ICONS_DIR / "gateways.png"
        if gateway_icon_path.exists():
            try:
                gw_img = Image.open(gateway_icon_path).resize((20, 20), Image.Resampling.LANCZOS)
                gw_ctk = ctk.CTkImage(light_image=gw_img, dark_image=gw_img, size=(20, 20))
                ctk.CTkLabel(header, image=gw_ctk, text="").pack(side="left", padx=(0, 6))
            except:
                pass
        ctk.CTkLabel(header, text="Gateways", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(side="left")
        
        status_color = {"online": COLORS["accent_green"], "partial": COLORS["accent_orange"],
                       "offline": COLORS["accent_red"]}.get(summary["status"], COLORS["text_muted"])
        
        status_badge = ctk.CTkFrame(header, fg_color=status_color, corner_radius=4)
        status_badge.pack(side="right")
        
        status_text = f"{summary['online']}/{summary['total']} online" if summary["total"] > 1 else \
                     ("Online" if summary["status"] == "online" else "Offline")
        ctk.CTkLabel(status_badge, text=status_text, font=ctk.CTkFont(size=10, weight="bold"),
                    text_color="white").pack(padx=6, pady=2)
        
        ctk.CTkFrame(frame, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=12, pady=2)
        
        # Gateway details
        content = ctk.CTkFrame(frame, fg_color="transparent")
        content.pack(fill="x", padx=12, pady=(0, 10))
        
        for gw in summary.get("details", []):
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            gw_status_color = {"online": COLORS["accent_green"], "partial": COLORS["accent_orange"],
                              "offline": COLORS["accent_red"], "unknown": COLORS["text_muted"]
                             }.get(gw["status"], COLORS["text_muted"])
            
            ctk.CTkLabel(row, text="●", font=ctk.CTkFont(size=11),
                        text_color=gw_status_color, width=16).pack(side="left")
            ctk.CTkLabel(row, text=gw["name"], font=ctk.CTkFont(size=12),
                        text_color=COLORS["text_primary"]).pack(side="left", padx=(0, 5))
            ctk.CTkLabel(row, text=f"({gw['type']})", font=ctk.CTkFont(size=11),
                        text_color=COLORS["text_muted"]).pack(side="left")
            ctk.CTkLabel(row, text=gw["status_text"], font=ctk.CTkFont(size=11),
                        text_color=gw_status_color).pack(side="right")
        
        return frame if use_grid else None
    
    def _create_capacity_info(self, parent, use_grid=False):
        """Create capacity metrics info section with async loading."""
        self.capacity_frame = ctk.CTkFrame(parent, corner_radius=10, fg_color=COLORS["bg_card"])
        if not use_grid:
            self.capacity_frame.pack(fill="x", padx=12, pady=6)
        
        # Header
        header = ctk.CTkFrame(self.capacity_frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 5))
        
        # Capacity icon
        capacity_icon_path = ICONS_DIR / "capacities.png"
        if capacity_icon_path.exists():
            try:
                cap_img = Image.open(capacity_icon_path).resize((20, 20), Image.Resampling.LANCZOS)
                cap_ctk = ctk.CTkImage(light_image=cap_img, dark_image=cap_img, size=(20, 20))
                ctk.CTkLabel(header, image=cap_ctk, text="").pack(side="left", padx=(0, 6))
            except:
                pass
        ctk.CTkLabel(header, text="Capacity", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(side="left")
        
        # Status badge placeholder
        self.capacity_status_badge = ctk.CTkFrame(header, fg_color=COLORS["text_muted"], corner_radius=4)
        self.capacity_status_badge.pack(side="right")
        self.capacity_status_label = ctk.CTkLabel(self.capacity_status_badge, text="Loading...", 
                                                   font=ctk.CTkFont(size=10, weight="bold"),
                                                   text_color="white")
        self.capacity_status_label.pack(padx=6, pady=2)
        
        ctk.CTkFrame(self.capacity_frame, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=12, pady=2)
        
        # Content container
        self.capacity_content = ctk.CTkFrame(self.capacity_frame, fg_color="transparent")
        self.capacity_content.pack(fill="x", padx=12, pady=(0, 10))
        
        # Utilization row
        util_row = ctk.CTkFrame(self.capacity_content, fg_color="transparent")
        util_row.pack(fill="x", pady=4)
        
        ctk.CTkLabel(util_row, text="Utilization", font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_muted"], width=100, anchor="w").pack(side="left")
        
        # Progress bar container
        bar_container = ctk.CTkFrame(util_row, fg_color="transparent", height=20)
        bar_container.pack(side="left", fill="x", expand=True, padx=(10, 0))
        bar_container.pack_propagate(False)
        
        # Background bar (track)
        self.capacity_bg_bar = ctk.CTkFrame(bar_container, fg_color=COLORS["bg_dark"], corner_radius=4, height=10)
        self.capacity_bg_bar.pack(side="left", fill="x", expand=True, pady=5)
        
        # Stacked fill bars: Background (blue) + Interactive (orange)
        # Background segment (left side)
        self.capacity_bg_fill = ctk.CTkFrame(self.capacity_bg_bar, fg_color=COLORS["accent_blue"], corner_radius=0, height=10)
        self.capacity_bg_fill.place(relx=0, rely=0, relwidth=0, relheight=1)
        
        # Interactive segment (right side of BG)
        self.capacity_int_fill = ctk.CTkFrame(self.capacity_bg_bar, fg_color=COLORS["accent_orange"], corner_radius=0, height=10)
        self.capacity_int_fill.place(relx=0, rely=0, relwidth=0, relheight=1)
        
        self.capacity_pct_label = ctk.CTkLabel(util_row, text="--", font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=COLORS["text_muted"], width=60, anchor="e")
        self.capacity_pct_label.pack(side="right")
        
        # Additional metrics row
        metrics_row = ctk.CTkFrame(self.capacity_content, fg_color="transparent")
        metrics_row.pack(fill="x", pady=2)
        
        # Legend with colored dots matching bar colors
        self.capacity_bg_dot = ctk.CTkLabel(metrics_row, text="●", font=ctk.CTkFont(size=11),
                    text_color=COLORS["accent_blue"])
        self.capacity_bg_dot.pack(side="left")
        
        self.capacity_bg_label = ctk.CTkLabel(metrics_row, text="BG: --", font=ctk.CTkFont(size=11),
                    text_color=COLORS["text_muted"])
        self.capacity_bg_label.pack(side="left", padx=(2, 8))
        
        self.capacity_int_dot = ctk.CTkLabel(metrics_row, text="●", font=ctk.CTkFont(size=11),
                    text_color=COLORS["accent_orange"])
        self.capacity_int_dot.pack(side="left")
        
        self.capacity_int_label = ctk.CTkLabel(metrics_row, text="Int: --", font=ctk.CTkFont(size=11),
                    text_color=COLORS["text_muted"])
        self.capacity_int_label.pack(side="left", padx=(2, 10))
        
        # Separator and total
        ctk.CTkLabel(metrics_row, text="=", font=ctk.CTkFont(size=11),
                    text_color=COLORS["text_muted"]).pack(side="left")
        
        self.capacity_total_label = ctk.CTkLabel(metrics_row, text="--", font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=COLORS["text_primary"])
        self.capacity_total_label.pack(side="left", padx=(4, 0))
        
        self.capacity_throttle_label = ctk.CTkLabel(metrics_row, text="",
                    font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"])
        self.capacity_throttle_label.pack(side="right")
        
        # Check for cached data - either from init or current state
        cached_data = self.capacity_data or state.capacity_metrics
        if cached_data:
            # Use cached data from state - display immediately
            self.capacity_data = cached_data if isinstance(cached_data, dict) else cached_data.copy() if hasattr(cached_data, 'copy') else cached_data
            self._update_capacity_from_cached_data()
        else:
            # No cached data, fetch async
            self._fetch_capacity_async()
        
        # Schedule periodic refresh (every 5 minutes to match background loop)
        self._schedule_capacity_refresh()
        
        return self.capacity_frame if use_grid else None
    
    def _fetch_capacity_async(self):
        """Fetch capacity metrics in a background thread."""
        import threading
        
        def fetch():
            try:
                metrics = CapacityMetrics(state.capacity_metrics_workspace)
                utilization = metrics.get_utilization()
                throttling = metrics.get_throttling_status()
                
                # Update UI on main thread - use flag instead of winfo_exists()
                if self._window_open and self.window:
                    self.window.after(0, lambda: self._update_capacity_ui(utilization, throttling))
            except Exception as e:
                log(f"Error fetching capacity metrics: {e}")
                if self._window_open and self.window:
                    self.window.after(0, lambda: self._update_capacity_ui(None, None, error=True))
        
        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()
    
    def _update_capacity_ui(self, utilization, throttling, error=False):
        """Update capacity UI with fetched data."""
        try:
            if error or not utilization:
                self.capacity_status_label.configure(text="Unavailable")
                self.capacity_status_badge.configure(fg_color=COLORS["text_muted"])
                self.capacity_pct_label.configure(text="N/A")
                return
            
            # API returns keys with brackets like "[UtilizationPct]" and values as decimals (0.53 = 53%)
            raw_pct = utilization.get("[UtilizationPct]", utilization.get("UtilizationPct", 0)) or 0
            pct = raw_pct * 100  # Convert decimal to percentage
            
            # Get BG and Interactive percentages
            raw_bg = utilization.get("[BackgroundPct]", utilization.get("BackgroundPct", 0)) or 0
            raw_int = utilization.get("[InteractivePct]", utilization.get("InteractivePct", 0)) or 0
            bg_pct = raw_bg * 100
            int_pct = raw_int * 100
            
            # Determine colors based on utilization
            if pct >= 100:
                status_color = COLORS["accent_red"]
                status_text = "Critical"
            elif pct >= 80:
                status_color = COLORS["accent_orange"]
                status_text = "High"
            else:
                status_color = COLORS["accent_green"]
                status_text = "Normal"
            
            # Update status badge
            self.capacity_status_badge.configure(fg_color=status_color)
            self.capacity_status_label.configure(text=status_text)
            
            # Update stacked progress bar (BG + Interactive)
            bg_ratio = min(bg_pct, 100) / 100
            int_ratio = min(int_pct, 100) / 100
            
            # Minimum visible width (1%) for non-zero values
            min_visible = 0.01
            if bg_ratio > 0 and bg_ratio < min_visible:
                bg_ratio = min_visible
            if int_ratio > 0 and int_ratio < min_visible:
                int_ratio = min_visible
            
            # Ensure total doesn't exceed 100%
            total = bg_ratio + int_ratio
            if total > 1:
                scale = 1 / total
                bg_ratio *= scale
                int_ratio *= scale
            
            # BG fills from left, Int fills from where BG ends
            self.capacity_bg_fill.place(relx=0, rely=0, relwidth=bg_ratio, relheight=1)
            self.capacity_int_fill.place(relx=bg_ratio, rely=0, relwidth=int_ratio, relheight=1)
            
            # Update percentage label
            self.capacity_pct_label.configure(text=f"{pct:.1f}%", text_color=status_color)
            
            # Update breakdown legend - update the separate colored labels
            self._update_capacity_legend(bg_pct, int_pct, pct)
            
            # Update throttling status based on utilization levels
            if pct >= 100:
                throttle_level = "Throttled"
                throttle_color = COLORS["accent_red"]
            elif pct >= 90:
                throttle_level = "At Risk"
                throttle_color = COLORS["accent_orange"]
            else:
                throttle_level = "No Throttling"
                throttle_color = COLORS["accent_green"]
            
            self.capacity_throttle_label.configure(
                text=f"⚡ {throttle_level}", 
                text_color=throttle_color
            )
                
        except Exception as e:
            log(f"Error updating capacity UI: {e}")
    
    def _update_capacity_legend(self, bg_pct, int_pct, total_pct=None):
        """Update the capacity legend labels with current values."""
        self.capacity_bg_label.configure(text=f"BG: {bg_pct:.1f}%")
        self.capacity_int_label.configure(text=f"Int: {int_pct:.1f}%")
        if total_pct is not None:
            self.capacity_total_label.configure(text=f"{total_pct:.1f}%")
    
    def _schedule_capacity_refresh(self):
        """Schedule periodic capacity refresh."""
        if self._window_open and self.window:
            self._fetch_capacity_async()
            # Refresh every 5 minutes (300000ms) to match background loop
            self.window.after(300000, self._schedule_capacity_refresh)
    
    def _update_capacity_from_cached_data(self):
        """Update capacity UI from cached data (no DAX query)."""
        try:
            if not self.capacity_data:
                return
            
            pct = self.capacity_data.get("utilization", 0)
            bg_pct = self.capacity_data.get("background", 0)
            int_pct = self.capacity_data.get("interactive", 0)
            
            # Determine colors based on utilization
            if pct >= 100:
                status_color = COLORS["accent_red"]
                status_text = "Critical"
            elif pct >= 80:
                status_color = COLORS["accent_orange"]
                status_text = "High"
            else:
                status_color = COLORS["accent_green"]
                status_text = "Normal"
            
            # Update status badge
            self.capacity_status_badge.configure(fg_color=status_color)
            self.capacity_status_label.configure(text=status_text)
            
            # Update stacked progress bar (BG + Interactive)
            bg_ratio = min(bg_pct, 100) / 100
            int_ratio = min(int_pct, 100) / 100
            
            # Minimum visible width (1%) for non-zero values
            min_visible = 0.01
            if bg_ratio > 0 and bg_ratio < min_visible:
                bg_ratio = min_visible
            if int_ratio > 0 and int_ratio < min_visible:
                int_ratio = min_visible
            
            # Ensure total doesn't exceed 100%
            total = bg_ratio + int_ratio
            if total > 1:
                scale = 1 / total
                bg_ratio *= scale
                int_ratio *= scale
            
            # BG fills from left, Int fills from where BG ends
            self.capacity_bg_fill.place(relx=0, rely=0, relwidth=bg_ratio, relheight=1)
            self.capacity_int_fill.place(relx=bg_ratio, rely=0, relwidth=int_ratio, relheight=1)
            
            # Update percentage label
            self.capacity_pct_label.configure(text=f"{pct:.1f}%", text_color=status_color)
            
            # Update breakdown legend
            self._update_capacity_legend(bg_pct, int_pct, pct)
            
            # Update throttling status
            if pct >= 100:
                throttle_level = "Throttled"
                throttle_color = COLORS["accent_red"]
            elif pct >= 90:
                throttle_level = "At Risk"
                throttle_color = COLORS["accent_orange"]
            else:
                throttle_level = "No Throttling"
                throttle_color = COLORS["accent_green"]
            
            self.capacity_throttle_label.configure(
                text=f"⚡ {throttle_level}", 
                text_color=throttle_color
            )
            
        except Exception as e:
            log(f"Error updating capacity from cached data: {e}")

    def _create_signin_prompt(self, parent):
        """Create sign-in prompt."""
        frame = ctk.CTkFrame(parent, corner_radius=10, fg_color="#2a2a4a")
        frame.pack(fill="x", padx=12, pady=6)
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)
        
        ctk.CTkLabel(inner, text="🔐 Sign in to view refresh data",
                    font=ctk.CTkFont(size=13)).pack(side="left")
        ctk.CTkButton(inner, text="Sign In", width=80, height=30, corner_radius=4,
                     font=ctk.CTkFont(size=12), command=self._sign_in).pack(side="right")
    
    def _create_history_table(self, parent):
        """Create history table with scrollable history items."""
        frame = ctk.CTkFrame(parent, corner_radius=10, fg_color=COLORS["bg_card"])
        frame.pack(fill="both", expand=True, padx=12, pady=6)
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 5))
        
        ctk.CTkLabel(header, text="Recent History", font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=COLORS["text_primary"]).pack(side="left")
        ctk.CTkLabel(header, text=f"{len(state.refresh_history)} refreshes",
                    font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"]).pack(side="right")
        
        ctk.CTkFrame(frame, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=12, pady=5)
        
        # Scrollable history
        history_scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent", height=200,
                                                scrollbar_fg_color="transparent",
                                                scrollbar_button_color=COLORS["bg_dark"],
                                                scrollbar_button_hover_color=COLORS["text_muted"])
        history_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        
        try:
            history_scroll._scrollbar.configure(width=4)
        except:
            pass
        
        if not state.refresh_history:
            ctk.CTkLabel(history_scroll, text="No history available", font=ctk.CTkFont(size=13),
                        text_color=COLORS["text_muted"]).pack(pady=15)
        else:
            for i, refresh in enumerate(state.refresh_history[:15]):
                self._create_history_row(history_scroll, i, refresh)
    
    def _create_history_row(self, parent, index, refresh):
        """Create a compact history row with expandable details."""
        status = refresh.get("status", "Unknown")
        status_color = get_status_color(status)
        request_id = refresh.get("requestId", "")
        refresh_type_raw = refresh.get("refreshType", "")
        
        supports_details = refresh_type_raw in ("ViaEnhancedApi", "DataFactory", "ViaApi")
        
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", pady=1)
        
        row = ctk.CTkFrame(container, fg_color="transparent", height=28)
        row.pack(fill="x")
        row.pack_propagate(False)
        
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=4, pady=2)
        
        if supports_details:
            arrow_label = ctk.CTkLabel(inner, text="▶", font=ctk.CTkFont(size=10),
                                       text_color=COLORS["text_muted"], width=16, cursor="hand2")
            arrow_label.pack(side="left")
            
            def toggle_details(event=None, rid=request_id, cont=container, arrow=arrow_label):
                self._toggle_table_details(rid, cont, arrow)
            
            arrow_label.bind("<Button-1>", toggle_details)
            row.bind("<Button-1>", toggle_details)
            inner.bind("<Button-1>", toggle_details)
            row.configure(cursor="hand2")
        else:
            ctk.CTkLabel(inner, text="", width=16).pack(side="left")
        
        ctk.CTkLabel(inner, text="●", font=ctk.CTkFont(size=12),
                    text_color=status_color, width=16).pack(side="left")
        
        status_display = "In Progress" if status.lower() == "unknown" else status.capitalize()
        ctk.CTkLabel(inner, text=status_display, font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_primary"], width=75, anchor="w").pack(side="left")
        
        end_time = parse_datetime(refresh.get("endTime"))
        start_time = parse_datetime(refresh.get("startTime"))
        
        if end_time:
            time_str = format_datetime(end_time)
        elif start_time:
            time_str = f"Started {format_datetime(start_time)}"
        else:
            time_str = "N/A"
        
        ctk.CTkLabel(inner, text=time_str, font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_secondary"], width=130, anchor="w").pack(side="left")
        
        ctk.CTkLabel(inner, text=get_refresh_type_display(refresh_type_raw),
                    font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"],
                    width=80, anchor="w").pack(side="left")
        
        # Duration
        if refresh.get("endTime"):
            duration = format_duration(refresh.get("startTime"), refresh.get("endTime"))
        elif refresh.get("startTime"):
            start_dt = parse_datetime(refresh.get("startTime"))
            if start_dt:
                elapsed = datetime.now(timezone.utc) - start_dt
                total_seconds = int(elapsed.total_seconds())
                if total_seconds < 60:
                    duration = f"{total_seconds}s..."
                elif total_seconds < 3600:
                    duration = f"{total_seconds // 60}m..."
                else:
                    duration = f"{total_seconds // 3600}h {(total_seconds % 3600) // 60}m..."
            else:
                duration = "..."
        else:
            duration = "..."
        
        ctk.CTkLabel(inner, text=duration, font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_muted"]).pack(side="right")
    
    def _toggle_table_details(self, request_id, container, arrow_label):
        """Toggle expanded table details."""
        if request_id in self.expanded_rows:
            self.expanded_rows[request_id].destroy()
            del self.expanded_rows[request_id]
            arrow_label.configure(text="▶")
        else:
            arrow_label.configure(text="▼")
            
            details_frame = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=6)
            details_frame.pack(fill="x", padx=(24, 0), pady=(2, 4))
            
            loading_label = ctk.CTkLabel(details_frame, text="Loading table details...",
                                         font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"])
            loading_label.pack(pady=8)
            
            self.expanded_rows[request_id] = details_frame
            
            def fetch_and_display():
                details = get_refresh_details(request_id)
                if self.window:
                    self.window.after(0, lambda: self._display_table_details(details_frame, details, loading_label))
            
            threading.Thread(target=fetch_and_display, daemon=True).start()
    
    def _display_table_details(self, details_frame, details, loading_label):
        """Display table-level refresh details."""
        try:
            if not details_frame.winfo_exists():
                return
        except:
            return
        
        try:
            loading_label.destroy()
        except:
            pass
        
        # Check for AI analysis on failed refreshes
        ai_analysis = None
        if state.last_refresh_status == "Failed":
            ai_analysis = state.last_refresh_info.get("ai_analysis")
        
        # Show AI Analysis section if available
        if ai_analysis:
            ai_frame = ctk.CTkFrame(details_frame, fg_color=COLORS["bg_dark"], corner_radius=6)
            ai_frame.pack(fill="x", padx=8, pady=(6, 4))
            
            # AI Header with severity badge
            ai_header = ctk.CTkFrame(ai_frame, fg_color="transparent")
            ai_header.pack(fill="x", padx=8, pady=(6, 2))
            
            ctk.CTkLabel(ai_header, text="🤖 AI Analysis",
                        font=ctk.CTkFont(size=11, weight="bold"),
                        text_color=COLORS["accent_blue"]).pack(side="left")
            
            severity = ai_analysis.get("severity", "medium")
            severity_colors = {"low": "#fbc02d", "medium": "#ff9800", "high": "#ff5722", "critical": "#D60029"}
            sev_color = severity_colors.get(severity, "#ff9800")
            
            sev_badge = ctk.CTkFrame(ai_header, fg_color=sev_color, corner_radius=4)
            sev_badge.pack(side="right")
            ctk.CTkLabel(sev_badge, text=severity.upper(), font=ctk.CTkFont(size=9, weight="bold"),
                        text_color="white").pack(padx=4, pady=1)
            
            # Summary
            summary = ai_analysis.get("summary", "")
            if summary:
                ctk.CTkLabel(ai_frame, text=summary, font=ctk.CTkFont(size=11),
                            text_color=COLORS["text_secondary"], wraplength=400, justify="left",
                            anchor="w").pack(fill="x", padx=8, pady=(2, 4))
            
            # Cause
            cause = ai_analysis.get("cause", "")
            if cause:
                ctk.CTkLabel(ai_frame, text=f"Cause: {cause}", font=ctk.CTkFont(size=10),
                            text_color=COLORS["text_muted"], wraplength=400, justify="left",
                            anchor="w").pack(fill="x", padx=8, pady=(0, 2))
            
            # Suggestions
            suggestions = ai_analysis.get("suggestions", [])
            if suggestions:
                ctk.CTkLabel(ai_frame, text="💡 Suggestions:",
                            font=ctk.CTkFont(size=10, weight="bold"),
                            text_color=COLORS["text_secondary"]).pack(anchor="w", padx=8, pady=(4, 2))
                for i, suggestion in enumerate(suggestions[:3], 1):
                    ctk.CTkLabel(ai_frame, text=f"  {i}. {suggestion}",
                                font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"],
                                wraplength=380, justify="left", anchor="w").pack(fill="x", padx=8)
                
                ctk.CTkFrame(ai_frame, height=6, fg_color="transparent").pack()
        
        if not details:
            ctk.CTkLabel(details_frame, text="Table details not available",
                        font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"]).pack(pady=8)
            return
        
        objects = details.get("objects", [])
        if not objects:
            ctk.CTkLabel(details_frame, text="No table-level details (standard refresh)",
                        font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"]).pack(pady=8)
            return
        
        header = ctk.CTkFrame(details_frame, fg_color="transparent")
        header.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(header, text=f"Tables refreshed: {len(objects)}",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=COLORS["text_secondary"]).pack(side="left")
        
        for obj in objects:
            table_name = obj.get("table", "Unknown")
            partition_name = obj.get("partition")
            obj_status = obj.get("status", "Unknown")
            obj_status_color = get_status_color(obj_status)
            
            table_row = ctk.CTkFrame(details_frame, fg_color="transparent", height=22)
            table_row.pack(fill="x", padx=8, pady=1)
            table_row.pack_propagate(False)
            
            ctk.CTkLabel(table_row, text="●", font=ctk.CTkFont(size=10),
                        text_color=obj_status_color, width=14).pack(side="left")
            
            display_name = f"{table_name} ({partition_name})" if partition_name and partition_name != table_name else table_name
            ctk.CTkLabel(table_row, text=display_name, font=ctk.CTkFont(size=11),
                        text_color=COLORS["text_primary"], anchor="w", width=150).pack(side="left", padx=(4, 0))
            
            start_time = obj.get("startTime")
            end_time = obj.get("endTime")
            if start_time or end_time:
                start_dt = parse_datetime(start_time)
                end_dt = parse_datetime(end_time)
                
                if start_dt and end_dt:
                    duration = format_duration(start_time, end_time)
                    time_str = f"{format_time_only(start_dt)} → {format_time_only(end_dt)} ({duration})"
                elif start_dt:
                    time_str = f"Started {format_time_only(start_dt)}"
                elif end_dt:
                    time_str = f"Ended {format_time_only(end_dt)}"
                else:
                    time_str = ""
                
                if time_str:
                    ctk.CTkLabel(table_row, text=time_str, font=ctk.CTkFont(size=10),
                                text_color=COLORS["text_muted"]).pack(side="right", padx=(0, 4))
            else:
                ctk.CTkLabel(table_row, text=obj_status.capitalize(), font=ctk.CTkFont(size=10),
                            text_color=COLORS["text_muted"]).pack(side="right")
        
        ctk.CTkFrame(details_frame, height=4, fg_color="transparent").pack()
    
    def _create_footer(self):
        """Create footer with action buttons."""
        footer = ctk.CTkFrame(self.window, height=55, corner_radius=0, fg_color=COLORS["bg_header"])
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        
        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)
        
        ctk.CTkButton(inner, text="Open in Power BI", width=110, height=34, corner_radius=6,
                     font=ctk.CTkFont(size=12), command=self._open_powerbi).pack(side="left")
        
        # Actions dropdown
        self.actions_var = ctk.StringVar(value="Actions")
        
        def on_action_select(choice):
            if choice == "Trigger Refresh":
                self._refresh_now()
            elif choice == "Cancel Refresh":
                self._cancel_refresh()
            self.actions_var.set("Actions")
        
        action_options = ["Cancel Refresh"] if state.last_refresh_status == "InProgress" else ["Trigger Refresh"]
        
        actions_menu = ctk.CTkOptionMenu(inner, values=action_options, variable=self.actions_var,
                                         width=100, height=34, corner_radius=6, font=ctk.CTkFont(size=12),
                                         fg_color=COLORS["border"], button_color=COLORS["border"],
                                         button_hover_color="#4a4a4a", dropdown_fg_color=COLORS["bg_card"],
                                         dropdown_hover_color=COLORS["border"], command=on_action_select)
        actions_menu.pack(side="left", padx=4)
        actions_menu.set("Actions")
        
        ctk.CTkButton(inner, text="Settings", width=70, height=34, corner_radius=6,
                     font=ctk.CTkFont(size=12), fg_color=COLORS["border"], hover_color="#4a4a4a",
                     command=self._show_settings).pack(side="left")
        
        # AI Insights button
        ctk.CTkButton(inner, text="✨ Insights", width=85, height=34, corner_radius=6,
                     font=ctk.CTkFont(size=12), fg_color=COLORS["accent_blue"], hover_color="#3a7ab0",
                     command=self._show_insights).pack(side="left", padx=(4, 0))
        
        self.refresh_data_btn = ctk.CTkButton(inner, text="Refresh Data", width=100, height=34, corner_radius=6,
                     font=ctk.CTkFont(size=12), fg_color=COLORS["border"], hover_color="#4a4a4a",
                     command=self._refresh_displayed_data)
        self.refresh_data_btn.pack(side="left", padx=(4, 0))
        
        ctk.CTkButton(inner, text="Close", width=65, height=34, corner_radius=6,
                     font=ctk.CTkFont(size=12), fg_color="#4a4a4a", hover_color="#5a5a5a",
                     command=self._on_close).pack(side="right")
    
    def _get_last_refresh_time_display(self) -> str:
        """Get formatted last refresh time."""
        if state.last_refresh_status == "NotSignedIn":
            return "Sign in to view"
        end_time = state.last_refresh_info.get("endTime")
        if end_time:
            return format_datetime(parse_datetime(end_time))
        return "Not checked yet"
    
    def _open_powerbi(self):
        """Open Power BI in browser."""
        url = f"https://app.powerbi.com/groups/{state.workspace_id}/datasets/{state.dataset_id}/details"
        webbrowser.open(url)
    
    def _refresh_now(self):
        """Trigger a refresh."""
        def do_refresh():
            success, message = trigger_refresh()
            if success:
                show_notification("⟳ Refresh Started", "A new refresh has been triggered.")
                time.sleep(3)
                from ..core import update_refresh_status
                update_refresh_status()
            else:
                show_notification("Refresh Failed", message, is_error=True)
        
        threading.Thread(target=do_refresh, daemon=True).start()
        self._on_close()
    
    def _cancel_refresh(self):
        """Cancel a refresh."""
        def do_cancel():
            success, message = cancel_refresh()
            if success:
                show_notification("Refresh Cancelled", "The in-progress refresh was cancelled.")
                time.sleep(2)
                from ..core import update_refresh_status
                update_refresh_status()
            else:
                show_notification("Cancel Failed", message, is_error=True)
        
        threading.Thread(target=do_cancel, daemon=True).start()
        self._on_close()
    
    def _show_insights(self):
        """Show the AI Insights window."""
        show_insights_window(self.window)
    
    def _refresh_displayed_data(self):
        """Refresh all displayed data by fetching fresh data from APIs."""
        # Show loading state
        if hasattr(self, 'refresh_data_btn'):
            self.refresh_data_btn.configure(text="Refreshing...", state="disabled")
        
        def do_refresh():
            from ..core import update_refresh_status
            update_refresh_status()
            
            # Update UI on main thread if window still open
            if self._window_open and self.window:
                try:
                    self.window.after(0, self._on_refresh_complete)
                except:
                    pass
        
        threading.Thread(target=do_refresh, daemon=True).start()
    
    def _on_refresh_complete(self):
        """Called when data refresh is complete."""
        # Reset button state
        if hasattr(self, 'refresh_data_btn'):
            self.refresh_data_btn.configure(text="Refresh Data", state="normal")
        
        # Update the displayed data
        self._update_displayed_data()
    
    def _update_displayed_data(self):
        """Update the displayed data in the UI (called on main thread)."""
        if not self._window_open or not self.window:
            return
        
        # Update capacity data from state
        if state.capacity_metrics:
            self.capacity_data = state.capacity_metrics.copy()
            self._update_capacity_from_cached_data()
        
        # For other sections, we'd need to rebuild them or store references
        # For now, show a notification that data was refreshed
        log("Displayed data refreshed from latest state")
    
    def _sign_in(self):
        """Trigger sign in."""
        self._on_close()
        def do_signin():
            token = get_access_token_interactive()
            if token:
                from ..core import update_refresh_status
                update_refresh_status()
        threading.Thread(target=do_signin, daemon=True).start()
    
    def _show_settings(self):
        """Show settings dialog."""
        from .settings_dialog import show_settings_dialog
        show_settings_dialog(self.window, self._on_close)
    
    def _on_close(self):
        """Handle window close."""
        self._window_open = False  # Set flag first to stop background threads
        
        # Stop background capacity update thread
        self._capacity_update_stop.set()
        if self._capacity_update_thread and self._capacity_update_thread.is_alive():
            self._capacity_update_thread.join(timeout=2)
        
        if self.window:
            self.window.quit()
            self.window.destroy()
            self.window = None
    
    def _background_capacity_update(self):
        """Background thread that updates capacity metrics every 5 minutes."""
        while not self._capacity_update_stop.wait(timeout=300):  # 300 seconds = 5 minutes
            try:
                if state.capacity_metrics_workspace:
                    metrics = CapacityMetrics(state.capacity_metrics_workspace)
                    util = metrics.get_utilization()
                    if util:
                        raw_pct = util.get("[UtilizationPct]", util.get("UtilizationPct", 0)) or 0
                        pct = raw_pct * 100
                        bg_pct = (util.get("[BackgroundPct]", util.get("BackgroundPct", 0)) or 0) * 100
                        int_pct = (util.get("[InteractivePct]", util.get("InteractivePct", 0)) or 0) * 100
                        
                        # Update local copy
                        self.capacity_data = {
                            "utilization": pct,
                            "background": bg_pct,
                            "interactive": int_pct,
                        }
                        
                        # Also update state for menu
                        state.capacity_metrics = self.capacity_data.copy()
                        
                        # Update UI if window still exists
                        if self.window and self.window.winfo_exists():
                            self.window.after(0, self._refresh_capacity_display)
                            
                        log(f"Capacity updated: {pct:.1f}% (BG: {bg_pct:.1f}%, Int: {int_pct:.1f}%)")
            except Exception as e:
                log(f"Error updating capacity in details window: {e}")
    
    def _refresh_capacity_display(self):
        """Refresh the capacity metrics display in the UI."""
        if self.capacity_data:
            util = self.capacity_data.get("utilization", 0)
            bg = self.capacity_data.get("background", 0)
            int_pct = self.capacity_data.get("interactive", 0)
            
            # Update the capacity labels if they exist
            # This would be called by the capacity info section
            self.window = None
