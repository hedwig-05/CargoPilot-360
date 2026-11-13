
from sqlalchemy import (
    Column,
    Integer,
    Enum,
    Text,
    JSON,
    DateTime,
    ForeignKey
)
from sqlalchemy.sql import func

from app.database.connection import Base


class ResolutionVerification(Base):

    __tablename__ = "resolution_verifications"

    verification_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    exception_id = Column(
        Integer,
        ForeignKey("exceptions.exception_id"),
        nullable=False
    )

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=False
    )

    workflow_id = Column(
        Integer,
        ForeignKey("agent_workflows.workflow_id"),
        nullable=False
    )

    run_id = Column(
        Integer,
        ForeignKey("agent_runs.run_id"),
        nullable=False
    )

    verification_status = Column(
        Enum(
            "VERIFIED",
            "NOT_VERIFIED",
            "INCONCLUSIVE"
        ),
        nullable=False
    )

    evidence_summary = Column(
        Text,
        nullable=False
    )

    validation_results = Column(
        JSON,
        nullable=True
    )

    verified_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
