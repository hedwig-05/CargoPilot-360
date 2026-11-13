
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    Text,
    ForeignKey,
    JSON
)
from sqlalchemy.sql import func

from app.database.connection import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id = Column(Integer, primary_key=True, autoincrement=True)

    run_public_id = Column(String(40), nullable=False, unique=True)

    workflow_id = Column(
        Integer,
        ForeignKey("agent_workflows.workflow_id"),
        nullable=False
    )

    parent_run_id = Column(
        Integer,
        ForeignKey("agent_runs.run_id"),
        nullable=True
    )

    step_no = Column(Integer, nullable=False, default=1)

    agent_type = Column(
        Enum(
            "SUPERVISOR",
            "MONITORING",
            "DOCUMENT",
            "INVESTIGATION",
            "DECISION",
            "ACTION",
            "VERIFICATION"
        ),
        nullable=False
    )

    node_name = Column(String(60), nullable=True)

    input_data = Column(JSON, nullable=True)

    output_data = Column(JSON, nullable=True)

    model_name = Column(String(60), nullable=True)

    prompt_version = Column(String(30), nullable=True)

    prompt_tokens = Column(Integer, nullable=True)

    completion_tokens = Column(Integer, nullable=True)

    latency_ms = Column(Integer, nullable=True)

    retry_count = Column(Integer, nullable=False, default=0)

    execution_status = Column(
        Enum(
            "PROCESSING",
            "WAITING_FOR_APPROVAL",
            "COMPLETED",
            "FAILED",
            "SKIPPED"
        ),
        nullable=False,
        default="PROCESSING"
    )

    error_message = Column(Text, nullable=True)

    started_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    completed_at = Column(DateTime, nullable=True)
