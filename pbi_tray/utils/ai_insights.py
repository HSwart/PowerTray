"""
AI Insights module for Power BI Tray application.

Uses OpenAI API to provide intelligent analysis of refresh failures,
capacity issues, and recommendations.
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from functools import lru_cache


# OpenAI client (lazy loaded)
_openai_client = None

# Cache for capacity analysis results
_capacity_insights_cache: Dict[str, Any] = {}
_capacity_insights_cache_time: Optional[datetime] = None
_CAPACITY_CACHE_DURATION = timedelta(minutes=15)


def _get_openai_client():
    """Get or create OpenAI client."""
    global _openai_client
    
    if _openai_client is not None:
        return _openai_client
    
    from ..config import state
    
    if not state.openai_api_key:
        return None
    
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=state.openai_api_key)
        return _openai_client
    except ImportError:
        print("OpenAI package not installed. Run: pip install openai")
        return None
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        return None


def reset_client():
    """Reset the OpenAI client (call when API key changes)."""
    global _openai_client
    _openai_client = None


def is_ai_enabled() -> bool:
    """Check if AI features are enabled (API key configured)."""
    from ..config import state
    return bool(state.openai_api_key)


def analyze_refresh_failure(
    error_message: str,
    refresh_info: dict,
    recent_history: Optional[list] = None
) -> Optional[dict]:
    """
    Analyze a refresh failure and provide insights.
    
    Args:
        error_message: The error message from the failed refresh
        refresh_info: The full refresh info dict from Power BI API
        recent_history: Recent refresh history for pattern detection
    
    Returns:
        dict with keys:
        - summary: Brief plain-English explanation
        - cause: Likely cause of the failure
        - suggestions: List of actionable suggestions
        - severity: 'low', 'medium', 'high', 'critical'
    """
    client = _get_openai_client()
    if not client:
        return None
    
    # Build context for the AI
    context = {
        "error_message": error_message[:2000],  # Limit size
        "status": refresh_info.get("status"),
        "refresh_type": refresh_info.get("refreshType"),
        "start_time": refresh_info.get("startTime"),
        "end_time": refresh_info.get("endTime"),
    }
    
    # Add recent failure patterns if available
    if recent_history:
        recent_failures = [
            {
                "status": r.get("status"),
                "error": r.get("serviceExceptionJson", "")[:200],
                "time": r.get("endTime")
            }
            for r in recent_history[:5]
            if r.get("status") == "Failed"
        ]
        if recent_failures:
            context["recent_failures"] = recent_failures
    
    prompt = f"""Analyze this Power BI semantic model refresh failure and provide actionable insights.

Refresh Details:
{json.dumps(context, indent=2)}

Respond in JSON format with these fields:
- summary: One sentence plain-English explanation of what went wrong
- cause: The likely root cause (be specific)
- suggestions: Array of 2-4 actionable suggestions to fix the issue
- severity: "low", "medium", "high", or "critical" based on impact
- is_recurring: true if this appears to be a recurring pattern

Focus on practical, actionable advice for a Power BI administrator."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Power BI expert assistant. Analyze refresh failures and provide clear, actionable insights. Always respond with valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content or "{}")
        return result
        
    except json.JSONDecodeError as e:
        print(f"AI response parse error: {e}")
        return None
    except Exception as e:
        print(f"AI analysis error: {e}")
        return None


