
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    Text,
    ForeignKey,
    Numeric
)
from sqlalchemy.sql import func

from app.database.connection import Base


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    risk_id = Column(Integer, primary_key=True, autoincrement=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=False
    )

    exception_id = Column(
        Integer,
        ForeignKey("exceptions.exception_id"),
        nullable=True
    )

    workflow_id = Column(
        Integer,
        ForeignKey("agent_workflows.workflow_id"),
        nullable=True
    )

    run_id = Column(
        Integer,
        ForeignKey("agent_runs.run_id"),
        nullable=True
    )

    risk_score = Column(Numeric(5, 2), nullable=False)

    previous_score = Column(Numeric(5, 2), nullable=True)

    risk_level = Column(
        Enum("LOW", "MEDIUM", "HIGH"),
        nullable=False
    )

    ruleset_version = Column(String(20), nullable=True)

    assessment_method = Column(
        Enum("RULES", "RULES_PLUS_LLM"),
        nullable=False,
        default="RULES"
    )

    explanation = Column(Text, nullable=True)

    assessed_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
