
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    Text,
    ForeignKey
)
from sqlalchemy.sql import func

from app.database.connection import Base


class AgentWorkflow(Base):
    __tablename__ = "agent_workflows"

    workflow_id = Column(Integer, primary_key=True, autoincrement=True)

    workflow_public_id = Column(String(40), nullable=False, unique=True)

    thread_id = Column(String(80), nullable=False)

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

    trigger_type = Column(
        Enum(
            "SIMULATOR_EVENT",
            "DOCUMENT_UPLOAD",
            "MONITORING_CYCLE",
            "MANUAL",
            "SCHEDULED"
        ),
        nullable=False
    )

    trigger_ref = Column(String(100), nullable=True)

    graph_name = Column(
        String(60),
        nullable=False,
        default="cargopilot_main"
    )

    graph_version = Column(String(20), nullable=True)

    status = Column(
        Enum(
            "RUNNING",
            "WAITING_FOR_APPROVAL",
            "COMPLETED",
            "FAILED",
            "CANCELLED"
        ),
        nullable=False,
        default="RUNNING"
    )

    current_node = Column(String(60), nullable=True)

    last_checkpoint_id = Column(String(100), nullable=True)

    error_message = Column(Text, nullable=True)

    triggered_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True
    )

    started_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    completed_at = Column(DateTime, nullable=True)
