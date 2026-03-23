"""RQ task: auto-assign RAW clips to available editors.

Assignment strategy: least-workload first.
  - Only considers active editors belonging to the same operator.
  - Skips clips that already have an editor assigned.
  - Moves clip status from RAW → EDITING on assignment.

Trigger: enqueue manually or on a schedule (e.g. every hour via APScheduler).
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db.engine import DATABASE_URL
from db.models_v2 import Client, ClientClip, ClipStatus, Editor

logger = logging.getLogger(__name__)


async def _assign_clips_async(operator_user_id: str) -> dict:
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSession = async_sessionmaker(engine, expire_on_commit=False)

    assigned = 0
    skipped = 0
    errors = []

    async with AsyncSession() as db:
        # Get all active editors for this operator
        editors_result = await db.execute(
            select(Editor)
            .where(Editor.user_id == operator_user_id)
            .where(Editor.is_active == True)
        )
        editors = editors_result.scalars().all()

        if not editors:
            logger.info("assign_clips: no active editors for operator %s", operator_user_id)
            await engine.dispose()
            return {"assigned": 0, "skipped": 0, "errors": ["No active editors"]}

        # Get all unassigned RAW clips for this operator's clients
        unassigned_result = await db.execute(
            select(ClientClip, Client)
            .join(Client, ClientClip.client_id == Client.id)
            .where(Client.user_id == operator_user_id)
            .where(ClientClip.status == ClipStatus.RAW)
            .where(ClientClip.editor_id == None)
            .order_by(ClientClip.created_at.asc())  # oldest first
        )
        unassigned_clips = unassigned_result.all()

        if not unassigned_clips:
            logger.info("assign_clips: no unassigned RAW clips for operator %s", operator_user_id)
            await engine.dispose()
            return {"assigned": 0, "skipped": 0, "errors": []}

        logger.info(
            "assign_clips: %d unassigned clips, %d editors for operator %s",
            len(unassigned_clips), len(editors), operator_user_id,
        )

        # Count current active workload per editor
        # (clips in EDITING or REVIEW state)
        workload: dict[str, int] = {str(e.id): 0 for e in editors}
        for editor in editors:
            wl_result = await db.execute(
                select(func.count(ClientClip.id))
                .join(Client, ClientClip.client_id == Client.id)
                .where(Client.user_id == operator_user_id)
                .where(ClientClip.editor_id == editor.id)
                .where(ClientClip.status.in_([ClipStatus.EDITING, ClipStatus.REVIEW]))
            )
            workload[str(editor.id)] = wl_result.scalar() or 0

        # Assign each clip to the editor with the lowest workload
        for clip, client in unassigned_clips:
            try:
                # Pick least-loaded editor
                best_editor = min(editors, key=lambda e: workload[str(e.id)])

                clip.editor_id = best_editor.id
                clip.status = ClipStatus.EDITING
                workload[str(best_editor.id)] += 1

                logger.info(
                    "assign_clips: clip %s → editor %s (workload now %d)",
                    clip.id, best_editor.name, workload[str(best_editor.id)],
                )
                assigned += 1
            except Exception as exc:
                logger.error("assign_clips: failed to assign clip %s: %s", clip.id, exc)
                errors.append(str(exc))
                skipped += 1

        await db.commit()

    await engine.dispose()

    logger.info(
        "assign_clips complete: %d assigned, %d skipped, %d errors",
        assigned, skipped, len(errors),
    )
    return {"assigned": assigned, "skipped": skipped, "errors": errors}


def assign_clips(operator_user_id: str) -> dict:
    """RQ entry point.

    Args:
        operator_user_id: UUID string of the operator (User.id) whose clips to assign.
    """
    return asyncio.run(_assign_clips_async(operator_user_id))
