"""Analytics reports generation.

Generates various reports from print analytics data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from src.utils import get_logger
from src.analytics.storage import AnalyticsStorage, create_storage

logger = get_logger("analytics.reports")


class ReportPeriod(str, Enum):
    """Time periods for reports."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    ALL_TIME = "all_time"


@dataclass
class MaterialUsageReport:
    """Report on material usage."""
    material_type: str
    total_grams: float
    total_cost: float
    usage_count: int
    avg_per_print: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "material_type": self.material_type,
            "total_grams": self.total_grams,
            "total_cost": self.total_cost,
            "usage_count": self.usage_count,
            "avg_per_print": self.avg_per_print,
        }


@dataclass
class SuccessRateReport:
    """Report on print success rates."""
    total_prints: int
    successful: int
    failed: int
    cancelled: int
    success_rate: float
    failure_rate: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_prints": self.total_prints,
            "successful": self.successful,
            "failed": self.failed,
            "cancelled": self.cancelled,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
        }


@dataclass
class CostReport:
    """Report on printing costs."""
    total_cost: float
    avg_cost_per_print: float
    cost_by_material: Dict[str, float]
    cost_trend: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_cost": self.total_cost,
            "avg_cost_per_print": self.avg_cost_per_print,
            "cost_by_material": self.cost_by_material,
            "cost_trend": self.cost_trend,
        }


@dataclass
class TimeReport:
    """Report on print times."""
    total_print_time_hours: float
    avg_print_time_hours: float
    longest_print_hours: float
    shortest_print_hours: float
    prints_by_day: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_print_time_hours": self.total_print_time_hours,
            "avg_print_time_hours": self.avg_print_time_hours,
            "longest_print_hours": self.longest_print_hours,
            "shortest_print_hours": self.shortest_print_hours,
            "prints_by_day": self.prints_by_day,
        }


@dataclass
class AnalyticsReport:
    """
    Comprehensive analytics report.

    Combines all report types into a single report.
    """

    period: ReportPeriod
    start_date: str
    end_date: str
    generated_at: str

    # Sub-reports
    success_rate: Optional[SuccessRateReport] = None
    material_usage: List[MaterialUsageReport] = field(default_factory=list)
    cost: Optional[CostReport] = None
    time: Optional[TimeReport] = None

    # Summary stats
    total_prints: int = 0
    total_material_grams: float = 0
    total_cost: float = 0
    total_print_hours: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period": self.period.value,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "generated_at": self.generated_at,
            "summary": {
                "total_prints": self.total_prints,
                "total_material_grams": self.total_material_grams,
                "total_cost": self.total_cost,
                "total_print_hours": self.total_print_hours,
            },
            "success_rate": self.success_rate.to_dict() if self.success_rate else None,
            "material_usage": [m.to_dict() for m in self.material_usage],
            "cost": self.cost.to_dict() if self.cost else None,
            "time": self.time.to_dict() if self.time else None,
        }


