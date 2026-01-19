"""Printer repository for printer-related database operations."""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Printer, PrinterStatus, PrinterMaterial
from src.db.repositories.base import BaseRepository


class PrinterRepository(BaseRepository[Printer]):
    """Repository for Printer entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Printer)

    async def get_by_serial(self, serial_number: str) -> Optional[Printer]:
        """Get printer by serial number."""
        result = await self.session.execute(
            select(Printer).where(Printer.serial_number == serial_number)
        )
        return result.scalar_one_or_none()

    async def get_by_organization(
        self,
        organization_id: str,
        status: Optional[PrinterStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Printer]:
        """Get printers in an organization."""
        query = select(Printer).where(Printer.organization_id == organization_id)

        if status:
            query = query.where(Printer.status == status)

        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_available(self, organization_id: str) -> List[Printer]:
        """Get printers that are available (idle or printing can queue)."""
        result = await self.session.execute(
            select(Printer).where(
                Printer.organization_id == organization_id,
                Printer.status.in_([PrinterStatus.IDLE, PrinterStatus.PRINTING])
            )
        )
        return list(result.scalars().all())

    async def get_online(self, organization_id: str) -> List[Printer]:
        """Get all online printers (seen in last 5 minutes)."""
        threshold = datetime.utcnow() - timedelta(minutes=5)
        result = await self.session.execute(
            select(Printer).where(
                Printer.organization_id == organization_id,
                Printer.last_seen > threshold,
                Printer.status != PrinterStatus.OFFLINE
            )
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        printer_id: str,
        status: PrinterStatus,
        **state_updates
    ) -> Optional[Printer]:
        """Update printer status and state."""
        return await self.update(
            printer_id,
            status=status,
            last_seen=datetime.utcnow(),
            **state_updates
        )

    async def update_temperatures(
        self,
        printer_id: str,
        bed_temp: Optional[float] = None,
        nozzle_temp: Optional[float] = None,
        chamber_temp: Optional[float] = None
    ) -> None:
        """Update printer temperature readings."""
        updates = {"last_seen": datetime.utcnow()}
        if bed_temp is not None:
            updates["bed_temp"] = bed_temp
        if nozzle_temp is not None:
            updates["nozzle_temp"] = nozzle_temp
        if chamber_temp is not None:
            updates["chamber_temp"] = chamber_temp
        await self.update(printer_id, **updates)

    async def update_print_progress(
        self,
        printer_id: str,
        progress: float,
        job_id: Optional[str] = None
    ) -> None:
        """Update current print progress."""
        await self.update(
            printer_id,
            print_progress=progress,
            current_job_id=job_id,
            last_seen=datetime.utcnow()
        )

    async def record_print_complete(
        self,
        printer_id: str,
        success: bool,
        duration_hours: float,
        filament_grams: float
    ) -> None:
        """Record a completed print in stats."""
        printer = await self.get_by_id(printer_id)
        if not printer:
            return

        updates = {
            "total_prints": printer.total_prints + 1,
            "total_print_time_hours": printer.total_print_time_hours + duration_hours,
            "total_filament_used_grams": printer.total_filament_used_grams + filament_grams,
            "nozzle_hours": printer.nozzle_hours + duration_hours,
            "status": PrinterStatus.IDLE,
            "current_job_id": None,
            "print_progress": None
        }
        if success:
            updates["successful_prints"] = printer.successful_prints + 1

        await self.update(printer_id, **updates)

    async def get_loaded_materials(self, printer_id: str) -> List[PrinterMaterial]:
        """Get materials currently loaded in printer."""
        result = await self.session.execute(
            select(PrinterMaterial)
            .where(PrinterMaterial.printer_id == printer_id)
            .order_by(PrinterMaterial.slot_number)
        )
        return list(result.scalars().all())

    async def set_loaded_material(
        self,
        printer_id: str,
        slot_number: int,
        material_id: Optional[str]
    ) -> PrinterMaterial:
        """Set material in a printer slot."""
        # Check if slot already has material
        result = await self.session.execute(
            select(PrinterMaterial).where(
                PrinterMaterial.printer_id == printer_id,
                PrinterMaterial.slot_number == slot_number
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.material_id = material_id
            existing.loaded_at = datetime.utcnow()
            await self.session.flush()
            return existing
        else:
            pm = PrinterMaterial(
                printer_id=printer_id,
                slot_number=slot_number,
                material_id=material_id
            )
            self.session.add(pm)
            await self.session.flush()
            return pm
