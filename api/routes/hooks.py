"""
AI Hook Generator — uses Claude to generate viral clip hooks.
Requires ANTHROPIC_API_KEY in environment.
"""

import os
from typing import Optional
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models_v2 import Client, ClientClip, ClipStatus, ClipTemplate
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/hooks", tags=["hooks"])

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


class HookGenerateRequest(BaseModel):
    niche: str = Field(..., description="Content niche e.g. fitness, finance, mindset")
    client_id: Optional[UUID] = Field(None, description="If provided, uses client's top-performing clips as context")
    context: Optional[str] = Field(None, description="Additional context about the creator or content")
    count: int = Field(5, ge=1, le=20)


class HookGenerateResponse(BaseModel):
    hooks: list[str]
    niche: str
    based_on_clips: int


@router.post("/generate", response_model=HookGenerateResponse)
async def generate_hooks(
    data: HookGenerateRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ANTHROPIC_API_KEY not configured",
        )

    # Pull top performing clips for context if client provided
    top_clips_context = ""
    clips_used = 0

    if data.client_id:
        # Verify ownership
        client_result = await db.execute(
            select(Client)
            .where(Client.id == data.client_id)
            .where(Client.user_id == current_user.id)
        )
        client = client_result.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Get top 10 posted clips by views
        clips_result = await db.execute(
            select(ClientClip)
            .where(ClientClip.client_id == data.client_id)
            .where(ClientClip.status == ClipStatus.POSTED)
            .where(ClientClip.total_views > 0)
            .order_by(desc(ClientClip.total_views))
            .limit(10)
        )
        top_clips = clips_result.scalars().all()
        clips_used = len(top_clips)

        if top_clips:
            clip_lines = []
            for c in top_clips:
                hook = c.hook_used or c.title or "No hook recorded"
                clip_lines.append(f'- "{hook}" → {c.total_views:,} views')
            top_clips_context = (
                f"\n\nTop performing clips for this creator:\n" + "\n".join(clip_lines)
            )

    # Also pull user's best templates for this niche
    templates_result = await db.execute(
        select(ClipTemplate)
        .where(ClipTemplate.user_id == current_user.id)
        .where(ClipTemplate.niche == data.niche)
        .where(ClipTemplate.avg_views > 0)
        .order_by(desc(ClipTemplate.avg_views))
        .limit(5)
    )
    templates = templates_result.scalars().all()
    templates_context = ""
    if templates:
        tmpl_lines = [f'- "{t.hook_text}" (avg {t.avg_views:,} views)' for t in templates]
        templates_context = (
            "\n\nYour proven hook templates for this niche:\n" + "\n".join(tmpl_lines)
        )

    context_block = ""
    if data.context:
        context_block = f"\n\nAdditional context: {data.context}"

    prompt = f"""You are an expert short-form content strategist specializing in viral clip hooks for {data.niche} content.

Generate {data.count} high-converting hook variations for a short-form video clip in the {data.niche} niche.{top_clips_context}{templates_context}{context_block}

Rules for great hooks:
- Open a loop or create immediate curiosity in the first 3 seconds
- Speak directly to the viewer's pain, desire, or identity
- Be specific — numbers and specifics outperform vague claims
- No clickbait — the hook must be deliverable in the clip
- Under 15 words ideally — punchy and direct
- Pattern interrupt — say something they haven't heard before

Return ONLY a numbered list of hooks, one per line. No explanations, no commentary.
Example format:
1. Hook text here
2. Hook text here
"""

    try:
        client_ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client_ai.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude API error in hook generator: {e}")
        raise HTTPException(status_code=500, detail="Hook generation failed — check API key")

    # Parse numbered list
    hooks = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Strip leading number and punctuation (1. 1) 1:)
        import re
        cleaned = re.sub(r"^\d+[\.\)\:]\s*", "", line).strip()
        if cleaned:
            hooks.append(cleaned)

    logger.info(f"Generated {len(hooks)} hooks for niche={data.niche}")
    return HookGenerateResponse(hooks=hooks, niche=data.niche, based_on_clips=clips_used)


@router.post("/save-hook")
async def save_hook_as_template(
    hook_text: str,
    niche: str,
    name: Optional[str] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a generated hook directly to your templates library."""
    template = ClipTemplate(
        user_id=current_user.id,
        name=name or hook_text[:60],
        niche=niche,
        hook_text=hook_text,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return {"saved": True, "template_id": str(template.id)}
