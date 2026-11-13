
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    Text,
    ForeignKey,
    ForeignKeyConstraint
)
from sqlalchemy.sql import func

from app.database.connection import Base


class Investigation(Base):
    __tablename__ = "investigations"

    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "workflow_id"],
            ["agent_runs.run_id", "agent_runs.workflow_id"],
            name="fk_inv_run"
        ),
    )

    investigation_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

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

    # Composite foreign key is defined in __table_args__
    run_id = Column(
        Integer,
        nullable=False
    )

    summary = Column(Text, nullable=False)

    possible_cause = Column(Text, nullable=True)

    affected_process = Column(String(100), nullable=True)

    urgency = Column(
        Enum("LOW", "MEDIUM", "HIGH", "CRITICAL"),
        nullable=False,
        default="MEDIUM"
    )

    recommended_next = Column(Text, nullable=True)

    status = Column(
        Enum("COMPLETED", "SUPERSEDED"),
        nullable=False,
        default="COMPLETED"
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
