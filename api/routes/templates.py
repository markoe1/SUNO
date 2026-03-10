"""Clip templates / hooks library routes."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models_v2 import ClipTemplate
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    niche: Optional[str] = None
    hook_text: str = Field(..., min_length=1)
    structure_notes: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    niche: Optional[str] = None
    hook_text: Optional[str] = None
    structure_notes: Optional[str] = None


class TemplateResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    niche: Optional[str]
    hook_text: str
    structure_notes: Optional[str]
    times_used: int
    avg_views: int

    class Config:
        from_attributes = True


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    template = ClipTemplate(
        user_id=current_user.id,
        name=data.name,
        niche=data.niche,
        hook_text=data.hook_text,
        structure_notes=data.structure_notes,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    logger.info(f"Created template: {template.name}")
    return template


@router.get("/", response_model=List[TemplateResponse])
async def list_templates(
    niche: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(ClipTemplate)
        .where(ClipTemplate.user_id == current_user.id)
        .order_by(desc(ClipTemplate.avg_views))
    )
    if niche:
        query = query.where(ClipTemplate.niche == niche)
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: UUID,
    data: TemplateUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClipTemplate)
        .where(ClipTemplate.id == template_id)
        .where(ClipTemplate.user_id == current_user.id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(tmpl, k, v)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClipTemplate)
        .where(ClipTemplate.id == template_id)
        .where(ClipTemplate.user_id == current_user.id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(tmpl)
    await db.commit()


@router.post("/{template_id}/record-use")
async def record_template_use(
    template_id: UUID,
    views_gained: int = 0,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Track that a template was used and update its stats."""
    result = await db.execute(
        select(ClipTemplate)
        .where(ClipTemplate.id == template_id)
        .where(ClipTemplate.user_id == current_user.id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")

    # Rolling average
    total_views = tmpl.avg_views * tmpl.times_used + views_gained
    tmpl.times_used += 1
    tmpl.avg_views = total_views // tmpl.times_used

    await db.commit()
    return {"times_used": tmpl.times_used, "avg_views": tmpl.avg_views}
