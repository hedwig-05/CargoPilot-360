from sqlalchemy import Column, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database.connection import Base


class ExceptionStatusHistory(Base):
    __tablename__ = "exception_status_history"

    log_id = Column(Integer, primary_key=True, autoincrement=True)

    exception_id = Column(
        Integer,
        ForeignKey("exceptions.exception_id"),
        nullable=False,
        index=True
    )

    old_status = Column(
        Enum(
            "OPEN",
            "INVESTIGATING",
            "AWAITING_APPROVAL",
            "IN_PROGRESS",
            "AWAITING_RESPONSE",
            "PENDING_3RD_PARTY",
            "RESOLVED",
            "CLOSED"
        ),
        nullable=True
    )

    new_status = Column(
        Enum(
            "OPEN",
            "INVESTIGATING",
            "AWAITING_APPROVAL",
            "IN_PROGRESS",
            "AWAITING_RESPONSE",
            "PENDING_3RD_PARTY",
            "RESOLVED",
            "CLOSED"
        ),
        nullable=False
    )

    changed_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    operator_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True
    )