def analyze_capacity_trends(
    current_utilization: float,
    background_pct: float,
    interactive_pct: float,
    is_throttled: bool = False
) -> Optional[dict]:
    """
    Analyze capacity utilization and provide insights.
    
    Returns:
        dict with keys:
        - status: 'healthy', 'warning', 'critical'
        - summary: Brief assessment
        - recommendations: List of suggestions
    """
    client = _get_openai_client()
    if not client:
        return None
    
    context = {
        "total_utilization_pct": round(current_utilization, 1),
        "background_pct": round(background_pct, 1),
        "interactive_pct": round(interactive_pct, 1),
        "is_throttled": is_throttled
    }
    
    prompt = f"""Analyze this Power BI/Fabric capacity utilization:

{json.dumps(context, indent=2)}

Provide a brief JSON response with:
- status: "healthy", "warning", or "critical"
- summary: One sentence assessment
- recommendations: Array of 1-3 specific suggestions if utilization is concerning

Note: Background = scheduled refreshes, Interactive = user queries.
Throttling occurs when utilization exceeds 100%."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Power BI capacity management expert. Provide concise, actionable insights."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content or "{}")
        
    except Exception as e:
        print(f"Capacity analysis error: {e}")
        return None


def get_weekly_summary(
    refresh_history: list,
    capacity_history: Optional[list] = None,
    gateway_issues: Optional[list] = None
) -> Optional[str]:
    """
    Generate a weekly health summary report.
    
    Args:
        refresh_history: List of refresh records from the past week
        capacity_history: Historical capacity data (if available)
        gateway_issues: List of gateway problems encountered
    
    Returns:
        Markdown-formatted summary string
    """
    client = _get_openai_client()
    if not client:
        return None
    
    # Calculate stats
    total_refreshes = len(refresh_history)
    successful = sum(1 for r in refresh_history if r.get("status") == "Completed")
    failed = sum(1 for r in refresh_history if r.get("status") == "Failed")
    success_rate = (successful / total_refreshes * 100) if total_refreshes > 0 else 0
    
    context = {
        "total_refreshes": total_refreshes,
        "successful": successful,
        "failed": failed,
        "success_rate_pct": round(success_rate, 1),
        "gateway_issues_count": len(gateway_issues) if gateway_issues else 0
    }
    
    # Include failure details
    if failed > 0:
        context["failure_samples"] = [
            {
                "error": r.get("serviceExceptionJson", "")[:150],
                "time": r.get("endTime")
            }
            for r in refresh_history[:10]
            if r.get("status") == "Failed"
        ][:3]
    
    prompt = f"""Generate a brief weekly Power BI health summary based on this data:

{json.dumps(context, indent=2)}

Write 3-5 sentences covering:
1. Overall health assessment
2. Notable issues or patterns
3. One key recommendation

Keep it concise and actionable. Use plain text, no markdown."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Power BI operations analyst. Write clear, executive-style summaries."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.5
        )
        
        content = response.choices[0].message.content
        return content.strip() if content else None
        
    except Exception as e:
        print(f"Weekly summary error: {e}")
        return None


def format_ai_notification(analysis: dict) -> tuple[str, str]:
    """
    Format AI analysis into notification title and body.
    
    Returns:
        (title, body) tuple for notification
    """
    if not analysis:
        return ("❌ Refresh Failed", "Unable to analyze the failure.")
    
    severity_emoji = {
        "low": "⚠️",
        "medium": "🔶",
        "high": "🔴",
        "critical": "🚨"
    }
    
    emoji = severity_emoji.get(analysis.get("severity", "medium"), "❌")
    title = f"{emoji} Refresh Failed"
    
    summary = analysis.get("summary", "Refresh failed.")
    suggestions = analysis.get("suggestions", [])
    
    body = summary
    if suggestions:
        body += f"\n💡 Tip: {suggestions[0]}"
    
    return (title, body)


# =============================================================================
# CAPACITY INSIGHTS
# =============================================================================


def _build_dax_daily_trend(capacity_name: str | None = None) -> str:
    """Build DAX query for daily trend, optionally filtered by capacity."""
    if capacity_name:
        # Use CALCULATETABLE with FILTER for proper capacity filtering
        return f"""EVALUATE
CALCULATETABLE(
    SUMMARIZECOLUMNS(
        Timepoints[Date],
        "UtilizationPct", [CU (s)],
        "BackgroundPct", [Background CU (s)],
        "InteractivePct", [Interactive CU (s)],
        "BillableUtilPct", [Background Billable CU %] + [Interactive Billable CU %]
    ),
    Capacities[Capacity name] = "{capacity_name}"
)
ORDER BY Timepoints[Date] DESC"""
    else:
        return """EVALUATE
SUMMARIZECOLUMNS(
    Timepoints[Date],
    "UtilizationPct", [CU (s)],
    "BackgroundPct", [Background CU (s)],
    "InteractivePct", [Interactive CU (s)],
    "BillableUtilPct", [Background Billable CU %] + [Interactive Billable CU %]
)
ORDER BY Timepoints[Date] DESC"""


