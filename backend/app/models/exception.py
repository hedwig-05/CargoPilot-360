from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    Text,
    ForeignKey,
    Computed,
    JSON,
    Boolean,
)
from sqlalchemy.sql import func

from app.database.connection import Base


class Exception(Base):
    __tablename__ = "exceptions"

    exception_id = Column(Integer, primary_key=True, autoincrement=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=False
    )

    exception_type = Column(
        Enum(
            "DOCUMENT_MISMATCH",
            "MISSING_DOCUMENT",
            "SHIPMENT_DELAY",
            "MISSING_MILESTONE",
            "CUSTOMS_HOLD",
            "STAKEHOLDER_RESPONSE_DELAY",
            "CONTAINER_NOT_DISCHARGED",
            "DAMAGE_SHORTAGE",
            "ROLLED_CARGO"
        ),
        nullable=False
    )

    description = Column(Text, nullable=False)

    # Source-owned evidence is authoritative; description remains a
    # compatibility projection until the verification reader is migrated.
    sources = Column(JSON, nullable=True)
    eligible_for_verification = Column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    severity_recalculation_pending = Column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    severity = Column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL"),
        nullable=False,
        default="MEDIUM"
    )

    status = Column(
        Enum(
            "OPEN",
            "INVESTIGATING",
            "AWAITING_APPROVAL",
            "IN_PROGRESS",
            "AWAITING_RESPONSE",
            "PENDING_3RD_PARTY",
            "RESOLVED",
            "CLOSED"
        ),
        nullable=False,
        default="OPEN"
    )

    event_id = Column(
        Integer,
        ForeignKey("shipment_events.event_id"),
        nullable=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.document_id"),
        nullable=True
    )

    assigned_to = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True
    )

    detected_by = Column(
        String(50),
        nullable=False,
        default="MONITORING_AGENT"
    )

    detected_by_run_id = Column(Integer, nullable=True)

    detected_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    acknowledged_at = Column(DateTime, nullable=True)

    resolved_at = Column(DateTime, nullable=True)

    total_paused_minutes = Column(Integer, nullable=False, default=0, server_default="0")

    resolution_notes = Column(Text, nullable=True)

    open_key = Column(
        String(120),
        Computed(
            "CASE WHEN status IN ('RESOLVED', 'CLOSED') "
            "THEN NULL "
            "ELSE CONCAT(shipment_id, ':', exception_type) END",
            persisted=True
        )
    )
