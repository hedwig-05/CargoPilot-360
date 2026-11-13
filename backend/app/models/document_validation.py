
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


class DocumentValidation(Base):
    __tablename__ = "document_validations"

    validation_id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    document_id = Column(
        Integer,
        ForeignKey("documents.document_id"),
        nullable=False
    )

    compared_document_id = Column(
        Integer,
        ForeignKey("documents.document_id"),
        nullable=True
    )

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=False
    )

    validation_run_id = Column(Integer, nullable=True)

    field_name = Column(String(100), nullable=False)

    extracted_value = Column(String(255), nullable=True)
    expected_value = Column(String(255), nullable=True)

    validation_result = Column(
        Enum("MATCH", "MISMATCH", "MISSING", "UNCERTAIN"),
        nullable=False
    )

    explanation = Column(Text, nullable=True)

    validated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