def _build_dax_hourly_pattern(capacity_name: str | None = None) -> str:
    """Build DAX query for hourly pattern, optionally filtered by capacity."""
    if capacity_name:
        return f"""EVALUATE
CALCULATETABLE(
    SUMMARIZECOLUMNS(
        Timepoints[Start of hour],
        "UtilizationPct", [CU (s)],
        "BackgroundPct", [Background CU (s)],
        "InteractivePct", [Interactive CU (s)],
        "BillableUtilPct", [Background Billable CU %] + [Interactive Billable CU %]
    ),
    Capacities[Capacity name] = "{capacity_name}"
)
ORDER BY Timepoints[Start of hour] ASC"""
    else:
        return """EVALUATE
SUMMARIZECOLUMNS(
    Timepoints[Start of hour],
    "UtilizationPct", [CU (s)],
    "BackgroundPct", [Background CU (s)],
    "InteractivePct", [Interactive CU (s)],
    "BillableUtilPct", [Background Billable CU %] + [Interactive Billable CU %]
)
ORDER BY Timepoints[Start of hour] ASC"""


_DAX_CAPACITY_DETAILS = """EVALUATE
SELECTCOLUMNS(
    Capacities,
    "CapacityName", Capacities[Capacity name],
    "SKU", Capacities[SKU],
    "Region", Capacities[Region],
    "State", Capacities[State],
    "Owners", Capacities[Owners]
)"""


def _build_dax_items_by_workspace(capacity_name: str | None = None) -> str:
    """Build DAX query for items by workspace, optionally filtered by capacity."""
    if capacity_name:
        return f"""EVALUATE
CALCULATETABLE(
    SUMMARIZECOLUMNS(
        Items[Workspace name],
        Items[Item kind],
        "TotalCU", [CU (s)],
        "ItemCount", COUNTROWS(Items)
    ),
    Capacities[Capacity name] = "{capacity_name}"
)
ORDER BY [TotalCU] DESC"""
    else:
        return """EVALUATE
SUMMARIZECOLUMNS(
    Items[Workspace name],
    Items[Item kind],
    "TotalCU", [CU (s)],
    "ItemCount", COUNTROWS(Items)
)
ORDER BY [TotalCU] DESC"""


def _build_dax_items_by_kind(capacity_name: str | None = None) -> str:
    """Build DAX query for items by kind, optionally filtered by capacity."""
    if capacity_name:
        return f"""EVALUATE
CALCULATETABLE(
    SUMMARIZECOLUMNS(
        Items[Item kind],
        "TotalCU", [CU (s)],
        "ItemCount", COUNTROWS(Items)
    ),
    Capacities[Capacity name] = "{capacity_name}"
)
ORDER BY [TotalCU] DESC"""
    else:
        return """EVALUATE
SUMMARIZECOLUMNS(
    Items[Item kind],
    "TotalCU", [CU (s)],
    "ItemCount", COUNTROWS(Items)
)
ORDER BY [TotalCU] DESC"""


def _execute_capacity_dax(workspace_id: str, dax_query: str) -> List[Dict[str, Any]]:
    """Execute a DAX query against the Capacity Metrics dataset."""
    from ..api.capacity_metrics import CapacityMetrics
    
    cm = CapacityMetrics(workspace_id)
    result = cm._execute_dax(dax_query)
    return cm._parse_dax_results(result)


