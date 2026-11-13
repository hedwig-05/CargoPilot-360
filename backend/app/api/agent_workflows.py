
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models import AgentWorkflow


router = APIRouter(
    prefix="/api",
    tags=["Agent Workflows"]
)


# ==========================================
# GET ALL AGENT WORKFLOWS
# ==========================================

@router.get("/agent-workflows")
def get_all_agent_workflows(
    db: Session = Depends(get_db)
):

    workflows = db.query(AgentWorkflow).all()

    return jsonable_encoder([
        {
            column.name: getattr(workflow, column.name)
            for column in AgentWorkflow.__table__.columns
        }
        for workflow in workflows
    ])
