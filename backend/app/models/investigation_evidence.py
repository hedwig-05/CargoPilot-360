
from sqlalchemy import (
    Column,
    Integer,
    Enum,
    DateTime,
    Text,
    ForeignKey
)
from sqlalchemy.sql import func

from app.database.connection import Base


class InvestigationEvidence(Base):
    __tablename__ = "investigation_evidence"

    evidence_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    investigation_id = Column(
        Integer,
        ForeignKey("investigations.investigation_id"),
        nullable=False
    )

    evidence_class = Column(
        Enum("CONFIRMED_FACT", "POSSIBLE_EXPLANATION"),
        nullable=False
    )

    statement = Column(Text, nullable=False)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=True
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

    validation_id = Column(
        Integer,
        ForeignKey("document_validations.validation_id"),
        nullable=True
    )

    exception_id = Column(
        Integer,
        ForeignKey("exceptions.exception_id"),
        nullable=True
    )

    risk_id = Column(
        Integer,
        ForeignKey("risk_assessments.risk_id"),
        nullable=True
    )

    action_id = Column(
        Integer,
        ForeignKey("actions.action_id"),
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )