"""Audit logging service."""
from datetime import datetime, timedelta
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import uuid
import structlog
from ..models.database import AuditEvent

logger = structlog.get_logger(__name__)


class AuditService:
    """Service for logging and querying audit events."""

    async def log_event(
        self,
        db: AsyncSession,
        event_type: str,
        entity_type: str,
        entity_id: str,
        details: dict[str, Any],
        actor_id: Optional[uuid.UUID] = None,
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            db: Database session
            event_type: Type of event (create, update, delete, etc.)
            entity_type: Type of entity (conversation, tool_run, etc.)
            entity_id: ID of the entity
            details: Additional event details
            actor_id: ID of the user performing the action

        Returns:
            Created AuditEvent
        """
        event = AuditEvent(
            actor_id=actor_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=details,
        )
        db.add(event)
        await db.flush()
        logger.info(
            "audit_event_logged",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=str(actor_id) if actor_id else None,
        )
        return event

    async def query_events(
        self,
        db: AsyncSession,
        event_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        days_back: int = 30,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditEvent], int]:
        """
        Query audit events with optional filtering.

        Args:
            db: Database session
            event_type: Filter by event type
            entity_type: Filter by entity type
            actor_id: Filter by actor
            days_back: Only include events from last N days
            limit: Maximum results
            offset: Pagination offset

        Returns:
            Tuple of (events, total_count)
        """
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        conditions = [AuditEvent.created_at >= cutoff]

        if event_type:
            conditions.append(AuditEvent.event_type == event_type)
        if entity_type:
            conditions.append(AuditEvent.entity_type == entity_type)
        if actor_id:
            conditions.append(AuditEvent.actor_id == actor_id)

        query = select(AuditEvent).where(and_(*conditions))

        # Get total count
        count_result = await db.execute(select(AuditEvent).where(and_(*conditions)))
        total = len(count_result.all())

        # Get paginated results
        result = await db.execute(
            query.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)
        )
        events = result.scalars().all()

        logger.debug(
            "audit_events_queried",
            event_type=event_type,
            entity_type=entity_type,
            returned=len(events),
            total=total,
        )
        return events, total

    async def get_user_activity(
        self,
        db: AsyncSession,
        actor_id: uuid.UUID,
        days_back: int = 7,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """
        Get activity history for a specific user.

        Args:
            db: Database session
            actor_id: User ID
            days_back: Days to look back
            limit: Maximum results

        Returns:
            List of audit events
        """
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        query = (
            select(AuditEvent)
            .where(
                and_(
                    AuditEvent.actor_id == actor_id,
                    AuditEvent.created_at >= cutoff,
                )
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def get_entity_history(
        self,
        db: AsyncSession,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """
        Get change history for a specific entity.

        Args:
            db: Database session
            entity_type: Type of entity
            entity_id: Entity ID
            limit: Maximum results

        Returns:
            List of audit events
        """
        query = (
            select(AuditEvent)
            .where(
                and_(
                    AuditEvent.entity_type == entity_type,
                    AuditEvent.entity_id == entity_id,
                )
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        return result.scalars().all()

    async def cleanup_old_events(
        self,
        db: AsyncSession,
        days_to_keep: int = 90,
    ) -> int:
        """
        Delete audit events older than N days.

        Args:
            db: Database session
            days_to_keep: Keep events from last N days

        Returns:
            Number of deleted events
        """
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        result = await db.execute(
            select(AuditEvent).where(AuditEvent.created_at < cutoff)
        )
        old_events = result.scalars().all()
        deleted_count = len(old_events)

        for event in old_events:
            await db.delete(event)

        await db.flush()
        logger.info("audit_cleanup_completed", deleted=deleted_count)
        return deleted_count
