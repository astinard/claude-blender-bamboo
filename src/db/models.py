"""SQLAlchemy ORM models for Claude Fab Lab.

Core database models for users, organizations, printers, jobs, materials, and analytics.
"""

import enum
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Enum, Index, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# ============================================================================
# Enums
# ============================================================================

class UserRole(str, enum.Enum):
    """User roles within an organization."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class PlanTier(str, enum.Enum):
    """Subscription plan tiers."""
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class PrinterStatus(str, enum.Enum):
    """Printer connection/operation status."""
    OFFLINE = "offline"
    IDLE = "idle"
    PRINTING = "printing"
    PAUSED = "paused"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class JobStatus(str, enum.Enum):
    """Print job status."""
    PENDING = "pending"
    QUEUED = "queued"
    PREPARING = "preparing"
    PRINTING = "printing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, enum.Enum):
    """Print job priority."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MaterialType(str, enum.Enum):
    """Common material types."""
    PLA = "PLA"
    PETG = "PETG"
    ABS = "ABS"
    ASA = "ASA"
    TPU = "TPU"
    NYLON = "Nylon"
    PC = "PC"
    PVA = "PVA"
    CUSTOM = "Custom"


# ============================================================================
# Core Models
# ============================================================================

class Organization(Base):
    """Organization/team that owns printers and employs users."""
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_tier: Mapped[PlanTier] = mapped_column(Enum(PlanTier), default=PlanTier.FREE)
    billing_email: Mapped[Optional[str]] = mapped_column(String(255))
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255))
    max_printers: Mapped[int] = mapped_column(Integer, default=1)
    max_users: Mapped[int] = mapped_column(Integer, default=1)
    storage_limit_gb: Mapped[int] = mapped_column(Integer, default=1)
    ai_generations_limit: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="organization")
    printers: Mapped[List["Printer"]] = relationship("Printer", back_populates="organization")
    materials: Mapped[List["Material"]] = relationship("Material", back_populates="organization")
    models: Mapped[List["Model3D"]] = relationship("Model3D", back_populates="organization")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "plan_tier": self.plan_tier.value,
            "max_printers": self.max_printers,
            "created_at": self.created_at.isoformat()
        }


class User(Base):
    """User account."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # OAuth fields
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50))
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
    print_jobs: Mapped[List["PrintJob"]] = relationship("PrintJob", back_populates="user")
    models: Mapped[List["Model3D"]] = relationship("Model3D", back_populates="user")
    api_keys: Mapped[List["APIKey"]] = relationship("APIKey", back_populates="user")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role.value,
            "organization_id": self.organization_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat()
        }


class APIKey(Base):
    """API key for programmatic access."""
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False)  # First 8 chars for identification
    scopes: Mapped[Optional[str]] = mapped_column(Text)  # JSON array of allowed scopes
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")


class Printer(Base):
    """3D printer device."""
    __tablename__ = "printers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "X1C", "P1S", "A1"
    serial_number: Mapped[Optional[str]] = mapped_column(String(100), unique=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv4 or IPv6
    access_code: Mapped[Optional[str]] = mapped_column(String(255))  # Encrypted
    status: Mapped[PrinterStatus] = mapped_column(Enum(PrinterStatus), default=PrinterStatus.OFFLINE)

    # Current state
    bed_temp: Mapped[Optional[float]] = mapped_column(Float)
    nozzle_temp: Mapped[Optional[float]] = mapped_column(Float)
    chamber_temp: Mapped[Optional[float]] = mapped_column(Float)
    current_job_id: Mapped[Optional[str]] = mapped_column(String(36))
    print_progress: Mapped[Optional[float]] = mapped_column(Float)  # 0-100

    # Stats
    total_prints: Mapped[int] = mapped_column(Integer, default=0)
    successful_prints: Mapped[int] = mapped_column(Integer, default=0)
    total_print_time_hours: Mapped[float] = mapped_column(Float, default=0.0)
    total_filament_used_grams: Mapped[float] = mapped_column(Float, default=0.0)

    # Maintenance
    nozzle_hours: Mapped[float] = mapped_column(Float, default=0.0)
    last_maintenance: Mapped[Optional[datetime]] = mapped_column(DateTime)

    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="printers")
    print_jobs: Mapped[List["PrintJob"]] = relationship("PrintJob", back_populates="printer")
    loaded_materials: Mapped[List["PrinterMaterial"]] = relationship("PrinterMaterial", back_populates="printer")

    __table_args__ = (
        Index("ix_printers_org_status", "organization_id", "status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "status": self.status.value,
            "bed_temp": self.bed_temp,
            "nozzle_temp": self.nozzle_temp,
            "print_progress": self.print_progress,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None
        }


class Material(Base):
    """Material/filament spool inventory."""
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_type: Mapped[MaterialType] = mapped_column(Enum(MaterialType), default=MaterialType.PLA)
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    color: Mapped[str] = mapped_column(String(50), nullable=False)
    color_hex: Mapped[Optional[str]] = mapped_column(String(7))  # #RRGGBB

    # Inventory
    total_weight_grams: Mapped[float] = mapped_column(Float, default=1000.0)
    remaining_grams: Mapped[float] = mapped_column(Float, default=1000.0)
    low_threshold_grams: Mapped[float] = mapped_column(Float, default=100.0)

    # Cost tracking
    cost_per_gram: Mapped[float] = mapped_column(Float, default=0.025)
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Print settings
    print_temp_min: Mapped[int] = mapped_column(Integer, default=190)
    print_temp_max: Mapped[int] = mapped_column(Integer, default=220)
    bed_temp_min: Mapped[int] = mapped_column(Integer, default=50)
    bed_temp_max: Mapped[int] = mapped_column(Integer, default=60)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="materials")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "material_type": self.material_type.value,
            "color": self.color,
            "remaining_grams": self.remaining_grams,
            "remaining_percent": round(self.remaining_grams / self.total_weight_grams * 100, 1)
        }


class PrinterMaterial(Base):
    """Material currently loaded in a printer's AMS slot."""
    __tablename__ = "printer_materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    printer_id: Mapped[str] = mapped_column(String(36), ForeignKey("printers.id"), index=True)
    material_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("materials.id"))
    slot_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-3 for AMS
    loaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    printer: Mapped["Printer"] = relationship("Printer", back_populates="loaded_materials")
    material: Mapped[Optional["Material"]] = relationship("Material")

    __table_args__ = (
        UniqueConstraint("printer_id", "slot_number", name="uq_printer_slot"),
    )


