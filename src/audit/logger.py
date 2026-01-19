"""Comprehensive audit logging for enterprise compliance.

Provides detailed activity tracking for security monitoring,
compliance reporting, and forensic analysis.
"""

import asyncio
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Awaitable
from uuid import uuid4

from src.utils import get_logger

logger = get_logger("audit")


class AuditCategory(str, Enum):
    """Categories of auditable events."""
    AUTH = "authentication"
    ACCESS = "access"
    DATA = "data"
    ADMIN = "administration"
    SYSTEM = "system"
    PRINT = "printing"
    API = "api"


class AuditAction(str, Enum):
    """Specific auditable actions."""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SSO_LOGIN = "sso_login"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLE = "mfa_enable"
    MFA_DISABLE = "mfa_disable"

    # Access
    RESOURCE_ACCESS = "resource_access"
    PERMISSION_DENIED = "permission_denied"
    API_CALL = "api_call"

    # Data
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    IMPORT = "import"

    # Administration
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_INVITE = "user_invite"
    ROLE_CHANGE = "role_change"
    ORG_UPDATE = "organization_update"
    SETTINGS_CHANGE = "settings_change"

    # System
    CONFIG_CHANGE = "config_change"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"
    ERROR = "error"
    SECURITY_ALERT = "security_alert"

    # Printing
    PRINT_START = "print_start"
    PRINT_COMPLETE = "print_complete"
    PRINT_FAIL = "print_fail"
    PRINT_CANCEL = "print_cancel"
    QUEUE_ADD = "queue_add"
    QUEUE_REMOVE = "queue_remove"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    NOTICE = "notice"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """An auditable event."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    category: AuditCategory = AuditCategory.SYSTEM
    action: AuditAction = AuditAction.ERROR
    severity: AuditSeverity = AuditSeverity.INFO

    # Actor (who performed the action)
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_type: str = "user"  # user, system, api_key, service

    # Target (what was affected)
    target_type: Optional[str] = None  # user, model, print_job, organization, etc.
    target_id: Optional[str] = None
    target_name: Optional[str] = None

    # Organization context
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None

    # Request context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None

    # Result
    success: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Additional data
    metadata: Dict[str, Any] = field(default_factory=dict)
    changes: Dict[str, Any] = field(default_factory=dict)  # before/after for updates

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class AuditQuery:
    """Query parameters for searching audit logs."""

    organization_id: Optional[str] = None
    actor_id: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    category: Optional[AuditCategory] = None
    action: Optional[AuditAction] = None
    severity: Optional[AuditSeverity] = None
    success: Optional[bool] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    ip_address: Optional[str] = None
    limit: int = 100
    offset: int = 0


class AuditSink:
    """Base class for audit log destinations."""

    async def write(self, event: AuditEvent) -> None:
        """Write an audit event."""
        raise NotImplementedError

    async def query(self, query: AuditQuery) -> List[AuditEvent]:
        """Query audit events."""
        raise NotImplementedError

    async def close(self) -> None:
        """Close the sink."""
        pass


class FileAuditSink(AuditSink):
    """Write audit logs to JSON files."""

    def __init__(
        self,
        log_dir: str = "logs/audit",
        rotate_daily: bool = True,
        max_file_size_mb: int = 100,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.rotate_daily = rotate_daily
        self.max_file_size_mb = max_file_size_mb
        self._current_file = None
        self._current_date = None

    def _get_log_file(self) -> Path:
        """Get the current log file path."""
        today = datetime.utcnow().date()
        if self.rotate_daily and self._current_date != today:
            self._current_date = today
            self._current_file = self.log_dir / f"audit-{today.isoformat()}.jsonl"
        elif self._current_file is None:
            self._current_file = self.log_dir / "audit.jsonl"
        return self._current_file

    async def write(self, event: AuditEvent) -> None:
        """Write event to log file."""
        log_file = self._get_log_file()
        line = event.to_json() + "\n"

        # Async file write
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._write_sync, log_file, line)

    def _write_sync(self, path: Path, line: str) -> None:
        """Synchronous file write."""
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)

    async def query(self, query: AuditQuery) -> List[AuditEvent]:
        """Query events from log files."""
        events = []
        log_files = sorted(self.log_dir.glob("audit*.jsonl"), reverse=True)

        for log_file in log_files:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        event = AuditEvent(**data)
                        if self._matches_query(event, query):
                            events.append(event)
                            if len(events) >= query.limit + query.offset:
                                break
                    except (json.JSONDecodeError, TypeError):
                        continue

            if len(events) >= query.limit + query.offset:
                break

        return events[query.offset:query.offset + query.limit]

    def _matches_query(self, event: AuditEvent, query: AuditQuery) -> bool:
        """Check if event matches query."""
        if query.organization_id and event.organization_id != query.organization_id:
            return False
        if query.actor_id and event.actor_id != query.actor_id:
            return False
        if query.target_type and event.target_type != query.target_type:
            return False
        if query.target_id and event.target_id != query.target_id:
            return False
        if query.category and event.category != query.category:
            return False
        if query.action and event.action != query.action:
            return False
        if query.severity and event.severity != query.severity:
            return False
        if query.success is not None and event.success != query.success:
            return False
        if query.ip_address and event.ip_address != query.ip_address:
            return False

        event_time = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        if query.start_time and event_time < query.start_time:
            return False
        if query.end_time and event_time > query.end_time:
            return False

        return True


class DatabaseAuditSink(AuditSink):
    """Write audit logs to database (for production)."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        # In production, initialize database connection pool

    async def write(self, event: AuditEvent) -> None:
        """Write event to database."""
        # In production, insert into audit_logs table
        logger.debug(f"DB audit: {event.action.value}")

    async def query(self, query: AuditQuery) -> List[AuditEvent]:
        """Query events from database."""
        # In production, build SQL query with filters
        return []