def _calculate_statistics(daily_data: List[Dict]) -> Dict[str, Any]:
    """Calculate statistical summaries from daily utilization data."""
    if not daily_data:
        return {}
    
    # Extract utilization values (CU seconds + Billable %)
    utilizations = []
    background_vals = []
    interactive_vals = []
    billable_pcts = []
    
    for row in daily_data:
        # Total CU (seconds) - includes both background and interactive
        util = row.get("[UtilizationPct]") or row.get("UtilizationPct")
        bg = row.get("[BackgroundPct]") or row.get("BackgroundPct") or 0
        inter = row.get("[InteractivePct]") or row.get("InteractivePct") or 0
        billable = row.get("[BillableUtilPct]") or row.get("BillableUtilPct") or 0
        
        if util is not None:
            try:
                utilizations.append(float(util))
                background_vals.append(float(bg))
                interactive_vals.append(float(inter))
                billable_pcts.append(float(billable))
            except (ValueError, TypeError):
                pass
    
    if not utilizations:
        return {}
    
    total_cu = sum(utilizations)
    total_bg = sum(background_vals)
    total_inter = sum(interactive_vals)
    
    avg_util = sum(billable_pcts) / len(billable_pcts) if billable_pcts else 0
    max_util = max(billable_pcts) if billable_pcts else 0
    min_util = min(billable_pcts) if billable_pcts else 0
    
    # Background vs Interactive split (as percentages of total)
    bg_pct = (total_bg / total_cu * 100) if total_cu > 0 else 0
    inter_pct = (total_inter / total_cu * 100) if total_cu > 0 else 0
    
    # Trend: compare first half vs second half
    mid = len(billable_pcts) // 2
    if mid > 0:
        recent_avg = sum(billable_pcts[:mid]) / mid if mid > 0 else avg_util
        older_avg = sum(billable_pcts[mid:]) / (len(billable_pcts) - mid) if len(billable_pcts) > mid else avg_util
        trend_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
    else:
        trend_pct = 0
    
    # Find anomalies (> 2x average)
    anomalies = []
    for i, row in enumerate(daily_data):
        date = row.get("Timepoints[Date]") or row.get("Date")
        if i < len(billable_pcts):
            util_val = billable_pcts[i]
            if util_val > avg_util * 2 and avg_util > 0:
                anomalies.append({"date": date, "utilization": util_val})
    
    return {
        "average_utilization": round(avg_util, 2),
        "max_utilization": round(max_util, 2),
        "min_utilization": round(min_util, 2),
        "background_pct": round(bg_pct, 1),
        "interactive_pct": round(inter_pct, 1),
        "total_cu_seconds": round(total_cu, 0),
        "trend_pct": round(trend_pct, 1),
        "data_points": len(utilizations),
        "anomalies": anomalies[:5]  # Top 5 anomalies
    }


def _normalize_recommendations(recs: List) -> List[str]:
    """Normalize recommendations to plain strings."""
    normalized = []
    for rec in recs:
        if isinstance(rec, str):
            normalized.append(rec)
        elif isinstance(rec, dict):
            # Extract text from various possible keys
            text = (rec.get("action") or rec.get("text") or 
                    rec.get("recommendation") or rec.get("message") or str(rec))
            normalized.append(str(text))
        else:
            normalized.append(str(rec))
    return normalized


def _calculate_hourly_patterns(hourly_data: List[Dict]) -> Dict[str, Any]:
    """Analyze hourly patterns to find peak hours."""
    if not hourly_data:
        return {}
    
    # Group by hour of day
    hour_totals: Dict[int, List[float]] = {}
    for row in hourly_data:
        hour_str = row.get("Timepoints[Start of hour]") or row.get("Start of hour")
        util = row.get("[UtilizationPct]") or row.get("UtilizationPct")
        
        if hour_str and util is not None:
            try:
                # Parse hour from timestamp
                if "T" in str(hour_str):
                    hour = int(hour_str.split("T")[1].split(":")[0])
                else:
                    hour = 0
                
                if hour not in hour_totals:
                    hour_totals[hour] = []
                hour_totals[hour].append(float(util))
            except (ValueError, TypeError, IndexError):
                pass
    
    if not hour_totals:
        return {}
    
    # Calculate average per hour
    hour_averages = {h: sum(vals) / len(vals) for h, vals in hour_totals.items()}
    
    # Find peak hours (top 3)
    sorted_hours = sorted(hour_averages.items(), key=lambda x: x[1], reverse=True)
    peak_hours = [{"hour": h, "avg_utilization": round(v, 2)} for h, v in sorted_hours[:3]]
    
    # Find off-peak hours (bottom 3)
    off_peak_hours = [{"hour": h, "avg_utilization": round(v, 2)} for h, v in sorted_hours[-3:]]
    
    return {
        "peak_hours": peak_hours,
        "off_peak_hours": off_peak_hours,
        "hour_averages": {str(h): round(v, 2) for h, v in hour_averages.items()}
    }


