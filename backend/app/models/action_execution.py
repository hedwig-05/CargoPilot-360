
from sqlalchemy import (
    Column,
    Integer,
    Enum,
    DateTime,
    Text,
    ForeignKey,
    JSON
)
from sqlalchemy.sql import func

from app.database.connection import Base


class ActionExecution(Base):
    __tablename__ = "action_executions"

    execution_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    action_id = Column(
        Integer,
        ForeignKey("actions.action_id"),
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
        nullable=True
    )

    attempt_no = Column(Integer, nullable=False, default=1)

    status = Column(
        Enum("STARTED", "SUCCEEDED", "FAILED"),
        nullable=False,
        default="STARTED"
    )

    request_data = Column(JSON, nullable=True)

    response_data = Column(JSON, nullable=True)

    error_message = Column(Text, nullable=True)

    started_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    completed_at = Column(DateTime, nullable=True)
