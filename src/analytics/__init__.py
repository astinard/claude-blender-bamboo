"""Analytics module for Claude Fab Lab.

Provides print job tracking, statistics, and reporting.
"""

from src.analytics.tracker import (
    PrintTracker,
    PrintRecord,
    PrintOutcome,
    track_print,
)
from src.analytics.reports import (
    AnalyticsReport,
    ReportPeriod,
    MaterialUsageReport,
    SuccessRateReport,
    CostReport,
    TimeReport,
    generate_report,
)
from src.analytics.storage import (
    AnalyticsStorage,
    create_storage,
)

__all__ = [
    "PrintTracker",
    "PrintRecord",
    "PrintOutcome",
    "track_print",
    "AnalyticsReport",
    "ReportPeriod",
    "MaterialUsageReport",
    "SuccessRateReport",
    "CostReport",
    "TimeReport",
    "generate_report",
    "AnalyticsStorage",
    "create_storage",
]
