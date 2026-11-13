
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.auth.dependencies import require_roles
from app.engines.monitoring_agent import run_monitoring_cycle
from app.models import Shipment


router = APIRouter(
    prefix="/api/monitoring",
    tags=["Monitoring"]
)


@router.post("/run")
def trigger_monitoring_cycle(
    shipment_id: int = Query(
        default=None,
        description="Optional shipment ID. If omitted, all active shipments are monitored."
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("ADMIN", "MANAGER"))
):
    """
    Trigger a monitoring cycle.

    Only ADMIN and MANAGER users can run
    the monitoring cycle.

    If shipment_id is provided, only that
    shipment is monitored.
    """

    if shipment_id is not None:

        shipment = (
            db.query(Shipment)
            .filter(
                Shipment.shipment_id == shipment_id
            )
            .first()
        )

        if shipment is None:
            raise HTTPException(
                status_code=404,
                detail="Shipment not found."
            )

        if shipment.status in ["DELIVERED", "CANCELLED"]:
            raise HTTPException(
                status_code=400,
                detail="Cannot monitor a delivered or cancelled shipment."
            )

    result = run_monitoring_cycle(
        db=db,
        triggered_by=current_user.user_id,
        shipment_id=shipment_id
    )

    return result
