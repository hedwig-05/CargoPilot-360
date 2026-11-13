
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    Enum,
    DateTime,
    ForeignKey,
    JSON
)
from sqlalchemy.sql import func

from app.database.connection import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    actor_type = Column(
        Enum("USER", "AGENT", "SYSTEM"),
        nullable=False
    )

    actor_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True
    )

    actor_name = Column(String(100), nullable=True)

    action = Column(String(100), nullable=False)

    entity_type = Column(String(50), nullable=False)

    entity_id = Column(Integer, nullable=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
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

    details = Column(JSON, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
