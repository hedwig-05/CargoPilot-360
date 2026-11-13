
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    ForeignKey,
    Numeric
)

from app.database.connection import Base


class RiskAssessmentFactor(Base):
    __tablename__ = "risk_assessment_factors"

    factor_id = Column(Integer, primary_key=True, autoincrement=True)

    risk_id = Column(
        Integer,
        ForeignKey("risk_assessments.risk_id"),
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

    weight = Column(Numeric(5, 2), nullable=False)

    points_awarded = Column(Numeric(5, 2), nullable=False)

    detail = Column(String(255), nullable=True)

    event_id = Column(
        Integer,
        ForeignKey("shipment_events.event_id"),
        nullable=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.document_id"),
        nullable=True
    )

    validation_id = Column(
        Integer,
        ForeignKey("document_validations.validation_id"),
        nullable=True
    )

    exception_id = Column(
        Integer,
        ForeignKey("exceptions.exception_id"),
        nullable=True
    )
