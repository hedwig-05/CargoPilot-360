
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


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"

    event_id = Column(Integer, primary_key=True, autoincrement=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=False
    )

    event_type = Column(
        Enum(
            "VESSEL_DEPARTED",
            "VESSEL_ARRIVED",
            "CONTAINER_DISCHARGED",
            "CUSTOMS_CLEARED",
            "DOCUMENTATION_COMPLETE",
            "DELIVERED"
        ),
        nullable=False
    )

    event_description = Column(Text, nullable=True)

    expected_time = Column(DateTime, nullable=False)
    actual_time = Column(DateTime, nullable=True)

    event_status = Column(
        Enum(
            "PENDING",
            "COMPLETED",
            "LATE",
            "MISSING",
            "INCONSISTENT"
        ),
        nullable=False,
        default="PENDING"
    )

    source = Column(String(50), nullable=False, default="SIMULATOR")

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
