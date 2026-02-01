"""
AI Insights module for Power BI Tray application.

Uses OpenAI API to provide intelligent analysis of refresh failures,
capacity issues, and recommendations.
"""

import json
from typing import Optional
from functools import lru_cache


# OpenAI client (lazy loaded)
_openai_client = None


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
