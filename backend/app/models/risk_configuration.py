
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Enum,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    func
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


class RiskConfiguration(Base):
    __tablename__ = "risk_configurations"

    configuration_id = Column(Integer, primary_key=True, index=True)

    configuration_name = Column(String(100), nullable=False)

    version = Column(String(20), nullable=False, unique=True)

    description = Column(Text, nullable=True)

    low_max_score = Column(Numeric(5, 2), nullable=False, default=29)

    medium_max_score = Column(Numeric(5, 2), nullable=False, default=59)

    high_max_score = Column(Numeric(5, 2), nullable=False, default=100)

    status = Column(
        Enum("DRAFT", "ACTIVE", "ARCHIVED"),
        nullable=False,
        default="DRAFT"
    )

    created_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False
    )

    activated_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True
    )

    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    activated_at = Column(DateTime, nullable=True)

    rules = relationship(
        "RiskFactorRule",
        back_populates="configuration",
        cascade="all, delete-orphan"
    )
