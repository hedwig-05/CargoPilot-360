
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    JSON
)
from sqlalchemy.sql import func

from app.database.connection import Base


class Action(Base):
    __tablename__ = "actions"

    action_id = Column(Integer, primary_key=True, autoincrement=True)

    plan_id = Column(
        Integer,
        ForeignKey("resolution_plans.plan_id"),
        nullable=False
    )

    workflow_id = Column(
        Integer,
        ForeignKey("agent_workflows.workflow_id"),
        nullable=False
    )

    created_by_run_id = Column(
        Integer,
        ForeignKey("agent_runs.run_id"),
        nullable=False
    )

    action_type = Column(
        Enum(
            "REQUEST_DOCUMENT_CORRECTION",
            "REQUEST_MISSING_DOCUMENT",
            "SEND_FOLLOW_UP_EMAIL",
            "NOTIFY_OPERATIONS_OFFICER",
            "ESCALATE_TO_MANAGER",
            "UPDATE_SHIPMENT_STATUS",
            "CREATE_NOTIFICATION"
        ),
        nullable=False
    )

    action_description = Column(Text, nullable=False)

    action_payload = Column(JSON, nullable=True)

    requires_approval = Column(
        Boolean,
        nullable=False,
        default=True
    )

    approval_status = Column(
        Enum("NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED"),
        nullable=False,
        default="PENDING"
    )

    approved_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True
    )

    approved_at = Column(DateTime, nullable=True)

    rejection_reason = Column(Text, nullable=True)

    execution_status = Column(
        Enum("NOT_STARTED", "EXECUTING", "SUCCEEDED", "FAILED", "SKIPPED"),
        nullable=False,
        default="NOT_STARTED"
    )

    idempotency_key = Column(String(100), nullable=False, unique=True)

    executed_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
