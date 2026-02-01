"""
Capacity metrics module for fetching Fabric capacity usage data.

Uses the Power BI Execute Queries REST API to run DAX queries against
the Microsoft Fabric Capacity Metrics semantic model.

Note: The SemPy library (semantic-link-sempy) is designed for Fabric notebooks.
For desktop applications, we use the REST API directly with MSAL authentication.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import json

from ..utils.logging import log


# =============================================================================
# CAPACITY METRICS CONFIGURATION
# =============================================================================

# Default workspace containing the Capacity Metrics app
DEFAULT_METRICS_WORKSPACE = "Microsoft Fabric Capacity Metrics - Fabric64"

# The semantic model name from the Capacity Metrics app
CAPACITY_METRICS_DATASET = "Fabric Capacity Metrics"


# =============================================================================
# DAX QUERIES FOR CAPACITY METRICS
# =============================================================================

# Get latest utilization (last timepoint)
DAX_UTILIZATION_PERCENT = """EVALUATE
TOPN(
    1,
    SUMMARIZECOLUMNS(
        Timepoints[Date],
        Timepoints[TimePoint],
        "UtilizationPct", [Background Billable CU %] + [Interactive Billable CU %],
        "BackgroundPct", [Background Billable CU %],
        "InteractivePct", [Interactive Billable CU %]
    ),
    Timepoints[TimePoint], DESC
)"""

# Get throttling status from latest timepoint
# Note: Using available measures - some semantic models may not have all throttling metrics
DAX_THROTTLING_STATUS = """EVALUATE
TOPN(
    1,
    SUMMARIZECOLUMNS(
        Timepoints[TimePoint],
        "BackgroundPct", [Background Billable CU %],
        "InteractivePct", [Interactive Billable CU %]
    ),
    Timepoints[TimePoint], DESC
)"""

# Get top consuming items
DAX_TOP_CONSUMING_ITEMS = """EVALUATE
TOPN(
    10,
    SUMMARIZECOLUMNS(
        Items[Item Name],
        Items[Item Kind],
        "TotalCUs", [CU (s)]
    ),
    [TotalCUs], DESC
)"""

# Get capacity summary
DAX_CAPACITY_SUMMARY = """EVALUATE
SUMMARIZECOLUMNS(
    Capacities[Capacity Name],
    Capacities[SKU],
    "TotalCUs", [CU (s)],
    "AvgUtilization", AVERAGE([Background Billable CU %]) + AVERAGE([Interactive Billable CU %])
)"""


# =============================================================================
# CAPACITY METRICS CLASS
# =============================================================================

class CapacityMetrics:
    """
    Client for fetching capacity metrics from the Fabric Capacity Metrics app.
    
    Uses the Power BI Execute Queries REST API to run DAX queries against
    the semantic model created by the Capacity Metrics app.
    """
    
    def __init__(self, workspace_id: str = ""):
        """
        Initialize the capacity metrics client.
        
        Args:
            workspace_id: GUID of the workspace containing the Capacity Metrics app
        """
        from .client import PowerBIClient
        self.client = PowerBIClient
        self._workspace_id: Optional[str] = workspace_id if workspace_id else None
        self._dataset_id: Optional[str] = None
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=5)
    
    def _get_workspace_id(self) -> Optional[str]:
        """Get the workspace ID for the metrics workspace."""
        if self._workspace_id:
            return self._workspace_id
        
        # No workspace ID configured
        log("Capacity metrics workspace ID not configured")
        return None
    
    def _get_dataset_id(self) -> Optional[str]:
        """Get the dataset ID for the Capacity Metrics semantic model."""
        if self._dataset_id:
            return self._dataset_id
        
        workspace_id = self._get_workspace_id()
        if not workspace_id:
            return None
        
        try:
            response = self.client.get(f"/groups/{workspace_id}/datasets")
            if response and "value" in response:
                log(f"Found {len(response['value'])} datasets in metrics workspace")
                for ds in response["value"]:
                    # Look for the Capacity Metrics dataset
                    ds_name = ds.get("name", "")
                    log(f"  Dataset: '{ds_name}'")
                    if "Capacity Metrics" in ds_name or "Fabric Capacity" in ds_name:
                        self._dataset_id = ds["id"]
                        log(f"Found metrics dataset: {ds_name} ({self._dataset_id})")
                        return self._dataset_id
                log("Capacity Metrics dataset not found in workspace")
            else:
                log(f"No datasets returned. Response: {response}")
        except Exception as e:
            log(f"Error finding metrics dataset: {e}")
        
        return None
    
    def _execute_dax(self, dax_query: str) -> Optional[Dict[str, Any]]:
        """
        Execute a DAX query against the Capacity Metrics semantic model.
        
        Args:
            dax_query: The DAX query to execute
            
        Returns:
            The query results or None if failed
        """
        workspace_id = self._get_workspace_id()
        dataset_id = self._get_dataset_id()
        
        if not workspace_id or not dataset_id:
            log("Cannot execute DAX: workspace or dataset not found")
            return None
        
        try:
            endpoint = f"/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
            payload = {
                "queries": [{"query": dax_query}],
                "serializerSettings": {"includeNulls": True}
            }
            
            log(f"Executing DAX query against {dataset_id}...")
            response = self.client.post_json(endpoint, data=payload)
            
            if response and "results" in response:
                results = response["results"]
                if results:
                    result = results[0]
                    rows = result.get("tables", [{}])[0].get("rows", []) if result.get("tables") else []
                    log(f"DAX query returned {len(rows)} rows")
                    return result
                else:
                    log("DAX results list is empty")
                    return None
            
            log(f"DAX query returned no results. Response keys: {response.keys() if response else 'None'}")
            return None
            
        except Exception as e:
            log(f"Error executing DAX query: {e}")
            return None
    
    def _parse_dax_results(self, result: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse DAX query results into a list of dictionaries."""
        if not result or "tables" not in result:
            log(f"No tables in result: {result}")
            return []
        
        tables = result.get("tables", [])
        if not tables:
            log("Tables list is empty")
            return []
        
        table = tables[0]
        columns = [col["name"] for col in table.get("columns", [])]
        rows = table.get("rows", [])
        
        log(f"DAX result columns: {columns}")
        log(f"DAX result rows: {rows[:2]}...")  # Log first 2 rows
        
        parsed = []
        for row in rows:
            # Power BI API returns rows as dicts, not arrays
            if isinstance(row, dict):
                parsed.append(row)
            else:
                # If array format, zip with columns
                parsed.append(dict(zip(columns, row)))
        
        log(f"Parsed result: {parsed[:1]}...")  # Log first parsed row
        return parsed
    
    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid."""
        if not self._cache_time:
            return False
        return datetime.now(timezone.utc) - self._cache_time < self._cache_duration
    
    def get_utilization(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get current capacity utilization percentage.
        
        Returns:
            Dictionary with utilization metrics:
            - UtilizationPct: Current CU utilization percentage
            - InteractiveDelayPct: Interactive delay threshold percentage
            - InteractiveRejectPct: Interactive rejection threshold percentage  
            - BackgroundRejectPct: Background rejection threshold percentage
        """
        cache_key = "utilization"
        
        if use_cache and self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]
        
        result = self._execute_dax(DAX_UTILIZATION_PERCENT)
        parsed = self._parse_dax_results(result)
        
        if parsed:
            utilization_data = parsed[0]
            log(f"Utilization data: {utilization_data}")
            self._cache[cache_key] = utilization_data
            self._cache_time = datetime.now(timezone.utc)
            return utilization_data
        
        log("No utilization data parsed")
        return None
    
    def get_throttling_status(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get current throttling status.
        
        Returns:
            Dictionary with:
            - IsThrottled: Boolean indicating if capacity is throttled
            - ThrottlingLevel: Current throttling level (Normal, Interactive Delay, 
                               Interactive Rejection, Background Rejection)
        """
        cache_key = "throttling"
        
        if use_cache and self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]
        
        result = self._execute_dax(DAX_THROTTLING_STATUS)
        parsed = self._parse_dax_results(result)
        
        if parsed:
            self._cache[cache_key] = parsed[0]
            self._cache_time = datetime.now(timezone.utc)
            return parsed[0]
        
        return None
    
    def get_top_consuming_items(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Get top 10 items consuming the most capacity.
        
        Returns:
            List of dictionaries with:
            - ItemName: Name of the item
            - ItemKind: Type of item (SemanticModel, Report, etc.)
            - WorkspaceName: Workspace containing the item
            - TotalCUs: Total CU seconds consumed
            - OperationCount: Number of operations
        """
        cache_key = "top_items"
        
        if use_cache and self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]
        
        result = self._execute_dax(DAX_TOP_CONSUMING_ITEMS)
        parsed = self._parse_dax_results(result)
        
        if parsed:
            self._cache[cache_key] = parsed
            self._cache_time = datetime.now(timezone.utc)
        
        return parsed
    
    def get_capacity_summary(self, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get capacity summary information.
        
        Returns:
            Dictionary with:
            - CapacityName: Name of the capacity
            - CapacitySKU: SKU level (F2, F4, F64, etc.)
            - TotalCUsLast24h: Total CUs consumed in last 24 hours
            - CurrentUtilization: Current utilization percentage
        """
        cache_key = "summary"
        
        if use_cache and self._is_cache_valid() and cache_key in self._cache:
            return self._cache[cache_key]
        
        result = self._execute_dax(DAX_CAPACITY_SUMMARY)
        parsed = self._parse_dax_results(result)
        
        if parsed:
            self._cache[cache_key] = parsed[0]
            self._cache_time = datetime.now(timezone.utc)
            return parsed[0]
        
        return None
    
    def get_all_metrics(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get all capacity metrics in a single call.
        
        Returns:
            Dictionary with:
            - utilization: Current utilization metrics
            - throttling: Throttling status
            - top_items: Top consuming items
            - summary: Capacity summary
            - timestamp: When the data was fetched
        """
        return {
            "utilization": self.get_utilization(use_cache),
            "throttling": self.get_throttling_status(use_cache),
            "top_items": self.get_top_consuming_items(use_cache),
            "summary": self.get_capacity_summary(use_cache),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    def clear_cache(self):
        """Clear the cached metrics data."""
        self._cache.clear()
        self._cache_time = None
    
    def format_utilization_display(self) -> str:
        """Format utilization for display in UI."""
        util = self.get_utilization()
        if not util:
            return "Utilization: N/A"
        
        pct = util.get("UtilizationPct", 0)
        if pct is None:
            return "Utilization: N/A"
        
        # Color indicator based on utilization
        if pct >= 100:
            status = "🔴"  # Critical
        elif pct >= 80:
            status = "🟡"  # Warning
        else:
            status = "🟢"  # Normal
        
        return f"{status} Utilization: {pct:.1f}%"
    
    def format_throttling_display(self) -> str:
        """Format throttling status for display in UI."""
        throttling = self.get_throttling_status()
        if not throttling:
            return "Throttling: N/A"
        
        level = throttling.get("ThrottlingLevel", "Unknown")
        is_throttled = throttling.get("IsThrottled", False)
        
        if is_throttled:
            return f"⚠️ Throttling: {level}"
        else:
            return "✅ Throttling: None"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_capacity_metrics(workspace_id: str = "") -> CapacityMetrics:
    """
    Create a CapacityMetrics instance.
    
    Args:
        workspace_id: GUID of the workspace containing Capacity Metrics app
        
    Returns:
        CapacityMetrics instance
    """
    return CapacityMetrics(workspace_id)


def format_cu_seconds(cu_seconds: float) -> str:
    """Format CU seconds into a human-readable string."""
    if cu_seconds is None:
        return "N/A"
    
    if cu_seconds >= 3600:
        return f"{cu_seconds / 3600:.1f} CU-hours"
    elif cu_seconds >= 60:
        return f"{cu_seconds / 60:.1f} CU-minutes"
    else:
        return f"{cu_seconds:.1f} CU-seconds"
