
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database.connection import get_db


router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"]
)


# GET GENERAL KPI OVERVIEW

@router.get("/overview")
def get_dashboard_overview(
    db: Session = Depends(get_db)
):
    result = db.execute(
        text("SELECT * FROM v_kpi_overview")
    ).mappings().all()

    return jsonable_encoder([dict(row) for row in result])


# GET AUTOMATION KPIs

@router.get("/automation")
def get_automation_kpis(
    db: Session = Depends(get_db)
):
    result = db.execute(
        text("SELECT * FROM v_kpi_automation")
    ).mappings().all()

    return jsonable_encoder([dict(row) for row in result])


# GET EXCEPTION STATISTICS

@router.get("/exception-stats")
def get_exception_statistics(
    db: Session = Depends(get_db)
):
    result = db.execute(
        text("SELECT * FROM v_exception_stats")
    ).mappings().all()

    return jsonable_encoder([dict(row) for row in result])
