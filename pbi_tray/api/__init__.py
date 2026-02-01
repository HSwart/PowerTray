"""
Power BI API client modules.
"""

from .client import PowerBIClient
from .refresh import (
    get_refresh_history,
    get_refresh_details,
    trigger_refresh,
    cancel_refresh,
)
from .gateway import (
    get_gateways,
    get_gateway_status_summary,
    get_gateway_display,
    has_gateway_warning,
)
from .pipelines import (
    get_pipeline_runs,
    get_all_pipeline_runs,
    get_pipeline_schedules,
    get_all_pipeline_schedules,
    get_next_scheduled_refresh,
    get_pipeline_info_for_display,
)
from .dataset import (
    get_semantic_model_name,
    get_workspace_name,
    get_dataset_info,
)
from .capacity_metrics import (
    CapacityMetrics,
    get_capacity_metrics,
    format_cu_seconds,
    DEFAULT_METRICS_WORKSPACE,
)

__all__ = [
    "PowerBIClient",
    "get_refresh_history",
    "get_refresh_details", 
    "trigger_refresh",
    "cancel_refresh",
    "get_gateways",
    "get_gateway_status_summary",
    "get_gateway_display",
    "has_gateway_warning",
    "get_pipeline_runs",
    "get_all_pipeline_runs",
    "get_pipeline_schedules",
    "get_all_pipeline_schedules",
    "get_next_scheduled_refresh",
    "get_pipeline_info_for_display",
    "get_semantic_model_name",
    "get_workspace_name",
    "get_dataset_info",
    "CapacityMetrics",
    "get_capacity_metrics",
    "format_cu_seconds",
    "DEFAULT_METRICS_WORKSPACE",
]