class Model3D(Base):
    """3D model file."""
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # File info
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    file_format: Mapped[str] = mapped_column(String(20), default="stl")  # stl, 3mf, obj

    # Geometry
    vertices: Mapped[Optional[int]] = mapped_column(Integer)
    faces: Mapped[Optional[int]] = mapped_column(Integer)
    volume_cm3: Mapped[Optional[float]] = mapped_column(Float)
    bounding_box: Mapped[Optional[str]] = mapped_column(Text)  # JSON: [x, y, z]
    is_watertight: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Print estimation
    estimated_print_time_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    estimated_material_grams: Mapped[Optional[float]] = mapped_column(Float)

    # AI generation
    was_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    generation_prompt: Mapped[Optional[str]] = mapped_column(Text)
    generation_provider: Mapped[Optional[str]] = mapped_column(String(50))

    # Version tracking
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("models.id"))

    # Thumbnail
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="models")
    user: Mapped["User"] = relationship("User", back_populates="models")
    print_jobs: Mapped[List["PrintJob"]] = relationship("PrintJob", back_populates="model")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "file_format": self.file_format,
            "volume_cm3": self.volume_cm3,
            "was_ai_generated": self.was_ai_generated,
            "version": self.version,
            "created_at": self.created_at.isoformat()
        }


class PrintJob(Base):
    """Print job record."""
    __tablename__ = "print_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    printer_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("printers.id"), index=True)
    model_id: Mapped[str] = mapped_column(String(36), ForeignKey("models.id"), index=True)

    # Job details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    priority: Mapped[JobPriority] = mapped_column(Enum(JobPriority), default=JobPriority.NORMAL)

    # Queue position
    queue_position: Mapped[Optional[int]] = mapped_column(Integer)

    # Time tracking
    queued_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    estimated_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    actual_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer)

    # Progress
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    current_layer: Mapped[Optional[int]] = mapped_column(Integer)
    total_layers: Mapped[Optional[int]] = mapped_column(Integer)

    # Material usage
    estimated_material_grams: Mapped[Optional[float]] = mapped_column(Float)
    actual_material_grams: Mapped[Optional[float]] = mapped_column(Float)
    material_cost: Mapped[Optional[float]] = mapped_column(Float)

    # Print settings
    settings: Mapped[Optional[str]] = mapped_column(Text)  # JSON

    # Failure tracking
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    failure_detected_by: Mapped[Optional[str]] = mapped_column(String(50))  # "user", "ai", "sensor"

    # G-code
    gcode_path: Mapped[Optional[str]] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="print_jobs")
    printer: Mapped[Optional["Printer"]] = relationship("Printer", back_populates="print_jobs")
    model: Mapped["Model3D"] = relationship("Model3D", back_populates="print_jobs")

    __table_args__ = (
        Index("ix_print_jobs_org_status", "organization_id", "status"),
        Index("ix_print_jobs_printer_started", "printer_id", "started_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority.value,
            "progress_percent": self.progress_percent,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "created_at": self.created_at.isoformat()
        }


class AnalyticsEvent(Base):
    """Time-series analytics event."""
    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    printer_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)

    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_data: Mapped[Optional[str]] = mapped_column(Text)  # JSON

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_analytics_printer_time", "printer_id", "timestamp"),
        Index("ix_analytics_org_type_time", "organization_id", "event_type", "timestamp"),
    )


class AuditLog(Base):
    """Audit log for compliance."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    user_email: Mapped[Optional[str]] = mapped_column(String(255))

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36))

    details: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))

    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_audit_org_time", "organization_id", "timestamp"),
        Index("ix_audit_user_time", "user_id", "timestamp"),
    )
