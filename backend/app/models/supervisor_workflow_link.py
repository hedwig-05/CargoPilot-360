from sqlalchemy import (
    Column,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func

from app.database.connection import Base


class SupervisorWorkflowLink(Base):
    """
    Records which exception workflows are coordinated by a
    shipment-level Supervisor workflow.

    This is deliberately separate from AgentWorkflow.parent_workflow_id,
    which continues to represent an execution dependency.
    """

    __tablename__ = "supervisor_workflow_links"

    __table_args__ = (
        UniqueConstraint(
            "supervisor_workflow_id",
            "exception_workflow_id",
            name="uq_supervisor_exception_workflow",
        ),
        Index(
            "ix_supervisor_workflow_links_action",
            "action_id",
        ),
    )

    link_id = Column(Integer, primary_key=True, autoincrement=True)

    supervisor_workflow_id = Column(
        Integer,
        ForeignKey("agent_workflows.workflow_id"),
        nullable=False,
    )

    exception_workflow_id = Column(
        Integer,
        ForeignKey("agent_workflows.workflow_id"),
        nullable=False,
    )

    exception_id = Column(
        Integer,
        ForeignKey("exceptions.exception_id"),
        nullable=False,
    )

    action_id = Column(
        Integer,
        ForeignKey("actions.action_id"),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