def analyze_capacity(
    workspace_id: str,
    capacity_name: str | None = None,
    use_cache: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Analyze capacity utilization and provide AI-powered insights.
    
    Fetches 14-day trend data, calculates statistics, detects anomalies,
    and uses OpenAI to generate actionable recommendations.
    
    Args:
        workspace_id: GUID of the workspace containing Capacity Metrics app
        capacity_name: Optional capacity name to filter by (None = all capacities)
        use_cache: Whether to use cached results (15-minute TTL)
    
    Returns:
        dict with keys:
        - status: 'healthy', 'warning', 'critical'
        - summary: Brief AI-generated assessment
        - recommendations: List of actionable suggestions
        - trend: 'increasing', 'decreasing', 'stable'
        - statistics: Calculated metrics (avg, max, min, trend_pct)
        - anomalies: List of detected anomalies
        - top_workspaces: Top consuming workspaces
        - capacities: Capacity details (SKU, region)
        - selected_capacity: Which capacity is being analyzed
        - generated_at: Timestamp of analysis
    """
    global _capacity_insights_cache, _capacity_insights_cache_time
    
    from . import log
    log(f"[analyze_capacity] Starting: workspace={workspace_id}, capacity={capacity_name}, use_cache={use_cache}")
    
    # Check cache (include capacity in cache key)
    cache_key = f"capacity_{workspace_id}_{capacity_name or 'all'}"
    if use_cache and _capacity_insights_cache_time:
        age = datetime.now() - _capacity_insights_cache_time
        if age < _CAPACITY_CACHE_DURATION and cache_key in _capacity_insights_cache:
            log(f"[analyze_capacity] Returning cached result (age={age})")
            return _capacity_insights_cache[cache_key]
    
    # Fetch data from DAX queries (with optional capacity filter)
    try:
        log(f"[analyze_capacity] Executing DAX queries...")
        daily_dax = _build_dax_daily_trend(capacity_name)
        log(f"[analyze_capacity] Daily DAX query:\\n{daily_dax}")
        daily_data = _execute_capacity_dax(workspace_id, daily_dax)
        log(f"[analyze_capacity] Daily data rows: {len(daily_data)}")
        if daily_data:
            log(f"[analyze_capacity] Sample daily row: {daily_data[0]}")
        
        hourly_data = _execute_capacity_dax(workspace_id, _build_dax_hourly_pattern(capacity_name))
        log(f"[analyze_capacity] Hourly data rows: {len(hourly_data)}")
        
        capacity_data = _execute_capacity_dax(workspace_id, _DAX_CAPACITY_DETAILS)
        items_by_workspace = _execute_capacity_dax(workspace_id, _build_dax_items_by_workspace(capacity_name))
        items_by_kind = _execute_capacity_dax(workspace_id, _build_dax_items_by_kind(capacity_name))
    except Exception as e:
        print(f"Error fetching capacity data: {e}")
        return None
    
    # Calculate statistics
    stats = _calculate_statistics(daily_data)
    log(f"[analyze_capacity] Statistics calculated: {stats}")
    
    hourly_patterns = _calculate_hourly_patterns(hourly_data)
    
    if not stats:
        log("[analyze_capacity] No stats calculated, returning unknown status")
        return {
            "status": "unknown",
            "summary": "Unable to calculate capacity statistics. Check workspace configuration.",
            "recommendations": [],
            "generated_at": datetime.now().isoformat()
        }
    
    # Determine trend
    trend_pct = stats.get("trend_pct", 0)
    if trend_pct > 10:
        trend = "increasing"
    elif trend_pct < -10:
        trend = "decreasing"
    else:
        trend = "stable"
    
    # Determine status
    avg_util = stats.get("average_utilization", 0)
    max_util = stats.get("max_utilization", 0)
    
    log(f"[analyze_capacity] avg_util={avg_util}, max_util={max_util}, trend={trend}")
    
    if max_util >= 100 or avg_util >= 80:
        status = "critical"
    elif max_util >= 80 or avg_util >= 50:
        status = "warning"
    else:
        status = "healthy"
    
    log(f"[analyze_capacity] Final status={status}")
    
    # Extract top workspaces (with CU usage now)
    top_workspaces = []
    for item in items_by_workspace[:10]:
        ws_name = item.get("Items[Workspace name]") or item.get("Workspace name")
        item_kind = item.get("Items[Item kind]") or item.get("Item kind")
        count = item.get("[ItemCount]") or item.get("ItemCount")
        total_cu = item.get("[TotalCU]") or item.get("TotalCU") or 0
        if ws_name:
            top_workspaces.append({
                "workspace": ws_name,
                "item_kind": item_kind,
                "item_count": count,
                "total_cu": total_cu
            })
    
    # Extract capacity details
    capacities = []
    for cap in capacity_data:
        capacities.append({
            "name": cap.get("[CapacityName]") or cap.get("Capacities[Capacity name]"),
            "sku": cap.get("[SKU]") or cap.get("Capacities[SKU]"),
            "region": cap.get("[Region]") or cap.get("Capacities[Region]"),
            "state": cap.get("[State]") or cap.get("Capacities[State]")
        })
    
    # Build result without AI (fallback)
    result = {
        "status": status,
        "trend": trend,
        "statistics": stats,
        "hourly_patterns": hourly_patterns,
        "anomalies": stats.get("anomalies", []),
        "top_workspaces": top_workspaces,
        "capacities": capacities,
        "selected_capacity": capacity_name or "All Capacities",
        "generated_at": datetime.now().isoformat()
    }
    
    # Generate AI insights if available
    client = _get_openai_client()
    if client:
        ai_insights = _generate_capacity_ai_insights(
            client, stats, hourly_patterns, capacities, top_workspaces, items_by_kind
        )
        if ai_insights:
            result["summary"] = ai_insights.get("summary", "")
            # Normalize recommendations to plain strings
            raw_recs = ai_insights.get("recommendations", [])
            result["recommendations"] = _normalize_recommendations(raw_recs)
            result["right_sizing"] = ai_insights.get("right_sizing")
            result["scheduling_suggestions"] = ai_insights.get("scheduling_suggestions")
    else:
        # Fallback to rule-based insights
        result["summary"] = _generate_rule_based_summary(stats, status, trend)
        result["recommendations"] = _generate_rule_based_recommendations(stats, status, trend, hourly_patterns)
    
    # Cache result
    _capacity_insights_cache[cache_key] = result
    _capacity_insights_cache_time = datetime.now()
    
    return result


def _generate_capacity_ai_insights(
    client,
    stats: Dict,
    hourly_patterns: Dict,
    capacities: List[Dict],
    top_workspaces: List[Dict],
    items_by_kind: List[Dict]
) -> Optional[Dict]:
    """Generate AI-powered capacity insights."""
    
    # Build context for AI
    context = {
        "statistics": {
            "average_utilization_pct": stats.get("average_utilization"),
            "max_utilization_pct": stats.get("max_utilization"),
            "min_utilization_pct": stats.get("min_utilization"),
            "trend_change_pct": stats.get("trend_pct"),
            "data_days": stats.get("data_points", 14),
            "anomaly_count": len(stats.get("anomalies", []))
        },
        "peak_hours": hourly_patterns.get("peak_hours", []),
        "off_peak_hours": hourly_patterns.get("off_peak_hours", []),
        "capacities": [{"name": c["name"], "sku": c["sku"]} for c in capacities[:5]],
        "top_workspaces": top_workspaces[:5],
        "item_types": [
            {"kind": i.get("Items[Item kind]"), "count": i.get("[ItemCount]")}
            for i in items_by_kind[:5]
        ],
        "anomalies": stats.get("anomalies", [])[:3]
    }
    
    prompt = f"""Analyze this Microsoft Fabric capacity utilization data and provide insights.

DATA:
{json.dumps(context, indent=2)}

Provide a JSON response with:
- summary: One concise sentence about capacity health (max 80 chars)
- recommendations: Array of 3-5 plain text strings (NOT objects). Each recommendation should be a short, actionable sentence (max 60 chars each). Example: ["Downsize F64 to F32 - only using 1%", "Move jobs to off-peak hours (1-6 AM)"]
- right_sizing: Short suggestion if SKU change needed, or null
- scheduling_suggestions: Short suggestion if load balancing needed, or null

IMPORTANT: recommendations must be an array of simple strings, not objects.

Consider:
1. Is utilization too low (wasting money) or too high (risk of throttling)?
2. Are there anomalies that need investigation?
3. Can workloads be rescheduled to off-peak hours?
4. Is the SKU appropriately sized for the workload?

Note: Fabric SKUs are F2, F4, F8, F16, F32, F64, F128, F256, F512, F1024, F2048.
Trial capacities (FT1) have limited features."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a Microsoft Fabric capacity optimization expert. Provide clear, actionable insights focused on cost optimization and performance. Always respond with valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=600,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content or "{}")
        
    except Exception as e:
        print(f"AI capacity analysis error: {e}")
        return None


def _generate_rule_based_summary(stats: Dict, status: str, trend: str) -> str:
    """Generate a summary without AI using rules."""
    avg = stats.get("average_utilization", 0)
    max_util = stats.get("max_utilization", 0)
    trend_pct = stats.get("trend_pct", 0)
    
    status_text = {
        "healthy": "Capacity is healthy",
        "warning": "Capacity needs attention",
        "critical": "Capacity is at risk"
    }.get(status, "Capacity status unknown")
    
    trend_text = ""
    if abs(trend_pct) > 10:
        direction = "up" if trend_pct > 0 else "down"
        trend_text = f" Utilization trending {direction} {abs(trend_pct):.0f}% vs previous period."
    
    return f"{status_text} with {avg:.1f}% average utilization (peak: {max_util:.1f}%).{trend_text}"


def _generate_rule_based_recommendations(
    stats: Dict, status: str, trend: str, hourly_patterns: Dict
) -> List[str]:
    """Generate recommendations without AI using rules."""
    recommendations = []
    avg = stats.get("average_utilization", 0)
    max_util = stats.get("max_utilization", 0)
    anomalies = stats.get("anomalies", [])
    
    # Low utilization
    if avg < 5:
        recommendations.append("Consider downsizing SKU or consolidating workloads - utilization is very low.")
    elif avg < 20:
        recommendations.append("Capacity is underutilized. Review if current SKU is cost-effective.")
    
    # High utilization
    if max_util >= 100:
        recommendations.append("Capacity exceeded 100% - throttling occurred. Consider upgrading SKU.")
    elif max_util >= 80:
        recommendations.append("Peak utilization nearing threshold. Monitor for throttling risk.")
    
    # Anomalies
    if anomalies:
        recommendations.append(f"Investigate {len(anomalies)} utilization spike(s) detected in the data.")
    
    # Peak hour suggestions
    peak_hours = hourly_patterns.get("peak_hours", [])
    if peak_hours and len(peak_hours) >= 2:
        hours = [str(h["hour"]) + ":00" for h in peak_hours[:2]]
        recommendations.append(f"Peak usage at {' and '.join(hours)}. Consider spreading workloads.")
    
    # Ensure at least one recommendation
    if not recommendations:
        recommendations.append("Capacity is well-balanced. Continue monitoring for changes.")
    
    return recommendations


def clear_capacity_insights_cache():
    """Clear the capacity insights cache."""
    global _capacity_insights_cache, _capacity_insights_cache_time
    _capacity_insights_cache.clear()
    _capacity_insights_cache_time = None