class ReportGenerator:
    """
    Generates analytics reports.

    Creates various reports from stored analytics data.
    """

    def __init__(self, storage: Optional[AnalyticsStorage] = None):
        """
        Initialize report generator.

        Args:
            storage: Analytics storage
        """
        self.storage = storage or create_storage()

    def generate_report(
        self,
        period: ReportPeriod = ReportPeriod.MONTH,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> AnalyticsReport:
        """
        Generate a comprehensive report.

        Args:
            period: Report period
            start_date: Custom start date
            end_date: Custom end date

        Returns:
            AnalyticsReport
        """
        # Calculate date range
        if not end_date:
            end_date = datetime.now().isoformat()

        if not start_date:
            start_date = self._get_period_start(period).isoformat()

        # Generate sub-reports
        success_report = self.generate_success_rate_report(start_date, end_date)
        material_reports = self.generate_material_usage_reports(start_date, end_date)
        cost_report = self.generate_cost_report(start_date, end_date)
        time_report = self.generate_time_report(start_date, end_date)

        # Get aggregate stats
        stats = self.storage.get_aggregate_stats(start_date, end_date)

        return AnalyticsReport(
            period=period,
            start_date=start_date,
            end_date=end_date,
            generated_at=datetime.now().isoformat(),
            success_rate=success_report,
            material_usage=material_reports,
            cost=cost_report,
            time=time_report,
            total_prints=stats.get("total_prints", 0) or 0,
            total_material_grams=stats.get("total_material_grams", 0) or 0,
            total_cost=stats.get("total_cost", 0) or 0,
            total_print_hours=(stats.get("total_duration_seconds", 0) or 0) / 3600,
        )

    def generate_success_rate_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> SuccessRateReport:
        """
        Generate success rate report.

        Args:
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            SuccessRateReport
        """
        stats = self.storage.get_aggregate_stats(start_date, end_date)

        total = stats.get("total_prints", 0) or 0
        successful = stats.get("successful_prints", 0) or 0
        failed = stats.get("failed_prints", 0) or 0
        cancelled = stats.get("cancelled_prints", 0) or 0

        success_rate = (successful / total * 100) if total > 0 else 0
        failure_rate = (failed / total * 100) if total > 0 else 0

        return SuccessRateReport(
            total_prints=total,
            successful=successful,
            failed=failed,
            cancelled=cancelled,
            success_rate=round(success_rate, 2),
            failure_rate=round(failure_rate, 2),
        )

    def generate_material_usage_reports(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[MaterialUsageReport]:
        """
        Generate material usage reports.

        Args:
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            List of MaterialUsageReport
        """
        summary = self.storage.get_material_summary(start_date, end_date)

        reports = []
        for item in summary:
            reports.append(MaterialUsageReport(
                material_type=item.get("material_type", "unknown"),
                total_grams=item.get("total_grams", 0) or 0,
                total_cost=item.get("total_cost", 0) or 0,
                usage_count=item.get("usage_count", 0) or 0,
                avg_per_print=item.get("avg_grams_per_use", 0) or 0,
            ))

        return reports

    def generate_cost_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> CostReport:
        """
        Generate cost report.

        Args:
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            CostReport
        """
        stats = self.storage.get_aggregate_stats(start_date, end_date)
        material_summary = self.storage.get_material_summary(start_date, end_date)
        daily_stats = self.storage.get_daily_stats(start_date, end_date)

        # Cost by material
        cost_by_material = {}
        for item in material_summary:
            material = item.get("material_type", "unknown")
            cost = item.get("total_cost", 0) or 0
            cost_by_material[material] = cost

        # Cost trend
        cost_trend = []
        for day in reversed(daily_stats[-30:]):  # Last 30 days
            cost_trend.append({
                "date": day.get("date"),
                "cost": day.get("total_cost", 0) or 0,
            })

        return CostReport(
            total_cost=stats.get("total_cost", 0) or 0,
            avg_cost_per_print=stats.get("avg_cost", 0) or 0,
            cost_by_material=cost_by_material,
            cost_trend=cost_trend,
        )

    def generate_time_report(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> TimeReport:
        """
        Generate time report.

        Args:
            start_date: Filter start date
            end_date: Filter end date

        Returns:
            TimeReport
        """
        stats = self.storage.get_aggregate_stats(start_date, end_date)
        records = self.storage.get_print_records(
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )

        # Calculate time statistics
        total_seconds = stats.get("total_duration_seconds", 0) or 0
        avg_seconds = stats.get("avg_duration_seconds", 0) or 0

        # Find longest and shortest
        durations = [r.get("duration_seconds", 0) for r in records if r.get("duration_seconds")]
        longest = max(durations) if durations else 0
        shortest = min(durations) if durations else 0

        # Prints by day of week
        prints_by_day = {
            "Monday": 0,
            "Tuesday": 0,
            "Wednesday": 0,
            "Thursday": 0,
            "Friday": 0,
            "Saturday": 0,
            "Sunday": 0,
        }

        for record in records:
            started = record.get("started_at")
            if started:
                try:
                    dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    day_name = dt.strftime("%A")
                    if day_name in prints_by_day:
                        prints_by_day[day_name] += 1
                except (ValueError, AttributeError):
                    pass

        return TimeReport(
            total_print_time_hours=round(total_seconds / 3600, 2),
            avg_print_time_hours=round(avg_seconds / 3600, 2),
            longest_print_hours=round(longest / 3600, 2),
            shortest_print_hours=round(shortest / 3600, 2),
            prints_by_day=prints_by_day,
        )

    def _get_period_start(self, period: ReportPeriod) -> datetime:
        """Get start date for a period."""
        now = datetime.now()

        if period == ReportPeriod.DAY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == ReportPeriod.WEEK:
            return now - timedelta(days=7)
        elif period == ReportPeriod.MONTH:
            return now - timedelta(days=30)
        elif period == ReportPeriod.QUARTER:
            return now - timedelta(days=90)
        elif period == ReportPeriod.YEAR:
            return now - timedelta(days=365)
        else:  # ALL_TIME
            return datetime(2020, 1, 1)


def generate_report(
    period: ReportPeriod = ReportPeriod.MONTH,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> AnalyticsReport:
    """
    Convenience function to generate a report.

    Args:
        period: Report period
        start_date: Custom start date
        end_date: Custom end date

    Returns:
        AnalyticsReport
    """
    generator = ReportGenerator()
    return generator.generate_report(period, start_date, end_date)
