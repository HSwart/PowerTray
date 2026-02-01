"""
Date and time utility functions for Power BI Tray application.
"""

from datetime import datetime, timezone, timedelta
from ..config import state, TIMEZONES, WINDOWS_TZ_OFFSETS


def parse_datetime(dt_string: str | None) -> datetime | None:
    """Parse ISO datetime string to datetime object."""
    if not dt_string:
        return None
    try:
        return datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def format_datetime(dt: datetime | None) -> str:
    """Format datetime to selected timezone."""
    if not dt:
        return "N/A"
    
    # Convert to selected timezone
    offset_hours = TIMEZONES.get(state.selected_timezone, 0)
    offset = timedelta(hours=offset_hours)
    
    # Convert from UTC to target timezone
    if dt.tzinfo is not None:
        dt_utc = dt.astimezone(timezone.utc)
    else:
        dt_utc = dt.replace(tzinfo=timezone.utc)
    
    dt_local = dt_utc + offset
    return dt_local.strftime("%Y-%m-%d %H:%M")


def format_time_only(dt: datetime | None) -> str:
    """Format datetime to time only (HH:MM:SS) in selected timezone."""
    if not dt:
        return "N/A"
    
    # Convert to selected timezone
    offset_hours = TIMEZONES.get(state.selected_timezone, 0)
    offset = timedelta(hours=offset_hours)
    
    # Convert from UTC to target timezone
    if dt.tzinfo is not None:
        dt_utc = dt.astimezone(timezone.utc)
    else:
        dt_utc = dt.replace(tzinfo=timezone.utc)
    
    dt_local = dt_utc + offset
    return dt_local.strftime("%H:%M:%S")


def format_duration(start_time: str | None, end_time: str | None) -> str:
    """Calculate and format duration between two times."""
    start_dt = parse_datetime(start_time)
    end_dt = parse_datetime(end_time)
    
    if not start_dt or not end_dt:
        return "N/A"
    
    duration = end_dt - start_dt
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 60:
        return f"{total_seconds}s"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def get_status_emoji(status: str | None) -> str:
    """Get emoji/symbol for status."""
    status_lower = status.lower() if status else ""
    if status_lower == "completed":
        return "✓"
    elif status_lower == "failed":
        return "✗"
    elif status_lower == "unknown":
        return "⟳"
    elif status_lower == "disabled":
        return "⊘"
    elif status_lower == "cancelled":
        return "⊗"
    return "?"


def get_refresh_type_display(refresh_type: str | None) -> str:
    """Get friendly display name for refresh type."""
    types = {
        "scheduled": "Scheduled",
        "ondemand": "On-Demand",
        "viaapi": "Via API",
        "viaenhancedapi": "Via Enhanced API",
        "datafactory": "Pipeline",
    }
    return types.get(refresh_type.lower() if refresh_type else "", refresh_type or "Unknown")


def calculate_next_run(config: dict) -> datetime | None:
    """Calculate the next run time from a schedule configuration."""
    now = datetime.now(timezone.utc)
    schedule_type = config.get("type", "")
    local_tz_id = config.get("localTimeZoneId", "UTC")
    
    # Parse end date to check if schedule is still valid
    end_str = config.get("endDateTime")
    if end_str:
        try:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            # Ensure timezone-aware comparison
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt < now:
                return None  # Schedule has ended
        except (ValueError, AttributeError):
            pass
    
    times = config.get("times", [])
    
    if schedule_type == "Daily":
        return find_next_daily_time(times, now, local_tz_id)
    elif schedule_type == "Weekly":
        weekdays = config.get("weekdays", [])
        return find_next_weekly_time(times, weekdays, now, local_tz_id)
    elif schedule_type == "Cron":
        interval = config.get("interval", 60)  # Default 60 minutes
        start_str = config.get("startDateTime")
        if start_str:
            try:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                # Ensure timezone-aware comparison
                if start_dt.tzinfo is None:
                    start_dt = start_dt.replace(tzinfo=timezone.utc)
                if start_dt > now:
                    return start_dt
                # Calculate next occurrence based on interval
                elapsed = (now - start_dt).total_seconds() / 60
                intervals_passed = int(elapsed / interval)
                next_run = start_dt + timedelta(minutes=(intervals_passed + 1) * interval)
                return next_run
            except (ValueError, AttributeError):
                pass
    
    return None


def find_next_daily_time(times: list, now: datetime, local_tz_id: str) -> datetime | None:
    """Find the next daily occurrence."""
    if not times:
        return None
    
    offset_hours = WINDOWS_TZ_OFFSETS.get(local_tz_id, 0)
    offset = timedelta(hours=offset_hours)
    
    # Convert now to local time
    local_now = now + offset
    
    for time_str in sorted(times):
        try:
            hour, minute = map(int, time_str.split(":"))
            scheduled_time = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if scheduled_time > local_now:
                # Convert back to UTC
                return scheduled_time - offset
        except (ValueError, AttributeError):
            continue
    
    # Next occurrence is tomorrow
    try:
        first_time = sorted(times)[0]
        hour, minute = map(int, first_time.split(":"))
        tomorrow = local_now + timedelta(days=1)
        scheduled_time = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return scheduled_time - offset
    except (ValueError, AttributeError, IndexError):
        return None


def find_next_weekly_time(times: list, weekdays: list, now: datetime, local_tz_id: str) -> datetime | None:
    """Find the next weekly occurrence."""
    if not times or not weekdays:
        return None
    
    weekday_map = {
        "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
        "Friday": 4, "Saturday": 5, "Sunday": 6
    }
    target_days = [weekday_map[d] for d in weekdays if d in weekday_map]
    
    if not target_days:
        return None
    
    offset_hours = WINDOWS_TZ_OFFSETS.get(local_tz_id, 0)
    offset = timedelta(hours=offset_hours)
    local_now = now + offset
    
    # Check today and next 7 days
    for day_offset in range(8):
        check_date = local_now + timedelta(days=day_offset)
        
        if check_date.weekday() in target_days:
            for time_str in sorted(times):
                try:
                    hour, minute = map(int, time_str.split(":"))
                    scheduled_time = check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    if scheduled_time > local_now:
                        return scheduled_time - offset
                except (ValueError, AttributeError):
                    continue
    
    return None
