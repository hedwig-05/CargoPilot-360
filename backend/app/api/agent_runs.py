
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import AgentRun


router = APIRouter(
    prefix="/api",
    tags=["Agent Runs"]
)


# ==========================================
# GET ALL AGENT RUNS
# ==========================================

@router.get("/agent-runs")
def get_all_agent_runs(
    db: Session = Depends(get_db)
):

    runs = db.query(AgentRun).order_by(
        AgentRun.run_id.desc()
    ).all()

    return jsonable_encoder([
        {
            column.name: getattr(run, column.name)
            for column in AgentRun.__table__.columns
        }
        for run in runs
    ])
