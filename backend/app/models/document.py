
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    DateTime,
    Text,
    CHAR,
    JSON,
    ForeignKey
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.sql import func

from app.database.connection import Base


class Document(Base):
    __tablename__ = "documents"

    document_id = Column(Integer, primary_key=True, autoincrement=True)

    shipment_id = Column(
        Integer,
        ForeignKey("shipments.shipment_id"),
        nullable=False
    )

    document_type = Column(
        Enum(
            "COMMERCIAL_INVOICE",
            "PACKING_LIST",
            "BILL_OF_LADING",
            "OTHER"
        ),
        nullable=False
    )

    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)

    file_hash = Column(CHAR(64), nullable=True)

    extracted_text = Column(LONGTEXT, nullable=True)
    extracted_fields = Column(JSON, nullable=True)

    extraction_status = Column(
        Enum("PENDING", "EXTRACTED", "FAILED", "NEEDS_REVIEW"),
        nullable=False,
        default="PENDING"
    )

    extraction_run_id = Column(Integer, nullable=True)

    validation_status = Column(
        Enum("NOT_VALIDATED", "VALID", "MISMATCH", "INCOMPLETE"),
        nullable=False,
        default="NOT_VALIDATED"
    )

    version_no = Column(Integer, nullable=False, default=1)

    uploaded_by = Column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=True
    )

    upload_date = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
