"""Analytics storage using SQLite.

Provides persistent storage for print analytics data.
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from src.utils import get_logger
from src.config import get_settings

logger = get_logger("analytics.storage")


@dataclass
class AnalyticsStorage:
    """
    SQLite-based storage for print analytics.

    Stores print records, material usage, and cost data.
    """

    db_path: str

    def __post_init__(self) -> None:
        """Initialize database."""
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS print_records (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    outcome TEXT DEFAULT 'unknown',
                    duration_seconds INTEGER,
                    layers_total INTEGER,
                    layers_completed INTEGER,
                    material_type TEXT,
                    material_used_grams REAL,
                    material_cost REAL,
                    printer_id TEXT,
                    notes TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS material_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_type TEXT NOT NULL,
                    amount_grams REAL NOT NULL,
                    cost REAL,
                    used_at TEXT NOT NULL,
                    print_id TEXT,
                    FOREIGN KEY (print_id) REFERENCES print_records(id)
                );

                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    prints_started INTEGER DEFAULT 0,
                    prints_completed INTEGER DEFAULT 0,
                    prints_failed INTEGER DEFAULT 0,
                    total_print_time_seconds INTEGER DEFAULT 0,
                    total_material_grams REAL DEFAULT 0,
                    total_cost REAL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_print_started ON print_records(started_at);
                CREATE INDEX IF NOT EXISTS idx_print_outcome ON print_records(outcome);
                CREATE INDEX IF NOT EXISTS idx_material_type ON material_usage(material_type);
                CREATE INDEX IF NOT EXISTS idx_material_date ON material_usage(used_at);
            """)

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection context."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_print_record(self, record: Dict[str, Any]) -> str:
        """
        Save a print record.

        Args:
            record: Print record data

        Returns:
            Record ID
        """
        record_id = record.get("id", "")
        metadata = record.get("metadata", {})

        with self._connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO print_records
                (id, file_name, file_path, started_at, completed_at, outcome,
                 duration_seconds, layers_total, layers_completed, material_type,
                 material_used_grams, material_cost, printer_id, notes, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record_id,
                record.get("file_name", ""),
                record.get("file_path"),
                record.get("started_at", datetime.now().isoformat()),
                record.get("completed_at"),
                record.get("outcome", "unknown"),
                record.get("duration_seconds"),
                record.get("layers_total"),
                record.get("layers_completed"),
                record.get("material_type"),
                record.get("material_used_grams"),
                record.get("material_cost"),
                record.get("printer_id"),
                record.get("notes"),
                json.dumps(metadata) if metadata else None,
            ))

        logger.debug(f"Saved print record: {record_id}")
        return record_id

    def get_print_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a print record by ID.

        Args:
            record_id: Record ID

        Returns:
            Print record or None
        """
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM print_records WHERE id = ?",
                (record_id,)
            ).fetchone()

            if row:
                return self._row_to_dict(row)
            return None

    def get_print_records(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        outcome: Optional[str] = None,
        material_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get print records with optional filters.

        Args:
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)
            outcome: Filter by outcome
            material_type: Filter by material type
            limit: Maximum records to return

        Returns:
            List of print records
        """
        query = "SELECT * FROM print_records WHERE 1=1"
        params = []

        if start_date:
            query += " AND started_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND started_at <= ?"
            params.append(end_date)
        if outcome:
            query += " AND outcome = ?"
            params.append(outcome)
        if material_type:
            query += " AND material_type = ?"
            params.append(material_type)

        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def log_material_usage(
        self,
        material_type: str,
        amount_grams: float,
        cost: Optional[float] = None,
        print_id: Optional[str] = None,
    ) -> None:
        """
        Log material usage.

        Args:
            material_type: Type of material
            amount_grams: Amount used in grams
            cost: Cost of material
            print_id: Associated print ID
        """
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO material_usage
                (material_type, amount_grams, cost, used_at, print_id)
                VALUES (?, ?, ?, ?, ?)
            """, (
                material_type,
                amount_grams,
                cost,
                datetime.now().isoformat(),
                print_id,
            ))

    def get_material_usage(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        material_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get material usage records.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date
            material_type: Filter by material type

        Returns:
            List of material usage records
        """
        query = "SELECT * FROM material_usage WHERE 1=1"
        params = []

        if start_date:
            query += " AND used_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND used_at <= ?"
            params.append(end_date)
        if material_type:
            query += " AND material_type = ?"
            params.append(material_type)

        query += " ORDER BY used_at DESC"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def update_daily_stats(
        self,
        date: str,
        prints_started: int = 0,
        prints_completed: int = 0,
        prints_failed: int = 0,
        print_time_seconds: int = 0,
        material_grams: float = 0,
        cost: float = 0,
    ) -> None:
        """
        Update daily statistics.

        Args:
            date: Date (YYYY-MM-DD format)
            prints_started: Number of prints started
            prints_completed: Number of prints completed
            prints_failed: Number of prints failed
            print_time_seconds: Total print time
            material_grams: Total material used
            cost: Total cost
        """
        with self._connection() as conn:
            # Try to update existing
            result = conn.execute("""
                UPDATE daily_stats SET
                    prints_started = prints_started + ?,
                    prints_completed = prints_completed + ?,
                    prints_failed = prints_failed + ?,
                    total_print_time_seconds = total_print_time_seconds + ?,
                    total_material_grams = total_material_grams + ?,
                    total_cost = total_cost + ?
                WHERE date = ?
            """, (
                prints_started, prints_completed, prints_failed,
                print_time_seconds, material_grams, cost, date
            ))

            # Insert if not exists
            if result.rowcount == 0:
                conn.execute("""
                    INSERT INTO daily_stats
                    (date, prints_started, prints_completed, prints_failed,
                     total_print_time_seconds, total_material_grams, total_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    date, prints_started, prints_completed, prints_failed,
                    print_time_seconds, material_grams, cost
                ))

    def get_daily_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get daily statistics.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of daily stats
        """
        query = "SELECT * FROM daily_stats WHERE 1=1"
        params = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def get_aggregate_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregate statistics.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Aggregate statistics
        """
        query = """
            SELECT
                COUNT(*) as total_prints,
                SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successful_prints,
                SUM(CASE WHEN outcome = 'failed' THEN 1 ELSE 0 END) as failed_prints,
                SUM(CASE WHEN outcome = 'cancelled' THEN 1 ELSE 0 END) as cancelled_prints,
                AVG(duration_seconds) as avg_duration_seconds,
                SUM(duration_seconds) as total_duration_seconds,
                SUM(material_used_grams) as total_material_grams,
                SUM(material_cost) as total_cost,
                AVG(material_used_grams) as avg_material_grams,
                AVG(material_cost) as avg_cost
            FROM print_records WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND started_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND started_at <= ?"
            params.append(end_date)

        with self._connection() as conn:
            row = conn.execute(query, params).fetchone()
            if row:
                return self._row_to_dict(row)
            return {}

    def get_material_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get material usage summary by type.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Material usage summary
        """
        query = """
            SELECT
                material_type,
                COUNT(*) as usage_count,
                SUM(amount_grams) as total_grams,
                SUM(cost) as total_cost,
                AVG(amount_grams) as avg_grams_per_use
            FROM material_usage
            WHERE material_type IS NOT NULL
        """
        params = []

        if start_date:
            query += " AND used_at >= ?"
            params.append(start_date)
        if end_date:
            query += " AND used_at <= ?"
            params.append(end_date)

        query += " GROUP BY material_type ORDER BY total_grams DESC"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def delete_print_record(self, record_id: str) -> bool:
        """
        Delete a print record.

        Args:
            record_id: Record ID to delete

        Returns:
            True if deleted
        """
        with self._connection() as conn:
            result = conn.execute(
                "DELETE FROM print_records WHERE id = ?",
                (record_id,)
            )
            return result.rowcount > 0

    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to dictionary."""
        d = dict(row)
        # Parse JSON metadata if present
        if "metadata" in d and d["metadata"]:
            try:
                d["metadata"] = json.loads(d["metadata"])
            except json.JSONDecodeError:
                pass
        return d


def create_storage(db_path: Optional[str] = None) -> AnalyticsStorage:
    """
    Create an analytics storage instance.

    Args:
        db_path: Path to database file (default: data/analytics.db)

    Returns:
        AnalyticsStorage instance
    """
    if db_path is None:
        settings = get_settings()
        data_dir = Path(settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = str(data_dir / "analytics.db")

    return AnalyticsStorage(db_path=db_path)
