"""
AI Insights Window - Displays capacity analysis and recommendations.
"""

import threading
import webbrowser
from datetime import datetime

import customtkinter as ctk

from ..config import state, ICO_PATH
from ..utils import log
from ..utils.ai_insights import analyze_capacity, is_ai_enabled, _execute_capacity_dax, _DAX_CAPACITY_DETAILS
from .theme import COLORS


class InsightsWindow:
    """A window showing AI-powered capacity insights and recommendations."""
    
    _instance = None
    
    def __init__(self, parent_window=None):
        self.window = None
        self.parent = parent_window
        self._loading = False
        self._available_capacities: list[str] = []
        self._selected_capacity = ctk.StringVar(value=state.selected_capacity or "All Capacities")
    
    @classmethod
    def show(cls, parent_window=None):
        """Show the insights window (singleton pattern)."""
        log("[InsightsWindow] show() called")
        if cls._instance is None or cls._instance.window is None:
            log("[InsightsWindow] Creating new instance")
            cls._instance = cls(parent_window)
            cls._instance._create_window()
        else:
            try:
                log("[InsightsWindow] Lifting existing window")
                cls._instance.window.lift()
                cls._instance.window.focus_force()
            except:
                log("[InsightsWindow] Existing window invalid, recreating")
                cls._instance = cls(parent_window)
                cls._instance._create_window()
    
    def _create_window(self):
        """Create the insights window."""
        if self.parent:
            self.window = ctk.CTkToplevel(self.parent)
            self.window.transient(self.parent)
        else:
            self.window = ctk.CTkToplevel()
        
        self.window.title("✨ Capacity Insights")
        self.window.geometry("550x650")
        self.window.resizable(True, True)
        self.window.minsize(450, 500)
        self.window.configure(fg_color=COLORS["bg_dark"])
        self.window.attributes("-topmost", True)
        
        # Set window icon
        if ICO_PATH.exists():
            try:
                self.window.iconbitmap(str(ICO_PATH))
            except Exception as e:
                log(f"Icon error: {e}")
        
        # Header
        self._create_header()
        
        # Main content (scrollable)
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.window,
            fg_color="transparent",
            corner_radius=0
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Initial content
        if state.capacity_insights:
            self._display_insights(state.capacity_insights)
        else:
            self._show_empty_state()
        
        # Footer
        self._create_footer()
        
        # Center on screen
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - 275
        y = (self.window.winfo_screenheight() // 2) - 325
        self.window.geometry(f"+{x}+{y}")
        
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self.window.focus_force()
    
    def _create_header(self):
        """Create header with title, capacity selector and status."""
        header = ctk.CTkFrame(self.window, height=120, corner_radius=0, fg_color=COLORS["bg_header"])
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Top row: Title and Status
        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x")
        
        # Left: Title
        left = ctk.CTkFrame(top_row, fg_color="transparent")
        left.pack(side="left", fill="y")
        
        ctk.CTkLabel(
            left,
            text="✨ Capacity Insights",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(anchor="w")
        
        # Subtitle with last updated time
        if state.capacity_insights:
            generated = state.capacity_insights.get("generated_at", "")
            selected_cap = state.capacity_insights.get("selected_capacity", "All Capacities")
            if generated:
                try:
                    dt = datetime.fromisoformat(generated)
                    time_str = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    time_str = "Unknown"
            else:
                time_str = "Unknown"
        else:
            time_str = "Not analyzed yet"
            selected_cap = "All Capacities"
        
        ctk.CTkLabel(
            left,
            text=f"Updated: {time_str} | {selected_cap}",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"]
        ).pack(anchor="w")
        
        # Right: Status badge
        if state.capacity_insights:
            status = state.capacity_insights.get("status", "unknown")
            status_colors = {
                "healthy": "#009180",
                "warning": "#fbc02d", 
                "critical": "#D60029",
                "unknown": COLORS["text_muted"]
            }
            badge_color = status_colors.get(status, COLORS["text_muted"])
            
            badge = ctk.CTkFrame(top_row, fg_color=badge_color, corner_radius=6)
            badge.pack(side="right", pady=4)
            
            ctk.CTkLabel(
                badge,
                text=status.upper(),
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="white"
            ).pack(padx=10, pady=4)
        
        # Bottom row: Capacity selector
        selector_row = ctk.CTkFrame(inner, fg_color="transparent")
        selector_row.pack(fill="x", pady=(8, 0))
        
        ctk.CTkLabel(
            selector_row,
            text="Capacity:",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"]
        ).pack(side="left")
        
        # Fetch available capacities
        self._load_available_capacities()
        
        capacity_options = ["All Capacities"] + self._available_capacities
        self.capacity_dropdown = ctk.CTkOptionMenu(
            selector_row,
            values=capacity_options,
            variable=self._selected_capacity,
            command=self._on_capacity_changed,
            width=250,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=COLORS["bg_card"],
            button_color=COLORS["bg_header"],
            dropdown_fg_color=COLORS["bg_card"]
        )
        self.capacity_dropdown.pack(side="left", padx=(8, 0))
    
    def _load_available_capacities(self):
        """Load available capacities from the metrics dataset."""
        log("[InsightsWindow] Loading available capacities...")
        if not state.capacity_metrics_workspace:
            log("[InsightsWindow] No capacity_metrics_workspace configured")
            self._available_capacities = []
            return
        
        try:
            capacity_data = _execute_capacity_dax(state.capacity_metrics_workspace, _DAX_CAPACITY_DETAILS)
            names = []
            for cap in capacity_data:
                name = cap.get("[CapacityName]") or cap.get("Capacities[Capacity name]")
                if name:
                    names.append(name)
            self._available_capacities = sorted(names)
            log(f"[InsightsWindow] Found {len(self._available_capacities)} capacities: {self._available_capacities}")
        except Exception as e:
            log(f"[InsightsWindow] Failed to load capacities: {e}")
            self._available_capacities = []
    
    def _on_capacity_changed(self, choice: str):
        """Handle capacity dropdown selection change."""
        log(f"[InsightsWindow] Capacity changed to: {choice}")
        if choice == "All Capacities":
            state.selected_capacity = ""
        else:
            state.selected_capacity = choice
        log(f"[InsightsWindow] state.selected_capacity = '{state.selected_capacity}'")
        # Don't auto-analyze - user must click Analyze Now
    
    def _show_empty_state(self):
        """Show empty state when no insights available."""
        # Clear existing content
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        empty_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        empty_frame.pack(fill="both", expand=True, pady=50)
        
        ctk.CTkLabel(
            empty_frame,
            text="📊",
            font=ctk.CTkFont(size=48)
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            empty_frame,
            text="Capacity Insights",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text_primary"]
        ).pack(pady=5)
        
        # Show instructions
        instructions = "1. Select a capacity from the dropdown above\n2. Click 'Analyze Now' to run analysis\n\nAnalysis includes utilization trends, peak hours,\nand AI-powered recommendations."
        
        ctk.CTkLabel(
            empty_frame,
            text=instructions,
            font=ctk.CTkFont(size=12),
            text_color=COLORS["text_muted"],
            justify="center"
        ).pack(pady=10)
        
        if not state.capacity_metrics_workspace:
            ctk.CTkLabel(
                empty_frame,
                text="⚠️ Configure 'capacity_metrics_workspace' in Settings first",
                font=ctk.CTkFont(size=11),
                text_color="#fbc02d"
            ).pack(pady=10)
    
    def _display_insights(self, insights: dict):
        """Display the capacity insights."""
        # Clear existing content
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()
        
        if not insights:
            self._show_empty_state()
            return
        
        # === SUMMARY SECTION ===
        self._create_section_header("Summary")
        
        summary_card = ctk.CTkFrame(self.scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
        summary_card.pack(fill="x", padx=15, pady=(0, 15))
        
        summary_text = insights.get("summary", "No summary available")
        ctk.CTkLabel(
            summary_card,
            text=summary_text,
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text_primary"],
            wraplength=480,
            justify="left"
        ).pack(padx=15, pady=15, anchor="w")
        
        # === STATISTICS SECTION ===
        self._create_section_header("Statistics")
        
        stats_card = ctk.CTkFrame(self.scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
        stats_card.pack(fill="x", padx=15, pady=(0, 15))
        
        stats = insights.get("statistics", {})
        stats_inner = ctk.CTkFrame(stats_card, fg_color="transparent")
        stats_inner.pack(fill="x", padx=15, pady=12)
        
        # Grid of stats - now with background/interactive breakdown
        bg_pct = stats.get('background_pct', 0)
        inter_pct = stats.get('interactive_pct', 0)
        total_cu = stats.get('total_cu_seconds', 0)
        
        stats_data = [
            ("Average Utilization", f"{stats.get('average_utilization', 0):.1f}%"),
            ("Peak Utilization", f"{stats.get('max_utilization', 0):.1f}%"),
            ("Minimum Utilization", f"{stats.get('min_utilization', 0):.1f}%"),
            ("Background Usage", f"{bg_pct:.1f}%"),
            ("Interactive Usage", f"{inter_pct:.1f}%"),
            ("Total CU (seconds)", f"{total_cu:,.0f}"),
            ("Trend (vs prior)", f"{'+' if stats.get('trend_pct', 0) > 0 else ''}{stats.get('trend_pct', 0):.1f}%"),
            ("Data Points", f"{stats.get('data_points', 0)} days"),
            ("Anomalies Detected", str(len(stats.get('anomalies', [])))),
        ]
        
        for i, (label, value) in enumerate(stats_data):
            row = ctk.CTkFrame(stats_inner, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            ctk.CTkLabel(
                row,
                text=label,
                font=ctk.CTkFont(size=11),
                text_color=COLORS["text_muted"],
                width=150,
                anchor="w"
            ).pack(side="left")
            
            ctk.CTkLabel(
                row,
                text=value,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=COLORS["text_primary"],
                anchor="w"
            ).pack(side="left", padx=10)
        
        # === HOURLY PATTERNS ===
        hourly = insights.get("hourly_patterns", {})
        if hourly.get("peak_hours") or hourly.get("off_peak_hours"):
            self._create_section_header("Hourly Patterns")
            
            patterns_card = ctk.CTkFrame(self.scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
            patterns_card.pack(fill="x", padx=15, pady=(0, 15))
            
            patterns_inner = ctk.CTkFrame(patterns_card, fg_color="transparent")
            patterns_inner.pack(fill="x", padx=15, pady=12)
            
            # Peak hours
            peak_hours = hourly.get("peak_hours", [])
            if peak_hours:
                peak_text = ", ".join([f"{h['hour']}:00 ({h['avg_utilization']:.1f}%)" for h in peak_hours[:3]])
                self._add_pattern_row(patterns_inner, "📈 Peak Hours", peak_text)
            
            # Off-peak hours
            off_peak = hourly.get("off_peak_hours", [])
            if off_peak:
                off_text = ", ".join([f"{h['hour']}:00 ({h['avg_utilization']:.1f}%)" for h in off_peak[:3]])
                self._add_pattern_row(patterns_inner, "📉 Off-Peak Hours", off_text)
        
        # === RECOMMENDATIONS ===
        recs = insights.get("recommendations", [])
        if recs:
            self._create_section_header(f"Recommendations ({len(recs)})")
            
            for i, rec in enumerate(recs, 1):
                rec_card = ctk.CTkFrame(self.scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
                rec_card.pack(fill="x", padx=15, pady=(0, 8))
                
                rec_inner = ctk.CTkFrame(rec_card, fg_color="transparent")
                rec_inner.pack(fill="x", padx=12, pady=10)
                
                # Number badge
                badge = ctk.CTkFrame(rec_inner, fg_color=COLORS["accent_blue"], corner_radius=4, width=24, height=24)
                badge.pack(side="left", padx=(0, 10))
                badge.pack_propagate(False)
                
                ctk.CTkLabel(
                    badge,
                    text=str(i),
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="white"
                ).pack(expand=True)
                
                # Recommendation text (full, wrapped)
                ctk.CTkLabel(
                    rec_inner,
                    text=rec,
                    font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_primary"],
                    wraplength=450,
                    justify="left",
                    anchor="w"
                ).pack(side="left", fill="x", expand=True)
        
        # === CAPACITIES ===
        capacities = insights.get("capacities", [])
        if capacities:
            self._create_section_header("Capacities")
            
            cap_card = ctk.CTkFrame(self.scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
            cap_card.pack(fill="x", padx=15, pady=(0, 15))
            
            cap_inner = ctk.CTkFrame(cap_card, fg_color="transparent")
            cap_inner.pack(fill="x", padx=15, pady=12)
            
            for cap in capacities:
                row = ctk.CTkFrame(cap_inner, fg_color="transparent")
                row.pack(fill="x", pady=3)
                
                name = cap.get("name", "Unknown")
                if len(name) > 30:
                    name = name[:27] + "..."
                
                ctk.CTkLabel(
                    row,
                    text=f"⚡ {name}",
                    font=ctk.CTkFont(size=11),
                    text_color=COLORS["text_primary"],
                    anchor="w"
                ).pack(side="left")
                
                sku = cap.get("sku", "?")
                region = cap.get("region", "?")
                ctk.CTkLabel(
                    row,
                    text=f"{sku} • {region}",
                    font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_muted"]
                ).pack(side="right")
        
        # === TOP WORKSPACES ===
        workspaces = insights.get("top_workspaces", [])
        if workspaces:
            self._create_section_header("Top Workspaces")
            
            ws_card = ctk.CTkFrame(self.scroll_frame, corner_radius=8, fg_color=COLORS["bg_card"])
            ws_card.pack(fill="x", padx=15, pady=(0, 15))
            
            ws_inner = ctk.CTkFrame(ws_card, fg_color="transparent")
            ws_inner.pack(fill="x", padx=15, pady=12)
            
            for ws in workspaces[:5]:
                row = ctk.CTkFrame(ws_inner, fg_color="transparent")
                row.pack(fill="x", pady=2)
                
                ws_name = ws.get("workspace", "Unknown")
                if len(ws_name) > 35:
                    ws_name = ws_name[:32] + "..."
                
                ctk.CTkLabel(
                    row,
                    text=ws_name,
                    font=ctk.CTkFont(size=11),
                    text_color=COLORS["text_primary"],
                    anchor="w"
                ).pack(side="left")
                
                item_kind = ws.get("item_kind", "")
                count = ws.get("item_count", 0)
                ctk.CTkLabel(
                    row,
                    text=f"{count} {item_kind}",
                    font=ctk.CTkFont(size=10),
                    text_color=COLORS["text_muted"]
                ).pack(side="right")
        
        # Bottom padding
        ctk.CTkFrame(self.scroll_frame, height=20, fg_color="transparent").pack()
    
    def _create_section_header(self, title: str):
        """Create a section header."""
        ctk.CTkLabel(
            self.scroll_frame,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["accent_blue"]
        ).pack(padx=15, pady=(15, 8), anchor="w")
    
    def _add_pattern_row(self, parent, label: str, value: str):
        """Add a row to the patterns section."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=3)
        
        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_muted"],
            width=120,
            anchor="w"
        ).pack(side="left")
        
        ctk.CTkLabel(
            row,
            text=value,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_primary"],
            anchor="w"
        ).pack(side="left", padx=10)
    
    def _create_footer(self):
        """Create footer with action buttons."""
        footer = ctk.CTkFrame(self.window, height=55, corner_radius=0, fg_color=COLORS["bg_header"])
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        
        inner = ctk.CTkFrame(footer, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=10)
        
        # Analyze button
        self.analyze_btn = ctk.CTkButton(
            inner,
            text="🔄 Analyze Now",
            width=120,
            height=34,
            corner_radius=6,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["accent_blue"],
            hover_color="#3a7ab0",
            command=self._analyze_now
        )
        self.analyze_btn.pack(side="left")
        
        # AI status indicator
        ai_status = "🤖 AI Enabled" if is_ai_enabled() else "📊 Rules Only"
        ai_color = "#009180" if is_ai_enabled() else COLORS["text_muted"]
        
        ctk.CTkLabel(
            inner,
            text=ai_status,
            font=ctk.CTkFont(size=10),
            text_color=ai_color
        ).pack(side="left", padx=15)
        
        # Close button
        ctk.CTkButton(
            inner,
            text="Close",
            width=70,
            height=34,
            corner_radius=6,
            font=ctk.CTkFont(size=12),
            fg_color=COLORS["border"],
            hover_color="#4a4a4a",
            command=self._on_close
        ).pack(side="right")
    
    def _analyze_now(self):
        """Run capacity analysis."""
        log("[InsightsWindow] _analyze_now() called")
        if self._loading:
            log("[InsightsWindow] Already loading, skipping")
            return
        
        if not state.capacity_metrics_workspace:
            log("[InsightsWindow] No capacity_metrics_workspace configured")
            self._show_error("Configure 'capacity_metrics_workspace' in Settings first.")
            return
        
        self._loading = True
        self.analyze_btn.configure(text="⏳ Analyzing...", state="disabled")
        
        # Get selected capacity (None for all)
        capacity_name = state.selected_capacity if state.selected_capacity else None
        log(f"[InsightsWindow] Starting analysis for capacity: {capacity_name or 'All Capacities'}")
        
        def do_analyze():
            try:
                log(f"[InsightsWindow] Calling analyze_capacity(workspace={state.capacity_metrics_workspace}, capacity={capacity_name})")
                insights = analyze_capacity(
                    state.capacity_metrics_workspace,
                    capacity_name=capacity_name,
                    use_cache=False
                )
                
                if insights:
                    log(f"[InsightsWindow] Analysis complete: status={insights.get('status')}, stats={insights.get('statistics')}")
                    state.capacity_insights = insights
                    # Update UI on main thread
                    if self.window:
                        self.window.after(0, self._refresh_display)
                else:
                    log("[InsightsWindow] Analysis returned None")
                    if self.window:
                        self.window.after(0, lambda: self._show_error("Analysis failed. Check logs."))
            except Exception as e:
                log(f"[InsightsWindow] Analysis error: {e}")
                if self.window:
                    self.window.after(0, lambda: self._show_error(f"Error: {str(e)[:50]}"))
            finally:
                self._loading = False
                if self.window:
                    self.window.after(0, lambda: self.analyze_btn.configure(text="🔄 Analyze Now", state="normal"))
        
        threading.Thread(target=do_analyze, daemon=True).start()
    
    def _refresh_display(self):
        """Refresh the display after analysis."""
        if not self.window:
            return
        
        if state.capacity_insights:
            self._display_insights(state.capacity_insights)
        
        # Update header - find and destroy old one
        for widget in self.window.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and widget.cget("height") == 120:
                widget.destroy()
                break
        
        # Recreate header
        self._create_header()
    
    def _show_error(self, message: str):
        """Show an error message."""
        if not self.window:
            return
        
        # Simple approach: show in label
        error_label = ctk.CTkLabel(
            self.scroll_frame,
            text=f"❌ {message}",
            font=ctk.CTkFont(size=12),
            text_color="#D60029"
        )
        error_label.pack(pady=10)
        
        # Auto-remove after 5 seconds
        self.window.after(5000, error_label.destroy)
    
    def _on_close(self):
        """Close the window."""
        if self.window:
            self.window.destroy()
            self.window = None
        InsightsWindow._instance = None


def show_insights_window(parent_window=None):
    """Show the insights window."""
    InsightsWindow.show(parent_window)
