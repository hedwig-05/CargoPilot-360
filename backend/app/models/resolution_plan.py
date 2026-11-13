
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


class ResolutionPlan(Base):
    __tablename__ = "resolution_plans"

    plan_id = Column(Integer, primary_key=True, autoincrement=True)

    exception_id = Column(
        Integer,
        ForeignKey("exceptions.exception_id"),
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

    investigation_id = Column(
        Integer,
        ForeignKey("investigations.investigation_id"),
        nullable=True
    )

    risk_id = Column(
        Integer,
        ForeignKey("risk_assessments.risk_id"),
        nullable=True
    )

    version_no = Column(Integer, nullable=False, default=1)

    supersedes_plan_id = Column(
        Integer,
        ForeignKey("resolution_plans.plan_id"),
        nullable=True
    )

    proposed_solution = Column(Text, nullable=False)

    reasoning = Column(Text, nullable=True)

    priority = Column(
        Enum("LOW", "MEDIUM", "HIGH", "URGENT"),
        nullable=False,
        default="MEDIUM"
    )

    status = Column(
        Enum(
            "DRAFT",
            "PENDING_APPROVAL",
            "APPROVED",
            "REJECTED",
            "SUPERSEDED",
            "EXECUTING",
            "COMPLETED",
            "FAILED"
        ),
        nullable=False,
        default="DRAFT"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )
