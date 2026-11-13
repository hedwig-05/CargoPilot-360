
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    Numeric,
    ForeignKey
)
from sqlalchemy.sql import func

from app.database.connection import Base


class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_ref = Column(String(50), nullable=False, unique=True)

    origin = Column(String(100), nullable=False)
    destination = Column(String(100), nullable=False)

    shipper = Column(String(150), nullable=False)
    consignee = Column(String(150), nullable=False)

    container_no = Column(String(50), nullable=True)

    container_type = Column(
        Enum("20FT", "40FT", "40HC", "OTHER"),
        nullable=False,
        default="40FT"
    )

    expected_arrival = Column(DateTime, nullable=False)
    actual_arrival = Column(DateTime, nullable=True)

    status = Column(
        Enum(
            "BOOKED",
            "DOCUMENTATION",
            "IN_TRANSIT",
            "ARRIVED",
            "CUSTOMS",
            "DELIVERED",
            "ON_HOLD",
            "CANCELLED"
        ),
        nullable=False,
        default="BOOKED"
    )

    current_risk_score = Column(Numeric(5, 2), nullable=False, default=0.00)

    current_risk_level = Column(
        Enum("LOW", "MEDIUM", "HIGH"),
        nullable=False,
        default="LOW"
    )

    assigned_user_id = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True
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
