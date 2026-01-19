"""3D model routes."""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.repositories.models import Model3DRepository
from src.auth.middleware import CurrentUser, require_permission
from src.auth.rbac import Permission

router = APIRouter()


class ModelResponse(BaseModel):
    id: str
    name: str
    file_format: str
    volume_cm3: Optional[float] = None
    was_ai_generated: bool
    version: int
    created_at: str


class ModelGenerate(BaseModel):
    prompt: str
    style: str = "realistic"


@router.get("", response_model=List[ModelResponse])
async def list_models(
    current_user: CurrentUser,
    ai_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """List 3D models."""
    repo = Model3DRepository(db)
    models = await repo.get_by_organization(
        current_user.org_id,
        ai_generated_only=ai_only
    )
    return [ModelResponse(**m.to_dict()) for m in models]


@router.get("/search")
async def search_models(
    q: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Search models by name or description."""
    repo = Model3DRepository(db)
    models = await repo.search(current_user.org_id, q)
    return [ModelResponse(**m.to_dict()) for m in models]


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db)
):
    """Get model details."""
    repo = Model3DRepository(db)
    model = await repo.get_by_id(model_id)
    if not model or model.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelResponse(**model.to_dict())


@router.post("/upload", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def upload_model(
    file: UploadFile = File(...),
    name: Optional[str] = None,
    current_user: CurrentUser = Depends(require_permission(Permission.MODELS_CREATE)),
    db: AsyncSession = Depends(get_db)
):
    """Upload a 3D model file."""
    import os
    from pathlib import Path

    # Validate file type
    allowed_extensions = {".stl", ".3mf", ".obj", ".gltf", ".glb"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"File type {ext} not supported")

    # Save file
    upload_dir = Path(f"data/models/{current_user.org_id}")
    upload_dir.mkdir(parents=True, exist_ok=True)

    import uuid
    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}{ext}"

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Create database record
    repo = Model3DRepository(db)
    model = await repo.create_model(
        organization_id=current_user.org_id,
        user_id=current_user.id,
        name=name or file.filename,
        file_path=str(file_path),
        file_format=ext[1:],
        file_size_bytes=len(content)
    )
    await db.commit()

    return ModelResponse(**model.to_dict())


@router.post("/generate", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def generate_model(
    request: ModelGenerate,
    current_user: CurrentUser = Depends(require_permission(Permission.AI_GENERATE)),
    db: AsyncSession = Depends(get_db)
):
    """Generate a 3D model from text prompt using AI."""
    # Check quota
    repo = Model3DRepository(db)
    from src.db.repositories.organizations import OrganizationRepository
    org_repo = OrganizationRepository(db)

    org = await org_repo.get_by_id(current_user.org_id)
    current_usage = await repo.get_ai_generation_count(current_user.org_id)

    if current_usage >= org.ai_generations_limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="AI generation quota exceeded"
        )

    # TODO: Implement actual AI generation
    # For now, create a placeholder record
    model = await repo.create_model(
        organization_id=current_user.org_id,
        user_id=current_user.id,
        name=f"Generated: {request.prompt[:50]}",
        file_path="pending",
        file_format="glb",
        was_ai_generated=True,
        generation_prompt=request.prompt,
        generation_provider="placeholder"
    )
    await db.commit()

    return ModelResponse(**model.to_dict())


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.MODELS_DELETE)),
    db: AsyncSession = Depends(get_db)
):
    """Delete a model."""
    repo = Model3DRepository(db)
    model = await repo.get_by_id(model_id)
    if not model or model.organization_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Model not found")

    # Delete file
    import os
    if model.file_path and os.path.exists(model.file_path):
        os.remove(model.file_path)

    await repo.delete(model_id)
    await db.commit()
