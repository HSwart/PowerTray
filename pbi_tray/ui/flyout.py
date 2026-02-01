"""
Tray Flyout - Modern OneDrive-style popup near the system tray.
"""

import json
import os
import subprocess
import sys
import webbrowser

from ..config import state
from ..api import get_refresh_details, CapacityMetrics
from ..utils import log, format_datetime, parse_datetime, format_duration
from ..utils.datetime_helpers import get_refresh_type_display
from .theme import COLORS, get_status_color


class TrayFlyout:
    """A modern flyout popup that appears near the system tray."""
    
    _instance = None
    _window = None
    _pending_show = False
    
    @classmethod
    def toggle(cls):
        """Toggle the flyout visibility."""
        if cls._window is not None:
            try:
                cls._window.destroy()
            except:
                pass
            cls._window = None
            return
        
        cls.show()
    
    @classmethod
    def show(cls):
        """Show the flyout near the system tray."""
        if cls._window is not None:
            try:
                cls._window.lift()
                cls._window.focus_force()
                return
            except:
                pass
        
        # Create window via subprocess to avoid threading issues
        cls._create_window_standalone()
    
    @classmethod
    def _create_window_standalone(cls):
        """Create the flyout window as a standalone process to avoid threading issues."""
        # Launch a separate Python process to show the flyout
        flyout_code = '''
import customtkinter as ctk
import tkinter as tk
import json
import webbrowser
import sys
import os

# Read data from stdin
data = json.loads(sys.stdin.read())
parent_pid = data.get("parent_pid")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def get_status_color(status):
    status_lower = status.lower() if status else ""
    colors = {
        "completed": "#009180", "success": "#009180",
        "failed": "#D60029", "error": "#D60029",
        "unknown": "#fbc02d", "inprogress": "#2d6491",
        "disabled": "#6a9ab8", "cancelled": "#6a9ab8",
        "not signed in": "#fbc02d",
    }
    return colors.get(status_lower, "#6a9ab8")

def check_parent():
    """Close if parent process died."""
    try:
        os.kill(parent_pid, 0)  # Check if parent alive
        window.after(1000, check_parent)
    except:
        window.destroy()

window = ctk.CTk()
window.title("")
window.overrideredirect(True)
window.attributes("-topmost", True)

# Compact size - dynamic height based on capacity and AI sections
base_height = 280
if data.get("capacity"):
    base_height = 360  # Extra height for capacity section
if data.get("ai_analysis"):
    base_height += 80  # Extra height for AI insights section
if data.get("capacity_insights"):
    base_height += 100  # Extra height for capacity insights section
width, height = 320, base_height
screen_width = window.winfo_screenwidth()
screen_height = window.winfo_screenheight()
x = screen_width - width - 12
y = screen_height - height - 52
window.geometry(f"{width}x{height}+{x}+{y}")

# Start parent check
window.after(1000, check_parent)

# Brand colors
BG_DARK = "#00334e"
BG_HEADER = "#2d6491"
TEXT_MUTED = "#6a9ab8"
TEXT_SEC = "#a8c8dc"
BORDER = "#2d6491"

main = ctk.CTkFrame(window, corner_radius=10, fg_color=BG_DARK)
main.pack(fill="both", expand=True, padx=1, pady=1)

# Header row
header = ctk.CTkFrame(main, fg_color="transparent", height=36)
header.pack(fill="x", padx=12, pady=(10, 6))
header.pack_propagate(False)

ctk.CTkLabel(header, text="Power BI Refresh", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")

status_color = get_status_color(data["status"])
badge = ctk.CTkFrame(header, fg_color=status_color, corner_radius=4)
badge.pack(side="right")
ctk.CTkLabel(badge, text=data["status"], font=ctk.CTkFont(size=10), text_color="white").pack(padx=6, pady=2)

# Divider
ctk.CTkFrame(main, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=4)

# Main info - compact rows
info_frame = ctk.CTkFrame(main, fg_color="transparent")
info_frame.pack(fill="x", padx=12, pady=4)

def add_row(parent, label, value, bold=False, value_color=None):
    row = ctk.CTkFrame(parent, fg_color="transparent", height=22)
    row.pack(fill="x", pady=1)
    row.pack_propagate(False)
    ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=11), text_color=TEXT_MUTED, width=100, anchor="w").pack(side="left")
    font = ctk.CTkFont(size=11, weight="bold") if bold else ctk.CTkFont(size=11)
    color = value_color if value_color else ("white" if bold else TEXT_SEC)
    ctk.CTkLabel(row, text=value, font=font, text_color=color, anchor="w").pack(side="left", fill="x", expand=True)

add_row(info_frame, "Last Refresh", data["last_refresh"], bold=True)
add_row(info_frame, "Type", data["refresh_type"])
add_row(info_frame, "Duration", data["duration"])
add_row(info_frame, "Timezone", data["timezone"])

# Capacity Section (if available)
if data.get("capacity"):
    # Divider before capacity
    ctk.CTkFrame(main, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=4)
    
    # Capacity header
    cap_header = ctk.CTkFrame(main, fg_color="transparent")
    cap_header.pack(fill="x", padx=12, pady=(2, 4))
    ctk.CTkLabel(cap_header, text="⚡ Fabric Capacity", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SEC).pack(side="left")
    
    cap = data["capacity"]
    cap_color = {"critical": "#D60029", "warning": "#fbc02d", "normal": "#009180"}.get(cap["status"], TEXT_MUTED)
    status_icon = {"critical": "🔴", "warning": "🟡", "normal": "🟢"}.get(cap["status"], "⚪")
    
    cap_badge = ctk.CTkFrame(cap_header, fg_color=cap_color, corner_radius=4)
    cap_badge.pack(side="right")
    ctk.CTkLabel(cap_badge, text=cap["status"].capitalize(), font=ctk.CTkFont(size=9, weight="bold"), text_color="white").pack(padx=5, pady=1)
    
    # Capacity details
    cap_frame = ctk.CTkFrame(main, fg_color="transparent")
    cap_frame.pack(fill="x", padx=12, pady=2)
    
    # Utilization with progress bar
    util_row = ctk.CTkFrame(cap_frame, fg_color="transparent", height=22)
    util_row.pack(fill="x", pady=1)
    util_row.pack_propagate(False)
    ctk.CTkLabel(util_row, text="Utilization", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED, width=70, anchor="w").pack(side="left")
    
    # Mini progress bar
    bar_bg = ctk.CTkFrame(util_row, fg_color=BG_DARK, corner_radius=3, width=80, height=10)
    bar_bg.pack(side="left", padx=(5, 8), pady=6)
    bar_bg.pack_propagate(False)
    pct_val = float(cap["utilization"].replace("%", "")) / 100
    bar_fill = ctk.CTkFrame(bar_bg, fg_color=cap_color, corner_radius=3)
    bar_fill.place(relx=0, rely=0, relwidth=min(pct_val, 1.0), relheight=1)
    
    ctk.CTkLabel(util_row, text=cap["utilization"], font=ctk.CTkFont(size=11, weight="bold"), text_color=cap_color, anchor="w").pack(side="left")
    
    # Background vs Interactive breakdown
    breakdown_row = ctk.CTkFrame(cap_frame, fg_color="transparent", height=20)
    breakdown_row.pack(fill="x", pady=1)
    breakdown_row.pack_propagate(False)
    ctk.CTkLabel(breakdown_row, text=f"BG: {cap.get('bg_pct', '--')}  |  Int: {cap.get('int_pct', '--')}", 
                 font=ctk.CTkFont(size=10), text_color=TEXT_MUTED).pack(side="left", padx=(75, 0))

# Divider
ctk.CTkFrame(main, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=6)

# Recent history - compact list
ctk.CTkLabel(main, text="Recent History", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SEC).pack(anchor="w", padx=12)

hist_frame = ctk.CTkFrame(main, fg_color="transparent")
hist_frame.pack(fill="x", padx=12, pady=(4, 8))

for h in data["history"][:3]:  # Only show 3 items
    row = ctk.CTkFrame(hist_frame, fg_color="transparent", height=20)
    row.pack(fill="x", pady=1)
    row.pack_propagate(False)
    
    color = get_status_color(h["status"])
    dot = tk.Canvas(row, width=8, height=8, bg=BG_DARK, highlightthickness=0)
    dot.pack(side="left", padx=(0, 6), pady=6)
    dot.create_oval(0, 0, 8, 8, fill=color, outline="")
    
    ctk.CTkLabel(row, text=h["status"].capitalize(), font=ctk.CTkFont(size=10), width=60, anchor="w").pack(side="left")
    ctk.CTkLabel(row, text=h["time"], font=ctk.CTkFont(size=10), text_color=TEXT_MUTED).pack(side="left", fill="x", expand=True)
    ctk.CTkLabel(row, text=h["type"], font=ctk.CTkFont(size=10), text_color=TEXT_MUTED).pack(side="right")

# AI Insights Section (if last refresh failed and analysis available)
if data.get("ai_analysis"):
    ctk.CTkFrame(main, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=4)
    
    ai = data["ai_analysis"]
    severity_colors = {"low": "#fbc02d", "medium": "#ff9800", "high": "#ff5722", "critical": "#D60029"}
    severity_color = severity_colors.get(ai.get("severity", "medium"), "#ff9800")
    
    # AI header
    ai_header = ctk.CTkFrame(main, fg_color="transparent")
    ai_header.pack(fill="x", padx=12, pady=(2, 4))
    ctk.CTkLabel(ai_header, text="🤖 AI Analysis", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SEC).pack(side="left")
    
    sev_badge = ctk.CTkFrame(ai_header, fg_color=severity_color, corner_radius=4)
    sev_badge.pack(side="right")
    ctk.CTkLabel(sev_badge, text=ai.get("severity", "").upper(), font=ctk.CTkFont(size=9, weight="bold"), text_color="white").pack(padx=5, pady=1)
    
    # Summary
    ai_frame = ctk.CTkFrame(main, fg_color="transparent")
    ai_frame.pack(fill="x", padx=12, pady=2)
    
    summary_text = ai.get("summary", "")[:100]
    if len(ai.get("summary", "")) > 100:
        summary_text += "..."
    ctk.CTkLabel(ai_frame, text=summary_text, font=ctk.CTkFont(size=10), text_color=TEXT_SEC, wraplength=290, justify="left").pack(anchor="w")
    
    # First suggestion
    suggestions = ai.get("suggestions", [])
    if suggestions:
        tip_text = f"💡 {suggestions[0][:80]}"
        if len(suggestions[0]) > 80:
            tip_text += "..."
        ctk.CTkLabel(ai_frame, text=tip_text, font=ctk.CTkFont(size=9), text_color=TEXT_MUTED, wraplength=290, justify="left").pack(anchor="w", pady=(4, 0))

# Capacity Insights Section (AI-powered analysis, always visible if available)
if data.get("capacity_insights"):
    ctk.CTkFrame(main, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=4)
    
    ci = data["capacity_insights"]
    status_colors = {"healthy": "#009180", "warning": "#fbc02d", "critical": "#D60029", "unknown": TEXT_MUTED}
    status_icons = {"healthy": "✅", "warning": "⚠️", "critical": "🚨", "unknown": "❓"}
    trend_icons = {"increasing": "📈", "decreasing": "📉", "stable": "➡️"}
    
    ci_status = ci.get("status", "unknown")
    ci_color = status_colors.get(ci_status, TEXT_MUTED)
    
    # Capacity Insights header
    ci_header = ctk.CTkFrame(main, fg_color="transparent")
    ci_header.pack(fill="x", padx=12, pady=(2, 4))
    ctk.CTkLabel(ci_header, text="✨ Capacity Insights", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SEC).pack(side="left")
    
    ci_badge = ctk.CTkFrame(ci_header, fg_color=ci_color, corner_radius=4)
    ci_badge.pack(side="right")
    ctk.CTkLabel(ci_badge, text=ci_status.capitalize(), font=ctk.CTkFont(size=9, weight="bold"), text_color="white").pack(padx=5, pady=1)
    
    # Summary and trend
    ci_frame = ctk.CTkFrame(main, fg_color="transparent")
    ci_frame.pack(fill="x", padx=12, pady=2)
    
    # Trend line
    trend = ci.get("trend", "stable")
    trend_pct = ci.get("trend_pct", 0)
    trend_icon = trend_icons.get(trend, "➡️")
    trend_text = f"{trend_icon} {'+' if trend_pct > 0 else ''}{trend_pct:.0f}% vs prior • Avg: {ci.get('avg_utilization', 0):.1f}%"
    ctk.CTkLabel(ci_frame, text=trend_text, font=ctk.CTkFont(size=10), text_color=TEXT_SEC).pack(anchor="w")
    
    # Summary
    summary_text = ci.get("summary", "")[:120]
    if len(ci.get("summary", "")) > 120:
        summary_text += "..."
    ctk.CTkLabel(ci_frame, text=summary_text, font=ctk.CTkFont(size=10), text_color=TEXT_MUTED, wraplength=290, justify="left").pack(anchor="w", pady=(2, 0))
    
    # First recommendation
    recs = ci.get("recommendations", [])
    if recs:
        rec_text = f"💡 {recs[0][:75]}"
        if len(recs[0]) > 75:
            rec_text += "..."
        ctk.CTkLabel(ci_frame, text=rec_text, font=ctk.CTkFont(size=9), text_color="#4a90d9", wraplength=290, justify="left").pack(anchor="w", pady=(4, 0))

# Footer buttons
footer = ctk.CTkFrame(main, fg_color="transparent")
footer.pack(fill="x", padx=12, pady=(0, 10))

def open_pbi():
    webbrowser.open(data["pbi_url"])
    window.destroy()

ctk.CTkButton(footer, text="Open in Power BI", width=120, height=28, corner_radius=4, fg_color=BG_HEADER, hover_color="#3a7ab0", font=ctk.CTkFont(size=11), command=open_pbi).pack(side="left")
ctk.CTkButton(footer, text="Close", width=60, height=28, corner_radius=4, fg_color="#184d47", hover_color="#1a5c54", font=ctk.CTkFont(size=11), command=window.destroy).pack(side="right")

window.bind("<Escape>", lambda e: window.destroy())
window.bind("<FocusOut>", lambda e: window.destroy())
window.mainloop()
'''
        
        # Prepare data for the flyout
        history_data = []
        for h in state.refresh_history[:3]:
            history_data.append({
                "status": h.get("status", "Unknown"),
                "time": format_datetime(parse_datetime(h.get("endTime"))),
                "type": get_refresh_type_display(h.get("refreshType"))
            })
        
        # Get capacity metrics if available
        capacity_data = None
        try:
            if state.capacity_metrics_workspace:
                metrics = CapacityMetrics(state.capacity_metrics_workspace)
                util = metrics.get_utilization()
                if util:
                    # API returns decimals with bracket keys, multiply by 100 for percentage
                    raw_pct = util.get("[UtilizationPct]", util.get("UtilizationPct", 0)) or 0
                    pct = raw_pct * 100
                    raw_bg = util.get("[BackgroundPct]", util.get("BackgroundPct", 0)) or 0
                    raw_int = util.get("[InteractivePct]", util.get("InteractivePct", 0)) or 0
                    bg_pct = raw_bg * 100
                    int_pct = raw_int * 100
                    capacity_data = {
                        "utilization": f"{pct:.1f}%",
                        "bg_pct": f"{bg_pct:.1f}%",
                        "int_pct": f"{int_pct:.1f}%",
                        "status": "critical" if pct >= 100 else ("warning" if pct >= 80 else "normal")
                    }
        except Exception as e:
            log(f"Error getting capacity metrics for flyout: {e}")
        
        # Get AI analysis if available (from last failed refresh)
        ai_analysis_data = None
        if state.last_refresh_status == "Failed":
            ai_analysis_data = state.last_refresh_info.get("ai_analysis")
        
        # Get capacity insights if available
        capacity_insights_data = None
        if state.capacity_insights:
            ci = state.capacity_insights
            capacity_insights_data = {
                "status": ci.get("status", "unknown"),
                "summary": ci.get("summary", ""),
                "trend": ci.get("trend", "stable"),
                "trend_pct": ci.get("statistics", {}).get("trend_pct", 0),
                "recommendations": ci.get("recommendations", [])[:3],
                "avg_utilization": ci.get("statistics", {}).get("average_utilization", 0),
                "max_utilization": ci.get("statistics", {}).get("max_utilization", 0),
            }
        
        flyout_data = json.dumps({
            "status": state.last_refresh_status,
            "last_refresh": _get_last_refresh_time_display(),
            "refresh_type": get_refresh_type_display(state.last_refresh_info.get('refreshType', 'N/A')),
            "duration": format_duration(state.last_refresh_info.get('startTime'), state.last_refresh_info.get('endTime')),
            "timezone": state.selected_timezone,
            "history": history_data,
            "capacity": capacity_data,
            "capacity_insights": capacity_insights_data,
            "ai_analysis": ai_analysis_data,
            "pbi_url": f"https://app.powerbi.com/groups/{state.workspace_id}/datasets/{state.dataset_id}/details",
            "authenticated": state.last_refresh_status != "NotSignedIn",
            "parent_pid": os.getpid()
        })
        
        # Run in subprocess
        try:
            process = subprocess.Popen(
                [sys.executable, "-c", flyout_code],
                stdin=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if process.stdin is not None:
                process.stdin.write(flyout_data.encode())
                process.stdin.close()
        except Exception as e:
            log(f"Error creating flyout subprocess: {e}")
    
    @classmethod
    def _close(cls):
        """Close the flyout."""
        if cls._window:
            try:
                cls._window.quit()
                cls._window.destroy()
            except:
                pass
            cls._window = None


def _get_last_refresh_time_display() -> str:
    """Get formatted last refresh time for display."""
    if state.last_refresh_status == "NotSignedIn":
        return "Sign in to view"
    end_time = state.last_refresh_info.get("endTime")
    if end_time:
        return format_datetime(parse_datetime(end_time))
    return "Not checked yet"
