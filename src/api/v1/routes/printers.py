"""Printer management routes."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.repositories.printers import PrinterRepository
from src.db.models import PrinterStatus
from src.auth.middleware import CurrentUser, require_permission
from src.auth.rbac import Permission
from src.utils import get_logger

logger = get_logger("api.printers")
router = APIRouter()


class PrinterCreate(BaseModel):
    name: str
    model: str
    ip_address: Optional[str] = None
    access_code: Optional[str] = None
    serial_number: Optional[str] = None


class PrinterUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    access_code: Optional[str] = None


class PrinterResponse(BaseModel):
    id: str
    name: str
    model: str
    status: str
    bed_temp: Optional[float] = None
    nozzle_temp: Optional[float] = None
    print_progress: Optional[float] = None
    last_seen: Optional[str] = None


@router.get("", response_model=List[PrinterResponse])
async def list_printers(
    current_user: CurrentUser,
    status_filter: Optional[PrinterStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all printers in the organization."""
    repo = PrinterRepository(db)
    printers = await repo.get_by_organization(
        current_user.org_id,
        status=status_filter
    )
    return [PrinterResponse(**p.to_dict()) for p in printers]


@router.post("", response_model=PrinterResponse, status_code=status.HTTP_201_CREATED)
async def create_printer(
    request: PrinterCreate,
    current_user: CurrentUser = Depends(require_permission(Permission.PRINTERS_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    """Add a new printer to the organization."""
    repo = PrinterRepository(db)
    printer = await repo.create(
        organization_id=current_user.org_id,
        name=request.name,
        model=request.model,
        ip_address=request.ip_address,
        access_code=request.access_code,
        serial_number=request.serial_number
    )
    await db.commit()
    logger.info(f"Printer created: {printer.id}")
    return PrinterResponse(**printer.to_dict())


@router.get("/{printer_id}", response_model=PrinterResponse)
async def get_printer(
    printer_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get printer details."""
    repo = PrinterRepository(db)
    printer = await repo.get_by_id(printer_id)

    if not printer or printer.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Printer not found")

    return PrinterResponse(**printer.to_dict())


@router.patch("/{printer_id}", response_model=PrinterResponse)
async def update_printer(
    printer_id: str,
    request: PrinterUpdate,
    current_user: CurrentUser = Depends(require_permission(Permission.PRINTERS_UPDATE)),
    db: AsyncSession = Depends(get_db)
):
    """Update printer settings."""
    repo = PrinterRepository(db)
    printer = await repo.get_by_id(printer_id)

    if not printer or printer.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Printer not found")

    updates = request.model_dump(exclude_unset=True)
    printer = await repo.update(printer_id, **updates)
    await db.commit()

    return PrinterResponse(**printer.to_dict())


@router.delete("/{printer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_printer(
    printer_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.PRINTERS_DELETE)),
    db: AsyncSession = Depends(get_db)
):
    """Remove a printer from the organization."""
    repo = PrinterRepository(db)
    printer = await repo.get_by_id(printer_id)

    if not printer or printer.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Printer not found")

    await repo.delete(printer_id)
    await db.commit()
    logger.info(f"Printer deleted: {printer_id}")


@router.post("/{printer_id}/command")
async def send_printer_command(
    printer_id: str,
    command: dict,
    current_user: CurrentUser = Depends(require_permission(Permission.PRINTERS_CONTROL)),
    db: AsyncSession = Depends(get_db)
):
    """Send a command to a printer."""
    repo = PrinterRepository(db)
    printer = await repo.get_by_id(printer_id)

    if not printer or printer.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Printer not found")

    # TODO: Implement actual printer communication via MQTT
    logger.info(f"Command sent to printer {printer_id}: {command}")

    return {"status": "command_sent", "printer_id": printer_id}
