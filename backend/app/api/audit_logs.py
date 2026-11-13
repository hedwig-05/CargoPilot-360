
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import AuditLog
from app.api.helpers import serialize_records, get_all_records


router = APIRouter(
    prefix="/api",
    tags=["Audit Logs"]
)


# GET ALL AUDIT LOGS

@router.get("/audit-logs")
def get_all_audit_logs(
    db: Session = Depends(get_db)
):
    records = get_all_records(db, AuditLog)

    return serialize_records(records, AuditLog)
