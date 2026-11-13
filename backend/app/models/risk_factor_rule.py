
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Enum,
    Boolean,
    ForeignKey
)
from sqlalchemy.orm import relationship

from app.database.connection import Base


class RiskFactorRule(Base):
    __tablename__ = "risk_factor_rules"

    rule_id = Column(Integer, primary_key=True, index=True)

    configuration_id = Column(
        Integer,
        ForeignKey("risk_configurations.configuration_id"),
        nullable=False
    )

    factor_code = Column(
        Enum(
            "DOCUMENT_MISMATCH",
            "ARRIVAL_DELAY",
            "MISSING_MILESTONE",
            "CUSTOMS_ISSUE",
            "STAKEHOLDER_DELAY"
        ),
        nullable=False
    )

    factor_name = Column(String(100), nullable=False)

    weight = Column(Numeric(5, 2), nullable=False)

    is_enabled = Column(Boolean, nullable=False, default=True)

    description = Column(String(255), nullable=True)

    configuration = relationship(
        "RiskConfiguration",
        back_populates="rules"
    )