class AuditLogger:
    """
    Comprehensive audit logging service.

    Features:
    - Multiple output sinks (file, database, external services)
    - Structured event data
    - Query and search capabilities
    - Automatic context capture
    - Compliance-ready formatting
    """

    def __init__(self):
        self._sinks: List[AuditSink] = []
        self._enabled = True
        self._default_severity = AuditSeverity.INFO
        self._hooks: List[Callable[[AuditEvent], Awaitable[None]]] = []

    def add_sink(self, sink: AuditSink) -> None:
        """Add an audit log sink."""
        self._sinks.append(sink)

    def add_hook(self, hook: Callable[[AuditEvent], Awaitable[None]]) -> None:
        """Add a hook to be called for each event."""
        self._hooks.append(hook)

    @property
    def enabled(self) -> bool:
        """Check if audit logging is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable audit logging."""
        self._enabled = True

    def disable(self) -> None:
        """Disable audit logging."""
        self._enabled = False

    async def log(self, event: AuditEvent) -> None:
        """
        Log an audit event.

        Args:
            event: The audit event to log
        """
        if not self._enabled:
            return

        # Write to all sinks
        for sink in self._sinks:
            try:
                await sink.write(event)
            except Exception as e:
                logger.error(f"Failed to write audit event to sink: {e}")

        # Call hooks
        for hook in self._hooks:
            try:
                await hook(event)
            except Exception as e:
                logger.error(f"Audit hook error: {e}")

    async def log_auth(
        self,
        action: AuditAction,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Log an authentication event."""
        event = AuditEvent(
            category=AuditCategory.AUTH,
            action=action,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            actor_id=actor_id,
            actor_email=actor_email,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            error_message=error_message,
            metadata=kwargs,
        )
        await self.log(event)

    async def log_access(
        self,
        action: AuditAction,
        actor_id: str,
        target_type: str,
        target_id: str,
        organization_id: Optional[str] = None,
        success: bool = True,
        **kwargs,
    ) -> None:
        """Log an access event."""
        event = AuditEvent(
            category=AuditCategory.ACCESS,
            action=action,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            organization_id=organization_id,
            success=success,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            metadata=kwargs,
        )
        await self.log(event)

    async def log_data(
        self,
        action: AuditAction,
        actor_id: str,
        target_type: str,
        target_id: str,
        organization_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log a data modification event."""
        event = AuditEvent(
            category=AuditCategory.DATA,
            action=action,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            organization_id=organization_id,
            changes=changes or {},
            metadata=kwargs,
        )
        await self.log(event)

    async def log_admin(
        self,
        action: AuditAction,
        actor_id: str,
        actor_email: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        organization_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> None:
        """Log an administrative action."""
        event = AuditEvent(
            category=AuditCategory.ADMIN,
            action=action,
            severity=AuditSeverity.NOTICE,
            actor_id=actor_id,
            actor_email=actor_email,
            target_type=target_type,
            target_id=target_id,
            organization_id=organization_id,
            changes=changes or {},
            metadata=kwargs,
        )
        await self.log(event)

    async def log_print(
        self,
        action: AuditAction,
        actor_id: str,
        job_id: str,
        organization_id: Optional[str] = None,
        printer_id: Optional[str] = None,
        success: bool = True,
        **kwargs,
    ) -> None:
        """Log a print-related event."""
        event = AuditEvent(
            category=AuditCategory.PRINT,
            action=action,
            actor_id=actor_id,
            target_type="print_job",
            target_id=job_id,
            organization_id=organization_id,
            success=success,
            metadata={"printer_id": printer_id, **kwargs},
        )
        await self.log(event)

    async def log_security_alert(
        self,
        message: str,
        ip_address: Optional[str] = None,
        actor_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Log a security alert."""
        event = AuditEvent(
            category=AuditCategory.SYSTEM,
            action=AuditAction.SECURITY_ALERT,
            severity=AuditSeverity.CRITICAL,
            actor_id=actor_id,
            ip_address=ip_address,
            error_message=message,
            metadata=kwargs,
        )
        await self.log(event)

    async def query(self, query: AuditQuery) -> List[AuditEvent]:
        """Query audit events."""
        all_events = []
        for sink in self._sinks:
            try:
                events = await sink.query(query)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Failed to query audit sink: {e}")

        # Sort by timestamp and apply limit
        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        return all_events[:query.limit]

    async def get_user_activity(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get recent activity for a user."""
        query = AuditQuery(
            actor_id=user_id,
            start_time=datetime.utcnow() - timedelta(days=days),
            limit=limit,
        )
        return await self.query(query)

    async def get_organization_activity(
        self,
        organization_id: str,
        days: int = 30,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get recent activity for an organization."""
        query = AuditQuery(
            organization_id=organization_id,
            start_time=datetime.utcnow() - timedelta(days=days),
            limit=limit,
        )
        return await self.query(query)

    async def get_failed_logins(
        self,
        hours: int = 24,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get recent failed login attempts."""
        query = AuditQuery(
            action=AuditAction.LOGIN_FAILURE,
            start_time=datetime.utcnow() - timedelta(hours=hours),
            limit=limit,
        )
        return await self.query(query)

    async def close(self) -> None:
        """Close all sinks."""
        for sink in self._sinks:
            await sink.close()


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
        # Add default file sink
        _audit_logger.add_sink(FileAuditSink())
    return _audit_logger


async def audit(
    action: AuditAction,
    actor_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    **kwargs,
) -> None:
    """
    Convenience function for logging audit events.

    Args:
        action: The action being logged
        actor_id: ID of the actor performing the action
        target_type: Type of the target resource
        target_id: ID of the target resource
        **kwargs: Additional event fields
    """
    audit_logger = get_audit_logger()

    event = AuditEvent(
        action=action,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        **kwargs,
    )

    await audit_logger.log(event)
